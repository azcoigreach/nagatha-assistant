// Main dashboard JavaScript functionality

// Auto-refresh interval for system status (2 minutes = 120000ms)
const SYSTEM_STATUS_REFRESH_INTERVAL = 120000; // 2 minutes
let systemStatusRefreshInterval = null;

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
        
        // Call API with refresh=true to trigger background refresh
        const data = await apiCall('/api/system-status/?refresh=true');
        updateSystemStatusDisplay(data);
        updateFooterStatus(data);
        
        // Show pulsing update indicator
        showUpdateIndicator();
        
    } catch (error) {
        console.error('Failed to refresh system status:', error);
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

function showUpdateIndicator() {
    const updateIcon = document.getElementById('system-status-update-icon');
    if (updateIcon) {
        // Make icon more visible during animation
        updateIcon.style.opacity = '1';
        updateIcon.style.transform = 'scale(1.2)';
        
        // Add pulsing animation class
        updateIcon.classList.add('pulse-animation');
        
        // Remove the animation class and reset after 2 seconds
        setTimeout(() => {
            updateIcon.classList.remove('pulse-animation');
            updateIcon.style.opacity = '0.3';
            updateIcon.style.transform = 'scale(1)';
        }, 2000);
    }
}

// Global variable to track refresh state
let isRefreshing = false;
let refreshTimeout = null;

function showTasksUpdateIndicator(startRefresh = false) {
    const updateIcon = document.getElementById('tasks-update-icon');
    if (!updateIcon) {
        console.error('Tasks update icon not found');
        return;
    }
    
    if (startRefresh) {
        // Starting a refresh
        console.log('Starting refresh indicator');
        isRefreshing = true;
        
        // Clear any existing timeout
        if (refreshTimeout) {
            clearTimeout(refreshTimeout);
            refreshTimeout = null;
        }
        
        // Remove any existing animation first
        updateIcon.classList.remove('pulse-animation');
        
        // Force a reflow to ensure the class removal takes effect
        updateIcon.offsetHeight;
        
        // Make icon visible and start pulsing
        updateIcon.style.opacity = '1';
        updateIcon.style.transform = 'scale(1.2)';
        updateIcon.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        updateIcon.style.color = '#00ff00';
        updateIcon.style.textShadow = '0 0 10px #00ff00';
        
        // Add pulsing animation class
        updateIcon.classList.add('pulse-animation');
        
    } else {
        // Ending a refresh
        console.log('Ending refresh indicator');
        isRefreshing = false;
        
        // Clear any existing timeout
        if (refreshTimeout) {
            clearTimeout(refreshTimeout);
            refreshTimeout = null;
        }
        
        // Remove animation and reset to normal state
        updateIcon.classList.remove('pulse-animation');
        updateIcon.style.opacity = '0.3';
        updateIcon.style.transform = 'scale(1)';
        updateIcon.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        updateIcon.style.color = '';
        updateIcon.style.textShadow = '';
    }
}



// Auto-refresh functions
function startAutoRefresh() {
    if (systemStatusRefreshInterval) {
        clearInterval(systemStatusRefreshInterval);
    }
    
    systemStatusRefreshInterval = setInterval(async () => {
        try {
            console.log('Auto-refreshing system status...');
            const data = await apiCall('/api/system-status/?refresh=true');
            updateSystemStatusDisplay(data);
            updateFooterStatus(data);
            showUpdateIndicator();
        } catch (error) {
            console.error('Auto-refresh failed:', error);
        }
    }, SYSTEM_STATUS_REFRESH_INTERVAL);
    
    console.log(`Auto-refresh started - refreshing every ${SYSTEM_STATUS_REFRESH_INTERVAL / 1000} seconds`);
}

function stopAutoRefresh() {
    if (systemStatusRefreshInterval) {
        clearInterval(systemStatusRefreshInterval);
        systemStatusRefreshInterval = null;
        console.log('Auto-refresh stopped');
    }
}

// Initialize auto-refresh when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Content Loaded - Dashboard.js initialized');
    
    // Add a visible indicator that JavaScript is working
    const body = document.body;
    if (body) {
        body.setAttribute('data-js-loaded', 'true');
        console.log('JavaScript loaded successfully - check body data-js-loaded attribute');
    }
    
    // Start auto-refresh after a short delay
    setTimeout(() => {
        startAutoRefresh();
    }, 5000); // Start after 5 seconds
});

// Task management functions
let tasksInitialized = false;
let lastTasksData = null;

