"""
CRUD record endpoints for JSONServer.

Endpoints:
    GET    /api/<table>              — Query records (with filters, sort, pagination)
    POST   /api/<table>              — Insert one or many records
    GET    /api/<table>/<id>         — Get a single record by ID
    PUT    /api/<table>/<id>         — Replace a record entirely
    PATCH  /api/<table>/<id>         — Update specific fields of a record
    DELETE /api/<table>/<id>         — Delete a record by ID
    DELETE /api/<table>              — Delete records matching filters
    GET    /api/<table>/count        — Count records (with optional filters)
    GET    /api/<table>/schema       — Get inferred table schema
"""

from flask import Blueprint, jsonify, request

from ..database import Database, DatabaseError, TableNotFoundError, RecordNotFoundError, ValidationError
from ..auth import sanitize_input

records_bp = Blueprint("records", __name__)

# Will be set by the app factory
db: Database = None
max_records: int = 1000


def init_records_bp(database: Database, max_records_per_request: int = 1000) -> Blueprint:
    """Initialize the blueprint with the database instance."""
    global db, max_records
    db = database
    max_records = max_records_per_request
    return records_bp


def _parse_filters() -> dict:
    """
    Parse query parameters into a filter dictionary.

    Supports two formats:
        1. Simple: ?field=value  (equality)
        2. Advanced: ?field__op=value  (operator)
           e.g., ?age__gt=18&status__eq=active

    Returns dict like: {"age": {"gt": 18}, "status": {"eq": "active"}}
    """
    filters = {}
    skip_params = {"sort_by", "sort_order", "limit", "offset", "api_key"}

    for key, value in request.args.items():
        if key in skip_params:
            continue

        if "__" in key:
            field, op = key.rsplit("__", 1)
        else:
            field = key
            op = "eq"

        # Type coercion for common values
        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False
        elif value.lower() == "null":
            value = None
        else:
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    pass  # Keep as string

        if field not in filters:
            filters[field] = {}
        filters[field][op] = value

    return filters


def _parse_pagination() -> tuple[int, int]:
    """Parse limit and offset from query parameters."""
    try:
        limit = min(int(request.args.get("limit", 100)), max_records)
        limit = max(limit, 1)
    except (ValueError, TypeError):
        limit = 100

    try:
        offset = max(int(request.args.get("offset", 0)), 0)
    except (ValueError, TypeError):
        offset = 0

    return limit, offset


def _ensure_table(name: str):
    """Get a table or return a 404 error response."""
    table = db.get_table(name)
    if not table.exists():
        return None, (jsonify({
            "error": "Not found",
            "message": f"Table '{name}' does not exist. Create it with POST /api/tables",
        }), 404)
    return table, None


# ── QUERY ─────────────────────────────────────────────────────

@records_bp.route("/api/<table_name>", methods=["GET"])
def query_records(table_name: str):
    """
    Query records with filtering, sorting, and pagination.

    Query params:
        - Any param becomes a filter (simple equality)
        - Use __ operator syntax for advanced filters: ?age__gt=18
        - sort_by=<field> — field to sort by
        - sort_order=asc|desc — sort direction
        - limit=<n> — max records to return (default 100, max 1000)
        - offset=<n> — skip N records

    Available operators: eq, ne, gt, gte, lt, lte, in, nin, contains, startswith, endswith, exists
    """
    table, err = _ensure_table(table_name)
    if err:
        return err

    try:
        filters = _parse_filters()
        limit, offset = _parse_pagination()
        sort_by = request.args.get("sort_by")
        sort_order = request.args.get("sort_order", "asc")

        result = table.get(
            filters=filters or None,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )

        return jsonify({
            "table": table_name,
            "records": result["records"],
            "total": result["total"],
            "limit": result["limit"],
            "offset": result["offset"],
            "has_more": result["has_more"],
        })
    except ValidationError as e:
        return jsonify({"error": "Validation error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Internal error", "message": str(e)}), 500


# ── INSERT ────────────────────────────────────────────────────

