#!/usr/bin/env python3
"""
EMSN 2.0 - Ulanzi Screenshot Server

HTTP server to serve screenshots from NAS share.
Runs on port 8082.

Endpoints:
- /latest - Laatste screenshot (voor Grafana live preview)
- /latest.json - Info over laatste screenshot als JSON
- /live - Live screenshot direct van Ulanzi (niet gecached)
- /* - Statische files uit screenshot directory
"""

import http.server
import socketserver
import os
import json
import urllib.request
from pathlib import Path
from datetime import datetime
from PIL import Image
import io

PORT = 8082
SCREENSHOT_DIR = Path("/mnt/nas-reports/ulanzi-screenshots")
ULANZI_IP = "192.168.1.11"
MATRIX_WIDTH = 32
MATRIX_HEIGHT = 8
SCALE_FACTOR = 10


def get_latest_screenshot():
    """Vind de meest recente screenshot."""
    latest_file = None
    latest_time = None

    for date_dir in sorted(SCREENSHOT_DIR.iterdir(), reverse=True):
        if date_dir.is_dir() and date_dir.name.startswith('20'):
            for f in sorted(date_dir.iterdir(), reverse=True):
                if f.suffix == '.png':
                    return f

    # Check root directory ook
    for f in sorted(SCREENSHOT_DIR.iterdir(), reverse=True):
        if f.is_file() and f.suffix == '.png':
            return f

    return None


def capture_live_screenshot():
    """Maak live screenshot van Ulanzi display."""
    try:
        url = f"http://{ULANZI_IP}/api/screen"
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())

        # Converteer RGB array naar image
        img = Image.new('RGB', (MATRIX_WIDTH, MATRIX_HEIGHT))
        pixels = img.load()

        for i, color in enumerate(data):
            x = i % MATRIX_WIDTH
            y = i // MATRIX_WIDTH
            r = (color >> 16) & 0xFF
            g = (color >> 8) & 0xFF
            b = color & 0xFF
            pixels[x, y] = (r, g, b)

        # Schaal op voor leesbaarheid
        img = img.resize(
            (MATRIX_WIDTH * SCALE_FACTOR, MATRIX_HEIGHT * SCALE_FACTOR),
            Image.NEAREST
        )

        # Converteer naar PNG bytes
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        return img_buffer.getvalue()

    except Exception as e:
        print(f"Live screenshot error: {e}")
        return None


class ScreenshotHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SCREENSHOT_DIR), **kwargs)

    def end_headers(self):
        # Add CORS headers en cache control
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

    def do_GET(self):
        if self.path == '/latest' or self.path == '/latest.png':
            # Serveer laatste screenshot
            latest = get_latest_screenshot()
            if latest:
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header('X-Screenshot-File', latest.name)
                self.end_headers()
                with open(latest, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "No screenshots found")
            return

        elif self.path == '/latest.json':
            # JSON info over laatste screenshot
            latest = get_latest_screenshot()
            if latest:
                # Parse filename voor info (format: HHMMSS_Soort.png)
                name = latest.stem
                parts = name.split('_', 1)
                time_str = parts[0] if len(parts) > 0 else ""
                species = parts[1] if len(parts) > 1 else ""

                info = {
                    'filename': latest.name,
                    'path': str(latest.relative_to(SCREENSHOT_DIR)),
                    'species': species,
                    'time': f"{time_str[:2]}:{time_str[2:4]}:{time_str[4:]}" if len(time_str) == 6 else time_str,
                    'date': latest.parent.name if latest.parent != SCREENSHOT_DIR else 'unknown',
                    'url': f"http://192.168.1.178:{PORT}/{latest.relative_to(SCREENSHOT_DIR)}",
                    'timestamp': datetime.fromtimestamp(latest.stat().st_mtime).isoformat()
                }

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(info, indent=2).encode())
            else:
                self.send_error(404, "No screenshots found")
            return

        elif self.path == '/live' or self.path == '/live.png':
            # Live screenshot direct van Ulanzi
            img_data = capture_live_screenshot()
            if img_data:
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header('X-Screenshot-Type', 'live')
                self.end_headers()
                self.wfile.write(img_data)
            else:
                self.send_error(503, "Could not capture live screenshot")
            return

        elif self.path == '/status':
            # Server status
            latest = get_latest_screenshot()

            # Tel screenshots
            total_screenshots = 0
            for date_dir in SCREENSHOT_DIR.iterdir():
                if date_dir.is_dir() and date_dir.name.startswith('20'):
                    total_screenshots += len(list(date_dir.glob('*.png')))

            status = {
                'server': 'EMSN Ulanzi Screenshot Server',
                'port': PORT,
                'screenshot_dir': str(SCREENSHOT_DIR),
                'total_screenshots': total_screenshots,
                'latest_screenshot': latest.name if latest else None,
                'ulanzi_ip': ULANZI_IP,
                'endpoints': ['/latest', '/latest.json', '/live', '/status']
            }

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(status, indent=2).encode())
            return

        # Default: serve static files
        super().do_GET()


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    os.chdir(SCREENSHOT_DIR)

    with ReusableTCPServer(("", PORT), ScreenshotHandler) as httpd:
        print(f"Screenshot server running on port {PORT}")
        print(f"Serving files from {SCREENSHOT_DIR}")
        print(f"Endpoints: /latest, /latest.json, /live, /status")
        httpd.serve_forever()
