#!/usr/bin/env python3
"""
Crea las tablas iniciales en JSONServer.
Ejecutar en consola PA: cd ~/JSONServer && python setup_db.py
"""
import requests, os

BASE = ***"JSONSERVER_URL", "http://localhost:5000")
KEY  = os.environ.get("JSONSERVER_API_KEY", "")
headers = {"Content-Type": "application/json"}
if KEY:
    headers["Authorization"] = f"Bearer {KEY}"

for table in ["pages", "services", "scans", "dorks"]:
    r = requests.post(f"{BASE}/api/tables", json={"name": table}, headers=headers)
    if r.status_code == 201:
        print(f"  [+] Tabla '{table}' creada")
    elif r.status_code == 409:
        print(f"  [=] Tabla '{table}' ya existe")
    else:
        print(f"  [!] Error '{table}': {r.status_code} {r.text[:100]}")

print("\nListo.")
