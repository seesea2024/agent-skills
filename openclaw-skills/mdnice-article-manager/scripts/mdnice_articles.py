#!/usr/bin/env python3
"""Manage mdnice articles via API using local Chrome cookies.

Commands:
  catalogs
  list --catalog NAME --out PATH
  delete --in PATH --log PATH
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests

DEFAULT_BASE = "https://api.mdnice.com"
DEFAULT_HOST = ".mdnice.com"
COMMON_PROFILES = ["Profile 1", "Default", "Profile 2"]


def chrome_root() -> Path:
    return Path.home() / "Library/Application Support/Google/Chrome"


def cookie_paths(profile: str | None = None) -> list[Path]:
    root = chrome_root()
    if profile:
        candidates = [root / profile / "Cookies", root / profile / "Network" / "Cookies"]
    else:
        candidates = []
        for p in COMMON_PROFILES:
            candidates += [root / p / "Cookies", root / p / "Network" / "Cookies"]
        candidates += [Path(x) for x in glob.glob(str(root / "*" / "Cookies"))]
        candidates += [Path(x) for x in glob.glob(str(root / "*" / "Network" / "Cookies"))]
    seen, out = set(), []
    for p in candidates:
        if p.exists() and p not in seen:
            seen.add(p); out.append(p)
    return out


def chrome_safe_storage_password() -> bytes:
    return subprocess.check_output(
        ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage"],
        stderr=subprocess.DEVNULL,
    ).strip()


def decrypt_chrome_v10(encrypted: bytes) -> str:
    if not encrypted:
        return ""
    if not encrypted.startswith(b"v10"):
        return encrypted.decode("utf-8", "ignore")
    key = hashlib.pbkdf2_hmac("sha1", chrome_safe_storage_password(), b"saltysalt", 1003, 16)
    iv = b" " * 16
    proc = subprocess.run(
        ["openssl", "enc", "-d", "-aes-128-cbc", "-K", key.hex(), "-iv", iv.hex()],
        input=encrypted[3:], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "ignore"))
    raw = proc.stdout
    # Newer Chrome prefixes decrypted cookie value with SHA256(host_key) first 32 bytes.
    if raw.startswith(b"eyJ"):
        value = raw
    else:
        value = raw[32:]
    return value.decode("utf-8", "ignore")



def read_cookie_value(db_path: Path, name: str, host: str = DEFAULT_HOST) -> str | None:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = con.execute(
            "select encrypted_value from cookies where host_key=? and name=?",
            (host, name),
        ).fetchone()
        if not row:
            return None
        return decrypt_chrome_v10(row[0])
    finally:
        con.close()


def load_auth(profile: str | None = None) -> tuple[dict[str, str], Path]:
    errors = []
    for db in cookie_paths(profile):
        try:
            token = read_cookie_value(db, "token")
            if token:
                username = read_cookie_value(db, "username") or ""
                user_out_id = read_cookie_value(db, "userOutId") or ""
                return {"token": token, "username": username, "userOutId": user_out_id}, db
        except Exception as e:
            errors.append(f"{db}: {e}")
    raise SystemExit("No valid mdnice token found in Chrome cookies. " + "; ".join(errors[:3]))


def headers(token: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + token, "Content-Type": "application/json"}

def api_get_catalogs(base: str, h: dict[str, str]) -> list[dict[str, Any]]:
    r = requests.get(base + "/catalogs", headers=h, timeout=20)
    data = r.json()
    if not data.get("success"):
        raise SystemExit(json.dumps(data, ensure_ascii=False))
    return data.get("data", {}).get("catalogList", [])


def find_catalog(catalogs: list[dict[str, Any]], name: str) -> dict[str, Any]:
    matches = [c for c in catalogs if c.get("name") == name]
    if not matches:
        available = ", ".join(c.get("name", "") for c in catalogs)
        raise SystemExit(f"Catalog not found: {name}. Available: {available}")
    if len(matches) > 1:
        raise SystemExit(f"Multiple catalogs named {name}; use API manually by catalogId.")
    return matches[0]


def api_list_articles(base: str, h: dict[str, str], catalog_id: int, page_size: int = 40) -> list[dict[str, Any]]:
    out = []
    page = 1
    while True:
        payload = {"currentPage": page, "pageSize": page_size, "catalogId": catalog_id}
        r = requests.post(base + "/articles/search", headers=h, json=payload, timeout=30)
        data = r.json()
        if not data.get("success"):
            raise SystemExit(json.dumps(data, ensure_ascii=False))
        d = data.get("data") or {}
        arr = d.get("articleList") or d.get("articles") or d.get("list") or []
        out.extend(arr)
        if not arr or len(arr) < page_size:
            break
        page += 1
    return out


def cmd_catalogs(args: argparse.Namespace) -> None:
    auth, db = load_auth(args.profile)
    cats = api_get_catalogs(args.base, headers(auth["token"]))
    print(f"cookieDb={db}")
    print(f"username={auth.get('username','')}")
    for c in cats:
        print(f"{c.get('catalogId')}\t{c.get('name')}")

def cmd_list(args: argparse.Namespace) -> None:
    auth, db = load_auth(args.profile)
    h = headers(auth["token"])
    cats = api_get_catalogs(args.base, h)
    cat = find_catalog(cats, args.catalog)
    articles = api_list_articles(args.base, h, int(cat["catalogId"]))
    result = {
        "catalogId": cat["catalogId"],
        "catalogName": cat["name"],
        "count": len(articles),
        "username": auth.get("username", ""),
        "cookieDb": str(db),
        "articles": articles,
    }
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"catalog={cat['name']} catalogId={cat['catalogId']} count={len(articles)} out={args.out}")
    for i, a in enumerate(articles, 1):
        print(f"{i:02d}. {a.get('title')!r} outId={a.get('outId')} id={a.get('id')} created={a.get('createTime') or a.get('createdAt')} updated={a.get('updateTime') or a.get('updatedAt')}")


def cmd_delete(args: argparse.Namespace) -> None:
    saved = json.loads(Path(args.input).read_text(encoding="utf-8"))
    catalog_id = int(saved["catalogId"])
    auth, db = load_auth(args.profile)
    h = headers(auth["token"])
    before = api_list_articles(args.base, h, catalog_id)
    wanted = [a for a in saved.get("articles", []) if a.get("outId")]
    results = []
    print(f"Pre-check count: {len(before)}")
    for i, a in enumerate(wanted, 1):
        oid = a["outId"]
        title = a.get("title")
        try:
            r = requests.delete(args.base + "/articles/" + oid, headers=h, timeout=30)
            try:
                body = r.json()
            except Exception:
                body = {"raw": r.text[:500]}
            ok = r.status_code == 200 and body.get("success") is True
            results.append({"index": i, "title": title, "outId": oid, "status": r.status_code, "ok": ok, "response": body})
            print(f"{i:02d}/{len(wanted)} {'OK' if ok else 'FAIL'} {title} {oid} {body.get('message')}")
        except Exception as e:
            results.append({"index": i, "title": title, "outId": oid, "ok": False, "error": repr(e)})
            print(f"{i:02d}/{len(wanted)} EXC {title} {oid} {e!r}")
        time.sleep(args.sleep)
    after = api_list_articles(args.base, h, catalog_id)
    log = {
        "catalogId": catalog_id,
        "catalogName": saved.get("catalogName"),
        "cookieDb": str(db),
        "beforeCount": len(before),
        "attempted": len(wanted),
        "successCount": sum(1 for x in results if x.get("ok")),
        "failCount": sum(1 for x in results if not x.get("ok")),
        "afterCount": len(after),
        "remaining": [{"title": a.get("title"), "outId": a.get("outId"), "id": a.get("id")} for a in after],
        "results": results,
    }
    Path(args.log).write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SUMMARY", json.dumps({k: log[k] for k in ["beforeCount", "attempted", "successCount", "failCount", "afterCount"]}, ensure_ascii=False))
    print("Log:", args.log)

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Manage mdnice articles via API using Chrome cookies")
    p.add_argument("--profile", help="Chrome profile name, e.g. 'Profile 1' or Default")
    p.add_argument("--base", default=DEFAULT_BASE, help="mdnice API base URL")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("catalogs", help="List catalogs")
    sp.set_defaults(func=cmd_catalogs)

    sp = sub.add_parser("list", help="List articles under a catalog and save JSON")
    sp.add_argument("--catalog", required=True, help="Exact catalog name")
    sp.add_argument("--out", required=True, help="Output JSON path")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("delete", help="Delete articles from a saved list and verify")
    sp.add_argument("--in", dest="input", required=True, help="Input JSON from list command")
    sp.add_argument("--log", required=True, help="Deletion result JSON path")
    sp.add_argument("--sleep", type=float, default=0.15, help="Seconds between delete calls")
    sp.set_defaults(func=cmd_delete)
    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
