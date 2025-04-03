import os
import json
import logging
import time
import shutil
from datetime import datetime, timedelta
from functools import wraps
import secrets # For generating secret key

from flask import (Flask, render_template, request, redirect, url_for, session,
                   send_from_directory, jsonify, flash, make_response)
from werkzeug.utils import secure_filename

# --- Configuration ---
CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    'UPLOAD_DIR': 'files',
    'STATIC_DIR': 'static', # Flask uses 'static' by default
    'PORT': 8000,
    'SESSION_TIMEOUT_MINUTES': 30, # Use minutes for session timeout
    'VALID_CREDENTIALS': {},
    'SECRET_KEY': '' # MUST be set for sessions
}
CONFIG = {}

# --- Flask App Initialization ---
app = Flask(__name__, template_folder='templates', static_folder='static')

# --- Logging Setup ---
# Configure Flask's logger
logging.basicConfig(level=logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - Client: %(client_ip)s - User: %(user)s - %(message)s')
handler.setFormatter(formatter)

# Add a filter to inject context
class ContextFilter(logging.Filter):
    def filter(self, record):
        record.client_ip = request.remote_addr if request else 'N/A'
        record.user = session.get('username', 'anonymous') if session else 'N/A'
        return True

app.logger.handlers.clear() # Remove default handlers
app.logger.addHandler(handler)
app.logger.addFilter(ContextFilter())
app.logger.setLevel(logging.INFO)

# --- Configuration Loading ---
def load_or_create_config():
    """Load config from file or create interactively."""
    global CONFIG
    if os.path.exists(CONFIG_FILE):
        app.logger.info(f"Loading configuration from {CONFIG_FILE}")
        try:
            with open(CONFIG_FILE, 'r') as f:
                CONFIG = json.load(f)
            # Ensure essential keys are present, merge with defaults
            for key, value in DEFAULT_CONFIG.items():
                CONFIG.setdefault(key, value)
        except Exception as e:
            app.logger.error(f"Failed to load configuration: {e}", exc_info=True)
            exit(1)
    else:
        app.logger.warning("Configuration file not found. Starting interactive setup...")
        CONFIG = DEFAULT_CONFIG.copy()
        while True:
            username = input("Enter admin username: ").strip()
            password = input("Enter admin password: ").strip()
            if not username or not password:
                print("Username and password cannot be empty. Please try again.")
                continue
            CONFIG['VALID_CREDENTIALS'][username] = password
            break

        port_str = input(f"Enter server port (default: {DEFAULT_CONFIG['PORT']}): ").strip()
        CONFIG['PORT'] = int(port_str) if port_str.isdigit() else DEFAULT_CONFIG['PORT']

        timeout_str = input(f"Enter session timeout in MINUTES (default: {DEFAULT_CONFIG['SESSION_TIMEOUT_MINUTES']}): ").strip()
        CONFIG['SESSION_TIMEOUT_MINUTES'] = int(timeout_str) if timeout_str.isdigit() else DEFAULT_CONFIG['SESSION_TIMEOUT_MINUTES']

        # Generate Secret Key
        CONFIG['SECRET_KEY'] = secrets.token_hex(24)
        app.logger.info(f"Generated new SECRET_KEY.")

        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(CONFIG, f, indent=4)
            app.logger.info(f"Configuration saved to {CONFIG_FILE}.")
        except Exception as e:
            app.logger.error(f"Failed to save configuration: {e}", exc_info=True)
            exit(1)

    # --- Apply Config to Flask App ---
    app.secret_key = CONFIG.get('SECRET_KEY')
    if not app.secret_key:
        app.logger.error("FATAL: SECRET_KEY is not set in config.json or generated. Sessions will not work.")
        exit(1)

    app.config['UPLOAD_FOLDER'] = os.path.abspath(CONFIG.get('UPLOAD_DIR', 'files'))
    app.permanent_session_lifetime = timedelta(minutes=CONFIG.get('SESSION_TIMEOUT_MINUTES', 30))

    # Create upload directory if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- Authentication Decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        # Optional: Implement activity-based timeout refresh here if desired,
        # but Flask's default permanent_session_lifetime usually suffices.
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        valid_creds = CONFIG.get('VALID_CREDENTIALS', {})

        if username in valid_creds and valid_creds[username] == password:
            session.permanent = True  # Use the configured timeout
            session['username'] = username
            app.logger.info(f"Login successful for user '{username}'")
            flash('Login successful!', 'success')
            next_url = request.args.get('next')
            return redirect(next_url or url_for('index'))
        else:
            app.logger.warning(f"Login failed for username '{username}'")
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('login'))

    # If GET request or login failed previously
    if 'username' in session:
        return redirect(url_for('index')) # Redirect if already logged in
    return render_template('login.html', current_year=datetime.now().year)


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    """Logs the user out."""
    username = session.pop('username', None)
    app.logger.info(f"User '{username}' logged out.")
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    """Serves the main file listing page."""
    return render_template('index.html', current_year=datetime.now().year)


