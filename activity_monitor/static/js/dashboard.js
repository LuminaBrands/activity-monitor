/* Activity Monitor Dashboard JavaScript */

// --- Date navigation ---
document.addEventListener('DOMContentLoaded', () => {
    const datePicker = document.getElementById('nav-date');
    if (datePicker) {
        const params = new URLSearchParams(window.location.search);
        const currentDate = params.get('date') || new Date().toISOString().split('T')[0];
        datePicker.value = currentDate;

        datePicker.addEventListener('change', (e) => {
            const date = e.target.value;
            const url = new URL(window.location);
            url.searchParams.set('date', date);
            window.location.href = url.toString();
        });
    }
});

function getCurrentDate() {
    const params = new URLSearchParams(window.location.search);
    return params.get('date') || new Date().toISOString().split('T')[0];
}

// --- Dashboard ---
async function loadDashboard(date) {
    try {
        const response = await fetch(`/api/activity/${date}`);
        const data = await response.json();
        renderStats(data.stats);
        renderTopApps(data.applications);
        renderComms(data.communications);
        renderScreenshots(data.screenshots);

        // Check for existing summary
        const summaryRes = await fetch(`/api/summary/${date}`);
        const summaryData = await summaryRes.json();
        if (summaryData.summary) {
            document.getElementById('summary-content').innerHTML = markdownToHtml(summaryData.summary);
        }
    } catch (err) {
        console.error('Failed to load dashboard:', err);
    }
}

function renderStats(stats) {
    if (!stats) return;
    setText('stat-active-minutes', stats.active_minutes || 0);
    setText('stat-keystrokes', formatNumber(stats.total_keystrokes || 0));
    setText('stat-apps', stats.app_count || 0);
    setText('stat-screenshots', stats.screenshot_count || 0);
    setText('stat-comms', stats.communication_sessions || 0);
}

function renderTopApps(apps) {
    const container = document.getElementById('top-apps');
    if (!container) return;

    if (!apps || apps.length === 0) {
        container.innerHTML = '<p class="placeholder">No application data yet.</p>';
        return;
    }

    container.innerHTML = apps.slice(0, 10).map(app => `
        <div class="app-item">
            <div>
                <span class="app-name">${escapeHtml(app.name)}</span>
                <span class="app-category">${escapeHtml(app.category || 'other')}</span>
            </div>
            <span class="app-time">${app.total_minutes} min</span>
        </div>
    `).join('');
}

function renderComms(comms) {
    const container = document.getElementById('recent-comms');
    if (!container) return;

    if (!comms || comms.length === 0) {
        container.innerHTML = '<p class="placeholder">No communication sessions yet.</p>';
        return;
    }

    container.innerHTML = comms.slice(0, 10).map(c => `
        <div class="comm-item">
            <div class="comm-app">${escapeHtml(c.application)}</div>
            <div class="comm-context">${escapeHtml(c.context || '')}</div>
            <div class="comm-time">${formatTime(c.timestamp)} - ${c.duration_minutes} min</div>
        </div>
    `).join('');
}

function renderScreenshots(screenshots) {
    const container = document.getElementById('screenshots-grid');
    if (!container) return;

    if (!screenshots || screenshots.length === 0) {
        container.innerHTML = '<p class="placeholder">No screenshots captured yet.</p>';
        return;
    }

    // Show last 8 screenshots
    container.innerHTML = screenshots.slice(-8).map(s => {
        const relativePath = s.file_path.split('screenshots/').pop();
        return `
            <div class="screenshot-item" onclick="showScreenshot('/screenshots/${escapeHtml(relativePath)}')">
                <img src="/screenshots/${escapeHtml(relativePath)}" alt="Screenshot" loading="lazy">
                <div class="screenshot-meta">
                    ${formatTime(s.timestamp)} - ${escapeHtml(s.active_app || '')}
                </div>
            </div>
        `;
    }).join('');
}

// --- Timeline ---
async function loadTimeline(date) {
    const container = document.getElementById('timeline');
    if (!container) return;

    try {
        const response = await fetch(`/api/timeline/${date}`);
        const events = await response.json();

        if (!events || events.length === 0) {
            container.innerHTML = '<p class="placeholder">No activity recorded for this date.</p>';
            return;
        }

        container.innerHTML = events.map(event => `
            <div class="timeline-event type-${event.type}">
                <div class="timeline-time">${formatTime(event.timestamp)}</div>
                <div class="timeline-title">${escapeHtml(event.title)}</div>
                <div class="timeline-detail">${escapeHtml(event.detail || '')}</div>
                ${event.duration_minutes ? `<span class="timeline-badge badge-${event.type}">${event.duration_minutes} min</span>` : ''}
                ${event.type === 'screenshot' ? `<span class="timeline-badge badge-screenshot">screenshot</span>` : ''}
            </div>
        `).join('');
    } catch (err) {
        container.innerHTML = '<p class="placeholder">Failed to load timeline.</p>';
        console.error('Failed to load timeline:', err);
    }
}

