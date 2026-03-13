// Main JavaScript for Localcito Client Web Interface

document.addEventListener('DOMContentLoaded', function() {
    // File upload form
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', handleFileUpload);
    }

    // Alert form
    const alertForm = document.getElementById('alertForm');
    if (alertForm) {
        alertForm.addEventListener('submit', handleAlert);
    }

    // Video upload form
    const videoForm = document.getElementById('videoForm');
    if (videoForm) {
        videoForm.addEventListener('submit', handleVideoUpload);
    }

    // Video flag radio buttons
    const flagRadios = document.querySelectorAll('input[name="flag"]');
    const scheduleFields = document.getElementById('scheduleFields');
    
    flagRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            if (this.value === 'scheduled' && scheduleFields) {
                scheduleFields.classList.add('active');
            } else if (scheduleFields) {
                scheduleFields.classList.remove('active');
            }
        });
    });
});

async function handleFileUpload(e) {
    e.preventDefault();
    
    const form = e.target;
    const fileInput = form.querySelector('input[type="file"]');
    const submitBtn = form.querySelector('button[type="submit"]');
    const messageDiv = document.getElementById('uploadMessage');
    
    if (!fileInput.files.length) {
        showMessage(messageDiv, 'Por favor selecciona un archivo', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    
    submitBtn.disabled = true;
    submitBtn.textContent = 'Enviando...';
    
    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            showMessage(messageDiv, data.message, 'success');
            form.reset();
        } else {
            showMessage(messageDiv, data.message, 'error');
        }
    } catch (error) {
        showMessage(messageDiv, 'Error de conexión: ' + error.message, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Enviar Archivo';
    }
}

async function handleAlert(e) {
    e.preventDefault();
    
    const form = e.target;
    const repetitions = form.querySelector('input[name="repetitions"]').value;
    const message = form.querySelector('textarea[name="message"]').value;
    const submitBtn = form.querySelector('button[type="submit"]');
    const messageDiv = document.getElementById('alertMessage');
    
    if (!message.trim()) {
        showMessage(messageDiv, 'El mensaje no puede estar vacío', 'error');
        return;
    }
    
    submitBtn.disabled = true;
    submitBtn.textContent = 'Enviando...';
    
    try {
        const response = await fetch('/send-notification', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                repetitions: parseInt(repetitions),
                message: message
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showMessage(messageDiv, data.message, 'success');
            form.reset();
        } else {
            showMessage(messageDiv, data.message, 'error');
        }
    } catch (error) {
        showMessage(messageDiv, 'Error de conexión: ' + error.message, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Enviar Alerta';
    }
}

async function handleVideoUpload(e) {
    e.preventDefault();
    
    const form = e.target;
    const fileInput = form.querySelector('input[type="file"]');
    const flag = form.querySelector('input[name="flag"]:checked').value;
    const submitBtn = form.querySelector('button[type="submit"]');
    const messageDiv = document.getElementById('videoMessage');
    
    if (!fileInput.files.length) {
        showMessage(messageDiv, 'Por favor selecciona un video', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('flag', flag);
    
    // Add schedule fields if scheduled
    if (flag === 'scheduled') {
        const scheduleTime = form.querySelector('input[name="schedule_time"]').value;
        const scheduleDays = form.querySelector('input[name="schedule_days"]').value;
        
        if (!scheduleTime || !scheduleDays) {
            showMessage(messageDiv, 'Completa los campos de programación', 'error');
            return;
        }
        
        formData.append('schedule_time', scheduleTime);
        formData.append('schedule_days', scheduleDays);
    }
    
    submitBtn.disabled = true;
    submitBtn.textContent = 'Enviando...';
    
    try {
        const response = await fetch('/videos', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            showMessage(messageDiv, data.message, 'success');
            form.reset();
            document.getElementById('scheduleFields').classList.remove('active');
        } else {
            showMessage(messageDiv, data.message, 'error');
        }
    } catch (error) {
        showMessage(messageDiv, 'Error de conexión: ' + error.message, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Enviar Video';
    }
}

function showMessage(element, text, type) {
    if (!element) return;
    
    element.textContent = text;
    element.className = 'message ' + type;
    element.style.display = 'block';
    
    setTimeout(() => {
        element.style.display = 'none';
    }, 5000);
}
