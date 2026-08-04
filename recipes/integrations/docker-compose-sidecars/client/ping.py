"""Ping the compose stack from the Code Editor.

Run this after `bash scripts/bootstrap.sh`. It resolves svc-a and svc-b by
their Docker network DNS names, which only works because the Code Editor
container was joined to agents-net by scripts/attach-editor.sh.
"""
import json
import sys
import urllib.request

TARGETS = ["http://svc-a:8080/", "http://svc-b:8080/"]


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
