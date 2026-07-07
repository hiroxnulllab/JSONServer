#!/usr/bin/env python3
"""
Comprehensive test suite for JSONServer API.
Tests all endpoints, error handling, edge cases, and security.

Usage:
    python test_api.py [base_url]
    python test_api.py http://localhost:5050
"""

import json
import sys
import time

import requests

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5050"
PASSED = 0
FAILED = 0
ERRORS = []


def test(name: str, method: str, url: str, *, json_data=None, params=None,
         expected_status: int = 200, check_contains: dict = None,
         check_not_contains: list = None):
    """Run a single test case."""
    global PASSED, FAILED, ERRORS

    try:
        kwargs = {"timeout": 10}
        if json_data is not None:
            kwargs["json"] = json_data
        if params:
            kwargs["params"] = params

        resp = getattr(requests, method.lower())(f"{BASE_URL}{url}", **kwargs)
        status_ok = resp.status_code == expected_status

        body = {}
        try:
            body = resp.json()
        except Exception:
            pass

        contains_ok = True
        if check_contains:
            for key, value in check_contains.items():
                if key not in body or body[key] != value:
                    contains_ok = False
                    break

        not_contains_ok = True
        if check_not_contains:
            for key in check_not_contains:
                if key in body:
                    not_contains_ok = False
                    break

        if status_ok and contains_ok and not_contains_ok:
            PASSED += 1
            print(f"  \033[92m[PASS]\033[0m {name}")
            return body
        else:
            FAILED += 1
            reason = []
            if not status_ok:
                reason.append(f"status {resp.status_code} != {expected_status}")
            if not contains_ok:
                reason.append(f"missing expected keys/values")
            if not not_contains_ok:
                reason.append(f"unexpected keys present")
            ERRORS.append((name, ", ".join(reason)))
            print(f"  \033[91m[FAIL]\033[0m {name} — {', '.join(reason)}")
            return body

    except Exception as e:
        FAILED += 1
        ERRORS.append((name, str(e)))
        print(f"  \033[91m[FAIL]\033[0m {name} — {e}")
        return {}


