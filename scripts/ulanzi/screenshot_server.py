#!/usr/bin/env python3
"""
EMSN 2.0 - Ulanzi Screenshot Server

Simple HTTP server to serve screenshots from NAS share.
Runs on port 8082.
"""

import http.server
import socketserver
import os
from pathlib import Path

PORT = 8082
SCREENSHOT_DIR = Path("/mnt/nas-reports/ulanzi-screenshots")

class ScreenshotHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SCREENSHOT_DIR), **kwargs)

    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

if __name__ == "__main__":
    os.chdir(SCREENSHOT_DIR)

    with socketserver.TCPServer(("", PORT), ScreenshotHandler) as httpd:
        print(f"Screenshot server running on port {PORT}")
        print(f"Serving files from {SCREENSHOT_DIR}")
        httpd.serve_forever()
