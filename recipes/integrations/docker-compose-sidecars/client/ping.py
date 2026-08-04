"""Ping the compose stack from the Code Editor.

Run this after `bash scripts/bootstrap.sh`. Inside a SageMaker AI Studio
space every container shares one network namespace with the editor, so
services are addressed via 127.0.0.1 on distinct ports rather than by
container DNS name.
"""
import json
import sys
import urllib.request

TARGETS = ["http://127.0.0.1:8080/", "http://127.0.0.1:8081/"]


def get(url: str) -> None:
    print(f"--> GET {url}")
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            print(json.dumps(json.loads(r.read().decode()), indent=2))
    except Exception as e:
        print(f"    ERROR: {e}", file=sys.stderr)
    print()


if __name__ == "__main__":
    for t in TARGETS:
        get(t)