def run_tests():
    """Run the full test suite."""
    global PASSED, FAILED

    print(f"\n{'='*60}")
    print(f"  JSONServer API Test Suite")
    print(f"  Target: {BASE_URL}")
    print(f"{'='*60}\n")

    # ── 1. Health & Root ────────────────────────────────────────
    print("\033[96m[1/10] Health & Root\033[0m")
    test("Root endpoint", "GET", "/", expected_status=200, check_contains={"name": "JSONServer"})
    test("Health check", "GET", "/health", expected_status=200, check_contains={"status": "healthy"})
    test("API docs", "GET", "/api", expected_status=200)
    test("404 handling", "GET", "/nonexistent", expected_status=404)

    # ── 2. Table Management ────────────────────────────────────
    print("\n\033[96m[2/10] Table Management\033[0m")
    test("Create table 'users'", "POST", "/api/tables",
         json_data={"name": "users"}, expected_status=201)
    test("Create table 'products'", "POST", "/api/tables",
         json_data={"name": "products"}, expected_status=201)
    test("Duplicate table error", "POST", "/api/tables",
         json_data={"name": "users"}, expected_status=409)
    test("Invalid table name", "POST", "/api/tables",
         json_data={"name": "123bad"}, expected_status=400)
    test("Missing table name", "POST", "/api/tables",
         json_data={}, expected_status=400)
    test("List tables", "GET", "/api/tables",
         expected_status=200)
    test("Get table stats", "GET", "/api/tables/users",
         expected_status=200)

    # ── 3. Insert Records ──────────────────────────────────────
    print("\n\033[96m[3/10] Insert Records\033[0m")
    test("Insert single user", "POST", "/api/users",
         json_data={"name": "Alice", "age": 30, "email": "alice@test.com", "role": "admin"},
         expected_status=201)
    test("Insert second user", "POST", "/api/users",
         json_data={"name": "Bob", "age": 25, "email": "bob@test.com", "role": "user"},
         expected_status=201)
    test("Insert third user", "POST", "/api/users",
         json_data={"name": "Charlie", "age": 35, "email": "charlie@test.com", "role": "user"},
         expected_status=201)
    test("Insert fourth user", "POST", "/api/users",
         json_data={"name": "Diana", "age": 28, "email": "diana@test.com", "role": "moderator"},
         expected_status=201)
    test("Batch insert products", "POST", "/api/products",
         json_data=[
             {"name": "Widget", "price": 9.99, "stock": 100, "category": "tools"},
             {"name": "Gadget", "price": 29.99, "stock": 50, "category": "electronics"},
             {"name": "Gizmo", "price": 14.99, "stock": 75, "category": "tools"},
         ],
         expected_status=201)
    test("Insert to nonexistent table", "POST", "/api/nonexistent",
         json_data={"test": True}, expected_status=404)

    # ── 4. Query Records ───────────────────────────────────────
    print("\n\033[96m[4/10] Query Records\033[0m")
    test("Get all users", "GET", "/api/users", expected_status=200)
    test("Filter by equality", "GET", "/api/users",
         params={"role": "admin"}, expected_status=200)
    test("Filter with gt operator", "GET", "/api/users",
         params={"age__gt": "27"}, expected_status=200)
    test("Filter with lte operator", "GET", "/api/users",
         params={"age__lte": "28"}, expected_status=200)
    test("Filter with contains", "GET", "/api/users",
         params={"name__contains": "li"}, expected_status=200)
    test("Sort ascending", "GET", "/api/users",
         params={"sort_by": "age", "sort_order": "asc"}, expected_status=200)
    test("Sort descending", "GET", "/api/users",
         params={"sort_by": "age", "sort_order": "desc"}, expected_status=200)
    test("Pagination limit=2", "GET", "/api/users",
         params={"limit": "2"}, expected_status=200)
    test("Pagination offset=2", "GET", "/api/users",
         params={"limit": "2", "offset": "2"}, expected_status=200)
    test("Combined filter+sort+page", "GET", "/api/users",
         params={"role": "user", "sort_by": "age", "sort_order": "desc", "limit": "1"},
         expected_status=200)

    # ── 5. Get By ID ───────────────────────────────────────────
    print("\n\033[96m[5/10] Get By ID\033[0m")
    test("Get user #1", "GET", "/api/users/1", expected_status=200, check_contains={"name": "Alice"})
    test("Get user #2", "GET", "/api/users/2", expected_status=200, check_contains={"name": "Bob"})
    test("Get nonexistent user", "GET", "/api/users/999", expected_status=404)

    # ── 6. Update (PATCH) ──────────────────────────────────────
    print("\n\033[96m[6/10] Update (PATCH)\033[0m")
    test("Update user age", "PATCH", "/api/users/1",
         json_data={"age": 31}, expected_status=200)
    test("Update user role", "PATCH", "/api/users/2",
         json_data={"role": "moderator"}, expected_status=200)
    test("Update nonexistent user", "PATCH", "/api/users/999",
         json_data={"age": 99}, expected_status=404)

    # ── 7. Replace (PUT) ───────────────────────────────────────
    print("\n\033[96m[7/10] Replace (PUT)\033[0m")
    test("Replace user #3", "PUT", "/api/users/3",
         json_data={"name": "Charles", "age": 36, "email": "charles@test.com", "role": "admin"},
         expected_status=200)
    test("Replace nonexistent", "PUT", "/api/users/999",
         json_data={"name": "Ghost"}, expected_status=404)

    # ── 8. Count & Schema ──────────────────────────────────────
    print("\n\033[96m[8/10] Count & Schema\033[0m")
    test("Count all users", "GET", "/api/users/count", expected_status=200)
    test("Count filtered users", "GET", "/api/users/count",
         params={"role": "admin"}, expected_status=200)
    test("Get user schema", "GET", "/api/users/schema", expected_status=200)

    # ── 9. Delete ──────────────────────────────────────────────
    print("\n\033[96m[9/10] Delete\033[0m")
    test("Delete user #4", "DELETE", "/api/users/4", expected_status=200)
    test("Delete already deleted", "DELETE", "/api/users/4", expected_status=404)
    test("Verify deletion", "GET", "/api/users/4", expected_status=404)
    test("Count after delete", "GET", "/api/users/count", expected_status=200)

    # ── 10. Table Cleanup ──────────────────────────────────────
    print("\n\033[96m[10/10] Table Cleanup\033[0m")
    test("Clear products table", "PUT", "/api/tables/products/clear", expected_status=200)
    test("Drop products table", "DELETE", "/api/tables/products", expected_status=200)
    test("Access dropped table", "GET", "/api/products", expected_status=404)
    test("Final table list", "GET", "/api/tables", expected_status=200)

    # ── Summary ────────────────────────────────────────────────
    total = PASSED + FAILED
    print(f"\n{'='*60}")
    print(f"  Results: {PASSED}/{total} passed", end="")
    if FAILED:
        print(f" | {FAILED} FAILED")
    else:
        print(" | ALL PASSED OK")
    print(f"{'='*60}")

    if ERRORS:
        print("\nFailed tests:")
        for name, reason in ERRORS:
            print(f"  - {name}: {reason}")

    return FAILED == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
