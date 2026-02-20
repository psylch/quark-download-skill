#!/usr/bin/env python3
"""Quark Search CLI — search, validate, detail, save cloud drive resources."""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

MAX_WORKERS = 6
HEALTH_CACHE = Path.home() / ".cache" / "quark-search" / "health.json"
HEALTH_TTL = 86400  # 24 hours

PANSOU_BASE = "https://s.panhunt.com/api"
QUARK_DRIVE = "https://drive-pc.quark.cn/1/clouddrive/share/sharepage"
QUARK_APP = "http://localhost:9128"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def log(msg):
    print(msg, file=sys.stderr)


def ok(data):
    json.dump({"ok": True, "data": data}, sys.stdout, ensure_ascii=False)
    print()


def fail(error, code="error"):
    json.dump({"ok": False, "error": error, "code": code}, sys.stdout, ensure_ascii=False)
    print()
    sys.exit(1)


def http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode()


def http_post_json(url, body, timeout=15):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"User-Agent": UA, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode()


def extract_pwd_id(s):
    """Extract pwd_id from a Quark share URL or return as-is if bare ID."""
    m = re.search(r"pan\.quark\.cn/s/([a-zA-Z0-9]+)", s)
    if m:
        return m.group(1)
    # bare ID: alphanumeric, reasonable length
    if re.fullmatch(r"[a-zA-Z0-9]{6,32}", s):
        return s
    return None


# ── Health / channels+plugins ──────────────────────────────────────────

def load_health_cache():
    if HEALTH_CACHE.exists():
        try:
            cached = json.loads(HEALTH_CACHE.read_text())
            if time.time() - cached.get("_ts", 0) < HEALTH_TTL:
                return cached
        except (json.JSONDecodeError, OSError):
            pass
    return None


def fetch_health():
    raw = http_get(f"{PANSOU_BASE}/health")
    data = json.loads(raw, strict=False)
    data["_ts"] = time.time()
    HEALTH_CACHE.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_CACHE.write_text(json.dumps(data, ensure_ascii=False))
    return data


def get_health(refresh=False):
    if not refresh:
        cached = load_health_cache()
        if cached:
            return cached
    return fetch_health()


# ── Validate ───────────────────────────────────────────────────────────

VALIDATE_CODES = {0: "valid", 41004: "expired", 41006: "not_exist"}


def validate_one(pwd_id):
    url = f"{QUARK_DRIVE}/token?pr=ucpro&fr=pc"
    try:
        raw = http_post_json(url, {"pwd_id": pwd_id, "passcode": ""})
        resp = json.loads(raw, strict=False)
        code = resp.get("code", -1)
        status = VALIDATE_CODES.get(code, "error")
        result = {"pwd_id": pwd_id, "status": status, "code": code}
        if code == 0:
            result["stoken"] = resp.get("data", {}).get("stoken", "")
        if resp.get("message"):
            result["message"] = resp["message"]
        return result
    except Exception as e:
        return {"pwd_id": pwd_id, "status": "error", "code": -1, "message": str(e)}


def validate_many(pwd_ids):
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {pool.submit(validate_one, pid): pid for pid in pwd_ids}
        for fut in as_completed(futs):
            results.append(fut.result())
    # preserve input order
    order = {pid: i for i, pid in enumerate(pwd_ids)}
    results.sort(key=lambda r: order.get(r["pwd_id"], 999))
    return results


# ── Detail ─────────────────────────────────────────────────────────────

def fetch_detail(pwd_id, stoken, pdir_fid="0", page=1, size=50):
    params = urllib.parse.urlencode({
        "pr": "ucpro", "fr": "pc",
        "pwd_id": pwd_id, "stoken": stoken,
        "pdir_fid": pdir_fid, "force": "0",
        "_page": str(page), "_size": str(size),
        "_sort": "file_type:asc,updated_at:desc",
    })
    url = f"{QUARK_DRIVE}/detail?{params}"
    raw = http_get(url)
    resp = json.loads(raw, strict=False)
    if resp.get("code", -1) != 0:
        return {"error": resp.get("message", "unknown error"), "code": resp.get("code")}

    items = []
    for f in resp.get("data", {}).get("list", []):
        item = {
            "file_name": f.get("file_name", ""),
            "size": f.get("size", 0),
            "dir": f.get("dir", False),
            "fid": f.get("fid", ""),
        }
        if f.get("dir"):
            item["include_items"] = f.get("include_items", 0)
        items.append(item)

    return {
        "pwd_id": pwd_id,
        "pdir_fid": pdir_fid,
        "total": resp.get("metadata", {}).get("_total", len(items)),
        "list": items,
    }


