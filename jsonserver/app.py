"""
Flask application factory for JSONServer.
Creates and configures the Flask app with all middleware, routes, and error handlers.
"""

import os
import sys

from flask import Flask, jsonify, request, g

from .config import get_config, Config
from .database import Database, DatabaseError, TableNotFoundError, RecordNotFoundError, ValidationError
from .auth import RateLimiter, require_auth, require_rate_limit, generate_api_key, get_client_ip
from .routes.tables import init_tables_bp
from .routes.records import init_records_bp


def create_app(config: Config = None) -> Flask:
    """
    Application factory.

    Args:
        config: Optional Config instance. If None, loads from environment.

    Returns:
        Configured Flask application.
    """
    if config is None:
        config = get_config()

    app = Flask(__name__)

    # Store config on app
    app.config["JSONSERVER"] = config

    # Initialize database
    db = Database(config.DB_PATH)

    # Initialize rate limiter
    rate_limiter = RateLimiter(max_requests=config.RATE_LIMIT)

    # Generate API key if auth required and no keys configured
    if config.REQUIRE_AUTH and not config.API_KEYS:
        new_key = generate_api_key()
        config.API_KEYS = [new_key]
        print(f"\n{'='*60}")
        print(f"  API Key (save this — shown only once):")
        print(f"  {new_key}")
        print(f"{'='*60}\n")

    # Register blueprints
    tables_bp = init_tables_bp(db)
    records_bp = init_records_bp(db, config.MAX_RECORDS_PER_REQUEST)

    # Apply middleware based on config
    if config.REQUIRE_AUTH:
        tables_bp.before_request(require_auth(config.API_KEYS)(lambda: None))
        records_bp.before_request(require_auth(config.API_KEYS)(lambda: None))

    # Rate limiting on all API routes
    @tables_bp.before_request
    @records_bp.before_request
    def apply_rate_limit():
        client_ip = get_client_ip()
        allowed, remaining, reset = rate_limiter.is_allowed(client_ip)
        g.rate_limit_headers = {
            "X-RateLimit-Limit": str(rate_limiter.max_requests),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset),
        }
        if not allowed:
            return jsonify({
                "error": "Rate limit exceeded",
                "message": f"Max {rate_limiter.max_requests} requests per {rate_limiter.window}s.",
                "retry_after": reset,
            }), 429

    app.register_blueprint(tables_bp)
    app.register_blueprint(records_bp)

    # ── Response middleware ──────────────────────────────────────

    @app.after_request
    def add_security_headers(response):
        """Add security headers to every response."""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = "default-src 'none'"
        response.headers["Referrer-Policy"] = "no-referrer"

        # CORS
        response.headers["Access-Control-Allow-Origin"] = config.CORS_ORIGINS
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-API-Key"

        # Rate limit headers
        if hasattr(g, "rate_limit_headers"):
            for key, value in g.rate_limit_headers.items():
                response.headers[key] = value

        return response

    # ── Error handlers ──────────────────────────────────────────

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({
            "error": "Not found",
            "message": "The requested endpoint does not exist.",
            "status": 404,
        }), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({
            "error": "Method not allowed",
            "message": f"The method {request.method} is not allowed for this endpoint.",
            "status": 405,
        }), 405

    @app.errorhandler(413)
    def payload_too_large(e):
        return jsonify({
            "error": "Payload too large",
            "message": f"Maximum payload size is {config.MAX_PAYLOAD_SIZE} bytes.",
            "status": 413,
        }), 413

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({
            "error": "Bad request",
            "message": str(e),
            "status": 400,
        }), 400

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({
            "error": "Internal server error",
            "message": "An unexpected error occurred.",
            "status": 500,
        }), 500

    # ── Root endpoints ──────────────────────────────────────────

    @app.route("/")
    def index():
        return jsonify({
            "name": "JSONServer",
            "version": "1.0.0",
            "description": "Lightweight JSON-based REST API database",
            "endpoints": {
                "tables": "/api/tables",
                "records": "/api/<table_name>",
                "health": "/health",
            },
        })

    @app.route("/health")
    def health():
        tables = db.list_tables()
        return jsonify({
            "status": "healthy",
            "tables": len(tables),
            "auth_required": config.REQUIRE_AUTH,
        })

    @app.route("/api", methods=["GET"])
    def api_docs():
        return jsonify({
            "api_version": "1.0.0",
            "endpoints": {
                "GET /api/tables": "List all tables",
                "POST /api/tables": "Create a table (body: {\"name\": \"table_name\"})",
                "GET /api/tables/<name>": "Table stats & schema",
                "DELETE /api/tables/<name>": "Drop a table",
                "PUT /api/tables/<name>/clear": "Clear all records",
                "GET /api/<table>": "Query records (?filter, ?sort_by, ?sort_order, ?limit, ?offset)",
                "POST /api/<table>": "Insert record(s)",
                "GET /api/<table>/<id>": "Get record by ID",
                "PUT /api/<table>/<id>": "Replace record",
                "PATCH /api/<table>/<id>": "Update record fields",
                "DELETE /api/<table>/<id>": "Delete record by ID",
                "DELETE /api/<table>": "Delete records by filter",
                "GET /api/<table>/count": "Count records",
                "GET /api/<table>/schema": "Get table schema",
            },
            "query_operators": ["eq", "ne", "gt", "gte", "lt", "lte", "in", "nin", "contains", "startswith", "endswith", "exists"],
            "query_syntax": "?field__op=value (e.g., ?age__gt=18&status__eq=active)",
        })

    # ── OPTIONS handler for CORS preflight ──────────────────────

    @app.route("/api/<path:path>", methods=["OPTIONS"])
    def handle_options(path):
        return "", 204

    # ── Payload size limit ──────────────────────────────────────

    @app.before_request
    def limit_payload():
        if request.content_length and request.content_length > config.MAX_PAYLOAD_SIZE:
            return jsonify({
                "error": "Payload too large",
                "message": f"Max size: {config.MAX_PAYLOAD_SIZE} bytes",
            }), 413

    return app
