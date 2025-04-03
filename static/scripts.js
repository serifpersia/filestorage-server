// static/scripts.js

document.addEventListener('DOMContentLoaded', () => {
    const refreshBtn = document.getElementById('refresh-btn');
    const uploadForm = document.getElementById('upload-form');
    const fileListContainer = document.getElementById('file-list'); // Changed variable name for clarity

    // Fetch initial file list if on the index page (where file-list exists)
    if (fileListContainer) {
        fetchFiles();
        // Attach refresh button listener only if it exists
        refreshBtn?.addEventListener('click', fetchFiles);
    }

    // Attach upload form listener only if it exists (on upload page)
    if (uploadForm) {
        uploadForm.addEventListener('submit', handleUpload);
    }

    // Drag and drop setup (if elements exist on the page, e.g., upload page)
    const uploadArea = document.getElementById('upload-area'); // Make sure this ID exists in upload.html if using drag/drop
    const fileInput = document.getElementById('file-input');
    if (uploadArea && fileInput) {
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                fileInput.files = e.dataTransfer.files;
                 // Optionally trigger upload or update display here
            }
        });
    }

    // --- Modal Handling ---
    // Rename Modal
    const renameModal = document.getElementById('rename-modal');
    const renameCloseButton = renameModal?.querySelector('.close-button');
    const renameConfirmBtn = document.getElementById('rename-confirm-btn');
    const newFilenameInput = document.getElementById('new-filename');

    // Function to open Rename Modal (called from dynamically added buttons)
    window.openRenameModal = (filename) => { // Make it globally accessible
        currentFilename = filename; // Use global 'currentFilename'
        if (newFilenameInput) newFilenameInput.value = filename;
        if (renameModal) renameModal.style.display = "flex"; // Use flex for centering
    };

    // Close Rename Modal via button
    renameCloseButton?.addEventListener('click', () => {
        if (renameModal) renameModal.style.display = "none";
    });

    // Confirm Rename action
    renameConfirmBtn?.addEventListener('click', () => {
        const newFilename = newFilenameInput?.value.trim();
        if (newFilename && newFilename !== currentFilename) {
            renameFile(currentFilename, newFilename);
            if (renameModal) renameModal.style.display = "none";
        } else if (!newFilename) {
            showPopup("Please enter a new filename.");
        } else {
            // Filename didn't change, just close modal
             if (renameModal) renameModal.style.display = "none";
        }
    });

    // Close modals if clicking outside the content area
    window.addEventListener('click', (event) => {
        if (event.target == renameModal) {
            renameModal.style.display = "none";
        }
        // Add similar logic for other modals if needed (e.g., progress modal if it's persistent)
    });

    // --- Auto-hide Flash Messages ---
    // Select all potential flash message containers/elements
    const flashMessages = document.querySelectorAll(
        '.flash-messages-container .alert, .flash-messages-local .alert, .login-container .flash-messages .alert'
    );

    const fadeOutDelay = 4000; // Time visible in milliseconds (e.g., 4 seconds)
    const transitionDuration = 600; // Match the LONGEST CSS transition duration (max-height, margin, padding)

    flashMessages.forEach((message) => {
        let fadeTimer;
        let removeTimer;

        // Function to start the fade-out process
        const startFadeOut = () => {
            // Clear any existing timers for this message to prevent duplicates
            clearTimeout(message.dataset.fadeTimer);
            clearTimeout(message.dataset.removeTimer);

            fadeTimer = setTimeout(() => {
                message.classList.add('fade-out'); // Add class to trigger CSS animation

                // Set timeout to remove the element after the CSS transition completes
                removeTimer = setTimeout(() => {
                    message.remove(); // Remove element from DOM
                }, transitionDuration);

                message.dataset.removeTimer = removeTimer; // Store timer ID

            }, fadeOutDelay);

             message.dataset.fadeTimer = fadeTimer; // Store timer ID
        };

        // Start the initial fade-out timer
        startFadeOut();

        // Optional: Pause fade-out on mouse hover
        message.addEventListener('mouseover', () => {
            clearTimeout(message.dataset.fadeTimer); // Clear the fade timer
            clearTimeout(message.dataset.removeTimer); // Clear the removal timer too
             // Optional: Slightly increase opacity to indicate pause?
             // message.style.opacity = '0.9';
        });

        // Optional: Resume fade-out on mouse leave
        message.addEventListener('mouseout', () => {
             // Only restart if it hasn't already started fading
             // Check if fade-out class is NOT present
             if (!message.classList.contains('fade-out')) {
                  startFadeOut(); // Simply restart the standard fade process
                  // message.style.opacity = ''; // Reset opacity if changed on hover
             }
        });
    });
	
}); // End DOMContentLoaded

// --- Global Variables ---
let currentFilename = null; // To store filename being renamed

// --- Core Functions ---