// --- Summary ---
async function loadSummary(date) {
    const container = document.getElementById('summary-content');
    if (!container) return;

    try {
        const response = await fetch(`/api/summary/${date}`);
        const data = await response.json();

        if (data.summary) {
            container.innerHTML = markdownToHtml(data.summary);
        } else {
            container.innerHTML = '<p class="placeholder">No summary generated yet. Click "Regenerate" to create one.</p>';
        }
    } catch (err) {
        container.innerHTML = '<p class="placeholder">Failed to load summary.</p>';
    }
}

async function generateSummary() {
    const date = getCurrentDate();
    const btn = document.getElementById('generate-summary-btn');
    const container = document.getElementById('summary-content');

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span>Generating...';
    }
    if (container) {
        container.innerHTML = '<p class="placeholder"><span class="spinner"></span>Generating AI summary... This may take a moment.</p>';
    }

    try {
        const response = await fetch(`/api/generate-summary/${date}`, { method: 'POST' });
        const data = await response.json();

        if (data.error) {
            container.innerHTML = `<p class="placeholder">Error: ${escapeHtml(data.error)}</p>`;
        } else if (data.summary) {
            container.innerHTML = markdownToHtml(data.summary);
        }
    } catch (err) {
        if (container) {
            container.innerHTML = '<p class="placeholder">Failed to generate summary. Check your API key configuration.</p>';
        }
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = 'Generate Summary';
        }
    }
}

async function generatePlan() {
    const btn = document.getElementById('generate-plan-btn');
    const container = document.getElementById('plan-content');

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span>Planning...';
    }
    if (container) {
        container.innerHTML = '<p class="placeholder"><span class="spinner"></span>Generating plan... This may take a moment.</p>';
    }

    try {
        const response = await fetch('/api/generate-plan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ days: 3 }),
        });
        const data = await response.json();

        if (data.error) {
            container.innerHTML = `<p class="placeholder">Error: ${escapeHtml(data.error)}</p>`;
        } else if (data.plan) {
            container.innerHTML = markdownToHtml(data.plan);
        }
    } catch (err) {
        if (container) {
            container.innerHTML = '<p class="placeholder">Failed to generate plan. Check your API key configuration.</p>';
        }
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = 'Generate Plan';
        }
    }
}

// --- Chat History ---
async function loadChatHistory(date) {
    try {
        const response = await fetch(`/api/chat-history/${date}`);
        const data = await response.json();

        // Render stats
        setText('chat-stat-sessions', data.stats.total_sessions || 0);
        setText('chat-stat-total-time', data.stats.total_minutes || 0);
        setText('chat-stat-apps', data.stats.unique_apps || 0);

        // Render by-app breakdown
        renderChatByApp(data.by_app);

        // Render conversations recap
        renderConversationsRecap(data.conversations_recap);

        // Render full list
        renderChatHistoryList(data.communications);
    } catch (err) {
        console.error('Failed to load chat history:', err);
    }
}

function renderChatByApp(apps) {
    const container = document.getElementById('chat-by-app');
    if (!container) return;

    if (!apps || apps.length === 0) {
        container.innerHTML = '<p class="placeholder">No communication apps used today.</p>';
        return;
    }

    container.innerHTML = apps.map(app => `
        <div class="app-item">
            <div>
                <span class="app-name">${escapeHtml(app.name)}</span>
                <span class="app-category">${app.sessions} session${app.sessions !== 1 ? 's' : ''}</span>
            </div>
            <span class="app-time">${app.total_minutes} min</span>
        </div>
    `).join('');
}

function renderConversationsRecap(recap) {
    const container = document.getElementById('chat-conversations-recap');
    if (!container) return;

    if (!recap) {
        container.innerHTML = '<p class="placeholder">Generate a summary from the Summary page to see an AI recap of your conversations.</p>';
        return;
    }

    container.innerHTML = markdownToHtml(recap);
}

function renderChatHistoryList(comms) {
    const container = document.getElementById('chat-history-list');
    if (!container) return;

    if (!comms || comms.length === 0) {
        container.innerHTML = '<p class="placeholder">No communication sessions recorded for this date.</p>';
        return;
    }

    container.innerHTML = comms.map(c => `
        <div class="chat-history-item">
            <div class="chat-history-app">${escapeHtml(c.application)}</div>
            <div class="chat-history-context">${escapeHtml(c.context || 'No context available')}</div>
            <div class="chat-history-meta">
                <span class="chat-history-time">${formatTime(c.timestamp)}</span>
                <span class="chat-history-duration">${c.duration_minutes} min</span>
            </div>
        </div>
    `).join('');
}