@app.route('/upload', methods=['GET'])
@login_required
def upload_page():
    """Serves the file upload page."""
    return render_template('upload.html', current_year=datetime.now().year)


@app.route('/api/files', methods=['GET'])
@login_required
def list_files():
    """API endpoint to list files in the upload directory."""
    files = []
    upload_dir = app.config['UPLOAD_FOLDER']
    try:
        for filename in os.listdir(upload_dir):
            filepath = os.path.join(upload_dir, filename)
            if os.path.isfile(filepath):
                try:
                    file_size = os.path.getsize(filepath)
                    modified_time = os.path.getmtime(filepath)
                    modified_date = datetime.fromtimestamp(modified_time).strftime('%Y-%m-%d %H:%M:%S')
                    files.append({
                        'name': filename,
                        'size': file_size,
                        'modified': modified_date
                    })
                except OSError as e:
                     app.logger.error(f"Could not get info for file: {filepath} - {e}")

        # Sort files by name, case-insensitive
        files.sort(key=lambda x: x['name'].lower())

    except FileNotFoundError:
         app.logger.warning(f"Upload directory not found: {upload_dir}")
         # Directory should have been created at startup, but handle anyway
         os.makedirs(upload_dir, exist_ok=True)
    except Exception as e:
        app.logger.error(f"Error listing files: {e}", exc_info=True)
        return jsonify({"error": "Could not list files"}), 500

    return jsonify({'files': files})


@app.route('/files/<path:filename>')
@login_required
def download_file(filename):
    """Serves a file for download."""
    app.logger.info(f"Download requested for file: {filename}")
    try:
        # Ensure filename is safe and path traversal isn't possible
        # send_from_directory handles this well
        return send_from_directory(
            app.config['UPLOAD_FOLDER'],
            filename,
            as_attachment=True
        )
    except FileNotFoundError:
        app.logger.warning(f"Download failed: File not found - {filename}")
        flash(f"File '{filename}' not found.", 'danger')
        return redirect(url_for('index')), 404
    except Exception as e:
        app.logger.error(f"Error sending file {filename}: {e}", exc_info=True)
        flash(f"Error downloading file '{filename}'.", 'danger')
        return redirect(url_for('index')), 500


@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    """Handles file uploads."""
    if 'file' not in request.files:
        app.logger.warning("Upload attempt with no file part")
        return jsonify({"success": False, "error": "No file part in the request"}), 400

    file = request.files['file']
    if file.filename == '':
        app.logger.warning("Upload attempt with no selected file")
        return jsonify({"success": False, "error": "No selected file"}), 400

    if file:
        # Sanitize filename
        filename = secure_filename(file.filename)
        upload_dir = app.config['UPLOAD_FOLDER']
        filepath = os.path.join(upload_dir, filename)

        # Handle potential filename collisions (optional: add timestamp or counter)
        counter = 1
        base, ext = os.path.splitext(filename)
        while os.path.exists(filepath):
            filepath = os.path.join(upload_dir, f"{base}_{counter}{ext}")
            counter += 1
        final_filename = os.path.basename(filepath) # Get the potentially modified filename

        try:
            app.logger.info(f"Starting upload for: {file.filename} as {final_filename}")
            file.save(filepath)
            app.logger.info(f"File uploaded successfully: {final_filename}")
            # flash(f"File '{final_filename}' uploaded successfully!", 'success') # Flash might not be seen due to JS redirect
            return jsonify({"success": True, "message": f"File '{final_filename}' uploaded successfully!"}), 201
        except Exception as e:
            app.logger.error(f"Failed to save uploaded file {final_filename}: {e}", exc_info=True)
            return jsonify({"success": False, "error": "Failed to save file on server"}), 500

    return jsonify({"success": False, "error": "Unknown upload error"}), 500


