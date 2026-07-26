#!/usr/bin/env python3
"""Verify health and perform one minimal, real model request after deployment."""

import argparse
import json
import sys
import urllib.error
import urllib.request


def request(url: str, payload: dict | None = None) -> tuple[int, dict]:
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if body else {}
    req = urllib.request.Request(url, data=body, headers=headers, method="POST" if body else "GET")
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        try:
            data = json.loads(exc.read())
        except (json.JSONDecodeError, UnicodeDecodeError):
            data = {"detail": "Non-JSON error response"}
        return exc.code, data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url", nargs="?", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    health_status, health = request(f"{base_url}/health/ready")
    if health_status != 200:
        print(f"readiness failed ({health_status}): {health.get('detail', health)}", file=sys.stderr)
        return 1

    ask_status, result = request(
        f"{base_url}/ask",
        {"query": "Say hello in one short sentence.", "history": "", "email": "guest"},
    )
    if ask_status != 200 or not str(result.get("answer", "")).strip():
        print(f"model smoke test failed ({ask_status}): {result.get('detail', result)}", file=sys.stderr)
        return 1

    print("readiness: ok")
    print("model request: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