function fetchFiles() {
    const fileList = document.getElementById('file-list');
    if (!fileList) return; // Don't run if the list element doesn't exist

    fileList.innerHTML = '<li>Loading files...</li>'; // Loading indicator

    fetch('/api/files') // Flask API endpoint
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            fileList.innerHTML = ''; // Clear loading/previous content

            if (!data.files || data.files.length === 0) {
                fileList.innerHTML = '<li>No files available</li>';
                return;
            }

            data.files.forEach(file => {
                const li = document.createElement('li');
                const fileIcon = getFileIcon(file.name);

                // Encode filename for URL and data attributes
                const encodedFilename = encodeURIComponent(file.name);

                // Consider adding a wrapper for actions on smaller screens
                li.innerHTML = `
                    <span class="file-icon">${fileIcon}</span>
                    <a href="/files/${encodedFilename}" title="Download ${file.name}">${file.name}</a>
                    <div class="file-details">
                        <span class="file-size">${formatBytes(file.size)}</span>
                        <span class="file-modified">${file.modified}</span>
                    </div>
                    <div class="file-actions">
                         <button class="rename-button" onclick="openRenameModal('${file.name}')">Rename</button>
                         <button class="delete-button" onclick="deleteFile('${file.name}')">Delete</button>
                     </div>
                `;
                fileList.appendChild(li);
            });

            // Note: Event listeners are now added inline via onclick="" above
            // This is simpler for dynamically generated content, though less ideal
            // than event delegation if the list was extremely large.
        })
        .catch(error => {
            console.error('Error fetching files:', error);
            fileList.innerHTML = '<li>Error loading files. Please try refreshing.</li>';
            showPopup('Error loading files. Check console for details.');
        });
}

function getFileIcon(filename) {
    const extension = filename.slice((filename.lastIndexOf(".") - 1 >>> 0) + 2).toLowerCase();
    // Add more icons as needed
    switch (extension) {
        case 'pdf': return '📄'; // Document
        case 'doc': case 'docx': return '📝'; // Word Doc
        case 'xls': case 'xlsx': return '📊'; // Excel Sheet
        case 'ppt': case 'pptx': return ' présentation'; // PowerPoint (adjust icon)
        case 'jpg': case 'jpeg': case 'png': case 'gif': case 'bmp': case 'webp': case 'svg': return '🖼️'; // Image
        case 'mp4': case 'avi': case 'mov': case 'mkv': case 'webm': return '🎬'; // Video
        case 'mp3': case 'wav': case 'ogg': case 'flac': return '🎵'; // Audio
        case 'zip': case 'rar': case '7z': case 'tar': case 'gz': return '📦'; // Archive
        case 'txt': case 'md': return '📜'; // Text/Markdown
        case 'js': case 'css': case 'html': case 'py': case 'java': case 'c': case 'cpp': return '💻'; // Code
        case 'exe': case 'msi': return '⚙️'; // Executable
        default: return '📁'; // Generic File/Folder icon as default
    }
}


function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    // Ensure i is within the bounds of the sizes array
    const sizeIndex = Math.min(i, sizes.length - 1);
    return parseFloat((bytes / Math.pow(k, sizeIndex)).toFixed(dm)) + ' ' + sizes[sizeIndex];
}

function deleteFile(filename) {
    // Use the globally accessible showConfirmPopup
    showConfirmPopup(`Are you sure you want to delete "${filename}"?`, () => {
        fetch(`/delete/${encodeURIComponent(filename)}`, {
            method: 'POST'
            // No body needed for delete if using URL param
        })
        .then(response => response.json()) // Expect JSON response from Flask
        .then(data => {
             if (data.success) {
                fetchFiles(); // Refresh list on success
                showPopup(data.message || 'File deleted successfully.');
            } else {
                showPopup(`Failed to delete file: ${data.error || 'Unknown server error'}`);
            }
        })
        .catch(error => {
            console.error('Error deleting file:', error);
            showPopup('Error deleting file. Check network connection or console.');
        });
    });
}


function renameFile(oldFilename, newFilename) {
    fetch(`/rename/${encodeURIComponent(oldFilename)}`, { // Use Flask route
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
            // Include CSRF token header here if using Flask-WTF
        },
        body: JSON.stringify({ new_filename: newFilename })
    })
    .then(response => response.json()) // Expect JSON response
    .then(data => {
        if (data.success) {
            fetchFiles(); // Refresh list on success
            showPopup(data.message || "File renamed successfully.");
        } else {
            showPopup(`Failed to rename file: ${data.error || 'Unknown server error'}`);
        }
    })
    .catch(error => {
        console.error('Error renaming file:', error);
        showPopup('Error renaming file. Check network connection or console.');
    });
}


