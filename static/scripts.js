document.addEventListener('DOMContentLoaded', () => {
    const refreshBtn = document.getElementById('refresh-btn');
    const fileList = document.getElementById('file-list');
    const uploadForm = document.getElementById('upload-form');

    if (fileList) {
        fetchFiles();
    }

    if (refreshBtn) {
        refreshBtn.addEventListener('click', fetchFiles);
    }

    if (uploadForm) {
        uploadForm.addEventListener('submit', handleUpload);
    }

    // Drag and drop functionality
    const uploadArea = document.getElementById('upload-area');
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
            fileInput.files = e.dataTransfer.files; // Assign dropped files to the input
            // Consider triggering the upload automatically here
        });
    }
});

let currentFilename = null; // Store the filename being renamed

function fetchFiles() {
    fetch('/api/files')
        .then(response => response.json())
        .then(data => {
            const fileList = document.getElementById('file-list');
            fileList.innerHTML = ''; // Clear existing list
            
            if (data.files.length === 0) {
                fileList.innerHTML = '<li>No files available</li>';
                return;
            }

            data.files.forEach(file => {
                const li = document.createElement('li');
                const fileIcon = getFileIcon(file.name); // Get file type icon
                li.innerHTML = `
                    <span class="file-icon">${fileIcon}</span>
                    <a href="/files/${encodeURIComponent(file.name)}">${file.name}</a>
                    <span class="file-size">${formatBytes(file.size)}</span>
                    <span class="file-modified">${file.modified}</span>
                    <button class="rename-button" data-filename="${file.name}">Rename</button>
                    <button class="delete-button" data-filename="${file.name}">Delete</button>
                `;
                fileList.appendChild(li);
            });

            // Add event listeners to rename and delete buttons
            document.querySelectorAll('.rename-button').forEach(button => {
                button.addEventListener('click', () => openRenameModal(button.dataset.filename));
            });

            document.querySelectorAll('.delete-button').forEach(button => {
                button.addEventListener('click', () => deleteFile(button.dataset.filename));
            });
        })
        .catch(error => {
            console.error('Error fetching files:', error);
            showPopup('Error loading files');
        });
}

function getFileIcon(filename) {
    const extension = filename.slice((filename.lastIndexOf(".") - 1 >>> 0) + 2);
    switch (extension.toLowerCase()) {
        case 'pdf': return '📄';
        case 'doc':
        case 'docx': return '📝';
        case 'xls':
        case 'xlsx': return '📊';
        case 'jpg':
        case 'jpeg':
        case 'png':
        case 'gif': return '🖼️';
        case 'mp4':
        case 'avi':
        case 'mov': return '🎬';
        case 'mp3':
        case 'wav': return '🎵';
        case 'zip':
        case 'rar': return '📦';
        case 'txt': return '📜';
        default: return '📄'; // Default document icon
    }
}

function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function deleteFile(filename) {
    showConfirmPopup(`Are you sure you want to delete ${filename}?`, () => {
        fetch(`/delete/${encodeURIComponent(filename)}`, {
            method: 'POST'
        })
        .then(response => {
            if (response.ok) {
                fetchFiles(); // Refresh list after successful deletion
            } else {
                showPopup('Failed to delete file');
            }
        })
        .catch(error => {
            console.error('Error deleting file:', error);
            showPopup('Error deleting file');
        });
    });
}

function openRenameModal(filename) {
    const renameModal = document.getElementById('rename-modal');
    const newFilenameInput = document.getElementById('new-filename');
    const renameConfirmBtn = document.getElementById('rename-confirm-btn');
    const closeButton = document.querySelector('.close-button');

    currentFilename = filename; // Store the filename

    newFilenameInput.value = filename; // Pre-fill the input with the current filename
    renameModal.style.display = "block";

    renameConfirmBtn.onclick = () => {
        const newFilename = newFilenameInput.value;
        if (newFilename && newFilename !== filename) {
            renameFile(filename, newFilename);
            renameModal.style.display = "none"; // Hide the modal after renaming
        } else {
            showPopup("Please enter a new filename.");
        }
    };

    closeButton.onclick = () => {
        renameModal.style.display = "none";
    };

    // Close the modal if the user clicks outside of it
    window.onclick = (event) => {
        if (event.target == renameModal) {
            renameModal.style.display = "none";
        }
    }
}

function renameFile(oldFilename, newFilename) {
    fetch(`/rename/${encodeURIComponent(oldFilename)}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ new_filename: newFilename })
    })
    .then(response => {
        if (response.ok) {
            fetchFiles(); // Refresh file list
            showPopup("File renamed successfully.");
        } else {
            showPopup("Failed to rename file.");
        }
    })
    .catch(error => {
        console.error('Error renaming file:', error);
        showPopup('Error renaming file');
    });
}

function handleUpload(e) {
    e.preventDefault();
    const fileInput = document.getElementById('file-input');
    const file = fileInput.files[0]; //Only one file

    if (!file) {
        showPopup("Please select a file to upload.");
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    const progressModal = document.getElementById('progress-modal');
    const progressFill = document.getElementById('progress-bar-fill');
    const progressText = document.getElementById('progress-text');

    xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
            const percent = (e.loaded / e.total) * 100;
            progressFill.style.width = `${percent}%`;
            progressText.textContent = `Uploading... ${Math.round(percent)}%`;
        }
    });

    xhr.addEventListener('load', () => {
        console.log("Response Status:", xhr.status);
        console.log("Response Text:", xhr.responseText); // Debugging

        try {
            const jsonResponse = JSON.parse(xhr.responseText);
            if (jsonResponse.success) {
                progressText.textContent = 'Upload Complete!';
                setTimeout(() => {
                    progressModal.style.display = 'none';
                    window.location.href = '/';
                }, 1000);
            } else {
                showPopup(`Upload failed: ${jsonResponse.message}`);
                progressModal.style.display = 'none';
            }
        } catch (e) {
            showPopup("Upload failed: Invalid server response.");
            progressModal.style.display = 'none';
        }
    });

    xhr.addEventListener('error', () => {
        showPopup("Upload failed due to network error.");
        progressModal.style.display = 'none';
    });

    xhr.open('POST', '/upload', true);
    xhr.send(formData);
    progressModal.style.display = 'block';
    progressFill.style.width = '0%';
}

function showPopup(message) {
    const popup = document.createElement('div');
    popup.classList.add('popup');
    popup.innerHTML = `<p>${message}</p><button onclick="this.parentElement.remove()">OK</button>`;
    document.body.appendChild(popup);
}

function showConfirmPopup(message, onConfirm) {
    const popup = document.createElement('div');
    popup.classList.add('popup');
    popup.innerHTML = `
        <p>${message}</p>
        <div>
            <button class="confirm-btn">Confirm</button>
            <button class="cancel-btn">Cancel</button>
        </div>
    `;
    document.body.appendChild(popup);

    // Add event listeners for buttons
    popup.querySelector('.confirm-btn').addEventListener('click', () => {
        onConfirm();
        popup.remove();
    });
    popup.querySelector('.cancel-btn').addEventListener('click', () => {
        popup.remove();
    });
}

document.getElementById('logout-btn')?.addEventListener('click', () => {
    fetch('/logout', { method: 'POST' })
        .then(() => window.location.href = '/static/login.html')
        .catch(error => console.error('Logout error:', error));
});