async function refreshTasks(showLoading = false) {
    console.log('refreshTasks called with showLoading:', showLoading);
    
    // Start the refresh indicator immediately
    const refreshStartTime = Date.now();
    showTasksUpdateIndicator(true); // true = start refresh
    
    // Add a visible indicator that refreshTasks is being called
    const body = document.body;
    if (body) {
        const currentTime = new Date().toLocaleTimeString();
        body.setAttribute('data-last-refresh', currentTime);
        console.log('Refresh timestamp set:', currentTime);
    }
    
    try {
        const tasksContainer = document.getElementById('tasks-container');
        if (!tasksContainer) {
            console.error('Tasks container not found');
            showTasksUpdateIndicator(false); // false = end refresh
            return;
        }
        
        // Show loading state ONLY on initial load (not manual refresh)
        if (!tasksInitialized) {
            tasksContainer.innerHTML = '<div class="text-center"><i class="bi bi-arrow-clockwise spin"></i> Loading tasks...</div>';
        }
        
        // Fetch active tasks from API
        const response = await fetch('/api/active-tasks/');
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error || 'Failed to fetch tasks');
        }
        
        // Check if data has actually changed
        const dataString = JSON.stringify(data);
        if (lastTasksData === dataString && tasksInitialized) {
            // Data hasn't changed, no need to update the display
            // But still need to end the refresh indicator
            showTasksUpdateIndicator(false); // false = end refresh
            return;
        }
        lastTasksData = dataString;
        
        // Build the tasks display
        let tasksHtml = '';
        
        // Show summary
        const summary = data.summary;
        tasksHtml += `
            <div class="mb-3">
                <div class="row text-center">
                    <div class="col-4">
                        <small class="text-muted">Recent</small>
                        <div class="fw-bold">${summary.recent_count}</div>
                    </div>
                    <div class="col-4">
                        <small class="text-muted">Active</small>
                        <div class="fw-bold">${summary.active_count}</div>
                    </div>
                    <div class="col-4">
                        <small class="text-muted">Scheduled</small>
                        <div class="fw-bold">${summary.scheduled_count}</div>
                    </div>
                </div>
            </div>
        `;
        
        // Show system status if Celery is not available
        if (data.system_info && data.system_info.message) {
            const statusClass = data.system_info.celery_status === 'error' ? 'warning' : 'info';
            tasksHtml += `
                <div class="alert alert-${statusClass} alert-sm mb-3">
                    <i class="bi bi-info-circle me-2"></i>
                    <strong>System Status:</strong> ${data.system_info.message}
                    ${data.system_info.celery_status === 'error' ? 
                        '<br><small>To enable background tasks, start Redis and Celery workers.</small>' : ''}
                </div>
            `;
        }
        
        // Show active Celery tasks
        if (data.active_celery_tasks && data.active_celery_tasks.length > 0) {
            tasksHtml += '<h6 class="text-primary mb-2"><i class="bi bi-play-circle"></i> Active Celery Tasks</h6>';
            data.active_celery_tasks.forEach(task => {
                const startTime = task.time_start ? new Date(task.time_start * 1000).toLocaleTimeString() : 'Unknown';
                tasksHtml += `
                    <div class="list-group-item px-0">
                        <div class="d-flex justify-content-between align-items-start">
                            <div class="flex-grow-1">
                                <h6 class="mb-1">${task.name}</h6>
                                <p class="mb-1 text-muted small">Worker: ${task.worker} | Started: ${startTime}</p>
                                <small class="text-muted">ID: ${task.id}</small>
                            </div>
                            <div>
                                <span class="badge bg-primary">Running</span>
                            </div>
                        </div>
                    </div>
                `;
            });
        }
        
        // Show recent database tasks
        if (data.recent_tasks && data.recent_tasks.length > 0) {
            tasksHtml += '<h6 class="text-info mb-2 mt-3"><i class="bi bi-clock-history"></i> Recent Tasks</h6>';
            data.recent_tasks.forEach(task => {
                const statusClass = task.status === 'running' ? 'primary' : 
                                  task.status === 'completed' ? 'success' : 
                                  task.status === 'failed' ? 'danger' : 'secondary';
                const createdTime = new Date(task.created_at).toLocaleString();
                
                tasksHtml += `
                    <div class="list-group-item px-0">
                        <div class="d-flex justify-content-between align-items-start">
                            <div class="flex-grow-1">
                                <h6 class="mb-1">${task.task_name}</h6>
                                <p class="mb-1 text-muted small">${task.description}</p>
                                <small class="text-muted">Created: ${createdTime}</small>
                            </div>
                            <div>
                                <span class="badge bg-${statusClass}">${task.status}</span>
                            </div>
                        </div>
                        ${task.status === 'running' && task.progress > 0 ? `
                            <div class="progress mt-2" style="height: 6px;">
                                <div class="progress-bar" style="width: ${task.progress}%"></div>
                            </div>
                        ` : ''}
                    </div>
                `;
            });
        }
        
        // Show scheduled tasks
        if (data.scheduled_tasks && data.scheduled_tasks.length > 0) {
            tasksHtml += '<h6 class="text-warning mb-2 mt-3"><i class="bi bi-calendar-event"></i> Scheduled Tasks</h6>';
            data.scheduled_tasks.forEach(task => {
                const lastRun = task.last_run ? new Date(task.last_run).toLocaleString() : 'Never';
                tasksHtml += `
                    <div class="list-group-item px-0">
                        <div class="d-flex justify-content-between align-items-start">
                            <div class="flex-grow-1">
                                <h6 class="mb-1">${task.name}</h6>
                                <p class="mb-1 text-muted small">${task.schedule} | Runs: ${task.total_run_count}</p>
                                <small class="text-muted">Last run: ${lastRun}</small>
                            </div>
                            <div>
                                <span class="badge bg-${task.enabled ? 'success' : 'secondary'}">${task.enabled ? 'Enabled' : 'Disabled'}</span>
                            </div>
                        </div>
                    </div>
                `;
            });
        }
        
        // Show empty state if no tasks and no system message
        if (!data.active_celery_tasks?.length && !data.recent_tasks?.length && !data.scheduled_tasks?.length && !data.system_info?.message) {
            tasksHtml = `
                <div class="text-center text-muted">
                    <i class="bi bi-check-circle display-4"></i>
                    <p class="mt-2">No active tasks</p>
                    <small>No Celery tasks, recent tasks, or scheduled jobs found.</small>
                </div>
            `;
        }
        
        // Update the display with fade-in effect
        tasksContainer.innerHTML = tasksHtml;
        tasksContainer.classList.add('fade-in');
        
        // Mark as initialized
        tasksInitialized = true;
        
        // End the refresh indicator with minimum duration
        const refreshDuration = Date.now() - refreshStartTime;
        const minDuration = 500; // Minimum 500ms to ensure visibility
        
        console.log(`Refresh completed in ${refreshDuration}ms`);
        
        if (refreshDuration < minDuration) {
            // If refresh was too fast, wait a bit before ending the indicator
            console.log(`Refresh was fast (${refreshDuration}ms), waiting ${minDuration - refreshDuration}ms before ending indicator`);
            setTimeout(() => {
                showTasksUpdateIndicator(false); // false = end refresh
            }, minDuration - refreshDuration);
        } else {
            // Refresh took long enough, end immediately
            console.log(`Refresh took ${refreshDuration}ms, ending indicator immediately`);
            showTasksUpdateIndicator(false); // false = end refresh
        }
        
    } catch (error) {
        console.error('Failed to refresh tasks:', error);
        const tasksContainer = document.getElementById('tasks-container');
        if (tasksContainer) {
            tasksContainer.innerHTML = `
                <div class="text-center text-muted">
                    <i class="bi bi-exclamation-triangle display-4"></i>
                    <p class="mt-2">Failed to load tasks</p>
                    <small>${error.message}</small>
                </div>
            `;
        }
        // End the refresh indicator even on error
        showTasksUpdateIndicator(false); // false = end refresh
    }
}