# ── Search ─────────────────────────────────────────────────────────────

def search_pansou(keyword, page=1, limit=30, channels_csv="", plugins_csv=""):
    params = urllib.parse.urlencode({
        "kw": keyword, "res": "merge", "src": "all",
        "channels": channels_csv, "plugins": plugins_csv,
        "page": str(page), "limit": str(limit),
    })
    url = f"{PANSOU_BASE}/search?{params}"
    raw = http_get(url, timeout=30)
    return json.loads(raw, strict=False)


def cmd_search(args):
    keyword = args.keyword
    top = args.top
    no_validate = args.no_validate
    page = args.page
    limit = args.limit

    # get channels/plugins
    log("Fetching health data...")
    health = get_health()
    channels_csv = ",".join(health.get("channels", []))
    plugins_csv = ",".join(health.get("plugins", []))

    log(f"Searching: {keyword}")
    resp = search_pansou(keyword, page=page, limit=limit,
                         channels_csv=channels_csv, plugins_csv=plugins_csv)

    if resp.get("code", -1) != 0:
        fail(f"PanSou error: {resp.get('message', 'unknown')}", "pansou_error")

    total = resp.get("data", {}).get("total", 0)
    if total == 0:
        ok({"keyword": keyword, "total": 0, "results": []})
        return

    merged = resp.get("data", {}).get("merged_by_type", {})
    # prioritize quark
    quark_items = merged.get("quark", [])

    if not quark_items:
        # report all types counts
        type_counts = {k: len(v) for k, v in merged.items() if v}
        ok({"keyword": keyword, "total": total, "quark_count": 0,
            "type_counts": type_counts, "results": []})
        return

    candidates = quark_items[:limit]
    log(f"Found {len(candidates)} quark results (total across types: {total})")

    # extract pwd_ids
    items_with_id = []
    for item in candidates:
        url = item.get("url", "")
        pid = extract_pwd_id(url)
        if pid:
            items_with_id.append((pid, item))

    if no_validate:
        results = []
        for pid, item in items_with_id[:top]:
            results.append({
                "pwd_id": pid,
                "url": item.get("url", ""),
                "note": item.get("note", ""),
                "source": item.get("source", ""),
                "datetime": item.get("datetime", ""),
            })
        ok({"keyword": keyword, "total": total, "results": results})
        return

    # validate in parallel
    all_pids = [pid for pid, _ in items_with_id]
    log(f"Validating {len(all_pids)} links...")
    val_results = validate_many(all_pids)
    val_map = {v["pwd_id"]: v for v in val_results}

    # collect valid ones, fetch details
    valid_items = []
    for pid, item in items_with_id:
        vr = val_map.get(pid, {})
        if vr.get("status") == "valid":
            valid_items.append((pid, item, vr.get("stoken", "")))

    log(f"{len(valid_items)} valid links")

    # fetch details in parallel for top N
    top_items = valid_items[:top]
    detail_map = {}
    if top_items:
        log(f"Fetching details for top {len(top_items)}...")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futs = {}
            for pid, item, stoken in top_items:
                futs[pool.submit(fetch_detail, pid, stoken)] = pid
            for fut in as_completed(futs):
                pid = futs[fut]
                try:
                    detail_map[pid] = fut.result()
                except Exception as e:
                    detail_map[pid] = {"error": str(e)}

    results = []
    for pid, item, stoken in top_items:
        entry = {
            "pwd_id": pid,
            "url": item.get("url", ""),
            "note": item.get("note", ""),
            "source": item.get("source", ""),
            "datetime": item.get("datetime", ""),
            "stoken": stoken,
            "detail": detail_map.get(pid, {}),
        }
        results.append(entry)

    ok({"keyword": keyword, "total": total, "valid_count": len(valid_items),
        "results": results})


# ── Save ───────────────────────────────────────────────────────────────

