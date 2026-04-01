document.addEventListener('DOMContentLoaded', () => {
    // ══════════════════════════════════════════════════════════════════════════
    // ── Auth Layer ────────────────────────────────────────────────────────────
    // ══════════════════════════════════════════════════════════════════════════

    const authView = document.getElementById('auth-view');
    const appContainer = document.querySelector('.app-container');
    const authError = document.getElementById('auth-error');
    const tabIndicator = document.querySelector('.auth-tab-indicator');

    // ── authFetch — injects Bearer token, auto-logouts on 401 ────────────────
    function authFetch(url, options = {}) {
        const token = localStorage.getItem('auth_token');
        options.headers = {
            ...(options.headers || {}),
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        };
        return fetch(url, options).then(res => {
            if (res.status === 401) { triggerLogout(); }
            return res;
        });
    }

    // ── Show / hide auth ──────────────────────────────────────────────────────
    function showApp(user) {
        authView.style.display = 'none';
        appContainer.style.display = 'flex';
        const avatar = document.getElementById('sidebar-avatar');
        const uname = document.getElementById('sidebar-username');
        if (avatar) avatar.textContent = (user.username || 'U')[0].toUpperCase();
        if (uname) uname.textContent = user.username || user.email;
    }

    function showAuth() {
        authView.style.display = 'flex';
        appContainer.style.display = 'none';
        clearAuthError();
    }

    // ── Session detection on load ─────────────────────────────────────────────
    const savedToken = localStorage.getItem('auth_token');
    const savedUser = (() => {
        try { return JSON.parse(localStorage.getItem('auth_user') || 'null'); } catch { return null; }
    })();

    if (savedToken && savedUser) {
        showApp(savedUser);
    } else {
        showAuth();
    }

    // ── Error helpers ─────────────────────────────────────────────────────────
    function showAuthError(msg) {
        authError.innerHTML = `<i class="fa-solid fa-circle-exclamation"></i> ${msg}`;
        authError.style.display = 'flex';
    }

    function clearAuthError() {
        authError.style.display = 'none';
        authError.innerHTML = '';
    }

    // ── Tab switching ─────────────────────────────────────────────────────────
    const formLogin = document.getElementById('form-login');
    const formRegister = document.getElementById('form-register');

    document.querySelectorAll('.auth-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.tab;
            document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            clearAuthError();
            if (target === 'login') {
                formLogin.style.display = 'flex';
                formRegister.style.display = 'none';
                tabIndicator.classList.remove('on-register');
            } else {
                formLogin.style.display = 'none';
                formRegister.style.display = 'flex';
                tabIndicator.classList.add('on-register');
            }
        });
    });

    // ── Password eye toggle ───────────────────────────────────────────────────
    document.querySelectorAll('.auth-eye-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const input = document.getElementById(btn.dataset.target);
            if (!input) return;
            const isHidden = input.type === 'password';
            input.type = isHidden ? 'text' : 'password';
            btn.querySelector('i').className = isHidden ? 'fa-regular fa-eye-slash' : 'fa-regular fa-eye';
        });
    });

    // ── Login ─────────────────────────────────────────────────────────────────
    formLogin.addEventListener('submit', async (e) => {
        e.preventDefault();
        clearAuthError();
        const btn = document.getElementById('login-submit-btn');
        const email = document.getElementById('login-email').value.trim();
        const password = document.getElementById('login-password').value;

        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Signing In\u2026';

        try {
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password }),
            });
            const data = await res.json();
            if (!res.ok) {
                showAuthError(data.detail || 'Login failed. Please try again.');
            } else {
                localStorage.setItem('auth_token', data.token);
                localStorage.setItem('auth_user', JSON.stringify(data.user));
                showApp(data.user);
            }
        } catch {
            showAuthError('Connection error. Is the server running?');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<span>Sign In</span><i class="fa-solid fa-arrow-right"></i>';
        }
    });

    // ── Register ──────────────────────────────────────────────────────────────
    formRegister.addEventListener('submit', async (e) => {
        e.preventDefault();
        clearAuthError();
        const btn = document.getElementById('register-submit-btn');
        const username = document.getElementById('reg-username').value.trim();
        const email = document.getElementById('reg-email').value.trim();
        const password = document.getElementById('reg-password').value;
        const confirm = document.getElementById('reg-confirm').value;

        if (password !== confirm) { showAuthError('Passwords do not match.'); return; }
        if (password.length < 6) { showAuthError('Password must be at least 6 characters.'); return; }

        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Creating Account\u2026';

        try {
            const res = await fetch('/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, email, password }),
            });
            const data = await res.json();
            if (!res.ok) {
                showAuthError(data.detail || 'Registration failed. Please try again.');
            } else {
                localStorage.setItem('auth_token', data.token);
                localStorage.setItem('auth_user', JSON.stringify(data.user));
                showApp(data.user);
            }
        } catch {
            showAuthError('Connection error. Is the server running?');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<span>Create Account</span><i class="fa-solid fa-arrow-right"></i>';
        }
    });

    // ── Logout ────────────────────────────────────────────────────────────────
    function triggerLogout() {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_user');
        // Reset chat to welcome state
        const msgs = document.getElementById('chat-messages');
        const welcome = document.querySelector('.welcome-container');
        if (msgs && welcome) {
            msgs.innerHTML = '';
            msgs.appendChild(welcome);
            welcome.style.display = '';
        }
        // Reset nav to chat tab
        document.querySelectorAll('.nav-item, .bottom-nav-item').forEach(n => {
            n.classList.toggle('active', n.getAttribute('data-page') === 'page-chat');
        });
        document.querySelectorAll('.page-view').forEach(p => {
            p.classList.toggle('active', p.id === 'page-chat');
        });
        document.getElementById('tab-login')?.click();
        showAuth();
    }

    document.getElementById('logout-btn')?.addEventListener('click', triggerLogout);

    // ══════════════════════════════════════════════════════════════════════════
    // ── End Auth Layer ────────────────────────────────────────────────────────
    // ══════════════════════════════════════════════════════════════════════════

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
            const response = await authFetch('/api/expenses/stats');
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
            const response = await authFetch('/api/expenses?limit=50');
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
                const res = await authFetch('/api/expenses/confirm', {
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
                            <i class="fa-solid fa-circle-check"></i> Saved! Expense for ${data.description} logged.
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
                const response = await authFetch('/api/expenses/upload', {
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
            const response = await authFetch('/api/chat', {
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

    // ── Voice STT ───────────────────────────────────────────────────────────
    const micBtn = document.getElementById('mic-btn');
    let isRecordingVoice = false;
    let voiceAudioCtx;
    let voiceProcessor;
    let voiceMicSource;
    let voiceSocket;

    if (micBtn) {
        micBtn.addEventListener('click', () => {
            if (isRecordingVoice) {
                stopVoiceRecording();
            } else {
                startVoiceRecording();
            }
        });
    }

    async function startVoiceRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            isRecordingVoice = true;
            micBtn.classList.add('recording');
            
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            voiceSocket = new WebSocket(`${protocol}//${window.location.host}/api/voice/transcribe`);
            voiceSocket.binaryType = 'arraybuffer';
            
            voiceSocket.onopen = () => setupVoiceProcessing(stream);

            voiceSocket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.channel === 'transcript') {
                    handleVoiceTranscript(data.text);
                } else if (data.channel === 'utterance_end') {
                    stopVoiceRecording(true); 
                } else if (data.channel === 'error') {
                    console.error('STT Error:', data.message);
                    stopVoiceRecording();
                }
            };

            voiceSocket.onclose = () => { if (isRecordingVoice) stopVoiceRecording(); };
            voiceSocket.onerror = () => stopVoiceRecording();

        } catch (err) {
            console.error('Mic access error:', err);
            appendMessage('error', 'Could not access microphone.');
        }
    }

    function setupVoiceProcessing(stream) {
        voiceAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const actualSampleRate = voiceAudioCtx.sampleRate;
        voiceMicSource = voiceAudioCtx.createMediaStreamSource(stream);
        voiceProcessor = voiceAudioCtx.createScriptProcessor(4096, 1, 1);

        voiceProcessor.onaudioprocess = (e) => {
            if (!isRecordingVoice || !voiceSocket || voiceSocket.readyState !== WebSocket.OPEN) return;
            const inputData = e.inputBuffer.getChannelData(0);
            const downsampled = downsampleAudio(inputData, actualSampleRate, 16000);
            const pcmBuffer = convertFloatTo16BitPCM(downsampled);
            voiceSocket.send(pcmBuffer);
        };

        voiceMicSource.connect(voiceProcessor);
        voiceProcessor.connect(voiceAudioCtx.destination);
    }

    function downsampleAudio(buffer, fromRate, toRate) {
        if (fromRate === toRate) return buffer;
        const ratio = fromRate / toRate;
        const result = new Float32Array(Math.round(buffer.length / ratio));
        let offsetResult = 0, offsetBuffer = 0;
        while (offsetResult < result.length) {
            const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
            let accum = 0, count = 0;
            for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
                accum += buffer[i]; count++;
            }
            result[offsetResult] = accum / count;
            offsetResult++; offsetBuffer = nextOffsetBuffer;
        }
        return result;
    }

    function convertFloatTo16BitPCM(buffer) {
        const pcm = new Int16Array(buffer.length);
        for (let i = 0; i < buffer.length; i++) {
            const s = Math.max(-1, Math.min(1, buffer[i]));
            pcm[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        return pcm.buffer;
    }

    function handleVoiceTranscript(text) {
        if (!text) return;
        messageInput.value = text;
        messageInput.style.height = 'auto';
        messageInput.style.height = (messageInput.scrollHeight) + 'px';
        sendBtn.toggleAttribute('disabled', messageInput.value.trim().length === 0);
    }

    function stopVoiceRecording(autoSubmit = false) {
        isRecordingVoice = false;
        micBtn.classList.remove('recording');
        if (voiceProcessor) { voiceProcessor.disconnect(); voiceProcessor = null; }
        if (voiceMicSource) { voiceMicSource.disconnect(); voiceMicSource = null; }
        if (voiceAudioCtx) { voiceAudioCtx.close(); voiceAudioCtx = null; }
        if (voiceSocket) { voiceSocket.close(); voiceSocket = null; }
        if (autoSubmit && messageInput.value.trim().length > 0) {
            chatForm.dispatchEvent(new Event('submit'));
        }
    }
});
