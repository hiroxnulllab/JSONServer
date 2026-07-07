<p align="center">
  <img src="https://img.shields.io/badge/JSONServer-v1.0.0-blue?style=for-the-badge&logo=json&logoColor=white" alt="JSONServer v1.0.0">
</p>

<p align="center">
  <strong>Lightweight JSON-based REST API database server.</strong><br>
  A full-featured database with CRUD, filtering, sorting, pagination, auth, and rate limiting — stored as plain JSON files. No MySQL. No PostgreSQL. No dependencies beyond Flask.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Flask-3.0+-000000?style=flat-square&logo=flask&logoColor=white" alt="Flask 3.0+">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="MIT License">
  <img src="https://img.shields.io/badge/Tests-46%2F46%20PASSED-brightgreen?style=flat-square" alt="46/46 Tests">
  <img src="https://img.shields.io/badge/Dependencies-1-lightgrey?style=flat-square" alt="1 Dependency">
</p>

---

## Why does this exist?

[PythonAnywhere free tier](https://www.pythonanywhere.com/) doesn't support MySQL or PostgreSQL. If you want to store data from a Flask app, your only option is flat files.

JSONServer turns that limitation into a feature. It gives you a **complete REST API database** backed by JSON files — with everything you'd expect from a real database: auto-incrementing IDs, query operators, sorting, pagination, batch operations, schema inference, API key authentication, rate limiting, thread-safe atomic writes, and security headers.

**One dependency. One file per table. Zero setup.**

---

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
  - [Root & Health](#root--health)
  - [Table Management](#table-management)
  - [Record Operations (CRUD)](#record-operations-crud)
  - [Count & Schema](#count--schema)
- [Query Syntax](#query-syntax)
  - [Simple Filters](#simple-filters)
  - [Operators](#operators)
  - [Sorting](#sorting)
  - [Pagination](#pagination)
  - [Combined Queries](#combined-queries)
- [Authentication](#authentication)
- [Full Examples](#full-examples)
  - [cURL](#curl)
  - [Python](#python)
  - [JavaScript](#javascript)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Error Handling](#error-handling)
- [Security](#security)
- [PythonAnywhere Deployment](#pythonanywhere-deployment)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [HiroDev Workspace](#hirodev-workspace)
- [License](#license)

---

## Features

### Database Engine
- **CRUD operations** — Create, Read, Update (PATCH), Replace (PUT), Delete
- **Auto-incrementing IDs** — each record gets a unique `id` field
- **Timestamps** — `_created_at` and `_updated_at` added automatically
- **Batch inserts** — insert hundreds of records in a single request
- **Schema inference** — inspect field types from existing data
- **Table stats** — record count, next ID, file size, creation date
- **In-memory caching** — 100ms TTL cache avoids repeated disk reads
- **Atomic writes** — write-to-temp + rename prevents corruption on crashes
- **Thread-safe** — `threading.RLock` on every write operation

### Query Engine
- **12 filter operators** — `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `nin`, `contains`, `startswith`, `endswith`, `exists`
- **Sorting** — by any field, ascending or descending
- **Pagination** — `limit` and `offset` parameters
- **Type coercion** — `true`/`false`/`null`/numbers auto-parsed from query strings

### Security
- **API key authentication** — via `Authorization: Bearer`, `X-API-Key` header, or `?api_key=` param
- **Rate limiting** — configurable requests per minute per IP with token bucket algorithm
- **Constant-time key comparison** — `hmac.compare_digest` prevents timing attacks
- **Input sanitization** — depth limiting (5 levels), string length limits (10,000 chars), key count limits (100 keys)
- **Security headers** — `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Content-Security-Policy`, `Referrer-Policy`
- **CORS** — configurable allowed origins
- **Payload limits** — max request body size (default 1MB)
- **Rate limit headers** — `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` on every response
- **X-Forwarded-For support** — correct client IP detection behind reverse proxies (PythonAnywhere)

### Infrastructure
- **Zero config** — runs with sensible defaults out of the box
- **CLI tool** — `--generate-key` for API key generation, `--env` for environment selection
- **Three environments** — development (no auth, debug on), production (auth required, strict), testing (isolated data dir)
- **Self-documenting** — `/api` endpoint returns full API documentation in JSON
- **CORS preflight** — automatic `OPTIONS` handling

---

## Quick Start

### Install & Run

```bash
pip install flask
python main.py
```

Server starts at `http://localhost:5000`. No API key required in development mode.

### With Authentication

```bash
# Generate an API key
python main.py --generate-key
# Output: Generated API key: jsk_xxxxxxxxxxxxxxxx

# Start with auth enabled
set JSONSERVER_API_KEYS=jsk_xxxxxxxxxxxxxxxx    # Windows
export JSONSERVER_API_KEYS=jsk_xxxxxxxxxxxxxxxx  # Linux/macOS
python main.py --env production
```

### First API Call

```bash
# Create a table
curl -X POST http://localhost:5000/api/tables -H "Content-Type: application/json" -d '{"name": "todos"}'

# Add a record
curl -X POST http://localhost:5000/api/todos -H "Content-Type: application/json" -d '{"title": "Learn Flask", "done": false}'

# Get all records
curl http://localhost:5000/api/todos
```

---

## API Reference

### Root & Health

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|:-------------:|
| `GET` | `/` | Server info (name, version, endpoints) | No |
| `GET` | `/health` | Health check (table count, auth status) | No |
| `GET` | `/api` | Full API documentation (JSON) | No |

**`GET /`** returns:
```json
{
  "name": "JSONServer",
  "version": "1.0.0",
  "description": "Lightweight JSON-based REST API database",
  "endpoints": {
    "tables": "/api/tables",
    "records": "/api/<table_name>",
    "health": "/health"
  }
}
```

**`GET /health`** returns:
```json
{
  "status": "healthy",
  "tables": 3,
  "auth_required": true
}
```

---

### Table Management

| Method | Endpoint | Description | Body |
|--------|----------|-------------|------|
| `GET` | `/api/tables` | List all tables with stats | — |
| `POST` | `/api/tables` | Create a new table | `{"name": "table_name"}` |
| `GET` | `/api/tables/<name>` | Table stats & inferred schema | — |
| `DELETE` | `/api/tables/<name>` | Drop table entirely | — |
| `PUT` | `/api/tables/<name>/clear` | Remove all records, keep structure | — |

**Table names** must start with a letter and can contain letters, numbers, underscores, and hyphens. Max 64 characters.

**`POST /api/tables`** — `201 Created`:
```json
{
  "table": "users",
  "created": true
}
```

**`GET /api/tables`** — `200 OK`:
```json
{
  "tables": [
    {
      "table": "users",
      "record_count": 4,
      "next_id": 5,
      "created_at": "2026-07-07T10:00:00",
      "updated_at": "2026-07-07T10:30:00",
      "file_size_bytes": 1024
    }
  ],
  "count": 1
}
```

**`GET /api/tables/users`** — `200 OK`:
```json
{
  "stats": {
    "table": "users",
    "record_count": 4,
    "next_id": 5,
    "created_at": "2026-07-07T10:00:00",
    "updated_at": "2026-07-07T10:30:00",
    "file_size_bytes": 1024
  },
  "schema": {
    "name": {"type": "str", "sample": "Alice"},
    "age": {"type": "int", "sample": 30},
    "role": {"type": "str", "sample": "admin"}
  }
}
```

---

### Record Operations (CRUD)

| Method | Endpoint | Description | Body |
|--------|----------|-------------|------|
| `GET` | `/api/<table>` | Query records (filters, sort, pagination) | — |
| `POST` | `/api/<table>` | Insert one or many records | `{...}` or `[{...}, ...]` |
| `GET` | `/api/<table>/<id>` | Get record by ID | — |
| `PUT` | `/api/<table>/<id>` | Replace entire record | `{...}` |
| `PATCH` | `/api/<table>/<id>` | Update specific fields | `{...}` |
| `DELETE` | `/api/<table>/<id>` | Delete record by ID | — |
| `DELETE` | `/api/<table>` | Delete by filter (requires filters) | — |

**`POST /api/users`** — `201 Created`:
```json
{
  "id": 1,
  "name": "Alice",
  "age": 30,
  "role": "admin",
  "_created_at": "2026-07-07T10:00:00",
  "_updated_at": "2026-07-07T10:00:00"
}
```

**`POST /api/users`** (batch) — `201 Created`:
```json
{
  "inserted": 3,
  "records": [
    {"id": 2, "name": "Bob", "_created_at": "...", "_updated_at": "..."},
    {"id": 3, "name": "Charlie", "_created_at": "...", "_updated_at": "..."},
    {"id": 4, "name": "Diana", "_created_at": "...", "_updated_at": "..."}
  ]
}
```

**`GET /api/users`** (query) — `200 OK`:
```json
{
  "table": "users",
  "records": [
    {"id": 1, "name": "Alice", "age": 30, "role": "admin", "_created_at": "...", "_updated_at": "..."},
    {"id": 2, "name": "Bob", "age": 25, "role": "user", "_created_at": "...", "_updated_at": "..."}
  ],
  "total": 4,
  "limit": 100,
  "offset": 0,
  "has_more": false
}
```

**`PATCH /api/users/1`** — merges fields, preserves others:
```json
// Request body: {"age": 31}
// Response: full record with age updated to 31
```

**`PUT /api/users/1`** — replaces everything except `id` and `_created_at`:
```json
// Request body: {"name": "Alice Smith", "age": 31, "role": "superadmin"}
// Response: new record, _created_at preserved, _updated_at refreshed
```

**`DELETE /api/users`** (bulk) — requires at least one filter:
```bash
curl -X DELETE "http://localhost:5000/api/users?role=inactive"
# Returns: {"deleted": true, "count": 3}
```

---

### Count & Schema

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/<table>/count` | Count records (supports filters) |
| `GET` | `/api/<table>/schema` | Get inferred field types |

```bash
# Count all users
curl http://localhost:5000/api/users/count
# → {"table": "users", "count": 4}

# Count only admins
curl "http://localhost:5000/api/users/count?role=admin"
# → {"table": "users", "count": 1}
```

---

## Query Syntax

### Simple Filters

Add query parameters to filter by exact match:

```
GET /api/users?role=admin&age=30
```

Type coercion happens automatically:
- `true` / `false` → boolean
- `null` → null
- `123` → integer
- `3.14` → float
- everything else → string

### Operators

Use `__` (double underscore) between field name and operator:

```
GET /api/users?field__operator=value
```

| Operator | Description | Example |
|----------|-------------|---------|
| `eq` | Equal to (default) | `?role__eq=admin` |
| `ne` | Not equal | `?role__ne=banned` |
| `gt` | Greater than | `?age__gt=18` |
| `gte` | Greater than or equal | `?age__gte=21` |
| `lt` | Less than | `?price__lt=50` |
| `lte` | Less than or equal | `?price__lte=29.99` |
| `in` | Value in list | `?role__in=admin,mod` |
| `nin` | Value not in list | `?role__nin=banned,guest` |
| `contains` | String contains substring | `?name__contains=john` |
| `startswith` | String starts with | `?email__startswith=admin` |
| `endswith` | String ends with | `?email__endswith=@gmail.com` |
| `exists` | Field exists (true) or not (false) | `?phone__exists=true` |

### Sorting

```
GET /api/users?sort_by=age&sort_order=asc
GET /api/users?sort_by=name&sort_order=desc
```

- `sort_by` — field name to sort by
- `sort_order` — `asc` (default) or `desc`

### Pagination

```
GET /api/users?limit=10&offset=0    # First page
GET /api/users?limit=10&offset=10   # Second page
GET /api/users?limit=10&offset=20   # Third page
```

- `limit` — max records to return (default: 100, max: 1000)
- `offset` — skip N records (default: 0)

The response includes `has_more: true/false` to know if more pages exist.

### Combined Queries

Everything composes. Filters, sorting, and pagination work together:

```
GET /api/users?role=admin&age__gt=21&sort_by=name&sort_order=asc&limit=5&offset=0
```

This reads as: *"Give me the first 5 admins older than 21, sorted by name A-Z."*

---

## Authentication

JSONServer supports three ways to send an API key (in order of precedence):

### 1. Authorization header (recommended)
```bash
curl -H "Authorization: Bearer jsk_xxxxxxxxxxxxxxxx" http://localhost:5000/api/users
```

### 2. X-API-Key header
```bash
curl -H "X-API-Key: jsk_xxxxxxxxxxxxxxxx" http://localhost:5000/api/users
```

### 3. Query parameter (least secure — for testing only)
```bash
curl "http://localhost:5000/api/users?api_key=jsk_xxxxxxxxxxxxxxxx"
```

### Behavior by Environment

| Environment | Auth Required | Rate Limit | Debug |
|-------------|:-------------:|:----------:|:-----:|
| `development` | No | 1000/min | Yes |
| `production` | Yes | 120/min | No |
| `testing` | No | 10000/min | Yes |

If auth is required and no keys are configured, JSONServer **auto-generates a key** and prints it to the console on startup.

### Generating Keys

```bash
python main.py --generate-key
# Output: Generated API key: jsk_xxxxxxxxxxxxxxxx
```

Keys are prefixed with `jsk_` for easy identification. Store them securely — they're shown only once.

---

## Full Examples

### cURL

```bash
# ── Tables ────────────────────────────────────────────────────
# Create
curl -X POST http://localhost:5000/api/tables \
  -H "Content-Type: application/json" \
  -d '{"name": "posts"}'

# List
curl http://localhost:5000/api/tables

# Stats
curl http://localhost:5000/api/tables/posts

# Clear (keep structure)
curl -X PUT http://localhost:5000/api/tables/posts/clear

# Drop (delete entirely)
curl -X DELETE http://localhost:5000/api/tables/posts


# ── Records ───────────────────────────────────────────────────
# Insert one
curl -X POST http://localhost:5000/api/posts \
  -H "Content-Type: application/json" \
  -d '{"title": "Hello World", "tags": ["intro"], "published": true}'

# Insert many
curl -X POST http://localhost:5000/api/posts \
  -H "Content-Type: application/json" \
  -d '[
    {"title": "First Post", "published": true},
    {"title": "Draft", "published": false},
    {"title": "Tutorial", "published": true}
  ]'

# Get all
curl http://localhost:5000/api/posts

# Get by ID
curl http://localhost:5000/api/posts/1

# Filter
curl "http://localhost:5000/api/posts?published=true"

# Sort + paginate
curl "http://localhost:5000/api/posts?sort_by=title&sort_order=asc&limit=5&offset=0"

# Update (PATCH — partial)
curl -X PATCH http://localhost:5000/api/posts/1 \
  -H "Content-Type: application/json" \
  -d '{"published": false}'

# Replace (PUT — full)
curl -X PUT http://localhost:5000/api/posts/1 \
  -H "Content-Type: application/json" \
  -d '{"title": "Updated Title", "tags": ["updated"], "published": true}'

# Delete by ID
curl -X DELETE http://localhost:5000/api/posts/1

# Delete by filter
curl -X DELETE "http://localhost:5000/api/posts?published=false"

# Count
curl http://localhost:5000/api/posts/count
curl "http://localhost:5000/api/posts/count?published=true"

# Schema
curl http://localhost:5000/api/posts/schema
```

### Python

```python
import requests

API = "http://localhost:5000"
HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": "jsk_xxxxxxxxxxxxxxxx",
}

# ── Create table ──────────────────────────────────────────────
requests.post(f"{API}/api/tables", json={"name": "notes"}, headers=HEADERS)

# ── Insert records ────────────────────────────────────────────
requests.post(f"{API}/api/notes", json={"text": "Buy milk", "priority": "high"}, headers=HEADERS)
requests.post(f"{API}/api/notes", json=[
    {"text": "Call dentist", "priority": "medium"},
    {"text": "Fix bug #42", "priority": "high"},
    {"text": "Read docs", "priority": "low"},
], headers=HEADERS)

# ── Query with filters ────────────────────────────────────────
r = requests.get(f"{API}/api/notes", params={"priority": "high"}, headers=HEADERS)
data = r.json()
print(f"Found {data['total']} high-priority notes:")
for note in data["records"]:
    print(f"  #{note['id']}: {note['text']}")

# ── Update a record ───────────────────────────────────────────
requests.patch(f"{API}/api/notes/1", json={"text": "Buy oat milk"}, headers=HEADERS)

# ── Count ─────────────────────────────────────────────────────
r = requests.get(f"{API}/api/notes/count", params={"priority": "high"}, headers=HEADERS)
print(f"High priority count: {r.json()['count']}")

# ── Delete by filter ──────────────────────────────────────────
requests.delete(f"{API}/api/notes", params={"priority": "low"}, headers=HEADERS)
```

### JavaScript

```javascript
const API = "http://localhost:5000";
const HEADERS = {
  "Content-Type": "application/json",
  "X-API-Key": "jsk_xxxxxxxxxxxxxxxx",
};

// ── Create table ──────────────────────────────────────────────
await fetch(`${API}/api/tables`, {
  method: "POST",
  headers: HEADERS,
  body: JSON.stringify({ name: "tasks" }),
});

// ── Insert records ────────────────────────────────────────────
await fetch(`${API}/api/tasks`, {
  method: "POST",
  headers: HEADERS,
  body: JSON.stringify([
    { title: "Deploy app", done: false },
    { title: "Write tests", done: true },
  ]),
});

// ── Query with filters ────────────────────────────────────────
const res = await fetch(`${API}/api/tasks?done=false&sort_by=title`, { headers: HEADERS });
const data = await res.json();
console.log(`${data.total} pending tasks:`, data.records);

// ── Update ────────────────────────────────────────────────────
await fetch(`${API}/api/tasks/1`, {
  method: "PATCH",
  headers: HEADERS,
  body: JSON.stringify({ done: true }),
});

// ── Delete by filter ──────────────────────────────────────────
await fetch(`${API}/api/tasks?done=true`, {
  method: "DELETE",
  headers: HEADERS,
});
```

---

## Architecture

```
                         ┌──────────────────────┐
                         │   HTTP Request       │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │   Flask App          │
                         │   (app.py)           │
                         │  ┌─────────────────┐ │
                         │  │ Security Headers│ │
                         │  │ Payload Limit   │ │
                         │  │ CORS            │ │
                         │  └─────────────────┘ │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
           ┌────────▼───────┐ ┌─────▼──────┐ ┌──────▼─────┐
           │  Auth (auth.py)│ │ Rate Limit │ │  Routes    │
           │  API Key Check │ │ Per-IP     │ │  tables.py │
           │  Timing-Safe   │ │ Token      │ │  records.py│
           │                │ │ Bucket     │ │            │
           └────────────────┘ └────────────┘ └──────┬─────┘
                                                    │
                                          ┌─────────▼─────────┐
                                          │  Database Engine  │
                                          │  (database.py)    │
                                          │  ┌──────────────┐ │
                                          │  │ In-Memory    │ │
                                          │  │ Cache (100ms)│ │
                                          │  └──────┬───────┘ │
                                          │  ┌──────▼───────┐ │
                                          │  │ Thread Lock  │ │
                                          │  │ (RLock)      │ │
                                          │  └──────┬───────┘ │
                                          │  ┌──────▼───────┐ │
                                          │  │ Atomic Write │ │
                                          │  │ (tmp+rename) │ │
                                          │  └──────┬───────┘ │
                                          └─────────┼─────────┘
                                                    │
                                           ┌────────▼─────────┐
                                           │   JSON Files     │
                                           │   data/          │
                                           │   ├── users.json │
                                           │   ├── posts.json │
                                           │   └── orders.json│
                                           └──────────────────┘
```

### How data is stored

Each table is a single JSON file in the `data/` directory. The structure:

```json
{
  "meta": {
    "next_id": 5,
    "created_at": "2026-07-07T10:00:00",
    "updated_at": "2026-07-07T10:30:00",
    "record_count": 4
  },
  "records": [
    {"id": 1, "name": "Alice", "age": 30, "_created_at": "...", "_updated_at": "..."},
    {"id": 2, "name": "Bob", "age": 25, "_created_at": "...", "_updated_at": "..."}
  ]
}
```

- **`meta.next_id`** — auto-incremented for each new record
- **`meta.record_count`** — updated on every insert/delete
- **`_created_at`** / **`_updated_at`** — ISO timestamps, auto-managed
- **`id`** — cannot be overwritten by PUT/PATCH

### Write Safety

Every write follows this sequence:
1. Acquire thread lock (`RLock`)
2. Read current data
3. Modify in memory
4. Write to `{table}.json.tmp`
5. Atomic rename (`os.replace`) to `{table}.json`
6. Release lock

If the process crashes mid-write, only the `.tmp` file is corrupted — the original `.json` file remains intact.

---

## Configuration

All settings via environment variables. Set them before starting the server, or in the WSGI file for PythonAnywhere.

| Variable | Default | Description |
|----------|---------|-------------|
| `JSONSERVER_ENV` | `development` | Environment mode: `development`, `production`, `testing` |
| `JSONSERVER_DB_PATH` | `data` | Directory where JSON table files are stored |
| `JSONSERVER_API_KEYS` | *(empty)* | Comma-separated API keys. If empty and auth is required, a key is auto-generated |
| `JSONSERVER_REQUIRE_AUTH` | `true` | Whether API key is required. Overridden to `true` in production |
| `JSONSERVER_RATE_LIMIT` | `120` | Max requests per minute per IP |
| `JSONSERVER_MAX_PAYLOAD` | `1048576` (1MB) | Max request body size in bytes |
| `JSONSERVER_MAX_RECORDS` | `1000` | Max records per batch insert or query response |
| `JSONSERVER_MAX_FIELD_LEN` | `10000` | Max string length per field value |
| `JSONSERVER_CORS_ORIGINS` | `*` | Allowed CORS origins |
| `JSONSERVER_HOST` | `0.0.0.0` | Host to bind (CLI mode only) |
| `JSONSERVER_PORT` | `5000` | Port to bind (CLI mode only) |
| `JSONSERVER_DEBUG` | `false` | Enable Flask debug mode |

### Environment Presets

| Setting | `development` | `production` | `testing` |
|---------|:-------------:|:------------:|:---------:|
| Debug | ✅ | ❌ | ✅ |
| Auth Required | ❌ | ✅ | ❌ |
| Rate Limit | 1000/min | 120/min | 10000/min |
| DB Path | `data` | `data` | `test_data` |

---

## Error Handling

All errors return a consistent JSON format:

```json
{
  "error": "Error Type",
  "message": "Human-readable description",
  "status": 400
}
```

| Status | Error | When |
|--------|-------|------|
| `400` | Bad Request | Invalid JSON, missing required fields, validation failure |
| `401` | Unauthorized | Missing or invalid API key |
| `404` | Not Found | Table or record doesn't exist |
| `405` | Method Not Allowed | Wrong HTTP method on an endpoint |
| `409` | Conflict | Table already exists (duplicate create) |
| `413` | Payload Too Large | Request body exceeds max size |
| `429` | Too Many Requests | Rate limit exceeded (includes `retry_after`) |
| `500` | Internal Server Error | Unexpected server error |

### Rate Limit Headers

Every response includes these headers:

```
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 119
X-RateLimit-Reset: 60
```

When rate-limited, the response body includes `retry_after` (seconds until the limit resets).

---

## Security

### Authentication
- API keys are checked via **constant-time comparison** (`hmac.compare_digest`) to prevent timing attacks
- Keys are prefixed with `jsk_` for easy identification
- Multiple keys supported — comma-separated in `JSONSERVER_API_KEYS`
- Auth can be disabled per environment (default in development)

### Input Sanitization
- **Nesting depth** limited to 5 levels
- **Object keys** limited to 100 per object, 200 chars per key name
- **Arrays** limited to 10,000 elements
- **Strings** limited to 10,000 characters
- **Request body** limited to 1MB by default

### Transport
- Security headers on every response:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Content-Security-Policy: default-src 'none'`
  - `Referrer-Policy: no-referrer`
- CORS fully configurable
- Always deploy behind **HTTPS** (Force HTTPS on PythonAnywhere)

### Data Integrity
- Atomic writes (write-to-temp + rename) prevent file corruption
- Thread-safe with `threading.RLock`
- `id` and `_created_at` fields are protected from overwrite
- Table names validated with regex: `^[a-zA-Z][a-zA-Z0-9_-]{0,63}$`

---

## PythonAnywhere Deployment

> **My PythonAnywhere username:** `HiroDev` — all `/home/HiroDev/` paths below refer to **my** account on the server. Replace with your own username if deploying under a different account.

### Current Server State

```
/home/HiroDev/
└── mysite/                                 ← PythonAnywhere project root
    └── flask_app.py                        ← Default Flask example
```

JSONServer is **not yet deployed**. Follow the steps below to upload and configure it.

---

### Step 0 — Create a PythonAnywhere account

> Skip if you already have one.

1. Go to [pythonanywhere.com/pricing](https://www.pythonanywhere.com/pricing/)
2. Find the plan **"Explore with a limited account"**
3. Click **"Create a Beginner account"**
4. Fill in: **Username** (e.g. `HiroDev`), **Email**, **Password**
5. Click **Sign Up**
6. **Verify your email** — check inbox, click the confirmation link
7. You'll see **"Welcome to PythonAnywhere!"** → click **"End Tour"**

You're now in the PythonAnywhere dashboard.

---

### Step 1 — Create the web app

1. Click **"Web"** in the top nav
2. Click **"Add a new web app"**
3. Click **Next** on the confirmation screen
4. Select **"Flask"**
5. Select **Python 3.10** (or newer)
6. Confirm the path (e.g. `/home/HiroDev/mysite/flask_app.py`) → click **Next**

Your site is live at `https://YOUR_USERNAME.pythonanywhere.com/` — but it shows the default "Hello from Flask!" page. We'll fix that.

---

### Step 1.5 — Force HTTPS

You're now on the **Web** tab with your site's configuration.

1. Scroll to the **"Security"** section
2. Toggle **"Force HTTPS"** to **active**

Without this, API keys sent over HTTP can be intercepted.

---

### Step 2 — Upload JSONServer

Click **"Files"** in the top nav.

**Create the folder structure first, then upload files at each level:**

1. In `/home/HiroDev/mysite/`, type `JSONServer` in the **"Enter new directory name"** field → press Enter
   - PythonAnywhere redirects you inside `JSONServer/`
2. Type `jsonserver` → press Enter
   - Redirected inside `jsonserver/`
3. Type `routes` → press Enter
   - Redirected inside `routes/`
4. **Upload** these files: `__init__.py`, `tables.py`, `records.py`
5. **Click `jsonserver`** in the breadcrumb path at the top → back to `jsonserver/`
6. **Upload** these files: `__init__.py`, `app.py`, `auth.py`, `config.py`, `database.py`
7. **Click `JSONServer`** in the breadcrumb → back to `JSONServer/`
8. **Upload** these files: `main.py`, `test_api.py`, `requirements.txt`

**Final structure:**

```
/home/HiroDev/
└── mysite/
    ├── flask_app.py
    └── JSONServer/                         ← Uploaded project
        ├── main.py
        ├── test_api.py
        ├── requirements.txt
        └── jsonserver/
            ├── __init__.py
            ├── app.py
            ├── auth.py
            ├── config.py
            ├── database.py
            └── routes/
                ├── __init__.py
                ├── tables.py
                └── records.py
```

> The `data/` directory is created automatically at runtime.

---

### Step 3 — Generate an API key

1. Click **"Consoles"** in the top nav
2. Under **"Other:"** click **"Bash"**
3. Run:

```bash
cd ~/mysite/JSONServer
python main.py --generate-key
```

4. **Copy the generated key** — you'll need it in the next step

---

### Step 4 — Patch the WSGI file

1. Go to the **Web** tab
2. Click the **WSGI configuration file** link (looks like `/var/www/hirodev_pythonanywhere_com_wsgi.py`)
3. It opens with the auto-generated Flask content
4. **Select all** (Ctrl+A) and **replace everything** with:

```python
# WSGI config for hirodev.pythonanywhere.com
# Serves JSONServer — lightweight JSON-based REST API database.

import sys
import os

# ── Environment config (set BEFORE importing the app) ──────────
os.environ['JSONSERVER_ENV'] = 'production'
os.environ['JSONSERVER_API_KEYS'] = 'PASTE_YOUR_GENERATED_KEY_HERE'
os.environ['JSONSERVER_DB_PATH'] = '/home/HiroDev/mysite/JSONServer/data'
os.environ['JSONSERVER_RATE_LIMIT'] = '120'
os.environ['JSONSERVER_CORS_ORIGINS'] = '*'

# ── Add JSONServer to the Python path ───────────────────────────
project_home = '/home/HiroDev/mysite/JSONServer'
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

# ── Create the Flask app via the JSONServer factory ─────────────
from jsonserver.app import create_app
application = create_app()
```

5. Replace `PASTE_YOUR_GENERATED_KEY_HERE` with the key from Step 3
6. Click **Save**

**What changed from the auto-generated WSGI:**

```diff
  import sys
+ import os
+
+ # Environment config
+ os.environ['JSONSERVER_ENV'] = 'production'
+ os.environ['JSONSERVER_API_KEYS'] = 'your_key_here'
+ os.environ['JSONSERVER_DB_PATH'] = '/home/HiroDev/mysite/JSONServer/data'
+ os.environ['JSONSERVER_RATE_LIMIT'] = '120'
+ os.environ['JSONSERVER_CORS_ORIGINS'] = '*'

- project_home = '/home/HiroDev/mysite'
+ project_home = '/home/HiroDev/mysite/JSONServer'
  if project_home not in sys.path:
      sys.path = [project_home] + sys.path

- from flask_app import app as application
+ from jsonserver.app import create_app
+ application = create_app()
```

---

### Step 5 — Reload

1. Go to the **Web** tab
2. Click the **🔁 Reload** button (white background, light blue circular arrows) next to your site URL

---

### Step 6 — Verify

In your Bash console on:

```bash
# Health check (no auth needed)
curl https://YOUR_USERNAME.pythonanywhere.com/health

# Create a table
curl -X POST https://YOUR_USERNAME.pythonanywhere.com/api/tables \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_key_here" \
  -d '{"name": "test"}'

# Insert a record
curl -X POST https://YOUR_USERNAME.pythonanywhere.com/api/test \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_key_here" \
  -d '{"hello": "world"}'

# Query it back
curl https://YOUR_USERNAME.pythonanywhere.com/api/test \
  -H "X-API-Key: your_key_here"
```

---

### Troubleshooting

> **Note:** `HiroDev` is **my** PythonAnywhere username (hiroxnull's account). All `/home/HiroDev/` paths refer to my home directory on the server. Replace with your own if deploying under a different account.

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: No module named 'jsonserver'` | `project_home` must be `/home/HiroDev/mysite/JSONServer`, not `/home/HiroDev/mysite` |
| `403 Forbidden` | WSGI file has a syntax error — check the **Error log** on the Web tab |
| `500 Internal Server Error` | Check **Server error log** on the Web tab — usually a missing env var or wrong path |
| Rate limit hit | Increase `JSONSERVER_RATE_LIMIT` in the WSGI file |
| Data not persisting | Check `JSONSERVER_DB_PATH` points to `/home/HiroDev/mysite/JSONServer/data` |
| Still shows "Hello from Flask!" | The old `from flask_app import app` line must be gone — replace **all** WSGI content |

---

## Testing

JSONServer includes a **46-test suite** covering every endpoint, error case, and edge case.

### Run locally

```bash
# Start the server
python main.py --port 5050

# In another terminal
python test_api.py
```

### Run against a remote server

```bash
python test_api.py https://YOUR_USERNAME.pythonanywhere.com
```

### What's tested

| Category | Tests | Coverage |
|----------|:-----:|----------|
| Health & Root | 4 | Root endpoint, health check, API docs, 404 handling |
| Table Management | 7 | Create, duplicate error, invalid name, missing name, list, stats |
| Insert Records | 6 | Single insert, batch insert, nonexistent table error |
| Query Records | 10 | Equality, gt, lte, contains, sort asc/desc, pagination, combined |
| Get By ID | 3 | Valid ID, second ID, nonexistent ID |
| Update (PATCH) | 3 | Partial update, role change, nonexistent record |
| Replace (PUT) | 2 | Full replace, nonexistent record |
| Count & Schema | 3 | Count all, count filtered, schema inference |
| Delete | 4 | Delete by ID, double delete, verify deletion, count after delete |
| Table Cleanup | 4 | Clear table, drop table, access dropped table, final list |
| **Total** | **46** | |

---

## Project Structure

```
JSONServer/
│
├── main.py                    # Entry point & CLI (--generate-key, --env, --port)
├── test_api.py                # Test suite (46 tests, 10 categories)
├── requirements.txt           # Dependencies: flask
├── README.md                  # This file
├── .gitignore
│
├── jsonserver/                # Core package
│   ├── __init__.py            # Package metadata (version, author)
│   ├── app.py                 # Flask app factory (middleware, CORS, error handlers, root endpoints)
│   ├── config.py              # Configuration management (env vars, environment presets)
│   ├── auth.py                # API key auth, rate limiting, input sanitization
│   ├── database.py            # JSON database engine (Table, Database, query operators, atomic writes)
│   │
│   └── routes/                # API endpoints
│       ├── __init__.py
│       ├── tables.py          # Table management (create, list, stats, drop, clear)
│       └── records.py         # CRUD operations (query, insert, update, replace, delete, count, schema)
│
└── data/                      # Runtime data (created automatically, gitignored)
    ├── users.json
    ├── posts.json
    └── ...
```

### File-by-File Breakdown

| File | Lines | Purpose |
|------|:-----:|---------|
| `database.py` | ~430 | Core engine. `Table` class handles CRUD, filtering, sorting, caching, atomic writes. `Database` class manages multiple tables. |
| `records.py` | ~210 | Routes for record CRUD. Parses filters from query params, handles pagination, type coercion. |
| `app.py` | ~170 | Flask factory. Registers blueprints, adds security headers, CORS, error handlers, rate limiting, payload limits. |
| `auth.py` | ~140 | `RateLimiter` (token bucket), `require_auth` (API key check), `sanitize_input` (depth/length limits), `generate_api_key`. |
| `config.py` | ~60 | `Config` class with env var parsing. Three presets: development, production, testing. |
| `tables.py` | ~70 | Routes for table management. |
| `test_api.py` | ~230 | 46-test suite with colorized output. |
| `main.py` | ~65 | CLI entry point with argparse. |

---

## Author

**hiroxnull** — [GitHub](https://github.com/hiroxnull)

## License

MIT License — see [LICENSE](LICENSE) for details.
