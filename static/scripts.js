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
});

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
                const link = document.createElement('a');
                const deleteBtn = document.createElement('button');
                
                link.href = `/files/${encodeURIComponent(file)}`;
                link.textContent = file;
                
                deleteBtn.textContent = 'Delete';
                deleteBtn.className = 'delete-button';
                deleteBtn.onclick = () => deleteFile(file);
                
                li.appendChild(link);
                li.appendChild(deleteBtn);
                fileList.appendChild(li);
            });
        })
        .catch(error => {
            console.error('Error fetching files:', error);
            showPopup('Error loading files');
        });
}

function deleteFile(filename) {
    // Show custom confirmation popup
    showConfirmPopup(`Are you sure you want to delete ${filename}?`, () => {
        // If confirmed, proceed with deletion
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

function handleUpload(e) {
    e.preventDefault();
    const fileInput = document.getElementById('file-input');
    const file = fileInput.files[0];

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