// --- Setup Status (Dashboard) ---
async function loadSetupStatus() {
    const section = document.getElementById('setup-section');
    if (!section) return;

    try {
        const response = await fetch('/api/setup-status');
        const data = await response.json();

        // Show setup section if anything is not configured
        const dismissed = localStorage.getItem('setup-dismissed');
        if (dismissed && data.api_key_configured && data.database_exists) {
            section.style.display = 'none';
            renderMonitorBar(data.monitors);
            return;
        }

        section.style.display = 'block';

        // Permissions step
        const permIcon = document.getElementById('step-permissions-icon');
        const permDetail = document.getElementById('permissions-detail');
        const permPanel = document.getElementById('permissions-panel');

        if (data.permissions.length > 0) {
            const allSatisfied = data.permissions.every(p => p.satisfied !== false);
            permIcon.innerHTML = allSatisfied ? '&#9745;' : '&#9744;';
            permIcon.className = 'step-icon ' + (allSatisfied ? 'step-done' : '');
            permDetail.textContent = `Platform: ${data.platform}. ${allSatisfied ? 'Permissions look good.' : 'Some permissions may need to be granted.'}`;

            permPanel.style.display = 'block';
            document.getElementById('permissions-list').innerHTML = data.permissions.map(p => `
                <div class="permission-item ${p.satisfied === false ? 'permission-needed' : ''}">
                    <div class="permission-name">${escapeHtml(p.name)} ${p.satisfied !== undefined ? (p.satisfied ? '<span class="perm-ok">OK</span>' : '<span class="perm-missing">Needed</span>') : ''}</div>
                    <div class="permission-desc">${escapeHtml(p.description)}</div>
                    <div class="permission-how">${escapeHtml(p.how)}</div>
                    <div class="permission-for">Required for: ${p.required_for.join(', ')}</div>
                </div>
            `).join('');
        } else {
            permIcon.innerHTML = '&#9745;';
            permIcon.className = 'step-icon step-done';
            permDetail.textContent = 'No special permissions needed.';
        }

        // API key step
        const apiIcon = document.getElementById('step-api-key-icon');
        if (data.api_key_configured) {
            apiIcon.innerHTML = '&#9745;';
            apiIcon.className = 'step-icon step-done';
        }

        // Monitors step
        const monIcon = document.getElementById('step-monitors-icon');
        const anyEnabled = Object.values(data.monitors).some(v => v);
        if (anyEnabled) {
            monIcon.innerHTML = '&#9745;';
            monIcon.className = 'step-icon step-done';
        }

        // Start step
        const startIcon = document.getElementById('step-start-icon');
        if (data.database_exists) {
            startIcon.innerHTML = '&#9745;';
            startIcon.className = 'step-icon step-done';
        }

        // Monitor bar
        renderMonitorBar(data.monitors);
    } catch (err) {
        console.error('Failed to load setup status:', err);
        section.style.display = 'none';
    }
}

function renderMonitorBar(monitors) {
    if (!monitors) return;
    for (const [key, enabled] of Object.entries(monitors)) {
        const dot = document.getElementById(`dot-${key}`);
        if (dot) {
            dot.className = 'monitor-dot ' + (enabled ? 'dot-enabled' : 'dot-disabled');
        }
    }
}

function dismissSetup() {
    localStorage.setItem('setup-dismissed', 'true');
    const section = document.getElementById('setup-section');
    if (section) section.style.display = 'none';
}

