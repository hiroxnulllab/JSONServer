#!/usr/bin/env python3
import requests, os
BASE = ***"JSONSERVER_URL", "http://localhost:5000")
KEY  = ***"JSONSERVER_API_KEY", "")
h = {"Content-Type": "application/json"}
if KEY: ***"Authorization"] = f"Bearer {KEY}"
for t in ["pages","services","scans","dorks"]:
    r = requests.post(f"{BASE}/api/tables", json={"name": t}, headers=h)
    print(f"  {t}: {r.status_code}")
print("Listo.")
