document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message-input');
    const sendBtn = document.getElementById('send-btn');
    const chatMessages = document.getElementById('chat-messages');
    const newChatBtn = document.getElementById('new-chat-btn');
    const welcomeContainer = document.querySelector('.welcome-container');
    const messageTemplate = document.getElementById('message-template');

    // Auto-resize textarea
    messageInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        if (this.scrollHeight > 200) {
            this.style.overflowY = 'auto';
        } else {
            this.style.overflowY = 'hidden';
        }
        
        // Enable/disable send button
        if (this.value.trim().length > 0) {
            sendBtn.removeAttribute('disabled');
        } else {
            sendBtn.setAttribute('disabled', 'true');
        }
    });

    // Handle Enter key (Shift+Enter for new line)
    messageInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (this.value.trim().length > 0) {
                chatForm.dispatchEvent(new Event('submit'));
            }
        }
    });

    // Theme Toggle
    const toggleTheme = () => {
        const body = document.querySelector('.app-container');
        if (body.classList.contains('theme-dark')) {
            body.classList.remove('theme-dark');
            body.classList.add('theme-light');
            document.getElementById('theme-toggle-desktop').innerHTML = '<i class="fa-solid fa-moon"></i>';
            document.getElementById('theme-toggle-mobile').innerHTML = '<i class="fa-solid fa-moon"></i>';
        } else {
            body.classList.remove('theme-light');
            body.classList.add('theme-dark');
            document.getElementById('theme-toggle-desktop').innerHTML = '<i class="fa-solid fa-sun"></i>';
            document.getElementById('theme-toggle-mobile').innerHTML = '<i class="fa-solid fa-sun"></i>';
        }
    };
    
    const desktopThemeBtn = document.getElementById('theme-toggle-desktop');
    const mobileThemeBtn = document.getElementById('theme-toggle-mobile');
    if(desktopThemeBtn) desktopThemeBtn.addEventListener('click', toggleTheme);
    if(mobileThemeBtn) mobileThemeBtn.addEventListener('click', toggleTheme);

    // Navigation Logic
    const navItems = document.querySelectorAll('.nav-item, .bottom-nav-item');
    const pageViews = document.querySelectorAll('.page-view');
    const fabBtn = document.querySelector('.fab-btn');
    
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const targetPage = item.getAttribute('data-page');
            
            navItems.forEach(nav => {
                if(nav.getAttribute('data-page') === targetPage) {
                    nav.classList.add('active');
                } else {
                    nav.classList.remove('active');
                }
            });
            
            pageViews.forEach(page => {
                if(page.id === targetPage) {
                    page.classList.add('active');
                } else {
                    page.classList.remove('active');
                }
            });
            
            if(fabBtn) {
                if(targetPage === 'page-chat') {
                    fabBtn.style.display = 'none';
                } else {
                    fabBtn.style.display = 'flex';
                }
            }
            
            if (targetPage === 'page-stats') {
                loadStats();
            } else if (targetPage === 'page-history') {
                loadHistory();
            }
        });
    });

    async function loadStats() {
        try {
            const response = await fetch('/api/expenses/stats');
            if (!response.ok) throw new Error('Failed to fetch stats');
            const data = await response.json();

            document.getElementById('stats-total-balance').textContent = `₹${data.total_expenses.toFixed(2)}`;
            document.getElementById('stats-expenses-val').textContent = `₹${data.total_expenses.toFixed(2)}`;
            document.getElementById('stats-income-val').textContent = `₹0.00`;

            const categoriesList = document.getElementById('stats-categories-list');
            categoriesList.innerHTML = '';
            
            if (data.top_categories.length === 0) {
                categoriesList.innerHTML = '<div style="text-align: center; color: var(--text-secondary); padding: 20px;">No expenses yet.</div>';
                return;
            }

            const colors = ['color-1', 'color-2', 'color-3', 'color-4'];

            data.top_categories.forEach((cat, index) => {
                const colorClass = colors[index % colors.length];
                const percentage = data.total_expenses > 0 ? Math.min(100, Math.round((cat.amount / data.total_expenses) * 100)) : 0;
                
                const item = document.createElement('div');
                item.className = 'category-item';
                item.innerHTML = `
                    <div class="cat-header">
                        <span class="cat-name"><span class="dot ${colorClass}"></span> ${cat.name || 'Unknown'}</span>
                        <span class="cat-amount">₹${cat.amount.toFixed(2)}</span>
                    </div>
                    <div class="progress-bar-bg"><div class="progress-bar ${colorClass}" style="width: ${percentage}%"></div></div>
                `;
                categoriesList.appendChild(item);
            });
        } catch (error) {
            console.error('Error loading stats:', error);
            document.getElementById('stats-categories-list').innerHTML = '<div style="text-align: center; color: var(--text-warning); padding: 20px;">Error loading stats</div>';
        }
    }

    async function loadHistory() {
        try {
            const response = await fetch('/api/expenses?limit=50');
            if (!response.ok) throw new Error('Failed to fetch history');
            const data = await response.json();

            const transactionList = document.getElementById('history-transaction-list');
            transactionList.innerHTML = '';

            if (data.length === 0) {
                transactionList.innerHTML = '<div style="text-align: center; color: var(--text-secondary); padding: 20px;">No transactions yet.</div>';
                return;
            }

            data.forEach(txn => {
                const item = document.createElement('div');
                item.className = 'txn-card';
                
                const categoryInitial = (txn.category && txn.category.length > 0) ? txn.category[0].toUpperCase() : 'E';
                
                item.innerHTML = `
                    <div class="txn-icon-wrapper" style="color: #4a5ee7; background-color: rgba(74, 94, 231, 0.08);">
                        ${categoryInitial}
                    </div>
                    <div class="txn-details">
                        <div class="txn-title">${txn.description || 'Expense'}</div>
                        <div class="txn-subtitle">${txn.category || 'General'} &bull; ${txn.date}</div>
                    </div>
                    <div class="txn-actions-amount">
                        <div class="txn-amount negative">-₹${txn.amount.toFixed(2)}</div>
                    </div>
                `;
                transactionList.appendChild(item);
            });

        } catch (error) {
            console.error('Error loading history:', error);
            document.getElementById('history-transaction-list').innerHTML = '<div style="text-align: center; color: var(--text-warning); padding: 20px;">Error loading history</div>';
        }
    }

    // Export CSV
    const exportCsvBtn = document.getElementById('btn-export-csv');
    if (exportCsvBtn) {
        exportCsvBtn.addEventListener('click', () => {
            window.location.href = '/api/expenses/export';
        });
    }

    // New Chat
    if (newChatBtn) {
        newChatBtn.addEventListener('click', () => {
            chatMessages.innerHTML = '';
            chatMessages.appendChild(welcomeContainer);
            welcomeContainer.style.display = 'block';
        });
    }

    // Form Submit
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = messageInput.value.trim();
        if (!message) return;

        // Hide welcome message if it exists
        if (welcomeContainer) {
            welcomeContainer.style.display = 'none';
        }

        // Add user message
        appendMessage('user', message);

        // Clear input
        messageInput.value = '';
        messageInput.style.height = 'auto';
        sendBtn.setAttribute('disabled', 'true');

        // Add typing indicator
        const typingId = addTypingIndicator();

        try {
            // Replace with actual API endpoint
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message })
            });

            const data = await response.json();
            
            // Remove typing indicator
            removeElement(typingId);
            
            // Add AI response
            if (response.ok) {
                appendMessage('ai', data.answer);
            } else {
                appendMessage('system', 'Sorry, I encountered an error while processing your request.');
            }
            
        } catch (error) {
            removeElement(typingId);
            appendMessage('system', 'Connection error. Please ensure the server is running.');
            console.error('Error:', error);
        }
    });

    function appendMessage(sender, text) {
        const item = messageTemplate.content.cloneNode(true);
        const messageDiv = item.querySelector('.message');
        const avatarDiv = item.querySelector('.avatar');
        const contentDiv = item.querySelector('.message-text');

        if (sender === 'user') {
            messageDiv.classList.add('user-message');
            avatarDiv.innerHTML = '<i class="fa-solid fa-user"></i>';
            // Simple text encoding to prevent XSS
            contentDiv.textContent = text;
        } else if (sender === 'ai') {
            messageDiv.classList.add('ai-message');
            avatarDiv.innerHTML = '<i class="fa-solid fa-wallet"></i>';
            // Can use marked.js later for markdown support
            contentDiv.innerHTML = '<p>' + text.replace(/\n/g, '<br>') + '</p>';
        } else {
            messageDiv.classList.add('ai-message');
            avatarDiv.innerHTML = '<i class="fa-solid fa-circle-exclamation" style="color: #ff5555"></i>';
            contentDiv.innerHTML = '<p style="color: #ff5555">' + text + '</p>';
        }

        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }

    function addTypingIndicator() {
        const id = 'typing-' + Date.now();
        const item = messageTemplate.content.cloneNode(true);
        const messageDiv = item.querySelector('.message');
        const avatarDiv = item.querySelector('.avatar');
        const contentDiv = item.querySelector('.message-text');

        messageDiv.id = id;
        messageDiv.classList.add('ai-message');
        avatarDiv.innerHTML = '<i class="fa-solid fa-wallet"></i>';
        
        contentDiv.innerHTML = `
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;

        chatMessages.appendChild(messageDiv);
        scrollToBottom();
        return id;
    }

    function removeElement(id) {
        const el = document.getElementById(id);
        if (el) {
            el.remove();
        }
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
});
