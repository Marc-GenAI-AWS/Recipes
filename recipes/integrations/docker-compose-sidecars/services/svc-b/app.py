import json
import socket
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

PEER_URL = "http://svc-a:8080/"


def fetch_peer():
    try:
        with urllib.request.urlopen(PEER_URL, timeout=3) as r:
            return json.loads(r.read().decode())
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        return {"error": str(e)}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = {
            "service": "svc-b",
            "hostname": socket.gethostname(),
            "peer_url": PEER_URL,
            "peer_response": fetch_peer(),
        }
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print("svc-b %s - %s" % (self.address_string(), format % args), flush=True)


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