def cmd_save(args):
    pwd_id = extract_pwd_id(args.pwd_id)
    if not pwd_id:
        fail(f"Invalid pwd_id or URL: {args.pwd_id}", "invalid_id")

    # Method 1: desktop_share_visiting
    try:
        log("Trying desktop_share_visiting...")
        raw = http_get(f"{QUARK_APP}/desktop_share_visiting?pwd_id={pwd_id}", timeout=5)
        resp = json.loads(raw, strict=False)
        ok({"method": "desktop_share_visiting", "pwd_id": pwd_id, "response": resp})
        return
    except Exception as e:
        log(f"Method 1 failed: {e}")

    # Method 2: desktop_caller deeplink
    try:
        log("Trying desktop_caller deeplink...")
        share_url = f"https://pan.quark.cn/s/{pwd_id}"
        deeplink = "qkclouddrive://save?url=" + urllib.parse.quote(share_url, safe="")
        caller_url = f"{QUARK_APP}/desktop_caller?deeplink=" + urllib.parse.quote(deeplink, safe="")
        raw = http_get(caller_url, timeout=5)
        resp = json.loads(raw, strict=False)
        ok({"method": "desktop_caller", "pwd_id": pwd_id, "response": resp})
        return
    except Exception as e:
        log(f"Method 2 failed: {e}")

    # Method 3: fallback browser open
    browser_url = f"https://pan.quark.cn/s/{pwd_id}"
    ok({"method": "browser_fallback", "pwd_id": pwd_id, "url": browser_url,
        "message": "APP methods failed. Open this URL in browser."})


# ── Subcommand handlers ───────────────────────────────────────────────

def cmd_validate(args):
    pwd_ids = []
    for s in args.targets:
        pid = extract_pwd_id(s)
        if pid:
            pwd_ids.append(pid)
        else:
            log(f"Skipping invalid input: {s}")

    if not pwd_ids:
        fail("No valid pwd_ids provided", "no_input")

    log(f"Validating {len(pwd_ids)} link(s)...")
    results = validate_many(pwd_ids)
    ok({"results": results})


def cmd_detail(args):
    pwd_id = extract_pwd_id(args.pwd_id)
    if not pwd_id:
        fail(f"Invalid pwd_id: {args.pwd_id}", "invalid_id")

    stoken = args.stoken
    pdir_fid = args.fid or "0"

    log(f"Fetching detail for {pwd_id} (fid={pdir_fid})...")
    result = fetch_detail(pwd_id, stoken, pdir_fid=pdir_fid)

    if "error" in result:
        fail(result["error"], code=str(result.get("code", "error")))
    ok(result)


def cmd_check(args):
    try:
        raw = http_get(f"{QUARK_APP}/desktop_info", timeout=5)
        resp = json.loads(raw, strict=False)
        ok(resp)
    except urllib.error.URLError:
        fail("Quark APP not running (localhost:9128 refused)", "app_not_running")
    except Exception as e:
        fail(str(e), "check_error")


def cmd_health(args):
    refresh = args.refresh
    try:
        data = get_health(refresh=refresh)
        # remove internal timestamp from output
        out = {k: v for k, v in data.items() if not k.startswith("_")}
        ok(out)
    except Exception as e:
        fail(str(e), "health_error")


# ── Main ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Quark Search CLI")
    sub = parser.add_subparsers(dest="command")

    # search
    p_search = sub.add_parser("search", help="Search resources via PanSou")
    p_search.add_argument("keyword", help="Search keyword")
    p_search.add_argument("--top", type=int, default=5, help="Top N valid results to return")
    p_search.add_argument("--no-validate", action="store_true", help="Skip validation")
    p_search.add_argument("--limit", type=int, default=30, help="Results per page")
    p_search.add_argument("--page", type=int, default=1, help="Page number")

    # validate
    p_val = sub.add_parser("validate", help="Validate share links")
    p_val.add_argument("targets", nargs="+", help="pwd_id or share URL(s)")

    # detail
    p_det = sub.add_parser("detail", help="Get file listing for a share")
    p_det.add_argument("pwd_id", help="pwd_id or share URL")
    p_det.add_argument("--stoken", required=True, help="Share token from validate")
    p_det.add_argument("--fid", default=None, help="Folder fid for subfolder browsing")

    # save
    p_save = sub.add_parser("save", help="Trigger Quark APP to save a share")
    p_save.add_argument("pwd_id", help="pwd_id or share URL")

    # check
    sub.add_parser("check", help="Check Quark APP status")

    # health
    p_health = sub.add_parser("health", help="Show PanSou health/channels/plugins")
    p_health.add_argument("--refresh", action="store_true", help="Force refresh cache")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    handlers = {
        "search": cmd_search,
        "validate": cmd_validate,
        "detail": cmd_detail,
        "save": cmd_save,
        "check": cmd_check,
        "health": cmd_health,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