@records_bp.route("/api/<table_name>", methods=["POST"])
def insert_record(table_name: str):
    """
    Insert one or many records.

    Body:
        - Single record: {"name": "John", "age": 30}
        - Multiple records: [{"name": "John"}, {"name": "Jane"}]
    """
    table, err = _ensure_table(table_name)
    if err:
        return err

    try:
        data = request.get_json(force=True)

        if not data:
            return jsonify({"error": "Validation error", "message": "Request body cannot be empty"}), 400

        if isinstance(data, list):
            if len(data) > max_records:
                return jsonify({
                    "error": "Validation error",
                    "message": f"Maximum {max_records} records per batch insert",
                }), 400
            sanitized = [sanitize_input(record) for record in data]
            result = table.insert_many(sanitized)
            return jsonify({"inserted": len(result), "records": result}), 201
        elif isinstance(data, dict):
            sanitized = sanitize_input(data)
            result = table.insert(sanitized)
            return jsonify(result), 201
        else:
            return jsonify({"error": "Validation error", "message": "Body must be a JSON object or array"}), 400

    except ValueError as e:
        return jsonify({"error": "Validation error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Internal error", "message": str(e)}), 500


# ── GET BY ID ─────────────────────────────────────────────────

@records_bp.route("/api/<table_name>/<int:record_id>", methods=["GET"])
def get_record(table_name: str, record_id: int):
    """Get a single record by ID."""
    table, err = _ensure_table(table_name)
    if err:
        return err

    try:
        record = table.get_by_id(record_id)
        return jsonify(record)
    except RecordNotFoundError as e:
        return jsonify({"error": "Not found", "message": str(e)}), 404


# ── UPDATE (PATCH) ────────────────────────────────────────────

@records_bp.route("/api/<table_name>/<int:record_id>", methods=["PATCH"])
def update_record(table_name: str, record_id: int):
    """Update specific fields of a record."""
    table, err = _ensure_table(table_name)
    if err:
        return err

    try:
        data = request.get_json(force=True)
        if not data or not isinstance(data, dict):
            return jsonify({"error": "Validation error", "message": "Body must be a JSON object"}), 400

        sanitized = sanitize_input(data)
        result = table.update(record_id, sanitized)
        return jsonify(result)
    except RecordNotFoundError as e:
        return jsonify({"error": "Not found", "message": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": "Validation error", "message": str(e)}), 400


# ── REPLACE (PUT) ─────────────────────────────────────────────

@records_bp.route("/api/<table_name>/<int:record_id>", methods=["PUT"])
def replace_record(table_name: str, record_id: int):
    """Replace an entire record."""
    table, err = _ensure_table(table_name)
    if err:
        return err

    try:
        data = request.get_json(force=True)
        if not data or not isinstance(data, dict):
            return jsonify({"error": "Validation error", "message": "Body must be a JSON object"}), 400

        sanitized = sanitize_input(data)
        result = table.replace(record_id, sanitized)
        return jsonify(result)
    except RecordNotFoundError as e:
        return jsonify({"error": "Not found", "message": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": "Validation error", "message": str(e)}), 400


# ── DELETE ────────────────────────────────────────────────────

@records_bp.route("/api/<table_name>/<int:record_id>", methods=["DELETE"])
def delete_record(table_name: str, record_id: int):
    """Delete a record by ID."""
    table, err = _ensure_table(table_name)
    if err:
        return err

    try:
        result = table.delete(record_id)
        return jsonify(result)
    except RecordNotFoundError as e:
        return jsonify({"error": "Not found", "message": str(e)}), 404


@records_bp.route("/api/<table_name>", methods=["DELETE"])
def delete_records(table_name: str):
    """Delete all records matching filters. Requires at least one filter."""
    table, err = _ensure_table(table_name)
    if err:
        return err

    filters = _parse_filters()
    if not filters:
        return jsonify({
            "error": "Validation error",
            "message": "DELETE on collection requires at least one filter. Use DELETE /api/<table>/<id> for single record, or add filters like ?status=inactive",
        }), 400

    try:
        result = table.delete_many(filters)
        return jsonify(result)
    except ValidationError as e:
        return jsonify({"error": "Validation error", "message": str(e)}), 400


# ── COUNT & SCHEMA ────────────────────────────────────────────

@records_bp.route("/api/<table_name>/count", methods=["GET"])
def count_records(table_name: str):
    """Count records, optionally with filters."""
    table, err = _ensure_table(table_name)
    if err:
        return err

    filters = _parse_filters()
    count = table.count(filters or None)
    return jsonify({"table": table_name, "count": count})


@records_bp.route("/api/<table_name>/schema", methods=["GET"])
def get_schema(table_name: str):
    """Get the inferred schema of a table."""
    table, err = _ensure_table(table_name)
    if err:
        return err

    schema = table.get_schema()
    return jsonify(schema)
