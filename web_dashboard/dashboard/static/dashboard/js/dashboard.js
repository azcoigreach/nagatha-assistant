// Main dashboard JavaScript functionality

// CSRF token setup for Django
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = getCookie('csrftoken');

// API helper function
async function apiCall(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
        },
        credentials: 'same-origin',
    };
    
    const mergedOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers,
        },
    };
    
    try {
        const response = await fetch(url, mergedOptions);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || `HTTP error! status: ${response.status}`);
        }
        
        return data;
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

// System status functions
async function refreshSystemStatus() {
    try {
        const statusButton = document.querySelector('button[onclick="refreshSystemStatus()"]');
        if (statusButton) {
            statusButton.disabled = true;
            statusButton.innerHTML = '<i class="bi bi-arrow-clockwise spinner-border spinner-border-sm"></i>';
        }
        
        const data = await apiCall('/api/system-status/');
        updateSystemStatusDisplay(data);
        updateFooterStatus(data);
        
    } catch (error) {
        console.error('Failed to refresh system status:', error);
        showError('Failed to refresh system status');
    } finally {
        const statusButton = document.querySelector('button[onclick="refreshSystemStatus()"]');
        if (statusButton) {
            statusButton.disabled = false;
            statusButton.innerHTML = '<i class="bi bi-arrow-clockwise"></i>';
        }
    }
}

function updateSystemStatusDisplay(data) {
    const container = document.getElementById('system-status-content');
    if (!container) return;
    
    const healthClass = data.system_health === 'healthy' ? 'success' : 
                       data.system_health === 'degraded' ? 'warning' : 'danger';
    
    let html = `
        <div class="row g-3">
            <div class="col-6">
                <div class="text-center">
                    <div class="h4 text-primary">${data.mcp_servers_connected}</div>
                    <small class="text-muted">MCP Servers</small>
                </div>
            </div>
            <div class="col-6">
                <div class="text-center">
                    <div class="h4 text-info">${data.total_tools_available}</div>
                    <small class="text-muted">Tools Available</small>
                </div>
            </div>
            <div class="col-12">
                <div class="d-flex justify-content-between align-items-center">
                    <span>Health:</span>
                    <span class="badge bg-${healthClass}">
                        ${data.system_health.charAt(0).toUpperCase() + data.system_health.slice(1)}
                    </span>
                </div>
            </div>
    `;
    
    if (data.cpu_usage !== null) {
        html += `
            <div class="col-12">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small>CPU Usage</small>
                    <small>${data.cpu_usage.toFixed(1)}%</small>
                </div>
                <div class="progress" style="height: 8px;">
                    <div class="progress-bar" style="width: ${data.cpu_usage}%"></div>
                </div>
            </div>
        `;
    }
    
    if (data.memory_usage !== null) {
        html += `
            <div class="col-12">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small>Memory Usage</small>
                    <small>${data.memory_usage.toFixed(1)}%</small>
                </div>
                <div class="progress" style="height: 8px;">
                    <div class="progress-bar" style="width: ${data.memory_usage}%"></div>
                </div>
            </div>
        `;
    }
    
    html += '</div>';
    container.innerHTML = html;
}

function updateFooterStatus(data) {
    const statusElement = document.getElementById('system-status');
    if (!statusElement) return;
    
    const healthClass = data.system_health === 'healthy' ? 'success' : 
                       data.system_health === 'degraded' ? 'warning' : 'danger';
    
    statusElement.innerHTML = `
        Status: <span class="badge bg-${healthClass}">
            ${data.system_health.charAt(0).toUpperCase() + data.system_health.slice(1)}
        </span>
    `;
}

// Task management functions
async function refreshTasks() {
    try {
        const tasksContainer = document.getElementById('tasks-container');
        if (!tasksContainer) return;
        
        // This would need to be implemented as an API endpoint
        // For now, just leave the existing content
        
    } catch (error) {
        console.error('Failed to refresh tasks:', error);
    }
}

// Session management functions
function loadSession(sessionId) {
    window.location.href = `/session/${sessionId}/`;
}

// Utility functions
function showError(message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-danger alert-dismissible fade show';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const main = document.querySelector('main');
    main.insertBefore(alertDiv, main.firstChild);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

function showSuccess(message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-success alert-dismissible fade show';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const main = document.querySelector('main');
    main.insertBefore(alertDiv, main.firstChild);
    
    // Auto-dismiss after 3 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 3000);
}

function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString();
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    console.log('Nagatha Dashboard initialized');
    
    // Initial data load
    if (typeof refreshSystemStatus === 'function') {
        refreshSystemStatus();
    }
    
    // Setup periodic refresh
    setInterval(() => {
        if (typeof refreshSystemStatus === 'function') {
            refreshSystemStatus();
        }
    }, 30000); // Refresh every 30 seconds
});