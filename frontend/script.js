document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message-input');
    const sendBtn = document.getElementById('send-btn');
    const chatMessages = document.getElementById('chat-messages');
    const newChatBtn = document.getElementById('new-chat-btn');
    const welcomeContainer = document.querySelector('.welcome-container');
    const messageTemplate = document.getElementById('message-template');

    const CATEGORIES = ['food', 'shopping', 'transport', 'entertainment', 'health', 'utilities', 'other'];

    // ── Auto-resize textarea ───────────────────────────────────────────────
    messageInput.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        this.style.overflowY = this.scrollHeight > 200 ? 'auto' : 'hidden';
        sendBtn.toggleAttribute('disabled', this.value.trim().length === 0);
    });

    messageInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (this.value.trim().length > 0) chatForm.dispatchEvent(new Event('submit'));
        }
    });

    // ── Theme Toggle ───────────────────────────────────────────────────────
    const toggleTheme = () => {
        const body = document.querySelector('.app-container');
        const isDark = body.classList.contains('theme-dark');
        body.classList.toggle('theme-dark', !isDark);
        body.classList.toggle('theme-light', isDark);
        const icon = isDark ? '<i class="fa-solid fa-moon"></i>' : '<i class="fa-solid fa-sun"></i>';
        document.getElementById('theme-toggle-desktop').innerHTML = icon;
        document.getElementById('theme-toggle-mobile').innerHTML = icon;
    };
    document.getElementById('theme-toggle-desktop')?.addEventListener('click', toggleTheme);
    document.getElementById('theme-toggle-mobile')?.addEventListener('click', toggleTheme);

    // ── Navigation ─────────────────────────────────────────────────────────
    const navItems = document.querySelectorAll('.nav-item, .bottom-nav-item');
    const pageViews = document.querySelectorAll('.page-view');

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const targetPage = item.getAttribute('data-page');
            navItems.forEach(nav => nav.classList.toggle('active', nav.getAttribute('data-page') === targetPage));
            pageViews.forEach(page => page.classList.toggle('active', page.id === targetPage));
            if (targetPage === 'page-stats') loadStats();
            else if (targetPage === 'page-history') loadHistory();
        });
    });

    // ── Stats ──────────────────────────────────────────────────────────────
    async function loadStats() {
        try {
            const response = await fetch('/api/expenses/stats');
            if (!response.ok) throw new Error('Failed to fetch stats');
            const data = await response.json();

            document.getElementById('stats-total-balance').textContent = `\u20b9${data.total_expenses.toFixed(2)}`;
            document.getElementById('stats-expenses-val').textContent = `\u20b9${data.total_expenses.toFixed(2)}`;
            document.getElementById('stats-income-val').textContent = `\u20b90.00`;

            const categoriesList = document.getElementById('stats-categories-list');
            categoriesList.innerHTML = '';
            if (data.top_categories.length === 0) {
                categoriesList.innerHTML = '<div style="text-align:center;color:var(--text-secondary);padding:20px;">No expenses yet.</div>';
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
                        <span class="cat-amount">\u20b9${cat.amount.toFixed(2)}</span>
                    </div>
                    <div class="progress-bar-bg"><div class="progress-bar ${colorClass}" style="width:${percentage}%"></div></div>
                `;
                categoriesList.appendChild(item);
            });
        } catch (error) {
            console.error('Error loading stats:', error);
            document.getElementById('stats-categories-list').innerHTML = '<div style="text-align:center;color:var(--text-warning);padding:20px;">Error loading stats</div>';
        }
    }

    // ── History ────────────────────────────────────────────────────────────
    async function loadHistory() {
        try {
            const response = await fetch('/api/expenses?limit=50');
            if (!response.ok) throw new Error('Failed to fetch history');
            const data = await response.json();
            const transactionList = document.getElementById('history-transaction-list');
            transactionList.innerHTML = '';
            if (data.length === 0) {
                transactionList.innerHTML = '<div style="text-align:center;color:var(--text-secondary);padding:20px;">No transactions yet.</div>';
                return;
            }
            data.forEach(txn => {
                const item = document.createElement('div');
                item.className = 'txn-card';
                const categoryInitial = (txn.category && txn.category.length > 0) ? txn.category[0].toUpperCase() : 'E';
                item.innerHTML = `
                    <div class="txn-icon-wrapper" style="color:#4a5ee7;background-color:rgba(74,94,231,0.08);">${categoryInitial}</div>
                    <div class="txn-details">
                        <div class="txn-title">${txn.description || 'Expense'}</div>
                        <div class="txn-subtitle">${txn.category || 'General'} &bull; ${txn.date}</div>
                    </div>
                    <div class="txn-actions-amount">
                        <div class="txn-amount negative">-\u20b9${txn.amount.toFixed(2)}</div>
                    </div>
                `;
                transactionList.appendChild(item);
            });
        } catch (error) {
            console.error('Error loading history:', error);
            document.getElementById('history-transaction-list').innerHTML = '<div style="text-align:center;color:var(--text-warning);padding:20px;">Error loading history</div>';
        }
    }

    // ── Export CSV ─────────────────────────────────────────────────────────
    document.getElementById('btn-export-csv')?.addEventListener('click', () => {
        window.location.href = '/api/expenses/export';
    });

    // ── New Chat ───────────────────────────────────────────────────────────
    newChatBtn?.addEventListener('click', () => {
        chatMessages.innerHTML = '';
        chatMessages.appendChild(welcomeContainer);
        welcomeContainer.style.display = 'block';
    });

    // ── Helpers ────────────────────────────────────────────────────────────
    function appendMessage(sender, text, id = null) {
        const item = messageTemplate.content.cloneNode(true);
        const messageDiv = item.querySelector('.message');
        if (id) messageDiv.id = id;
        const avatarDiv = item.querySelector('.avatar');
        const contentDiv = item.querySelector('.message-text');

        if (sender === 'user') {
            messageDiv.classList.add('user-message');
            avatarDiv.innerHTML = '<i class="fa-solid fa-user"></i>';
            contentDiv.textContent = text;
        } else if (sender === 'ai') {
            messageDiv.classList.add('ai-message');
            avatarDiv.innerHTML = '<i class="fa-solid fa-wallet"></i>';
            contentDiv.innerHTML = '<p>' + text.replace(/\n/g, '<br>') + '</p>';
        } else {
            messageDiv.classList.add('ai-message');
            avatarDiv.innerHTML = '<i class="fa-solid fa-circle-exclamation" style="color:#ff5555"></i>';
            contentDiv.innerHTML = `<p style="color:#ff5555">${text}</p>`;
        }

        chatMessages.appendChild(messageDiv);
        scrollToBottom();
        return messageDiv;
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
        document.getElementById(id)?.remove();
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // ── Confirmation Card ──────────────────────────────────────────────────
    /**
     * Renders a confirmation card inside a new AI bubble.
     *
     * @param {Object} preview  - ExpensePreview from the API
     * @param {string} preview.amount
     * @param {string} preview.category
     * @param {string} preview.date
     * @param {string} preview.payment_mode
     * @param {string} preview.description
     * @param {string|null} preview.ocr_text
     * @param {string|null} preview.source   - 'image' | 'text'
     */
    function renderConfirmationCard(preview) {
        const item = messageTemplate.content.cloneNode(true);
        const messageDiv = item.querySelector('.message');
        const avatarDiv = item.querySelector('.avatar');
        const contentDiv = item.querySelector('.message-text');

        messageDiv.classList.add('ai-message');
        avatarDiv.innerHTML = '<i class="fa-solid fa-wallet"></i>';

        const catOptions = CATEGORIES.map(c =>
            `<option value="${c}" ${c === preview.category ? 'selected' : ''}>${c.charAt(0).toUpperCase() + c.slice(1)}</option>`
        ).join('');

        const ocrSection = preview.ocr_text
            ? `<details class="confirm-ocr">
                   <summary>View extracted text</summary>
                   <pre>${escapeHtml(preview.ocr_text)}</pre>
               </details>`
            : '';

        const sourceLabel = preview.source === 'image' ? '🧾 Review Receipt' : '✏️ Review Expense';

        contentDiv.innerHTML = `
            <p style="margin-bottom:10px;color:var(--text-secondary);font-size:0.9rem;">
                Here's what I extracted. Edit any field if needed, then confirm to save.
            </p>
            <div class="confirm-card">
                <div class="confirm-card-title">${sourceLabel}</div>
                <div class="confirm-fields">
                    <div class="confirm-field">
                        <label for="cf-amount">Amount</label>
                        <input id="cf-amount" type="number" min="0.01" step="0.01" value="${preview.amount}" placeholder="0.00" />
                    </div>
                    <div class="confirm-field">
                        <label for="cf-category">Category</label>
                        <select id="cf-category">${catOptions}</select>
                    </div>
                    <div class="confirm-field">
                        <label for="cf-date">Date</label>
                        <input id="cf-date" type="date" value="${preview.date}" />
                    </div>
                    <div class="confirm-field">
                        <label for="cf-payment">Payment</label>
                        <input id="cf-payment" type="text" value="${escapeHtml(preview.payment_mode)}" placeholder="e.g. UPI, cash" />
                    </div>
                    <div class="confirm-field">
                        <label for="cf-desc">Description</label>
                        <input id="cf-desc" type="text" value="${escapeHtml(preview.description)}" placeholder="What was bought" />
                    </div>
                </div>
                ${ocrSection}
                <div class="confirm-btn-row">
                    <button class="btn-confirm" id="btn-confirm-save">
                        <i class="fa-solid fa-check"></i> Confirm &amp; Save
                    </button>
                    <button class="btn-cancel" id="btn-confirm-cancel">Cancel</button>
                </div>
            </div>
        `;

        chatMessages.appendChild(messageDiv);
        scrollToBottom();

        // Wire up buttons
        const confirmBtn = messageDiv.querySelector('#btn-confirm-save');
        const cancelBtn = messageDiv.querySelector('#btn-confirm-cancel');

        confirmBtn.addEventListener('click', async () => {
            // Validate amount
            const amountInput = messageDiv.querySelector('#cf-amount');
            const amount = parseFloat(amountInput.value);
            if (isNaN(amount) || amount <= 0) {
                amountInput.classList.add('field-error');
                amountInput.focus();
                return;
            }
            amountInput.classList.remove('field-error');

            // Collect fields
            const body = {
                amount: amount,
                category: messageDiv.querySelector('#cf-category').value,
                date: messageDiv.querySelector('#cf-date').value,
                payment_mode: messageDiv.querySelector('#cf-payment').value.trim() || 'cash',
                description: messageDiv.querySelector('#cf-desc').value.trim() || 'Expense',
            };

            // Disable button to prevent double-submit
            confirmBtn.disabled = true;
            confirmBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

            try {
                const res = await fetch('/api/expenses/confirm', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
                const data = await res.json();

                if (res.ok) {
                    // Replace confirm card content with success summary
                    const card = messageDiv.querySelector('.confirm-card');
                    card.innerHTML = `
                        <div style="display:flex;align-items:center;gap:8px;font-weight:600;color:var(--accent-primary);margin-bottom:10px;">
                            <i class="fa-solid fa-circle-check"></i> Saved! Expense #${data.id} logged.
                        </div>
                        <div style="display:grid;grid-template-columns:110px 1fr;gap:6px 10px;font-size:0.88rem;line-height:1.7;">
                            <span style="color:var(--text-secondary);font-weight:600;text-transform:uppercase;font-size:0.78rem;">Amount</span>
                            <span>\u20b9${data.amount.toFixed(2)}</span>
                            <span style="color:var(--text-secondary);font-weight:600;text-transform:uppercase;font-size:0.78rem;">Category</span>
                            <span>${data.category}</span>
                            <span style="color:var(--text-secondary);font-weight:600;text-transform:uppercase;font-size:0.78rem;">Date</span>
                            <span>${data.date}</span>
                            <span style="color:var(--text-secondary);font-weight:600;text-transform:uppercase;font-size:0.78rem;">Payment</span>
                            <span>${data.payment_mode}</span>
                            <span style="color:var(--text-secondary);font-weight:600;text-transform:uppercase;font-size:0.78rem;">Description</span>
                            <span>${data.description}</span>
                        </div>
                    `;
                    scrollToBottom();
                } else {
                    // Re-enable so user can retry
                    confirmBtn.disabled = false;
                    confirmBtn.innerHTML = '<i class="fa-solid fa-check"></i> Confirm &amp; Save';
                    appendMessage('system', `\u274c ${data.detail || 'Failed to save. Please try again.'}`);
                }
            } catch (err) {
                confirmBtn.disabled = false;
                confirmBtn.innerHTML = '<i class="fa-solid fa-check"></i> Confirm &amp; Save';
                appendMessage('system', '\uD83D\uDD0C Connection error while saving. Please try again.');
                console.error('Confirm error:', err);
            }
        });

        cancelBtn.addEventListener('click', () => {
            const card = messageDiv.querySelector('.confirm-card');
            card.innerHTML = `
                <p style="color:var(--text-secondary);font-size:0.88rem;">
                    <i class="fa-solid fa-ban" style="margin-right:6px;"></i>Cancelled — no expense was logged.
                </p>
            `;
            scrollToBottom();
        });
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    // ── Image Upload ───────────────────────────────────────────────────────
    const attachBtn = document.getElementById('attach-btn');
    const imageUpload = document.getElementById('image-upload');

    if (attachBtn && imageUpload) {
        attachBtn.addEventListener('click', () => imageUpload.click());

        imageUpload.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            if (welcomeContainer) welcomeContainer.style.display = 'none';
            appendMessage('user', `\uD83D\uDCCE Uploading receipt: ${file.name}`);
            const typingId = addTypingIndicator();

            const formData = new FormData();
            formData.append('file', file);

            try {
                const response = await fetch('/api/expenses/upload', {
                    method: 'POST',
                    body: formData,
                });
                const data = await response.json();
                removeElement(typingId);

                if (response.ok) {
                    renderConfirmationCard(data);
                } else {
                    appendMessage('system', `\u274c ${data.detail || 'Upload failed. Please try again.'}`);
                }
            } catch (error) {
                removeElement(typingId);
                appendMessage('system', '\uD83D\uDD0C Connection error during upload. Please ensure the server is running.');
                console.error('Upload error:', error);
            }

            imageUpload.value = '';
        });
    }

    // ── Chat Submit ────────────────────────────────────────────────────────
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = messageInput.value.trim();
        if (!message) return;

        if (welcomeContainer) welcomeContainer.style.display = 'none';
        appendMessage('user', message);

        messageInput.value = '';
        messageInput.style.height = 'auto';
        sendBtn.setAttribute('disabled', 'true');

        const typingId = addTypingIndicator();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message }),
            });

            const data = await response.json();
            removeElement(typingId);

            if (!response.ok) {
                appendMessage('system', 'Sorry, I encountered an error while processing your request.');
                return;
            }

            if (data.intent === 'log' && data.expense) {
                // Only render the confirmation card (it has its own intro)
                renderConfirmationCard(data.expense);
            } else {
                appendMessage('ai', data.answer);
            }

        } catch (error) {
            removeElement(typingId);
            appendMessage('system', '\uD83D\uDD0C Connection error. Please ensure the server is running.');
            console.error('Chat error:', error);
        }
    });
});
