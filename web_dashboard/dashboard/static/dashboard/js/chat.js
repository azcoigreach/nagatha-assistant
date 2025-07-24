// Chat functionality for Nagatha Dashboard

// Chat state
let currentSessionId = null;
let messagePollingInterval = null;

// Initialize chat functionality
document.addEventListener('DOMContentLoaded', function() {
    const messageForm = document.getElementById('message-form');
    const messageInput = document.getElementById('message-input');
    const sessionIdInput = document.getElementById('session-id');
    const currentSessionInput = document.getElementById('current-session-id');
    
    // Set current session ID from hidden input if available
    if (sessionIdInput) {
        currentSessionId = sessionIdInput.value;
    } else if (currentSessionInput) {
        currentSessionId = currentSessionInput.value || null;
    }
    
    // Setup message form
    if (messageForm) {
        messageForm.addEventListener('submit', handleMessageSubmit);
    }
    
    // Setup Enter key handling
    if (messageInput) {
        messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleMessageSubmit(e);
            }
        });
    }
    
    // Auto-focus message input
    if (messageInput && !messageInput.disabled) {
        messageInput.focus();
    }
});

// Handle message form submission
async function handleMessageSubmit(e) {
    e.preventDefault();
    
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const message = messageInput.value.trim();
    
    if (!message) return;
    
    // Disable input during send
    messageInput.disabled = true;
    sendButton.disabled = true;
    sendButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span>';
    
    try {
        // Add user message to UI immediately
        addMessageToUI({
            content: message,
            message_type: 'user',
            created_at: new Date().toISOString()
        });
        
        // Clear input
        messageInput.value = '';
        
        // Send message to server
        const response = await apiCall('/api/send-message/', {
            method: 'POST',
            body: JSON.stringify({
                message: message,
                session_id: currentSessionId
            })
        });
        
        // Update session ID if this was a new conversation
        if (response.session_id && !currentSessionId) {
            currentSessionId = response.session_id;
            const currentSessionInput = document.getElementById('current-session-id');
            if (currentSessionInput) {
                currentSessionInput.value = response.session_id;
            }
        }
        
        // Handle immediate response (no longer using tasks)
        if (response.success && response.assistant_message_id) {
            // Add assistant message to UI immediately
            addMessageToUI({
                content: response.response,
                message_type: 'assistant',
                created_at: new Date().toISOString()
            });
        } else if (!response.success) {
            // Handle error response
            addMessageToUI({
                content: `Error: ${response.error || 'Unknown error'}`,
                message_type: 'error',
                created_at: new Date().toISOString()
            });
        }
        
    } catch (error) {
        console.error('Failed to send message:', error);
        
        // Add error message to UI
        addMessageToUI({
            content: `Error: ${error.message}`,
            message_type: 'error',
            created_at: new Date().toISOString()
        });
        
    } finally {
        // Re-enable input
        messageInput.disabled = false;
        sendButton.disabled = false;
        sendButton.innerHTML = '<i class="bi bi-send"></i>';
        messageInput.focus();
    }
}

// Add message to UI
function addMessageToUI(message) {
    const messagesContainer = document.getElementById('messages-container');
    if (!messagesContainer) return;
    
    // Clear placeholder content if it exists
    const placeholder = messagesContainer.querySelector('.text-center.text-muted');
    if (placeholder) {
        placeholder.remove();
    }
    
    // Create message element
    const messageDiv = document.createElement('div');
    messageDiv.className = `message mb-3 fade-in ${message.message_type === 'user' ? 'text-end' : ''}`;
    
    let messageClass = 'bg-secondary border'; // Changed from bg-white to bg-secondary for dark theme
    if (message.message_type === 'user') {
        messageClass = 'bg-primary text-white';
    } else if (message.message_type === 'system') {
        messageClass = 'bg-info text-white';
    } else if (message.message_type === 'error') {
        messageClass = 'bg-danger text-white';
    }
    
    const timestamp = new Date(message.created_at).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit'
    });
    
    messageDiv.innerHTML = `
        <div class="d-inline-block max-width-75 p-3 rounded ${messageClass}">
            <div class="message-content">${escapeHtml(message.content).replace(/\n/g, '<br>')}</div>
            <small class="opacity-75 d-block mt-1">${timestamp}</small>
        </div>
    `;
    
    messagesContainer.appendChild(messageDiv);
    scrollToBottom();
}

// Note: Polling function removed since we now use synchronous responses

// Load session messages
async function loadSessionMessages(sessionId) {
    try {
        const data = await apiCall(`/api/session/${sessionId}/messages/`);
        
        // Clear existing messages
        const messagesContainer = document.getElementById('messages-container');
        if (!messagesContainer) return;
        
        messagesContainer.innerHTML = '';
        
        // Add all messages
        if (data.messages && data.messages.length > 0) {
            data.messages.forEach(message => {
                addMessageToUI(message);
            });
        } else {
            messagesContainer.innerHTML = `
                <div class="text-center text-muted">
                    <i class="bi bi-chat-text display-4"></i>
                    <p class="mt-2">No messages yet. Start the conversation!</p>
                </div>
            `;
        }
        
    } catch (error) {
        console.error('Failed to load session messages:', error);
    }
}

// Scroll to bottom of messages
function scrollToBottom() {
    const messagesContainer = document.getElementById('messages-container');
    if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Auto-resize textarea (if needed)
function autoResizeTextarea(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';
}

// Handle typing indicators (for future enhancement)
function showTypingIndicator() {
    const messagesContainer = document.getElementById('messages-container');
    if (!messagesContainer) return;
    
    const existingIndicator = document.getElementById('typing-indicator');
    if (existingIndicator) return; // Already showing
    
    const typingDiv = document.createElement('div');
    typingDiv.id = 'typing-indicator';
    typingDiv.className = 'message mb-3 fade-in';
    typingDiv.innerHTML = `
        <div class="d-inline-block p-3 rounded bg-light border">
            <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    
    messagesContainer.appendChild(typingDiv);
    scrollToBottom();
}

function hideTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

// CSS for typing indicator dots
const typingStyle = document.createElement('style');
typingStyle.textContent = `
    .typing-dots {
        display: inline-flex;
        align-items: center;
    }
    
    .typing-dots span {
        height: 8px;
        width: 8px;
        background-color: #999;
        border-radius: 50%;
        display: inline-block;
        margin: 0 2px;
        animation: typing 1.4s infinite ease-in-out;
    }
    
    .typing-dots span:nth-child(1) { animation-delay: -0.32s; }
    .typing-dots span:nth-child(2) { animation-delay: -0.16s; }
    
    @keyframes typing {
        0%, 80%, 100% { transform: scale(0); opacity: 0.5; }
        40% { transform: scale(1); opacity: 1; }
    }
`;
document.head.appendChild(typingStyle);