// --- Settings Page ---
async function loadSettings() {
    try {
        const [configRes, statusRes] = await Promise.all([
            fetch('/api/config'),
            fetch('/api/setup-status'),
        ]);
        const config = await configRes.json();
        const status = await statusRes.json();

        // Platform and permissions
        const platformEl = document.getElementById('settings-platform');
        if (platformEl) {
            platformEl.textContent = `Detected platform: ${status.platform}`;
        }

        const permList = document.getElementById('settings-permissions');
        if (permList && status.permissions.length > 0) {
            permList.innerHTML = status.permissions.map(p => `
                <div class="permission-item ${p.satisfied === false ? 'permission-needed' : ''}">
                    <div class="permission-name">${escapeHtml(p.name)} ${p.satisfied !== undefined ? (p.satisfied ? '<span class="perm-ok">OK</span>' : '<span class="perm-missing">Needed</span>') : ''}</div>
                    <div class="permission-desc">${escapeHtml(p.description)}</div>
                    <div class="permission-how">${escapeHtml(p.how)}</div>
                    <div class="permission-for">Required for: ${p.required_for.join(', ')}</div>
                </div>
            `).join('');
        } else if (permList) {
            permList.innerHTML = '<p class="placeholder">No special permissions needed on this platform.</p>';
        }

        // API key status
        const apiStatus = document.getElementById('api-key-status');
        if (apiStatus) {
            apiStatus.textContent = config.analysis.anthropic_api_key_set
                ? 'API key is configured.'
                : 'No API key configured yet.';
            apiStatus.className = 'settings-field-status ' + (config.analysis.anthropic_api_key_set ? 'status-ok' : 'status-warn');
        }

        // Model select
        const modelSelect = document.getElementById('model-select');
        if (modelSelect) {
            modelSelect.value = config.analysis.model || 'claude-sonnet-4-6';
        }

        // Monitor toggles
        setToggle('toggle-keyboard', config.monitoring.keyboard.enabled);
        setToggle('toggle-applications', config.monitoring.applications.enabled);
        setToggle('toggle-screenshots', config.monitoring.screenshots.enabled);
        setToggle('toggle-communications', config.monitoring.communications.enabled);

        // Screenshot settings
        const ssInterval = document.getElementById('screenshot-interval');
        if (ssInterval) ssInterval.value = config.monitoring.screenshots.interval_seconds;

        const ssQuality = document.getElementById('screenshot-quality');
        if (ssQuality) ssQuality.value = config.monitoring.screenshots.quality;

        const ssStorage = document.getElementById('screenshot-storage');
        if (ssStorage) ssStorage.value = config.monitoring.screenshots.max_storage_gb;

    } catch (err) {
        console.error('Failed to load settings:', err);
    }
}

function setToggle(id, value) {
    const el = document.getElementById(id);
    if (el) el.checked = value;
}

function toggleApiKeyVisibility() {
    const input = document.getElementById('api-key-input');
    if (!input) return;
    input.type = input.type === 'password' ? 'text' : 'password';
}

async function saveSettings() {
    const btn = document.getElementById('save-settings-btn');
    const status = document.getElementById('save-status');

    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Saving...';
    }

    const apiKey = document.getElementById('api-key-input')?.value || '';
    const model = document.getElementById('model-select')?.value || 'claude-sonnet-4-6';

    const config = {
        monitoring: {
            keyboard: {
                enabled: document.getElementById('toggle-keyboard')?.checked ?? true,
            },
            applications: {
                enabled: document.getElementById('toggle-applications')?.checked ?? true,
            },
            screenshots: {
                enabled: document.getElementById('toggle-screenshots')?.checked ?? true,
                interval_seconds: parseInt(document.getElementById('screenshot-interval')?.value || '300'),
                quality: parseInt(document.getElementById('screenshot-quality')?.value || '50'),
                max_storage_gb: parseInt(document.getElementById('screenshot-storage')?.value || '5'),
            },
            communications: {
                enabled: document.getElementById('toggle-communications')?.checked ?? true,
            },
        },
        analysis: {
            model: model,
        },
    };

    // Only include API key if user entered one
    if (apiKey) {
        config.analysis.anthropic_api_key = apiKey;
    }

    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config),
        });
        const result = await response.json();

        if (result.error) {
            if (status) {
                status.textContent = 'Error: ' + result.error;
                status.className = 'settings-save-status status-error';
            }
        } else {
            if (status) {
                status.textContent = 'Settings saved. Restart the monitor to apply changes.';
                status.className = 'settings-save-status status-ok';
            }
            // Reload settings to reflect saved state
            loadSettings();
        }
    } catch (err) {
        if (status) {
            status.textContent = 'Failed to save settings.';
            status.className = 'settings-save-status status-error';
        }
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Save Settings';
        }
    }
}

// --- Screenshot modal ---
function showScreenshot(src) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.onclick = () => overlay.remove();
    overlay.innerHTML = `<img src="${src}" alt="Screenshot">`;
    document.body.appendChild(overlay);
}

// --- Utilities ---
function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function formatNumber(n) {
    return n.toLocaleString();
}

function formatTime(isoString) {
    if (!isoString) return '';
    try {
        const d = new Date(isoString);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
        return isoString.substring(11, 16);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function markdownToHtml(md) {
    if (!md) return '';
    // Simple markdown to HTML conversion
    let html = md
        // Code blocks
        .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
        // Headers
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        // Bold and italic
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        // Lists
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        .replace(/^(\d+)\. (.+)$/gm, '<li>$2</li>')
        // Paragraphs
        .replace(/\n\n/g, '</p><p>')
        // Line breaks
        .replace(/\n/g, '<br>');

    // Wrap consecutive <li> tags in <ul>
    html = html.replace(/(<li>.*?<\/li>(?:<br>)?)+/g, (match) => {
        return '<ul>' + match.replace(/<br>/g, '') + '</ul>';
    });

    return '<p>' + html + '</p>';
}