// Session management functions
function loadSession(sessionId) {
    window.location.href = `/session/${sessionId}/`;
}

// Usage data functions
async function refreshUsageData() {
    try {
        const usageButton = document.querySelector('button[onclick="refreshUsageData()"]');
        if (usageButton) {
            usageButton.disabled = true;
            usageButton.innerHTML = '<i class="bi bi-arrow-clockwise spinner-border spinner-border-sm"></i>';
        }
        
        const data = await apiCall('/api/usage-data/');
        updateUsageDataDisplay(data);
        
        // Show pulsing update indicator
        showUsageUpdateIndicator();
        
    } catch (error) {
        console.error('Failed to refresh usage data:', error);
        const container = document.getElementById('usage-data-content');
        if (container) {
            container.innerHTML = `
                <div class="text-center text-muted">
                    <i class="bi bi-exclamation-triangle display-4"></i>
                    <p class="mt-2">Failed to load usage data</p>
                    <small>${error.message}</small>
                </div>
            `;
        }
    } finally {
        const usageButton = document.querySelector('button[onclick="refreshUsageData()"]');
        if (usageButton) {
            usageButton.disabled = false;
            usageButton.innerHTML = '<i class="bi bi-arrow-clockwise"></i>';
        }
    }
}

function updateUsageDataDisplay(data) {
    const container = document.getElementById('usage-data-content');
    if (!container) return;
    
    if (!data.success) {
        container.innerHTML = `
            <div class="text-center text-muted">
                <i class="bi bi-exclamation-triangle display-4"></i>
                <p class="mt-2">Failed to load usage data</p>
                <small>${data.message || 'Unknown error'}</small>
            </div>
        `;
        return;
    }
    
    let html = `
        <div class="row g-3">
            <div class="col-6">
                <div class="text-center">
                    <div class="h4 text-primary">${data.total_requests}</div>
                    <small class="text-muted">Total Requests</small>
                </div>
            </div>
            <div class="col-6">
                <div class="text-center">
                    <div class="h4 text-success">$${data.total_cost.toFixed(2)}</div>
                    <small class="text-muted">Total Cost</small>
                </div>
            </div>
            <div class="col-12">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small>Daily Requests</small>
                    <small>${data.daily_usage.requests}</small>
                </div>
                <div class="progress" style="height: 8px;">
                    <div class="progress-bar bg-primary" style="width: ${Math.min((data.daily_usage.requests / Math.max(data.total_requests, 1)) * 100, 100)}%"></div>
                </div>
            </div>
            <div class="col-12">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small>Daily Cost</small>
                    <small>$${data.daily_usage.cost.toFixed(2)}</small>
                </div>
                <div class="progress" style="height: 8px;">
                    <div class="progress-bar bg-success" style="width: ${Math.min((data.daily_usage.cost / Math.max(data.total_cost, 0.01)) * 100, 100)}%"></div>
                </div>
            </div>
    `;
    
    // Show model usage if available
    if (data.model_usage && Object.keys(data.model_usage).length > 0) {
        html += '<div class="col-12"><h6 class="text-info mb-2">Model Usage</h6>';
        Object.entries(data.model_usage).forEach(([model, usage]) => {
            const lastUsed = usage.last_used ? new Date(usage.last_used).toLocaleDateString() : 'Unknown';
            html += `
                <div class="small mb-2">
                    <div class="d-flex justify-content-between">
                        <span class="fw-bold">${model}</span>
                        <span class="text-muted">$${usage.cost.toFixed(2)}</span>
                    </div>
                    <div class="d-flex justify-content-between text-muted">
                        <small>${usage.requests} requests</small>
                        <small>${usage.tokens.toLocaleString()} tokens</small>
                    </div>
                    <small class="text-muted">Last used: ${lastUsed}</small>
                </div>
            `;
        });
        html += '</div>';
    }
    
    html += `
        </div>
        <div class="mt-3">
            <small class="text-muted">
                <i class="bi bi-clock"></i> Last updated: ${new Date(data.last_updated).toLocaleString()}
            </small>
        </div>
    `;
    
    container.innerHTML = html;
}

function showUsageUpdateIndicator() {
    const updateIcon = document.getElementById('usage-data-update-icon');
    if (updateIcon) {
        // Make icon more visible during animation
        updateIcon.style.opacity = '1';
        updateIcon.style.transform = 'scale(1.2)';
        
        // Add pulsing animation class
        updateIcon.classList.add('pulse-animation');
        
        // Remove the animation class and reset after 2 seconds
        setTimeout(() => {
            updateIcon.classList.remove('pulse-animation');
            updateIcon.style.opacity = '0.3';
            updateIcon.style.transform = 'scale(1)';
        }, 2000);
    }
}

// Utility functions

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
    
    if (typeof refreshUsageData === 'function') {
        refreshUsageData();
    }
    
    // Setup periodic refresh
    setInterval(() => {
        if (typeof refreshSystemStatus === 'function') {
            refreshSystemStatus();
        }
    }, 30000); // Refresh every 30 seconds
    
    // Setup periodic usage data refresh (every 5 minutes)
    setInterval(() => {
        if (typeof refreshUsageData === 'function') {
            refreshUsageData();
        }
    }, 300000); // Refresh every 5 minutes
});