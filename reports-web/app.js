// EMSN Reports Web Interface
let allReports = [];
let currentFilter = 'all';
let availableStyles = [];

// API configuration - direct connection to Pi for POST requests (NAS proxy blocks POST)
const PI_API_BASE = 'http://192.168.1.178:8081';

// Detect if we're accessing via the NAS proxy
function isViaProxy() {
    return window.location.hostname === '192.168.1.25';
}

// Get the correct API URL - use direct Pi connection for POST-requiring endpoints
function getApiUrl(endpoint, requiresPost = false) {
    if (requiresPost && isViaProxy()) {
        // NAS proxy blocks POST, so go directly to Pi
        return `${PI_API_BASE}/${endpoint}`;
    }
    // Use relative URL (works for both direct and proxy access)
    return endpoint;
}

// Load reports on page load
document.addEventListener('DOMContentLoaded', () => {
    loadReports();
    setupFilters();
    setupTabs();
    loadStyles();
    setupGenerator();
    setupEmailManagement();
    setupScheduleTab();
});

async function loadReports() {
    try {
        const response = await fetch('reports.json');
        if (!response.ok) {
            throw new Error('Failed to load reports');
        }

        const data = await response.json();
        allReports = data.reports;

        displayReports(allReports);
    } catch (error) {
        console.error('Error loading reports:', error);
        showError('Kon rapporten niet laden. Probeer de pagina te verversen.');
    }
}

function setupFilters() {
    const filterButtons = document.querySelectorAll('.filter-btn');

    filterButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            // Update active state
            filterButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Apply filter
            currentFilter = btn.dataset.filter;
            filterReports();
        });
    });
}

function filterReports() {
    const cards = document.querySelectorAll('.report-card');
    const sections = document.querySelectorAll('.report-section');

    cards.forEach(card => {
        const type = card.dataset.type;

        if (currentFilter === 'all' || currentFilter === type) {
            card.classList.remove('hidden');
        } else {
            card.classList.add('hidden');
        }
    });

    // Hide empty sections
    sections.forEach(section => {
        const visibleCards = section.querySelectorAll('.report-card:not(.hidden)');
        section.style.display = visibleCards.length === 0 ? 'none' : 'block';
    });
}

function displayReports(reports) {
    const container = document.getElementById('reports-list');

    if (reports.length === 0) {
        container.innerHTML = '<div class="error">Geen rapporten gevonden</div>';
        return;
    }

    // Group reports by category
    const periodieke = reports.filter(r => ['week', 'month', 'season', 'year'].includes(r.type));
    const soorten = reports.filter(r => r.type === 'species');

    // Sort each group by generated date (newest first)
    const sortByDate = (a, b) => {
        const dateA = new Date(a.generated || a.modified);
        const dateB = new Date(b.generated || b.modified);
        return dateB - dateA;
    };

    periodieke.sort(sortByDate);
    soorten.sort(sortByDate);

    // Build HTML with section headers
    let html = '';

    if (periodieke.length > 0) {
        html += '<div class="report-section"><h3 class="section-header">Periodieke Rapporten</h3>';
        html += '<div class="reports-grid">';
        html += periodieke.map(report => createReportCard(report)).join('');
        html += '</div></div>';
    }

    if (soorten.length > 0) {
        html += '<div class="report-section"><h3 class="section-header">Soort Rapporten</h3>';
        html += '<div class="reports-grid">';
        html += soorten.map(report => createReportCard(report)).join('');
        html += '</div></div>';
    }

    container.innerHTML = html;
}

