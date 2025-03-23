document.addEventListener('DOMContentLoaded', () => {
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => location.reload());
    }

    const uploadForm = document.getElementById('upload-form');
    if (uploadForm) {
        uploadForm.addEventListener('submit', handleUpload);
    }
});

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