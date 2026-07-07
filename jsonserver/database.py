"""
JSON Database Engine for JSONServer.

Core storage engine that manages JSON files as "tables".
Supports CRUD operations, advanced querying, pagination, sorting,
and thread-safe file operations with file locking.

Designed to be fast: in-memory caching, minimal disk I/O,
and atomic writes to prevent data corruption.
"""

import json
import os
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class DatabaseError(Exception):
    """Base exception for database operations."""
    pass


class TableNotFoundError(DatabaseError):
    """Raised when a requested table does not exist."""
    pass


class RecordNotFoundError(DatabaseError):
    """Raised when a requested record does not exist."""
    pass


class ValidationError(DatabaseError):
    """Raised when input data fails validation."""
    pass


# Query operators for filtering
OPERATORS = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "in": lambda a, b: a in b if isinstance(b, list) else False,
    "nin": lambda a, b: a not in b if isinstance(b, list) else True,
    "contains": lambda a, b: b in a if isinstance(a, str) else False,
    "startswith": lambda a, b: a.startswith(b) if isinstance(a, str) else False,
    "endswith": lambda a, b: a.endswith(b) if isinstance(a, str) else False,
    "exists": lambda a, b: (a is not None) == b,
}


class Table:
    """
    Represents a single JSON table (collection).

    Each table is stored as a JSON file on disk with the structure:
    {
        "meta": {"next_id": 1, "created_at": "...", "updated_at": "..."},
        "records": [{"id": 1, ...}, ...]
    }

    Maintains an in-memory cache for fast reads.
    Uses file locking for thread-safe writes.
    """

    def __init__(self, name: str, db_path: str):
        self.name = name
        self.filepath = os.path.join(db_path, f"{name}.json")
        self._lock = threading.RLock()
        self._cache: Optional[dict] = None
        self._cache_time: float = 0
        self._cache_ttl: float = 0.1  # 100ms cache TTL

    def exists(self) -> bool:
        """Check if the table file exists on disk."""
        return os.path.isfile(self.filepath)

    def create(self) -> dict:
        """Create a new empty table."""
        with self._lock:
            if self.exists():
                raise DatabaseError(f"Table '{self.name}' already exists")

            data = {
                "meta": {
                    "next_id": 1,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                    "record_count": 0,
                },
                "records": [],
            }
            self._write(data)
            self._cache = data
            return {"table": self.name, "created": True}

    def drop(self) -> dict:
        """Delete the table entirely."""
        with self._lock:
            if not self.exists():
                raise TableNotFoundError(f"Table '{self.name}' not found")
            os.remove(self.filepath)
            self._cache = None
            return {"table": self.name, "dropped": True}

    def clear(self) -> dict:
        """Remove all records but keep the table structure."""
        with self._lock:
            data = self._read()
            data["records"] = []
            data["meta"]["next_id"] = 1
            data["meta"]["updated_at"] = datetime.utcnow().isoformat()
            data["meta"]["record_count"] = 0
            self._write(data)
            self._cache = data
            return {"table": self.name, "cleared": True, "records_removed": data["meta"]["record_count"]}

    def insert(self, record: dict) -> dict:
        """
        Insert a new record into the table.

        Automatically assigns an auto-incrementing ID and timestamps.

        Args:
            record: Dictionary of field-value pairs.

        Returns:
            The inserted record with generated ID.
        """
        with self._lock:
            data = self._read()

            # Assign ID
            record_id = data["meta"]["next_id"]
            record["id"] = record_id
            record["_created_at"] = datetime.utcnow().isoformat()
            record["_updated_at"] = record["_created_at"]

            data["records"].append(record)
            data["meta"]["next_id"] = record_id + 1
            data["meta"]["updated_at"] = datetime.utcnow().isoformat()
            data["meta"]["record_count"] = len(data["records"])

            self._write(data)
            self._cache = data
            return record

    def insert_many(self, records: list[dict]) -> list[dict]:
        """Insert multiple records in a single operation for speed."""
        with self._lock:
            data = self._read()
            inserted = []
            now = datetime.utcnow().isoformat()

            for record in records:
                record_id = data["meta"]["next_id"]
                record["id"] = record_id
                record["_created_at"] = now
                record["_updated_at"] = now
                data["records"].append(record)
                data["meta"]["next_id"] = record_id + 1
                inserted.append(record)

            data["meta"]["updated_at"] = now
            data["meta"]["record_count"] = len(data["records"])

            self._write(data)
            self._cache = data
            return inserted

    def get(
        self,
        filters: Optional[dict] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "asc",
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """
        Query records with filtering, sorting, and pagination.

        Filter format:
            {"field": {"operator": value}}
            e.g., {"age": {"gt": 18}, "status": {"eq": "active"}}

        Args:
            filters: Dictionary of field-operator-value filters.
            sort_by: Field name to sort by.
            sort_order: "asc" or "desc".
            limit: Maximum records to return.
            offset: Number of records to skip.

        Returns:
            Dictionary with records, total count, and pagination info.
        """
        data = self._read()
        records = data["records"]

        # Apply filters
        if filters:
            records = self._apply_filters(records, filters)

        total = len(records)

        # Apply sorting
        if sort_by:
            records = self._apply_sort(records, sort_by, sort_order)

        # Apply pagination
        paginated = records[offset:offset + limit]

        return {
            "records": paginated,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total,
        }

    def get_by_id(self, record_id: int) -> dict:
        """Retrieve a single record by its ID."""
        data = self._read()
        for record in data["records"]:
            if record.get("id") == record_id:
                return record
        raise RecordNotFoundError(f"Record {record_id} not found in '{self.name}'")

    def update(self, record_id: int, updates: dict) -> dict:
        """
        Update specific fields of a record (PATCH semantics).

        Args:
            record_id: ID of the record to update.
            updates: Dictionary of fields to update.

        Returns:
            The updated record.
        """
        with self._lock:
            data = self._read()

            for i, record in enumerate(data["records"]):
                if record.get("id") == record_id:
                    # Don't allow overwriting the ID
                    updates.pop("id", None)
                    updates.pop("_created_at", None)
                    updates["_updated_at"] = datetime.utcnow().isoformat()

                    data["records"][i].update(updates)
                    data["meta"]["updated_at"] = datetime.utcnow().isoformat()

                    self._write(data)
                    self._cache = data
                    return data["records"][i]

            raise RecordNotFoundError(f"Record {record_id} not found in '{self.name}'")

    def replace(self, record_id: int, new_data: dict) -> dict:
        """
        Replace an entire record (PUT semantics).

        Preserves id and _created_at, replaces everything else.
        """
        with self._lock:
            data = self._read()

            for i, record in enumerate(data["records"]):
                if record.get("id") == record_id:
                    new_data["id"] = record_id
                    new_data["_created_at"] = record.get("_created_at", datetime.utcnow().isoformat())
                    new_data["_updated_at"] = datetime.utcnow().isoformat()

                    data["records"][i] = new_data
                    data["meta"]["updated_at"] = datetime.utcnow().isoformat()

                    self._write(data)
                    self._cache = data
                    return new_data

            raise RecordNotFoundError(f"Record {record_id} not found in '{self.name}'")

    def delete(self, record_id: int) -> dict:
        """Delete a record by its ID."""
        with self._lock:
            data = self._read()

            for i, record in enumerate(data["records"]):
                if record.get("id") == record_id:
                    removed = data["records"].pop(i)
                    data["meta"]["updated_at"] = datetime.utcnow().isoformat()
                    data["meta"]["record_count"] = len(data["records"])

                    self._write(data)
                    self._cache = data
                    return {"deleted": True, "id": record_id, "record": removed}

            raise RecordNotFoundError(f"Record {record_id} not found in '{self.name}'")

    def delete_many(self, filters: dict) -> dict:
        """Delete all records matching the given filters."""
        with self._lock:
            data = self._read()
            before = len(data["records"])
            data["records"] = [
                r for r in data["records"]
                if not self._matches_filters(r, filters)
            ]
            deleted_count = before - len(data["records"])

            data["meta"]["updated_at"] = datetime.utcnow().isoformat()
            data["meta"]["record_count"] = len(data["records"])

            self._write(data)
            self._cache = data
            return {"deleted": True, "count": deleted_count}

    def count(self, filters: Optional[dict] = None) -> int:
        """Count records, optionally with filters."""
        data = self._read()
        if not filters:
            return data["meta"]["record_count"]
        return len(self._apply_filters(data["records"], filters))

    def get_schema(self) -> dict:
        """Return the table schema by inspecting existing records."""
        data = self._read()
        fields = {}
        for record in data["records"]:
            for key, value in record.items():
                if key not in fields:
                    fields[key] = {"type": type(value).__name__, "sample": value}
        return {
            "table": self.name,
            "fields": fields,
            "record_count": data["meta"]["record_count"],
        }

    def get_stats(self) -> dict:
        """Return table statistics."""
        data = self._read()
        return {
            "table": self.name,
            "record_count": data["meta"]["record_count"],
            "next_id": data["meta"]["next_id"],
            "created_at": data["meta"]["created_at"],
            "updated_at": data["meta"]["updated_at"],
            "file_size_bytes": os.path.getsize(self.filepath) if self.exists() else 0,
        }

    # ── Internal methods ──────────────────────────────────────────

    def _read(self) -> dict:
        """
        Read table data from cache or disk.
        Uses a short TTL cache to avoid repeated disk reads in bursts.
        """
        now = time.monotonic()
        if self._cache is not None and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        if not self.exists():
            raise TableNotFoundError(f"Table '{self.name}' not found")

        with open(self.filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._cache = data
        self._cache_time = now
        return data

    def _write(self, data: dict) -> None:
        """Write data to disk atomically (write-to-temp then rename)."""
        tmp_path = self.filepath + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            # Atomic rename (works on both Linux and Windows)
            if os.path.exists(self.filepath):
                os.replace(tmp_path, self.filepath)
            else:
                os.rename(tmp_path, self.filepath)
        except Exception:
            # Clean up temp file on failure
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    def _apply_filters(self, records: list[dict], filters: dict) -> list[dict]:
        """Apply a set of filters to a list of records."""
        result = []
        for record in records:
            if self._matches_filters(record, filters):
                result.append(record)
        return result

    def _matches_filters(self, record: dict, filters: dict) -> bool:
        """Check if a record matches all the given filters."""
        for field, condition in filters.items():
            if not isinstance(condition, dict):
                # Simple equality: {"field": value}
                condition = {"eq": condition}

            for op, expected in condition.items():
                if op not in OPERATORS:
                    raise ValidationError(f"Unknown operator: '{op}'. Valid: {list(OPERATORS.keys())}")

                actual = record.get(field)
                try:
                    if not OPERATORS[op](actual, expected):
                        return False
                except TypeError:
                    return False
        return True

    def _apply_sort(self, records: list[dict], sort_by: str, sort_order: str) -> list[dict]:
        """Sort records by a field."""
        reverse = sort_order.lower() == "desc"

        def sort_key(record):
            value = record.get(sort_by)
            if value is None:
                return ("",)  # Sort None values last
            return (str(value),)

        try:
            return sorted(records, key=sort_key, reverse=reverse)
        except TypeError:
            return records


class Database:
    """
    Main database manager.

    Manages multiple Table instances, handles initialization,
    and provides table listing and backup functionality.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._tables: dict[str, Table] = {}
        self._lock = threading.Lock()

        # Ensure storage directory exists
        os.makedirs(db_path, exist_ok=True)

    def get_table(self, name: str) -> Table:
        """
        Get or create a Table instance.
        Does NOT create the table on disk — use table.create() for that.
        """
        if name not in self._tables:
            with self._lock:
                if name not in self._tables:
                    self._tables[name] = Table(name, self.db_path)
        return self._tables[name]

    def list_tables(self) -> list[dict]:
        """List all tables with their basic stats."""
        tables = []
        for json_file in Path(self.db_path).glob("*.json"):
            name = json_file.stem
            table = self.get_table(name)
            try:
                stats = table.get_stats()
                tables.append(stats)
            except (DatabaseError, json.JSONDecodeError):
                continue
        return tables

    def table_exists(self, name: str) -> bool:
        """Check if a table exists."""
        return os.path.isfile(os.path.join(self.db_path, f"{name}.json"))

    def backup(self, backup_dir: str = "backups") -> str:
        """Create a timestamped backup of all tables."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"backup_{timestamp}")
        os.makedirs(backup_path, exist_ok=True)

        for json_file in Path(self.db_path).glob("*.json"):
            shutil.copy2(json_file, backup_path)

        return backup_path

    def validate_table_name(self, name: str) -> bool:
        """
        Validate a table name.
        Only allows alphanumeric characters, underscores, and hyphens.
        """
        import re
        return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$", name))
