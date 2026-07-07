"""
Table management endpoints for JSONServer.

Endpoints:
    GET    /api/tables              — List all tables
    POST   /api/tables              — Create a new table
    GET    /api/tables/<name>       — Get table stats
    DELETE /api/tables/<name>       — Drop a table
    PUT    /api/tables/<name>/clear — Clear all records from a table
"""

from flask import Blueprint, jsonify, request

from ..database import Database, DatabaseError, TableNotFoundError, ValidationError

tables_bp = Blueprint("tables", __name__)

# Will be set by the app factory
db: Database = None


def init_tables_bp(database: Database) -> Blueprint:
    """Initialize the blueprint with the database instance."""
    global db
    db = database
    return tables_bp


@tables_bp.route("/api/tables", methods=["GET"])
def list_tables():
    """List all tables with their stats."""
    try:
        tables = db.list_tables()
        return jsonify({
            "tables": tables,
            "count": len(tables),
        })
    except Exception as e:
        return jsonify({"error": "Internal error", "message": str(e)}), 500


@tables_bp.route("/api/tables", methods=["POST"])
def create_table():
    """Create a new table."""
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()

    if not name:
        return jsonify({
            "error": "Validation error",
            "message": "Table name is required. Provide: {\"name\": \"your_table\"}",
        }), 400

    if not db.validate_table_name(name):
        return jsonify({
            "error": "Validation error",
            "message": "Invalid table name. Use alphanumeric characters, underscores, and hyphens. Must start with a letter. Max 64 chars.",
        }), 400

    try:
        table = db.get_table(name)
        result = table.create()
        return jsonify(result), 201
    except DatabaseError as e:
        return jsonify({"error": "Conflict", "message": str(e)}), 409


@tables_bp.route("/api/tables/<name>", methods=["GET"])
def get_table_stats(name: str):
    """Get stats for a specific table."""
    try:
        table = db.get_table(name)
        stats = table.get_stats()
        schema = table.get_schema()
        return jsonify({
            "stats": stats,
            "schema": schema["fields"],
        })
    except TableNotFoundError as e:
        return jsonify({"error": "Not found", "message": str(e)}), 404


@tables_bp.route("/api/tables/<name>", methods=["DELETE"])
def drop_table(name: str):
    """Drop a table entirely."""
    try:
        table = db.get_table(name)
        result = table.drop()
        return jsonify(result)
    except TableNotFoundError as e:
        return jsonify({"error": "Not found", "message": str(e)}), 404


@tables_bp.route("/api/tables/<name>/clear", methods=["PUT"])
def clear_table(name: str):
    """Clear all records from a table."""
    try:
        table = db.get_table(name)
        result = table.clear()
        return jsonify(result)
    except TableNotFoundError as e:
        return jsonify({"error": "Not found", "message": str(e)}), 404