function createReportCard(report) {
    const detections = report.total_detections ? report.total_detections.toLocaleString('nl-NL') : 'N/A';
    const species = report.unique_species || 'N/A';
    const period = report.period || '';

    const typeLabels = {
        'week': 'Wekelijks',
        'month': 'Maandelijks',
        'season': 'Seizoen',
        'year': 'Jaarlijks',
        'species': 'Soort'
    };
    const typeLabel = typeLabels[report.type] || report.type;

    // Format generated date
    const genDate = report.generated ? new Date(report.generated) : null;
    const dateStr = genDate ? genDate.toLocaleDateString('nl-NL', {
        day: 'numeric',
        month: 'short',
        year: 'numeric'
    }) : '';

    // Check if report is new (less than 24 hours old AND not yet read)
    const readReports = JSON.parse(localStorage.getItem('readReports') || '[]');
    const isUnread = !readReports.includes(report.filename);
    const isNew = genDate && (Date.now() - genDate.getTime()) < 24 * 60 * 60 * 1000 && isUnread;

    return `
        <div class="report-card" data-type="${report.type}">
            <div class="report-header">
                <span class="report-type ${report.type}">
                    ${typeLabel}
                </span>
                ${isNew ? '<span class="badge-new">Nieuw</span>' : ''}
            </div>

            <h2 class="report-title">
                ${report.year} - ${report.title}
            </h2>

            <p class="report-period">${period || dateStr}</p>

            <div class="report-stats">
                <div class="stat">
                    <div class="stat-value">${detections}</div>
                    <div class="stat-label">Detecties</div>
                </div>
                <div class="stat">
                    <div class="stat-value">${species}</div>
                    <div class="stat-label">Soorten</div>
                </div>
            </div>

            <div class="report-actions">
                <a href="view-interactive.html?report=${encodeURIComponent(report.filename)}" class="btn btn-primary" title="Interactieve versie met grafieken">
                    Interactief
                </a>
                <a href="view.html?report=${encodeURIComponent(report.filename)}" class="btn btn-secondary" title="Volledige tekst versie">
                    Tekst
                </a>
                <a href="api/pdf?file=${encodeURIComponent(report.filename)}" class="btn btn-secondary" download title="Download als PDF">
                    PDF
                </a>
            </div>
        </div>
    `;
}

function showError(message) {
    const container = document.getElementById('reports-list');
    container.innerHTML = `<div class="error">${message}</div>`;
}

// Tab navigation
function setupTabs() {
    const tabButtons = document.querySelectorAll('.main-tab');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.tab;

            // Update button states
            tabButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Update content visibility
            tabContents.forEach(content => {
                content.classList.remove('active');
            });
            document.getElementById(`${tabId}-tab`).classList.add('active');
        });
    });
}

// Load available writing styles
async function loadStyles() {
    try {
        const response = await fetch('api/styles');
        if (!response.ok) throw new Error('Failed to load styles');

        const data = await response.json();
        availableStyles = data.styles;

        const select = document.getElementById('style-select');
        select.innerHTML = availableStyles.map(style =>
            `<option value="${style.id}" ${style.id === data.default ? 'selected' : ''}>
                ${style.name}
            </option>`
        ).join('');

        // Show description for default style
        updateStyleDescription();

        // Update description on change
        select.addEventListener('change', updateStyleDescription);
    } catch (error) {
        console.error('Error loading styles:', error);
    }
}

function updateStyleDescription() {
    const select = document.getElementById('style-select');
    const descriptionEl = document.getElementById('style-description');
    const selectedStyle = availableStyles.find(s => s.id === select.value);

    if (selectedStyle) {
        descriptionEl.textContent = selectedStyle.description;
    } else {
        descriptionEl.textContent = '';
    }
}

// Setup generator form
function setupGenerator() {
    const reportTypeSelect = document.getElementById('report-type');
    const form = document.getElementById('generate-form');

    // Show/hide options based on report type
    reportTypeSelect.addEventListener('change', () => {
        const type = reportTypeSelect.value;

        // Hide all option groups
        document.getElementById('season-options').classList.add('hidden');
        document.getElementById('year-options').classList.add('hidden');
        document.getElementById('species-options').classList.add('hidden');

        // Show relevant options
        if (type === 'season') {
            document.getElementById('season-options').classList.remove('hidden');
        } else if (type === 'year') {
            document.getElementById('year-options').classList.remove('hidden');
        } else if (type === 'species') {
            document.getElementById('species-options').classList.remove('hidden');
            loadSpeciesList();
        }
    });

    // Handle form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        await generateReport();
    });
}

