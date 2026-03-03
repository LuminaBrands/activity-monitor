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
