# -*- coding: utf-8 -*-
import httpx
from collections import Counter

d = httpx.get("http://127.0.0.1:8000/api/cases/3", timeout=15, trust_env=False).json()
print("status:", d["status"], "| stage:", d["stage"])
print("evidence count:", len(d["evidence"]))
rel = Counter(e["relation"] for e in d["evidence"])
print("关系分布:", dict(rel))
print("--- 证据明细 ---")
for e in d["evidence"][:8]:
    print(f"  [{e['relation']}|{e['reliability']}] {e['name'][:35]}")
    note = e.get("note") or ""
    if "判定理由" in note:
        print(f"      ...{note[-90:]}")
print("report:", (d.get("report") or {}).get("conclusion", "无"))
print("log:")
for item in d.get("running_log", []):
    ok = "OK " if item.get("ok") else "SKIP"
    detail = str(item.get("detail", ""))[:50]
    print("  ", ok, item.get("name"), "-", detail)