// Load species list for species report
async function loadSpeciesList() {
    const select = document.getElementById('species-select');

    try {
        const response = await fetch('api/species');
        if (!response.ok) throw new Error('Failed to load species');

        const data = await response.json();
        select.innerHTML = '<option value="">Selecteer een soort...</option>' +
            data.species.map(s =>
                `<option value="${s.common_name}">${s.common_name} (${s.total_detections.toLocaleString('nl-NL')} detecties)</option>`
            ).join('');
    } catch (error) {
        console.error('Error loading species:', error);
        select.innerHTML = '<option value="">Fout bij laden soorten</option>';
    }
}

// Generate report
async function generateReport() {
    const form = document.getElementById('generate-form');
    const progress = document.getElementById('generation-progress');
    const result = document.getElementById('generation-result');
    const generateBtn = document.getElementById('generate-btn');

    // Get form values
    const reportType = document.getElementById('report-type').value;
    const style = document.getElementById('style-select').value;

    // Build request body
    const body = {
        type: reportType,
        style: style
    };

    // Add type-specific options
    if (reportType === 'season') {
        const season = document.getElementById('season-select').value;
        const year = document.getElementById('season-year').value;
        if (season) body.season = season;
        if (year) body.year = parseInt(year);
    } else if (reportType === 'year') {
        const year = document.getElementById('year-select').value;
        if (year) body.year = parseInt(year);
    } else if (reportType === 'species') {
        body.species = document.getElementById('species-select').value;
        if (!body.species) {
            alert('Selecteer een vogelsoort');
            return;
        }
    }

    // Show progress
    form.classList.add('hidden');
    progress.classList.remove('hidden');
    result.classList.add('hidden');
    generateBtn.disabled = true;

    try {
        const response = await fetch(getApiUrl('api/generate', true), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(body)
        });

        const data = await response.json();

        // Hide progress
        progress.classList.add('hidden');

        // Show result
        result.classList.remove('hidden');
        result.classList.remove('success', 'error');

        if (data.success) {
            result.classList.add('success');
            result.querySelector('.result-message').textContent = 'Rapport succesvol gegenereerd';

            // Refresh reports list
            await loadReports();

            // Show link to view reports
            const link = document.getElementById('result-link');
            link.classList.remove('hidden');
            link.onclick = () => {
                // Switch to reports tab
                document.querySelector('.main-tab[data-tab="reports"]').click();
                result.classList.add('hidden');
                form.classList.remove('hidden');
            };
            link.textContent = 'Bekijk rapporten';
        } else {
            result.classList.add('error');
            result.querySelector('.result-message').textContent =
                data.error || 'Er is een fout opgetreden';
            document.getElementById('result-link').classList.add('hidden');
        }
    } catch (error) {
        console.error('Error generating report:', error);
        progress.classList.add('hidden');
        result.classList.remove('hidden');
        result.classList.add('error');
        result.querySelector('.result-message').textContent =
            'Netwerkfout: ' + error.message;
        document.getElementById('result-link').classList.add('hidden');
    }

    generateBtn.disabled = false;

    // Add button to try again
    setTimeout(() => {
        if (!result.classList.contains('hidden')) {
            const retryBtn = document.createElement('button');
            retryBtn.className = 'btn btn-primary';
            retryBtn.textContent = 'Opnieuw proberen';
            retryBtn.onclick = () => {
                result.classList.add('hidden');
                form.classList.remove('hidden');
            };
            if (!result.querySelector('.retry-btn')) {
                retryBtn.classList.add('retry-btn');
                result.appendChild(retryBtn);
            }
        }
    }, 100);
}

// =============================================================================
// EMAIL MANAGEMENT
// =============================================================================

let emailRecipients = [];

