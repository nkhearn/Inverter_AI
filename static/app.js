document.addEventListener('DOMContentLoaded', () => {
    // Tab switching
    const navItems = document.querySelectorAll('.nav-item');
    const tabContents = document.querySelectorAll('.tab-content');

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const tabId = item.getAttribute('data-tab');
            navItems.forEach(n => n.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            item.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        });
    });

    // Load saved settings on load
    loadSettings();
    checkHealth();

    // Form handlers
    document.getElementById('settings-form').addEventListener('submit', handleSaveSettings);
    document.getElementById('query-form').addEventListener('submit', handleQuerySubmit);
    document.getElementById('primary-provider').addEventListener('change', () => {
        updateActiveProviderLabel();
        toggleGoogleAuthSection();
    });
    document.getElementById('google-auth-type').addEventListener('change', toggleGoogleAuthSection);
    document.getElementById('google-signin-btn').addEventListener('click', handleGoogleSignIn);
});

function getSettings() {
    return {
        provider: localStorage.getItem('inv_provider') || 'google',
        googleAuthType: localStorage.getItem('inv_google_auth_type') || 'api_key',
        googleClientId: localStorage.getItem('inv_google_client_id') || '',
        googleAccessToken: localStorage.getItem('inv_google_access_token') || '',
        geminiKeys: parseKeys(localStorage.getItem('inv_gemini_keys') || ''),
        groqKeys: parseKeys(localStorage.getItem('inv_groq_keys') || ''),
        openrouterKeys: parseKeys(localStorage.getItem('inv_openrouter_keys') || ''),
        openaiKeys: parseKeys(localStorage.getItem('inv_openai_keys') || ''),
        mcpUrl: localStorage.getItem('inv_mcp_url') || 'http://127.0.0.1:8000/mcp'
    };
}

function parseKeys(str) {
    return str.split('\n').map(k => k.trim()).filter(k => k.length > 0);
}

function loadSettings() {
    const settings = getSettings();
    document.getElementById('primary-provider').value = settings.provider;
    document.getElementById('google-auth-type').value = settings.googleAuthType;
    document.getElementById('google-client-id').value = settings.googleClientId;
    document.getElementById('google-access-token').value = settings.googleAccessToken;
    document.getElementById('gemini-keys').value = (settings.geminiKeys || []).join('\n');
    document.getElementById('groq-keys').value = (settings.groqKeys || []).join('\n');
    document.getElementById('openrouter-keys').value = (settings.openrouterKeys || []).join('\n');
    document.getElementById('openai-keys').value = (settings.openaiKeys || []).join('\n');
    document.getElementById('mcp-server-url').value = settings.mcpUrl;

    updateActiveProviderLabel();
    toggleGoogleAuthSection();
}

function toggleGoogleAuthSection() {
    const provider = document.getElementById('primary-provider').value;
    const authType = document.getElementById('google-auth-type').value;

    const keyGroup = document.getElementById('google-api-key-group');
    const oauthGroup = document.getElementById('google-oauth-group');

    if (provider === 'google') {
        if (authType === 'oauth') {
            keyGroup.style.display = 'none';
            oauthGroup.style.display = 'block';
        } else {
            keyGroup.style.display = 'block';
            oauthGroup.style.display = 'none';
        }
    } else {
        keyGroup.style.display = 'block';
        oauthGroup.style.display = 'none';
    }
}

function handleGoogleSignIn() {
    const clientId = document.getElementById('google-client-id').value.trim();
    if (!clientId) {
        alert('Please enter a Google OAuth Client ID in the field above before signing in.');
        return;
    }

    if (typeof google === 'undefined' || !google.accounts || !google.accounts.oauth2) {
        alert('Google Identity Services script failed to load. Please check your internet connection or enter an access token manually.');
        return;
    }

    const tokenClient = google.accounts.oauth2.initTokenClient({
        client_id: clientId,
        scope: 'https://www.googleapis.com/auth/generative-language',
        callback: (tokenResponse) => {
            if (tokenResponse && tokenResponse.access_token) {
                document.getElementById('google-access-token').value = tokenResponse.access_token;
                localStorage.setItem('inv_google_access_token', tokenResponse.access_token);

                const saveStatus = document.getElementById('save-status');
                saveStatus.innerText = '✓ Signed in with Google! Access token retrieved.';
                setTimeout(() => { saveStatus.innerText = ''; }, 4000);
            } else if (tokenResponse && tokenResponse.error) {
                alert('Google Sign-In Error: ' + tokenResponse.error);
            }
        },
    });

    tokenClient.requestAccessToken();
}

function updateActiveProviderLabel() {
    const providerMap = {
        google: 'Google AI Studio',
        groq: 'GroqCloud',
        openrouter: 'OpenRouter',
        openai: 'OpenAI',
        mock: 'Mock Engine'
    };
    const val = document.getElementById('primary-provider').value;
    document.getElementById('active-provider-label').innerText = providerMap[val] || val;
}

