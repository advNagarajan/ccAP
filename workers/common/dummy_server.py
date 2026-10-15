import http.server
import os
import threading
import logging

logger = logging.getLogger("dummy_health_server")

class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_POST(self):
        self.do_GET()

    def log_message(self, format, *args):
        # Suppress standard logging to prevent request spam in logs
        pass

_server_started = False

def start_dummy_server():
    global _server_started
    if _server_started:
        return
    _server_started = True

    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting dummy HTTP health server on port {port} for Cloud Run readiness...")
    
    def run_server():
        try:
            server = http.server.HTTPServer(("0.0.0.0", port), HealthCheckHandler)
            server.serve_forever()
        except Exception as e:
            logger.error(f"Failed to run dummy health server: {e}")

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