function setupEmailManagement() {
    // Setup add recipient form
    const addForm = document.getElementById('add-recipient-form');
    if (addForm) {
        addForm.addEventListener('submit', handleAddRecipient);
    }

    // Setup send copy form
    const sendCopyForm = document.getElementById('send-copy-form');
    if (sendCopyForm) {
        sendCopyForm.addEventListener('submit', handleSendCopy);
    }

    // Setup test email form
    const testForm = document.getElementById('test-email-form');
    if (testForm) {
        testForm.addEventListener('submit', handleTestEmail);
    }

    // Load data when email tab is shown
    document.querySelectorAll('.main-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            if (tab.dataset.tab === 'email') {
                loadEmailRecipients();
                loadReportsForCopy();
            }
        });
    });
}

async function loadEmailRecipients() {
    const container = document.getElementById('recipients-list');
    container.innerHTML = '<div class="loading">Laden...</div>';

    try {
        const response = await fetch(getApiUrl('api/email/recipients', false));
        const data = await response.json();

        if (data.error) {
            container.innerHTML = `<div class="error">${data.error}</div>`;
            return;
        }

        emailRecipients = data.recipients || [];
        renderRecipientsList();
        updateCopyRecipients();

    } catch (error) {
        console.error('Error loading recipients:', error);
        container.innerHTML = '<div class="error">Kon ontvangers niet laden</div>';
    }
}

function renderRecipientsList() {
    const container = document.getElementById('recipients-list');

    if (emailRecipients.length === 0) {
        container.innerHTML = '<p class="no-data">Geen ontvangers geconfigureerd</p>';
        return;
    }

    const modeLabels = {
        'auto': 'Automatisch',
        'manual': 'Handmatig'
    };

    const typeLabels = {
        'weekly': 'Week',
        'monthly': 'Maand',
        'seasonal': 'Seizoen',
        'yearly': 'Jaar'
    };

    let html = '<table class="recipients-table"><thead><tr>';
    html += '<th>E-mailadres</th><th>Naam</th><th>Modus</th><th>Rapporttypes</th><th>Acties</th>';
    html += '</tr></thead><tbody>';

    emailRecipients.forEach(r => {
        const types = (r.report_types || []).map(t => typeLabels[t] || t).join(', ');
        html += `<tr>
            <td>${escapeHtml(r.email)}</td>
            <td>${escapeHtml(r.name || '-')}</td>
            <td><span class="mode-badge ${r.mode}">${modeLabels[r.mode] || r.mode}</span></td>
            <td>${r.mode === 'auto' ? types : '-'}</td>
            <td>
                <button class="btn btn-small btn-danger" onclick="deleteRecipient('${escapeHtml(r.email)}')">Verwijderen</button>
            </td>
        </tr>`;
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;');
}

async function handleAddRecipient(e) {
    e.preventDefault();

    const email = document.getElementById('recipient-email').value.trim();
    const name = document.getElementById('recipient-name').value.trim();
    const mode = document.getElementById('recipient-mode').value;

    // Get selected report types
    const reportTypes = [];
    document.querySelectorAll('input[name="report-type"]:checked').forEach(cb => {
        reportTypes.push(cb.value);
    });

    try {
        const response = await fetch(getApiUrl('api/email/recipients', true), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email,
                name,
                mode,
                report_types: reportTypes
            })
        });

        const data = await response.json();

        if (data.success) {
            // Clear form
            document.getElementById('recipient-email').value = '';
            document.getElementById('recipient-name').value = '';
            document.getElementById('recipient-mode').value = 'auto';
            document.querySelectorAll('input[name="report-type"]').forEach(cb => cb.checked = true);

            // Reload list
            await loadEmailRecipients();
            alert(data.message);
        } else {
            alert('Fout: ' + (data.error || 'Onbekende fout'));
        }
    } catch (error) {
        console.error('Error adding recipient:', error);
        alert('Fout bij toevoegen: ' + error.message);
    }
}