function handleSaveSettings(e) {
    e.preventDefault();
    const provider = document.getElementById('primary-provider').value;
    const googleAuthType = document.getElementById('google-auth-type').value;
    const googleClientId = document.getElementById('google-client-id').value;
    const googleAccessToken = document.getElementById('google-access-token').value;
    const geminiKeys = document.getElementById('gemini-keys').value;
    const groqKeys = document.getElementById('groq-keys').value;
    const openrouterKeys = document.getElementById('openrouter-keys').value;
    const openaiKeys = document.getElementById('openai-keys').value;
    const mcpUrl = document.getElementById('mcp-server-url').value;

    localStorage.setItem('inv_provider', provider);
    localStorage.setItem('inv_google_auth_type', googleAuthType);
    localStorage.setItem('inv_google_client_id', googleClientId);
    localStorage.setItem('inv_google_access_token', googleAccessToken);
    localStorage.setItem('inv_gemini_keys', geminiKeys);
    localStorage.setItem('inv_groq_keys', groqKeys);
    localStorage.setItem('inv_openrouter_keys', openrouterKeys);
    localStorage.setItem('inv_openai_keys', openaiKeys);
    localStorage.setItem('inv_mcp_url', mcpUrl);

    updateActiveProviderLabel();

    const saveStatus = document.getElementById('save-status');
    saveStatus.innerText = '✓ Settings saved to local storage!';
    setTimeout(() => { saveStatus.innerText = ''; }, 3000);
}

async function checkHealth() {
    try {
        const res = await fetch('/api/health');
        const data = await res.json();
        const dot = document.getElementById('mcp-dot');
        const urlDisplay = document.getElementById('mcp-url-display');

        if (data.mcp_server === 'running') {
            dot.classList.add('online');
            urlDisplay.innerText = data.mcp_url;
        } else {
            dot.classList.remove('online');
            urlDisplay.innerText = `${data.mcp_url} (${data.mcp_server})`;
        }
    } catch (err) {
        console.error('Health check failed', err);
    }
}

async function handleQuerySubmit(e) {
    e.preventDefault();
    const inputEl = document.getElementById('user-input');
    const promptText = inputEl.value.trim();
    if (!promptText) return;

    inputEl.value = '';

    // Append user message
    appendUserMessage(promptText);

    // Append loading assistant message
    const assistantMsgId = appendAssistantLoadingMessage();

    // Gather settings
    const settings = getSettings();
    let keys = [];
    if (settings.provider === 'google') keys = settings.geminiKeys;
    else if (settings.provider === 'groq') keys = settings.groqKeys;
    else if (settings.provider === 'openrouter') keys = settings.openrouterKeys;
    else if (settings.provider === 'openai') keys = settings.openaiKeys;

    try {
        const payload = {
            prompt: promptText,
            provider: settings.provider,
            auth_type: settings.provider === 'google' ? settings.googleAuthType : 'api_key',
            access_token: settings.googleAccessToken,
            api_keys: keys,
            mcp_url: settings.mcpUrl
        };

        const response = await fetch('/api/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Error processing query');
        }

        renderAssistantResponse(assistantMsgId, data);
    } catch (err) {
        renderAssistantError(assistantMsgId, err.message);
    }
}

function appendUserMessage(text) {
    const container = document.getElementById('chat-messages');
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message user-message';
    msgDiv.innerHTML = `<div class="message-content">${escapeHtml(text)}</div>`;
    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
}

function appendAssistantLoadingMessage() {
    const container = document.getElementById('chat-messages');
    const msgId = 'msg-' + Date.now();
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message assistant-message';
    msgDiv.id = msgId;
    msgDiv.innerHTML = `<div class="message-content">⏳ <em>Analyzing database schema and querying via MCP...</em></div>`;
    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
    return msgId;
}

function renderAssistantResponse(msgId, data) {
    const msgDiv = document.getElementById(msgId);
    if (!msgDiv) return;

    let html = `<div class="message-content">`;
    html += `<div>${escapeHtml(data.summary)}</div>`;

    if (data.sql_query) {
        html += `
            <div class="sql-box">
                <div class="sql-title">Executed MCP SQL Query</div>
                <div class="sql-code">${escapeHtml(data.sql_query)}</div>
            </div>
        `;
    }

    if (data.query_results && data.query_results.length > 0) {
        html += `
            <details class="results-details">
                <summary>View SQL Results (${data.query_results.length} rows)</summary>
                <div class="results-table-container">
                    ${buildTableHtml(data.query_results)}
                </div>
            </details>
        `;
    }

    html += `</div>`;
    msgDiv.innerHTML = html;

    const container = document.getElementById('chat-messages');
    container.scrollTop = container.scrollHeight;
}

function renderAssistantError(msgId, errorMsg) {
    const msgDiv = document.getElementById(msgId);
    if (!msgDiv) return;

    msgDiv.innerHTML = `
        <div class="message-content" style="border-color: var(--danger);">
            ❌ <strong>Error:</strong> ${escapeHtml(errorMsg)}
        </div>
    `;
}

function buildTableHtml(rows) {
    if (!rows || rows.length === 0) return '<p>No rows returned.</p>';
    const keys = Object.keys(rows[0]);

    let table = '<table><thead><tr>';
    keys.forEach(k => { table += `<th>${escapeHtml(k)}</th>`; });
    table += '</tr></thead><tbody>';

    rows.slice(0, 20).forEach(r => {
        table += '<tr>';
        keys.forEach(k => {
            const val = r[k] !== null && r[k] !== undefined ? r[k] : '';
            table += `<td>${escapeHtml(String(val))}</td>`;
        });
        table += '</tr>';
    });

    table += '</tbody></table>';
    if (rows.length > 20) {
        table += `<p style="font-size: 0.75rem; margin-top: 0.25rem; color: var(--text-secondary);">Showing first 20 of ${rows.length} rows.</p>`;
    }
    return table;
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
