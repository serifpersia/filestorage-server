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
from datetime import datetime

# Configuration file path
CONFIG_FILE = "config.json"

# Default configuration
DEFAULT_CONFIG = {
    'UPLOAD_DIR': 'files',
    'STATIC_DIR': 'static',
    'PORT': 8000,
    'SESSION_TIMEOUT': 60  # in seconds
}

# Global configuration and session storage
CONFIG = {}
SESSIONS = {}  # Store session data with timestamps
sessions_lock = Lock()  # Lock for thread-safe session operations

# Setup logging to terminal with detailed format
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - ClientIP: %(client_ip)s - SessionID: %(session_id)s - %(message)s'
)

# Add extra fields to logger for client IP and session ID
class ContextFilter(logging.Filter):
    def filter(self, record):
        record.client_ip = getattr(record, 'client_ip', 'N/A')
        record.session_id = getattr(record, 'session_id', 'N/A')
        return True

logger.addFilter(ContextFilter())

# Thread-safe file operations
file_lock = Lock()

def load_or_create_config():
    """Load config from file or create a new one if it doesn't exist."""
    global CONFIG

    if os.path.exists(CONFIG_FILE):
        logger.info(f"Loading configuration from {CONFIG_FILE}...", extra={'client_ip': 'N/A', 'session_id': 'N/A'})
        try:
            with open(CONFIG_FILE, 'r') as f:
                CONFIG = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}", extra={'client_ip': 'N/A', 'session_id': 'N/A'})
            exit(1)
    else:
        logger.info("Configuration file not found. Creating a new one...", extra={'client_ip': 'N/A', 'session_id': 'N/A'})
        CONFIG = DEFAULT_CONFIG.copy()
        while True:
            username = input("Enter admin username: ").strip()
            password = input("Enter admin password: ").strip()
            port = input(f"Enter server port (default: {DEFAULT_CONFIG['PORT']}): ").strip() or DEFAULT_CONFIG['PORT']
            session_timeout = input(f"Enter session timeout in seconds (default: {DEFAULT_CONFIG['SESSION_TIMEOUT']}): ").strip() or DEFAULT_CONFIG['SESSION_TIMEOUT']

            if not username or not password:
                print("Username and password cannot be empty. Please try again.")
                continue

            try:
                port = int(port)
                session_timeout = int(session_timeout)
                break
            except ValueError:
                print("Port and session timeout must be valid integers. Please try again.")

        CONFIG.update({
            'PORT': port,
            'SESSION_TIMEOUT': session_timeout,
            'VALID_CREDENTIALS': {username: password}
        })

        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(CONFIG, f, indent=4)
            logger.info(f"Configuration saved to {CONFIG_FILE}.", extra={'client_ip': 'N/A', 'session_id': 'N/A'})
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}", extra={'client_ip': 'N/A', 'session_id': 'N/A'})
            exit(1)

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
    pass

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        """Override default logging to suppress unwanted messages."""
        pass  # Disable default HTTP logging; we'll use our custom logging

    def get_session_id(self):
        """Helper method to get session ID from cookies."""
        if "Cookie" in self.headers:
            cookies = http.cookies.SimpleCookie(self.headers["Cookie"])
            return cookies.get("session_id")
        return None

    def update_session_activity(self, session_id):
        """Update session last activity timestamp."""
        with sessions_lock:
            if session_id in SESSIONS:
                SESSIONS[session_id]['last_activity'] = time.time()

    def is_authenticated(self):
        """Check if the user is authenticated and session is still valid."""
        session_id = self.get_session_id()
        client_ip = self.client_address[0]
        if not session_id:
            return False
            
        with sessions_lock:
            if session_id.value not in SESSIONS:
                return False
                
            last_activity = SESSIONS[session_id.value]['last_activity']
            current_time = time.time()
            if (current_time - last_activity) > CONFIG['SESSION_TIMEOUT']:
                username = SESSIONS[session_id.value]['username']
                logger.info(f"Session expired due to inactivity for user {username}", extra={'client_ip': client_ip, 'session_id': session_id.value})
                del SESSIONS[session_id.value]
                return False
                
            return True

    def do_GET(self):
        """Handle GET requests."""
        session_id = self.get_session_id()
        client_ip = self.client_address[0]
        logger.info(f"Client connected, requesting: {self.path}", extra={'client_ip': client_ip, 'session_id': session_id.value if session_id else 'N/A'})

        if self.path in ["/", "/upload"] and not self.is_authenticated():
            logger.info("Redirecting unauthenticated client to login", extra={'client_ip': client_ip, 'session_id': 'N/A'})
            self.send_response(302)
            self.send_header("Location", "/static/login.html")
            self.send_header("Set-Cookie", "session_id=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT")
            self.end_headers()
            return
        
        if self.path == "/":
            logger.info("Serving index page", extra={'client_ip': client_ip, 'session_id': session_id.value})
            self.serve_index()
        elif self.path == "/api/files":
            logger.info("Serving file list", extra={'client_ip': client_ip, 'session_id': session_id.value})
            self.list_files()
        elif self.path == "/upload":
            logger.info("Serving upload form", extra={'client_ip': client_ip, 'session_id': session_id.value})
            self.show_upload_form()
        elif self.path.startswith("/files/"):
            self.serve_file()
        elif self.path.startswith("/static/"):
            logger.info(f"Serving static file: {self.path}", extra={'client_ip': client_ip, 'session_id': session_id.value if session_id else 'N/A'})
            self.serve_static()
        else:
            logger.info(f"404 - Page not found: {self.path}", extra={'client_ip': client_ip, 'session_id': session_id.value if session_id else 'N/A'})
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """Handle POST requests."""
        session_id = self.get_session_id()
        client_ip = self.client_address[0]
        logger.info(f"Client sent POST request to: {self.path}", extra={'client_ip': client_ip, 'session_id': session_id.value if session_id else 'N/A'})

        if self.path == "/login":
            self.handle_login()
        elif not self.is_authenticated():
            logger.info("Redirecting unauthenticated client to login", extra={'client_ip': client_ip, 'session_id': 'N/A'})
            self.send_response(302)
            self.send_header("Location", "/static/login.html")
            self.send_header("Set-Cookie", "session_id=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT")
            self.end_headers()
        elif self.path == "/logout":
            self.handle_logout()
        elif self.path == "/upload":
            self.upload_file()
        elif self.path.startswith("/delete/"):
            self.delete_file()
        elif self.path.startswith("/rename/"):
            self.rename_file()
        else:
            logger.info(f"404 - POST endpoint not found: {self.path}", extra={'client_ip': client_ip, 'session_id': session_id.value if session_id else 'N/A'})
            self.send_response(404)
            self.end_headers()

    def handle_login(self):
        """Process login requests and create session."""
        client_ip = self.client_address[0]
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode()
        params = urllib.parse.parse_qs(post_data)

        username = params.get("username", [""])[0]
        password = params.get("password", [""])[0]

        if username in CONFIG['VALID_CREDENTIALS'] and CONFIG['VALID_CREDENTIALS'][username] == password:
            session_id = str(time.time()) + str(id(self))
            with sessions_lock:
                SESSIONS[session_id] = {
                    'last_activity': time.time(),
                    'username': username
                }
            logger.info(f"Client logged in as {username}", extra={'client_ip': client_ip, 'session_id': session_id})
            self.send_response(302)
            self.send_header("Set-Cookie", f"session_id={session_id}; Path=/; HttpOnly")
            self.send_header("Location", "/")
            self.end_headers()
        else:
            logger.warning("Login failed - invalid credentials", extra={'client_ip': client_ip, 'session_id': 'N/A'})
            self.send_response(302)
            self.send_header("Location", "/static/login.html")
            self.end_headers()

    def handle_logout(self):
        """Handle logout and remove session."""
        session_id = self.get_session_id()
        client_ip = self.client_address[0]
        if session_id and session_id.value in SESSIONS:
            with sessions_lock:
                username = SESSIONS[session_id.value]['username']
                del SESSIONS[session_id.value]
            logger.info(f"Client logged out manually (username: {username})", extra={'client_ip': client_ip, 'session_id': session_id.value})
        
        self.send_response(302)
        self.send_header("Set-Cookie", "session_id=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT")
        self.send_header("Location", "/static/login.html")
        self.end_headers()

    def serve_index(self):
        """Serve the index.html file."""
        with open(os.path.join(CONFIG['STATIC_DIR'], 'index.html'), 'r', encoding='utf-8') as file:
            content = file.read()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))

    def list_files(self):
        """Return JSON list of files."""
        with file_lock:
            if not os.path.exists(CONFIG['UPLOAD_DIR']):
                os.makedirs(CONFIG['UPLOAD_DIR'])
            files = []
            for filename in os.listdir(CONFIG['UPLOAD_DIR']):
                filepath = os.path.join(CONFIG['UPLOAD_DIR'], filename)
                if os.path.isfile(filepath):
                    file_size = os.path.getsize(filepath)
                    modified_time = os.path.getmtime(filepath)
                    modified_date = datetime.fromtimestamp(modified_time).strftime('%Y-%m-%d %H:%M:%S')
                    files.append({
                        'name': filename,
                        'size': file_size,
                        'modified': modified_date
                    })
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'files': files}).encode())

    def show_upload_form(self):
        """Serve the upload form."""
        with open(os.path.join(CONFIG['STATIC_DIR'], 'upload.html'), 'r', encoding='utf-8') as file:
            content = file.read()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))

    def serve_file(self):
        """Serve requested file for download and keep session active."""
        session_id = self.get_session_id()
        client_ip = self.client_address[0]
        if not session_id or session_id.value not in SESSIONS:
            logger.warning("Unauthorized file access attempt", extra={'client_ip': client_ip, 'session_id': 'N/A'})
            self.send_response(403)
            self.end_headers()
            return

        filepath = os.path.join(CONFIG['UPLOAD_DIR'], urllib.parse.unquote(self.path[7:]))
        filename = os.path.basename(filepath)
        
        if os.path.isfile(filepath):
            logger.info(f"Client started downloading file: {filename}", extra={'client_ip': client_ip, 'session_id': session_id.value})
            self.send_response(200)
            mime_type, _ = mimetypes.guess_type(filepath)
            file_size = os.path.getsize(filepath)

            self.send_header('Content-Type', mime_type or 'application/octet-stream')
            self.send_header('Content-Length', str(file_size))
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.end_headers()

            chunk_size = 1024 * 64
            bytes_served = 0
            with open(filepath, 'rb') as file:
                while chunk := file.read(chunk_size):
                    self.wfile.write(chunk)
                    self.wfile.flush()
                    bytes_served += len(chunk)
                    logger.info(f"Serving {filename}: {bytes_served}/{file_size} bytes", extra={'client_ip': client_ip, 'session_id': session_id.value})
                    self.update_session_activity(session_id.value)  # Update session during download
            
            logger.info(f"Client finished downloading file: {filename}", extra={'client_ip': client_ip, 'session_id': session_id.value})
            self.update_session_activity(session_id.value)  # Final update after download
        else:
            logger.warning(f"File not found: {filename}", extra={'client_ip': client_ip, 'session_id': session_id.value})
            self.send_response(404)
            self.end_headers()

    def upload_file(self):
        """Handle file uploads and keep session active."""
        session_id = self.get_session_id()
        client_ip = self.client_address[0]
        if not session_id or session_id.value not in SESSIONS:
            logger.warning("Unauthorized upload attempt", extra={'client_ip': client_ip, 'session_id': 'N/A'})
            self.send_response(403)
            self.end_headers()
            return

        content_length = int(self.headers.get('Content-Length', 0))
        content_type, pdict = cgi.parse_header(self.headers['Content-Type'])
        if content_type != 'multipart/form-data':
            logger.error("Invalid form data for upload", extra={'client_ip': client_ip, 'session_id': session_id.value})
            self.send_error_response(400, "Invalid form data")
            return

        pdict['boundary'] = bytes(pdict['boundary'], 'utf-8')
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': self.headers['Content-Type']}
        )

        if 'file' not in form:
            logger.error("No file uploaded", extra={'client_ip': client_ip, 'session_id': session_id.value})
            self.send_error_response(400, "No file uploaded")
            return

        file_item = form['file']
        filename = os.path.basename(file_item.filename)
        if not filename:
            logger.error("Invalid filename for upload", extra={'client_ip': client_ip, 'session_id': session_id.value})
            self.send_error_response(400, "Invalid filename")
            return

        filepath = os.path.join(CONFIG['UPLOAD_DIR'], filename)
        with file_lock:
            if os.path.exists(filepath):
                filepath = os.path.join(CONFIG['UPLOAD_DIR'], f"{int(time.time())}_{filename}")

            logger.info(f"Client started uploading file: {filename}", extra={'client_ip': client_ip, 'session_id': session_id.value})
            chunk_size = 1024 * 64
            bytes_written = 0
            with open(filepath, 'wb') as f:
                while True:
                    chunk = file_item.file.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    f.flush()
                    bytes_written += len(chunk)
                    logger.info(f"Uploading {filename}: {bytes_written} bytes", extra={'client_ip': client_ip, 'session_id': session_id.value})
                    self.update_session_activity(session_id.value)  # Update session during upload

        logger.info(f"Client finished uploading file: {filename}", extra={'client_ip': client_ip, 'session_id': session_id.value})
        self.update_session_activity(session_id.value)  # Final update after upload

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response = {"success": True, "message": "Upload successful", "filename": filename}
        self.wfile.write(json.dumps(response).encode())

    def delete_file(self):
        """Handle file deletion."""
        session_id = self.get_session_id()
        client_ip = self.client_address[0]
        filepath = os.path.join(CONFIG['UPLOAD_DIR'], urllib.parse.unquote(self.path[8:]))
        filename = os.path.basename(filepath)
        with file_lock:
            if os.path.isfile(filepath):
                os.remove(filepath)
                logger.info(f"File deleted: {filename}", extra={'client_ip': client_ip, 'session_id': session_id.value})
                self.send_response(302)
                self.send_header('Location', '/')
                self.end_headers()
            else:
                logger.warning(f"File not found for deletion: {filename}", extra={'client_ip': client_ip, 'session_id': session_id.value})
                self.send_error_response(404, "File not found")

    def rename_file(self):
        """Handle file rename requests."""
        session_id = self.get_session_id()
        client_ip = self.client_address[0]
        old_filename = urllib.parse.unquote(self.path[8:])
        old_filepath = os.path.join(CONFIG['UPLOAD_DIR'], old_filename)

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        try:
            request_data = json.loads(body)
            new_filename = request_data.get('new_filename')
        except json.JSONDecodeError:
            logger.error("Invalid JSON for rename request", extra={'client_ip': client_ip, 'session_id': session_id.value})
            self.send_error_response(400, "Invalid JSON")
            return

        if not new_filename:
            logger.error("New filename is required for rename", extra={'client_ip': client_ip, 'session_id': session_id.value})
            self.send_error_response(400, "New filename is required")
            return

        new_filepath = os.path.join(CONFIG['UPLOAD_DIR'], new_filename)

        with file_lock:
            if not os.path.isfile(old_filepath):
                logger.warning(f"File not found for rename: {old_filename}", extra={'client_ip': client_ip, 'session_id': session_id.value})
                self.send_error_response(404, "File not found")
                return

            if os.path.exists(new_filepath):
                logger.error(f"File already exists: {new_filename}", extra={'client_ip': client_ip, 'session_id': session_id.value})
                self.send_error_response(409, "File already exists")
                return

            try:
                os.rename(old_filepath, new_filepath)
                logger.info(f"File renamed from {old_filename} to {new_filename}", extra={'client_ip': client_ip, 'session_id': session_id.value})
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "message": "File renamed successfully"}).encode('utf-8'))
            except Exception as e:
                logger.error(f"Error renaming file: {e}", extra={'client_ip': client_ip, 'session_id': session_id.value})
                self.send_error_response(500, "Failed to rename file")

    def serve_static(self):
        """Serve static files."""
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

    def send_error_response(self, status_code, message):
        """Send error response in JSON format."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())

if __name__ == '__main__':
    load_or_create_config()
    for dir_name in [CONFIG['UPLOAD_DIR'], CONFIG['STATIC_DIR']]:
        os.makedirs(dir_name, exist_ok=True)
    server_address = ('', CONFIG['PORT'])
    httpd = ThreadingHTTPServer(server_address, SimpleHTTPRequestHandler)
    logger.info(f"Server started on port {CONFIG['PORT']}", extra={'client_ip': 'N/A', 'session_id': 'N/A'})
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutting down...", extra={'client_ip': 'N/A', 'session_id': 'N/A'})
        httpd.server_close()