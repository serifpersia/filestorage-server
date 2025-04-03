![image](https://github.com/user-attachments/assets/7b43b33c-1ad6-4254-a285-8b3e2cb8589a)

# Flask FileStorage Server

A simple web-based file storage server built with Python and Flask. It allows users on a local network to easily upload, download, list, rename, and delete files through a web interface secured by basic authentication.

## Features

*   Web interface for file management (list, upload, download, rename, delete).
*   Basic username/password authentication.
*   Session management with configurable timeout.
*   Configuration via `config.json` (auto-generated on first run).
*   Designed for easy use on a trusted local network.
*   Includes helper scripts (`run.sh` for Linux, `run.bat` for Windows) for setup and execution.

## Requirements

**Common:**
*   **Python:** Version 3.9 or newer. Download from [python.org](https://www.python.org/downloads/). Ensure Python is added to your system's PATH during installation.

**Linux Specific:**
*   **Linux Package:** `python3.9-venv` (or the equivalent for your Python 3.9+ version, e.g., `python3.10-venv`, `python3.11-venv`). This is needed by the `run.sh` script to create a virtual environment.
    *   Install using: `sudo apt update && sudo apt install python3.9-venv` (Debian/Ubuntu example for Python 3.9).

**Windows Specific:**
*   Python's built-in `venv` module is typically included, so no separate package is usually needed if Python was installed correctly.

**Dependencies:**
*   Flask (installed via `pip` by the setup scripts).

## Setup and Running

**Linux**

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/serifpersia/filestorage-server.git
    cd filestorage-server
    ```

2.  **Make the script executable (if needed):**
    ```bash
    chmod +x run.sh
    ```

3.  **Run the setup and launch script:**
    This script handles checking prerequisites, creating the `venv` virtual environment, installing dependencies, and starting the server.
    ```bash
    ./run.sh
    ```

**Windows**

1.  **Clone the repository or download the files:**
    Use Git or download the source code ZIP and extract it.


2.  **Run the setup and launch script:**
    Double-click `run.bat` in File Explorer, or run it from the command line:
    ```cmd
    run.bat
    ```
---

**First Run Configuration (Both Linux and Windows)**

*   If `config.json` doesn't exist when you first run the script (`run.sh` or `run.bat`), you will be prompted in the terminal/console to set:
    *   Admin username
    *   Admin password
    *   Server port (defaults to 8000)
    *   Session timeout in minutes (defaults to 30)
*   A `config.json` file will be created. **Keep this file secure, especially the `SECRET_KEY`.**

**Stopping the Server (Both Linux and Windows)**

*   Press `Ctrl+C` in the terminal or command prompt window where the server is running.

## Accessing the Server

1.  Find the **local IP address** of the machine running the server.
    *   Linux: Use `ip addr` or `hostname -I`.
    *   Windows: Use `ipconfig` in Command Prompt. Look for the "IPv4 Address" under your active network adapter (Ethernet or Wi-Fi).
2.  Open a web browser on **any device on the same local network**.
3.  Navigate to `http://<your-server-ip>:<port>`.
    *   Replace `<your-server-ip>` with the actual IP address (e.g., `192.168.1.100`).
    *   Replace `<port>` with the port configured (default is 8000).
    *   Example: `http://192.168.1.100:8000`
4.  You can also access it from the server machine itself using `http://127.0.0.1:8000` or `http://localhost:8000`.
5.  Log in using the admin username and password you created.

## Usage

*   **Upload:** Click "Upload New File", select a file, and click "Upload".
*   **Download:** Click the filename in the list.
*   **Rename:** Click the "Rename" button next to a file, enter the new name, and confirm.
*   **Delete:** Click the "Delete" button next to a file and confirm the action.
*   **Refresh:** Click the "Refresh" button to update the file list.
*   **Logout:** Click the "Logout" button.

## Security Considerations for Local Use

*   **Network:** This server is intended for **trusted local networks**. Do not expose it directly to the internet without significant security hardening (HTTPS, reverse proxy, stronger authentication, firewall rules, etc.).
*   **Password:** Use a strong admin password.
*   **SECRET_KEY:** Protect the `SECRET_KEY` in `config.json`.
*   **File Uploads:** While `secure_filename` prevents basic path traversal, users can upload any *type* of file. Be mindful of this in your environment.

## License

MIT License - see [LICENSE](LICENSE) file.