async function deleteRecipient(email) {
    if (!confirm(`Weet je zeker dat je ${email} wilt verwijderen?`)) {
        return;
    }

    try {
        const response = await fetch(getApiUrl(`api/email/recipients/${encodeURIComponent(email)}`, true), {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            await loadEmailRecipients();
        } else {
            alert('Fout: ' + (data.error || 'Onbekende fout'));
        }
    } catch (error) {
        console.error('Error deleting recipient:', error);
        alert('Fout bij verwijderen: ' + error.message);
    }
}

async function loadReportsForCopy() {
    const select = document.getElementById('copy-report');
    if (!select) return;

    // Use already loaded reports if available
    if (allReports.length > 0) {
        populateReportSelect(select, allReports);
    } else {
        try {
            const response = await fetch('reports.json');
            const data = await response.json();
            populateReportSelect(select, data.reports || []);
        } catch (error) {
            console.error('Error loading reports for copy:', error);
        }
    }
}

function populateReportSelect(select, reports) {
    select.innerHTML = '<option value="">Selecteer rapport...</option>';
    reports.forEach(r => {
        select.innerHTML += `<option value="${r.filename}">${r.year} - ${r.title}</option>`;
    });
}

function updateCopyRecipients() {
    const container = document.getElementById('copy-recipients');
    if (!container) return;

    if (emailRecipients.length === 0) {
        container.innerHTML = '<p class="no-data">Voeg eerst ontvangers toe</p>';
        return;
    }

    let html = '';
    emailRecipients.forEach(r => {
        const label = r.name ? `${r.name} (${r.email})` : r.email;
        html += `<label><input type="checkbox" name="copy-recipient" value="${escapeHtml(r.email)}"> ${escapeHtml(label)}</label>`;
    });
    container.innerHTML = html;
}

async function handleSendCopy(e) {
    e.preventDefault();

    const report = document.getElementById('copy-report').value;
    const recipients = [];
    document.querySelectorAll('input[name="copy-recipient"]:checked').forEach(cb => {
        recipients.push(cb.value);
    });

    if (!report) {
        alert('Selecteer een rapport');
        return;
    }
    if (recipients.length === 0) {
        alert('Selecteer minimaal één ontvanger');
        return;
    }

    const resultEl = document.getElementById('send-copy-result');
    resultEl.classList.remove('hidden', 'success', 'error');
    resultEl.textContent = 'Versturen...';

    try {
        const response = await fetch(getApiUrl('api/email/send-copy', true), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ report, recipients })
        });

        const data = await response.json();

        if (data.success) {
            resultEl.classList.add('success');
            resultEl.textContent = data.message;
        } else {
            resultEl.classList.add('error');
            resultEl.textContent = 'Fout: ' + (data.error || 'Onbekende fout');
        }
    } catch (error) {
        console.error('Error sending copy:', error);
        resultEl.classList.add('error');
        resultEl.textContent = 'Netwerkfout: ' + error.message;
    }
}

async function handleTestEmail(e) {
    e.preventDefault();

    const email = document.getElementById('test-email-address').value.trim();
    const resultEl = document.getElementById('test-email-result');

    resultEl.classList.remove('hidden', 'success', 'error');
    resultEl.textContent = 'Versturen...';

    try {
        const response = await fetch(getApiUrl('api/email/test', true), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });

        const data = await response.json();

        if (data.success) {
            resultEl.classList.add('success');
            resultEl.textContent = data.message;
        } else {
            resultEl.classList.add('error');
            resultEl.textContent = 'Fout: ' + (data.error || 'Onbekende fout');
        }
    } catch (error) {
        console.error('Error sending test email:', error);
        resultEl.classList.add('error');
        resultEl.textContent = 'Netwerkfout: ' + error.message;
    }
}

// =============================================================================
// SCHEDULE TAB
// =============================================================================

function setupScheduleTab() {
    // Setup quick action buttons
    document.querySelectorAll('.btn-action').forEach(btn => {
        btn.addEventListener('click', () => handleQuickAction(btn.dataset.action));
    });

    // Load data when schedule tab is shown
    document.querySelectorAll('.main-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            if (tab.dataset.tab === 'schedule') {
                loadSchedule();
                loadGenerationHistory();
            }
        });
    });
}