function handleUpload(e) {
    e.preventDefault(); // Prevent default form submission
    const fileInput = document.getElementById('file-input');
    const file = fileInput.files[0];

    if (!file) {
        showPopup("Please select a file to upload.");
        return;
    }

    const formData = new FormData();
    formData.append('file', file); // 'file' must match the name expected by Flask request.files

    const xhr = new XMLHttpRequest();
    const progressModal = document.getElementById('progress-modal');
    const progressFill = document.getElementById('progress-bar-fill');
    const progressText = document.getElementById('progress-text');

    // --- Progress Handling ---
    xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
            const percent = Math.round((e.loaded / e.total) * 100);
            if (progressFill) progressFill.style.width = `${percent}%`;
            if (progressText) progressText.textContent = `Uploading... ${percent}%`;
        } else {
             if (progressText) progressText.textContent = `Uploading...`; // Indeterminate
        }
    });

    // --- Completion Handling ---
    xhr.addEventListener('load', () => {
        // Hide progress bar slightly before showing popup/redirecting
        // setTimeout(() => {
        //      if (progressModal) progressModal.style.display = 'none';
        // }, 500); // Short delay

        console.log("Upload Response Status:", xhr.status);
        console.log("Upload Response Text:", xhr.responseText);

        let jsonResponse = {};
        try {
             // Check if response is not empty before parsing
            if (xhr.responseText) {
                 jsonResponse = JSON.parse(xhr.responseText);
            } else if (xhr.status >= 200 && xhr.status < 300) {
                // Handle empty success responses (like 201 Created often is)
                jsonResponse = { success: true, message: "Upload successful (empty response)." };
            } else {
                 // If response is empty and status indicates error
                 jsonResponse = { success: false, error: `Upload failed with status ${xhr.status} (empty response).` };
            }
        } catch (parseError) {
            console.error("Failed to parse upload response:", parseError);
            // If parsing fails, rely on status code
             if (xhr.status >= 200 && xhr.status < 300) {
                 jsonResponse = { success: true, message: "Upload successful (non-JSON response)." };
             } else {
                showPopup(`Upload failed: Invalid server response. Status: ${xhr.status}`);
                if (progressModal) progressModal.style.display = 'none'; // Hide modal on error
                return; // Stop further processing
            }
        }

        // Process the parsed or constructed JSON response
         if (jsonResponse.success) {
             if (progressText) progressText.textContent = 'Upload Complete!';
             showPopup(jsonResponse.message || 'Upload Complete!');
             // Redirect to index page after a short delay
             setTimeout(() => {
                 window.location.href = '/'; // Redirect to the main page
             }, 1500); // Adjust delay as needed
         } else {
             if (progressModal) progressModal.style.display = 'none'; // Hide modal on failure
             showPopup(`Upload failed: ${jsonResponse.error || jsonResponse.message || 'Unknown error'}`);
         }
    });

    // --- Error Handling ---
    xhr.addEventListener('error', () => {
        if (progressModal) progressModal.style.display = 'none';
        showPopup("Upload failed. Network error or server unreachable.");
        console.error('XHR upload error occurred.');
    });

    // --- Abort Handling ---
    xhr.addEventListener('abort', () => {
        if (progressModal) progressModal.style.display = 'none';
        showPopup("Upload aborted.");
        console.log('XHR upload aborted.');
    });


    // --- Send Request ---
    xhr.open('POST', '/upload', true); // Ensure URL matches Flask route
    // Add CSRF token header if required by Flask-WTF:
    // const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    // if (csrfToken) {
    //     xhr.setRequestHeader('X-CSRFToken', csrfToken);
    // }
    xhr.send(formData);

    // --- Show Progress Modal ---
    if (progressModal) {
        progressModal.style.display = 'flex'; // Use flex for centering
        if (progressFill) progressFill.style.width = '0%';
        if (progressText) progressText.textContent = 'Uploading... 0%';
    }
}


// --- UI Helper Functions ---

// Generic message popup
function showPopup(message) {
    // Remove existing popups first
    document.querySelectorAll('.popup').forEach(p => p.remove());

    const popup = document.createElement('div');
    popup.classList.add('popup');
    popup.innerHTML = `
        <p>${message}</p>
        <button class="ok-btn">OK</button>
    `; // Use a class for the button
    document.body.appendChild(popup);

    // Add event listener to the OK button
    popup.querySelector('.ok-btn').addEventListener('click', () => {
        popup.remove();
    });
}

// Confirmation popup
function showConfirmPopup(message, onConfirm) {
     // Remove existing popups first
    document.querySelectorAll('.popup').forEach(p => p.remove());

    const popup = document.createElement('div');
    popup.classList.add('popup'); // Reuse popup styling
    popup.innerHTML = `
        <p>${message}</p>
        <div class="popup-actions">
            <button class="confirm-btn">Confirm</button>
            <button class="cancel-btn">Cancel</button>
        </div>
    `;
    document.body.appendChild(popup);

    popup.querySelector('.confirm-btn').addEventListener('click', () => {
        onConfirm(); // Execute the callback function
        popup.remove();
    });
    popup.querySelector('.cancel-btn').addEventListener('click', () => {
        popup.remove(); // Just remove the popup
    });
}

// Logout is handled by a standard form POST in index.html now
// document.getElementById('logout-btn')?.addEventListener('click', () => { ... }); // Remove this listener