@app.route('/delete/<path:filename>', methods=['POST'])
@login_required
def delete_file(filename):
    """Deletes a specified file."""
    # Sanitize filename just in case, though it comes from our list
    filename = secure_filename(filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    app.logger.info(f"Delete requested for file: {filename}")
    if os.path.isfile(filepath):
        try:
            os.remove(filepath)
            app.logger.info(f"File deleted successfully: {filename}")
            # flash(f"File '{filename}' deleted.", 'success') # JS handles UI update
            return jsonify({"success": True, "message": f"File '{filename}' deleted."}), 200
        except Exception as e:
            app.logger.error(f"Error deleting file {filename}: {e}", exc_info=True)
            return jsonify({"success": False, "error": f"Could not delete file '{filename}'."}), 500
    else:
        app.logger.warning(f"Delete failed: File not found - {filename}")
        return jsonify({"success": False, "error": f"File '{filename}' not found."}), 404


@app.route('/rename/<path:old_filename>', methods=['POST'])
@login_required
def rename_file(old_filename):
    """Renames a specified file."""
    data = request.get_json()
    if not data or 'new_filename' not in data:
        return jsonify({"success": False, "error": "Missing 'new_filename' in request"}), 400

    new_filename_raw = data['new_filename'].strip()
    if not new_filename_raw:
         return jsonify({"success": False, "error": "New filename cannot be empty"}), 400

    # Sanitize both filenames
    old_filename_safe = secure_filename(old_filename)
    new_filename_safe = secure_filename(new_filename_raw)

    if not new_filename_safe: # Check if sanitization resulted in empty string
        return jsonify({"success": False, "error": "Invalid new filename provided"}), 400

    old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], old_filename_safe)
    new_filepath = os.path.join(app.config['UPLOAD_FOLDER'], new_filename_safe)

    app.logger.info(f"Rename requested: '{old_filename_safe}' -> '{new_filename_safe}'")

    if not os.path.isfile(old_filepath):
        app.logger.warning(f"Rename failed: Source file not found - {old_filename_safe}")
        return jsonify({"success": False, "error": f"Original file '{old_filename_safe}' not found."}), 404

    if os.path.exists(new_filepath):
        app.logger.warning(f"Rename failed: Target file already exists - {new_filename_safe}")
        return jsonify({"success": False, "error": f"File '{new_filename_safe}' already exists."}), 409 # Conflict

    try:
        os.rename(old_filepath, new_filepath)
        app.logger.info(f"File renamed successfully: '{old_filename_safe}' -> '{new_filename_safe}'")
        return jsonify({"success": True, "message": "File renamed successfully."}), 200
    except Exception as e:
        app.logger.error(f"Error renaming file {old_filename_safe} to {new_filename_safe}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to rename file on server."}), 500


# --- Error Handlers ---
@app.errorhandler(404)
def page_not_found(e):
    app.logger.warning(f"404 Not Found: {request.path}")
    # You can render a custom 404 template
    # return render_template('404.html'), 404
    return jsonify({"error": "Not Found", "message": "The requested URL was not found on the server."}), 404

@app.errorhandler(500)
def internal_server_error(e):
    app.logger.error(f"500 Internal Server Error: {e}", exc_info=True)
    # return render_template('500.html'), 500
    return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred."}), 500

@app.errorhandler(405) # Method Not Allowed
def method_not_allowed(e):
    app.logger.warning(f"405 Method Not Allowed: {request.method} for {request.path}")
    return jsonify({"error": "Method Not Allowed", "message": "The method is not allowed for the requested URL."}), 405


# --- Main Execution ---
if __name__ == '__main__':
    load_or_create_config()
    port = CONFIG.get('PORT', 8000)
    app.logger.info(f"Starting Flask server on http://0.0.0.0:{port}")
    app.logger.info(f"Upload directory: {app.config['UPLOAD_FOLDER']}")
    app.logger.info(f"Session timeout: {app.permanent_session_lifetime}")
    # Use host='0.0.0.0' to make it accessible on your local network
    # Use debug=True only for development, NEVER in production
    app.run(host='0.0.0.0', port=port, debug=False) # Set debug=True for development reload & debugger