async function loadSchedule() {
    const container = document.getElementById('schedule-list');
    if (!container) return;

    container.innerHTML = '<div class="loading">Laden...</div>';

    try {
        const response = await fetch(getApiUrl('api/schedule', false));
        const data = await response.json();

        if (data.error) {
            container.innerHTML = `<div class="error">${data.error}</div>`;
            return;
        }

        if (!data.schedules || data.schedules.length === 0) {
            container.innerHTML = '<p class="no-data">Geen geplande rapporten gevonden</p>';
            return;
        }

        let html = '<table class="schedule-table"><thead><tr>';
        html += '<th>Rapport</th><th>Planning</th><th>Volgende generatie</th><th>Status</th>';
        html += '</tr></thead><tbody>';

        data.schedules.forEach(s => {
            const statusClass = s.active ? 'active' : 'inactive';
            const statusText = s.active ? 'Actief' : 'Inactief';
            html += `<tr>
                <td><strong>${escapeHtml(s.name)}</strong></td>
                <td>${escapeHtml(s.schedule)}</td>
                <td>${escapeHtml(s.next_run)}</td>
                <td><span class="status-badge ${statusClass}">${statusText}</span></td>
            </tr>`;
        });

        html += '</tbody></table>';
        container.innerHTML = html;

    } catch (error) {
        console.error('Error loading schedule:', error);
        container.innerHTML = '<div class="error">Kon planning niet laden</div>';
    }
}

async function loadGenerationHistory() {
    const container = document.getElementById('generation-history');
    if (!container) return;

    container.innerHTML = '<div class="loading">Laden...</div>';

    try {
        const response = await fetch(getApiUrl('api/schedule/history', false));
        const data = await response.json();

        if (data.error) {
            container.innerHTML = `<div class="error">${data.error}</div>`;
            return;
        }

        if (!data.history || data.history.length === 0) {
            container.innerHTML = '<p class="no-data">Geen recente generaties gevonden</p>';
            return;
        }

        let html = '<table class="history-table"><thead><tr>';
        html += '<th>Bestand</th><th>Type</th><th>Gegenereerd</th><th>Grootte</th><th>Status</th>';
        html += '</tr></thead><tbody>';

        data.history.forEach(h => {
            const statusClass = h.status === 'success' ? 'success' : 'error';
            html += `<tr>
                <td><a href="view.html?report=${encodeURIComponent(h.filename)}">${escapeHtml(h.filename)}</a></td>
                <td>${escapeHtml(h.type)}</td>
                <td>${escapeHtml(h.generated)}</td>
                <td>${escapeHtml(h.size)}</td>
                <td><span class="status-badge ${statusClass}">${h.status === 'success' ? 'OK' : 'Fout'}</span></td>
            </tr>`;
        });

        html += '</tbody></table>';
        container.innerHTML = html;

    } catch (error) {
        console.error('Error loading history:', error);
        container.innerHTML = '<div class="error">Kon geschiedenis niet laden</div>';
    }
}

async function handleQuickAction(action) {
    const resultEl = document.getElementById('quick-action-result');
    if (!resultEl) return;

    // Disable all action buttons
    document.querySelectorAll('.btn-action').forEach(btn => {
        btn.disabled = true;
        btn.classList.add('loading');
    });

    resultEl.classList.remove('hidden', 'success', 'error');
    resultEl.textContent = 'Rapport wordt gegenereerd... (dit kan 30-60 seconden duren)';

    try {
        const response = await fetch(getApiUrl('api/schedule/quick-generate', true), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action })
        });

        const data = await response.json();

        if (data.success) {
            resultEl.classList.add('success');
            resultEl.textContent = data.message;
            // Refresh history and reports list
            loadGenerationHistory();
            loadReports();
        } else {
            resultEl.classList.add('error');
            resultEl.textContent = 'Fout: ' + (data.error || 'Onbekende fout');
        }
    } catch (error) {
        console.error('Error generating report:', error);
        resultEl.classList.add('error');
        resultEl.textContent = 'Netwerkfout: ' + error.message;
    }

    // Re-enable buttons
    document.querySelectorAll('.btn-action').forEach(btn => {
        btn.disabled = false;
        btn.classList.remove('loading');
    });
}
