import os
import logging
import urllib.parse
import mimetypes
import http.cookies
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from threading import Lock
import time
import shutil
import cgi
import json

# Configuration
CONFIG = {
    'UPLOAD_DIR': 'files',
    'STATIC_DIR': 'static',
    'PORT': 8000,
    'SESSION_TIMEOUT': 360
}

# Valid credentials
VALID_CREDENTIALS = {"admin": "admin"}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='server.log'
)
logger = logging.getLogger(__name__)

# Thread-safe file operations
file_lock = Lock()

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
    pass

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def is_authenticated(self):
        """Check if the user is authenticated via cookies."""
        if "Cookie" in self.headers:
            cookies = http.cookies.SimpleCookie(self.headers["Cookie"])
            session = cookies.get("session")
            if session and session.value == "authenticated":
                #timestamp = cookies.get("timestamp") # commented timeout check
                #if timestamp and (time.time() - float(timestamp.value)) < CONFIG['SESSION_TIMEOUT']:
                    return True
        return False

    def do_GET(self):
        """Handle GET requests, redirect to login if unauthorized."""
        if self.path in ["/", "/upload"] and not self.is_authenticated():
            self.send_response(302)
            self.send_header("Location", "/static/login.html")
            self.end_headers()
            return
        
        if self.path == "/":
            self.list_files()
        elif self.path == "/upload":
            self.show_upload_form()
        elif self.path.startswith("/files/"):
            self.serve_file()
        elif self.path.startswith("/static/"):
            self.serve_static()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """Handle POST requests."""
        if self.path == "/login":
            self.handle_login()
        elif not self.is_authenticated():
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Forbidden")
        elif self.path == "/upload":
            self.upload_file()
        elif self.path.startswith("/delete/"):
            self.delete_file()
        else:
            self.send_response(404)
            self.end_headers()

    def handle_login(self):
        """Process login requests."""
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode()
        params = urllib.parse.parse_qs(post_data)

        username = params.get("username", [""])[0]
        password = params.get("password", [""])[0]

        if username in VALID_CREDENTIALS and VALID_CREDENTIALS[username] == password:
            self.send_response(302)
            self.send_header("Set-Cookie", "session=authenticated; Path=/; HttpOnly")
            self.send_header("Set-Cookie", f"timestamp={time.time()}; Path=/; HttpOnly")
            self.send_header("Location", "/")
            self.end_headers()
        else:
            self.send_response(302)
            self.send_header("Location", "/static/login.html")
            self.end_headers()

    def list_files(self):
        with file_lock:
            if not os.path.exists(CONFIG['UPLOAD_DIR']):
                os.makedirs(CONFIG['UPLOAD_DIR'])
            files = os.listdir(CONFIG['UPLOAD_DIR'])
        
        file_list = ''.join(
            f'<li><a href="/files/{urllib.parse.quote(file)}">{file}</a> '
            f'<form style="display:inline;" action="/delete/{urllib.parse.quote(file)}" method="post">'
            f'<button type="submit" class="delete-button">Delete</button></form></li>'
            for file in files
        )
        
        with open(os.path.join(CONFIG['STATIC_DIR'], 'index.html'), 'r') as file:
            content = file.read().replace("{file_list}", file_list or "<li>No files available</li>")
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(content.encode())

    def show_upload_form(self):
        with open(os.path.join(CONFIG['STATIC_DIR'], 'upload.html'), 'r') as file:
            content = file.read()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(content.encode())

    def serve_file(self):
        """Serve a file while resetting session timer periodically."""
        filepath = os.path.join(CONFIG['UPLOAD_DIR'], urllib.parse.unquote(self.path[7:]))
        
        if os.path.isfile(filepath):
            self.send_response(200)
            mime_type, _ = mimetypes.guess_type(filepath)
            file_size = os.path.getsize(filepath)

            self.send_header('Content-Type', mime_type or 'application/octet-stream')
            self.send_header('Content-Length', str(file_size))
            self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(filepath)}"')
            self.end_headers()

            chunk_size = 1024 * 64  # 64KB chunks

            with open(filepath, 'rb') as file:
                while chunk := file.read(chunk_size):
                    self.wfile.write(chunk)
                    self.wfile.flush()
                    
        else:
            self.send_response(404)
            self.end_headers()

    def upload_file(self):
        content_length = int(self.headers.get('Content-Length', 0))
        
        content_type, pdict = cgi.parse_header(self.headers['Content-Type'])
        if content_type != 'multipart/form-data':
            self.send_error_response(400, "Invalid form data")
            return

        pdict['boundary'] = bytes(pdict['boundary'], 'utf-8')
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': self.headers['Content-Type']}
        )

        if 'file' not in form:
            self.send_error_response(400, "No file uploaded")
            return

        file_item = form['file']
        filename = os.path.basename(file_item.filename)
        if not filename:
            self.send_error_response(400, "Invalid filename")
            return

        filepath = os.path.join(CONFIG['UPLOAD_DIR'], filename)
        with file_lock:
            if os.path.exists(filepath):
                filepath = os.path.join(CONFIG['UPLOAD_DIR'], f"{int(time.time())}_{filename}")

            with open(filepath, 'wb') as f:
                shutil.copyfileobj(file_item.file, f)

        # Send JSON response instead of a redirect
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response = {"success": True, "message": "Upload successful", "filename": filename}
        self.wfile.write(json.dumps(response).encode())
        
    def delete_file(self):
        filepath = os.path.join(CONFIG['UPLOAD_DIR'], urllib.parse.unquote(self.path[8:]))
        with file_lock:
            if os.path.isfile(filepath):
                os.remove(filepath)
                self.send_response(302)
                self.send_header('Location', '/')
                self.end_headers()
            else:
                self.send_error_response(404, "File not found")
                
    def serve_static(self):
        filepath = os.path.join(CONFIG['STATIC_DIR'], self.path[len('/static/'):])
        if os.path.isfile(filepath):
            self.send_response(200)
            mime_type, _ = mimetypes.guess_type(filepath)
            self.send_header('Content-Type', mime_type or 'text/plain')
            self.end_headers()
            with open(filepath, 'rb') as file:
                self.wfile.write(file.read())
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    for dir_name in [CONFIG['UPLOAD_DIR'], CONFIG['STATIC_DIR']]:
        os.makedirs(dir_name, exist_ok=True)
    
    server_address = ('', CONFIG['PORT'])
    httpd = ThreadingHTTPServer(server_address, SimpleHTTPRequestHandler)
    logger.info(f"Starting server on port {CONFIG['PORT']}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
        httpd.server_close()
