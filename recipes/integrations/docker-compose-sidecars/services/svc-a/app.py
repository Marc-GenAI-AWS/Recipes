import json
import os
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("SVC_PORT", "8080"))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = {
            "service": "svc-a",
            "hostname": socket.gethostname(),
            "port": PORT,
            "hello": "world",
        }
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print("svc-a %s - %s" % (self.address_string(), format % args), flush=True)


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
