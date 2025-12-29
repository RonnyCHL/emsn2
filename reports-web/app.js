// EMSN Reports Web Interface
let allReports = [];
let currentFilter = 'all';
let currentSearchQuery = '';
let availableStyles = [];

// Favorites stored in localStorage
function getFavorites() {
    return JSON.parse(localStorage.getItem('favoriteReports') || '[]');
}

function isFavorite(filename) {
    return getFavorites().includes(filename);
}

function toggleFavorite(filename) {
    const favorites = getFavorites();
    const index = favorites.indexOf(filename);
    if (index > -1) {
        favorites.splice(index, 1);
    } else {
        favorites.push(filename);
    }
    localStorage.setItem('favoriteReports', JSON.stringify(favorites));
    // Re-render to update star
    displayReports(filterReports(allReports));
}

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
    setupReviewTab();
    loadPendingCount();
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
            displayReports(filterReports(allReports));
        });
    });

    // Setup search on Enter key
    const searchInput = document.getElementById('report-search');
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                searchReports();
            }
        });
    }
}

function filterReports(reports) {
    let filtered = reports;

    // Filter by type
    if (currentFilter === 'favorites') {
        const favorites = getFavorites();
        filtered = filtered.filter(r => favorites.includes(r.filename));
    } else if (currentFilter !== 'all') {
        filtered = filtered.filter(r => r.type === currentFilter);
    }

    // Filter by search query
    if (currentSearchQuery) {
        const query = currentSearchQuery.toLowerCase();
        filtered = filtered.filter(r => {
            // Search in filename, title, and top species
            const searchText = [
                r.filename,
                r.title || '',
                r.period || '',
                ...(r.top_species || [])
            ].join(' ').toLowerCase();
            return searchText.includes(query);
        });
    }

    return filtered;
}

function searchReports() {
    const searchInput = document.getElementById('report-search');
    currentSearchQuery = searchInput ? searchInput.value.trim() : '';
    displayReports(filterReports(allReports));
}

function clearSearch() {
    const searchInput = document.getElementById('report-search');
    if (searchInput) searchInput.value = '';
    currentSearchQuery = '';
    displayReports(filterReports(allReports));
}

function filterFavorites() {
    const checkbox = document.getElementById('show-favorites-only');
    if (checkbox && checkbox.checked) {
        currentFilter = 'favorites';
    } else {
        currentFilter = 'all';
    }
    // Update filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.filter === currentFilter);
    });
    displayReports(filterReports(allReports));
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

    // Check if favorite
    const favorite = isFavorite(report.filename);
    const starClass = favorite ? 'favorite-star active' : 'favorite-star';
    const starTitle = favorite ? 'Verwijder uit favorieten' : 'Voeg toe aan favorieten';

    return `
        <div class="report-card" data-type="${report.type}">
            <div class="report-header">
                <span class="report-type ${report.type}">
                    ${typeLabel}
                </span>
                ${isNew ? '<span class="badge-new">Nieuw</span>' : ''}
                <button class="${starClass}" onclick="toggleFavorite('${escapeHtml(report.filename)}')" title="${starTitle}">
                    ${favorite ? '★' : '☆'}
                </button>
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
                <button class="btn btn-primary" onclick="downloadPdfWithProgress('${escapeHtml(report.filename)}')" title="Download als PDF">
                    Download PDF
                </button>
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

// Progress tracking
let progressTimer = null;
let elapsedTimer = null;
let startTime = null;

// Update progress step
function updateProgressStep(stepName, status) {
    const step = document.querySelector(`.progress-step[data-step="${stepName}"]`);
    if (!step) return;

    // Remove previous states
    step.classList.remove('active', 'completed');

    if (status === 'active') {
        step.classList.add('active');
        step.querySelector('.step-icon').textContent = '⏳';
    } else if (status === 'completed') {
        step.classList.add('completed');
        step.querySelector('.step-icon').textContent = '✓';
    }
}

// Update progress bar
function updateProgressBar(percent) {
    const bar = document.getElementById('generation-progress-bar');
    if (bar) {
        bar.style.width = `${percent}%`;
    }
}

// Update elapsed time display
function updateElapsedTime() {
    if (!startTime) return;
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const display = document.getElementById('progress-elapsed');
    if (display) {
        display.textContent = `Verstreken tijd: ${elapsed}s`;
    }
}

// Reset progress UI
function resetProgressUI() {
    const steps = document.querySelectorAll('.progress-step');
    steps.forEach(step => {
        step.classList.remove('active', 'completed');
        step.querySelector('.step-icon').textContent = '⏳';
    });
    updateProgressBar(0);

    if (progressTimer) {
        clearTimeout(progressTimer);
        progressTimer = null;
    }
    if (elapsedTimer) {
        clearInterval(elapsedTimer);
        elapsedTimer = null;
    }
}

// Simulate progress steps with realistic timing
function simulateProgress() {
    const steps = [
        { name: 'connect', delay: 500, percent: 5 },
        { name: 'collect', delay: 2000, percent: 20 },
        { name: 'highlights', delay: 1500, percent: 30 },
        { name: 'claude', delay: 25000, percent: 75 },  // Claude takes longest
        { name: 'charts', delay: 5000, percent: 90 },
        { name: 'save', delay: 2000, percent: 100 }
    ];

    let totalDelay = 0;

    steps.forEach((step, index) => {
        // Mark as active
        progressTimer = setTimeout(() => {
            // Complete previous step
            if (index > 0) {
                updateProgressStep(steps[index - 1].name, 'completed');
            }
            // Mark current as active
            updateProgressStep(step.name, 'active');
            updateProgressBar(step.percent - 10);
        }, totalDelay);

        totalDelay += step.delay;
    });

    // Final completion will be handled when API returns
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

    // Reset and show progress
    resetProgressUI();
    form.classList.add('hidden');
    progress.classList.remove('hidden');
    result.classList.add('hidden');
    generateBtn.disabled = true;

    // Start timing
    startTime = Date.now();
    elapsedTimer = setInterval(updateElapsedTime, 1000);

    // Start simulated progress
    simulateProgress();

    try {
        const response = await fetch(getApiUrl('api/generate', true), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(body)
        });

        const data = await response.json();

        // Stop timers
        if (progressTimer) clearTimeout(progressTimer);
        if (elapsedTimer) clearInterval(elapsedTimer);

        // Complete all steps on success
        if (data.success) {
            const allSteps = ['connect', 'collect', 'highlights', 'claude', 'charts', 'save'];
            allSteps.forEach(step => updateProgressStep(step, 'completed'));
            updateProgressBar(100);

            // Small delay before showing result
            await new Promise(resolve => setTimeout(resolve, 500));
        }

        // Hide progress
        progress.classList.add('hidden');

        // Show result
        result.classList.remove('hidden');
        result.classList.remove('success', 'error');

        if (data.success) {
            result.classList.add('success');
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            result.querySelector('.result-message').textContent =
                `Rapport succesvol gegenereerd in ${elapsed} seconden`;

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

        // Stop timers
        if (progressTimer) clearTimeout(progressTimer);
        if (elapsedTimer) clearInterval(elapsedTimer);

        progress.classList.add('hidden');
        result.classList.remove('hidden');
        result.classList.add('error');
        result.querySelector('.result-message').textContent =
            'Netwerkfout: ' + error.message;
        document.getElementById('result-link').classList.add('hidden');
    }

    generateBtn.disabled = false;
    startTime = null;

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
                loadEmailHistory();
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

    const styleLabels = {
        'wetenschappelijk': 'Wetenschappelijk',
        'populair': 'Populair',
        'kinderen': 'Kinderen',
        'technisch': 'Technisch'
    };

    let html = '<table class="recipients-table"><thead><tr>';
    html += '<th>E-mailadres</th><th>Naam</th><th>Modus</th><th>Stijl</th><th>Rapporttypes</th><th>Acties</th>';
    html += '</tr></thead><tbody>';

    emailRecipients.forEach(r => {
        const types = (r.report_types || []).map(t => typeLabels[t] || t).join(', ');
        const style = r.style || 'wetenschappelijk';
        const styleLabel = styleLabels[style] || style;
        html += `<tr>
            <td>${escapeHtml(r.email)}</td>
            <td>${escapeHtml(r.name || '-')}</td>
            <td><span class="mode-badge ${r.mode}">${modeLabels[r.mode] || r.mode}</span></td>
            <td><span class="style-badge ${style}">${styleLabel}</span></td>
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
    const style = document.getElementById('recipient-style').value;

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
                style,
                report_types: reportTypes
            })
        });

        const data = await response.json();

        if (data.success) {
            // Clear form
            document.getElementById('recipient-email').value = '';
            document.getElementById('recipient-name').value = '';
            document.getElementById('recipient-mode').value = 'auto';
            document.getElementById('recipient-style').value = 'wetenschappelijk';
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
            // Refresh email history
            loadEmailHistory();
        } else {
            resultEl.classList.add('error');
            resultEl.textContent = 'Fout: ' + (data.error || 'Onbekende fout');
            // Refresh history to show failed attempt
            loadEmailHistory();
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

// Load email send history
async function loadEmailHistory() {
    const container = document.getElementById('email-history-list');
    if (!container) return;

    container.innerHTML = '<div class="loading">Laden...</div>';

    try {
        const response = await fetch(getApiUrl('api/email/history', false));
        const data = await response.json();

        if (data.error) {
            container.innerHTML = `<div class="error">${data.error}</div>`;
            return;
        }

        const history = data.history || [];

        if (history.length === 0) {
            container.innerHTML = '<p class="no-data">Nog geen rapporten verzonden per e-mail</p>';
            return;
        }

        let html = '<table class="email-history-table"><thead><tr>';
        html += '<th>Datum</th><th>Rapport</th><th>Ontvangers</th><th>Status</th>';
        html += '</tr></thead><tbody>';

        history.forEach(h => {
            const date = new Date(h.timestamp);
            const dateStr = date.toLocaleDateString('nl-NL', {
                day: 'numeric',
                month: 'short',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });

            const statusClass = h.status === 'success' ? 'success' : 'error';
            const statusText = h.status === 'success' ? 'Verzonden' : 'Mislukt';
            const recipients = h.recipients.join(', ');
            const reportName = h.report.replace('.md', '');

            html += `<tr>
                <td>${escapeHtml(dateStr)}</td>
                <td>${escapeHtml(reportName)}</td>
                <td>${escapeHtml(recipients)}</td>
                <td>
                    <span class="status-badge ${statusClass}">${statusText}</span>
                    ${h.error ? `<span class="error-hint" title="${escapeHtml(h.error)}">ℹ️</span>` : ''}
                </td>
            </tr>`;
        });

        html += '</tbody></table>';
        container.innerHTML = html;

    } catch (error) {
        console.error('Error loading email history:', error);
        container.innerHTML = '<div class="error">Kon verzendhistorie niet laden</div>';
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
                loadSkippedReports();
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

async function loadSkippedReports() {
    const container = document.getElementById('skipped-reports-list');
    if (!container) return;

    container.innerHTML = '<div class="loading">Laden...</div>';

    try {
        const response = await fetch(getApiUrl('api/schedule/skipped', false));
        const data = await response.json();

        if (data.error) {
            container.innerHTML = `<div class="error">${data.error}</div>`;
            return;
        }

        if (!data.skipped || data.skipped.length === 0) {
            container.innerHTML = '<p class="no-data">Geen overgeslagen rapporten (goed nieuws!)</p>';
            return;
        }

        // Show most recent first
        const skipped = data.skipped.slice().reverse();

        let html = '<table class="skipped-table"><thead><tr>';
        html += '<th>Datum/Tijd</th><th>Periode</th><th>Reden</th><th>Detecties</th><th>Soorten</th>';
        html += '</tr></thead><tbody>';

        skipped.forEach(s => {
            const timestamp = new Date(s.timestamp).toLocaleString('nl-NL', {
                day: '2-digit', month: '2-digit', year: 'numeric',
                hour: '2-digit', minute: '2-digit'
            });
            html += `<tr>
                <td>${escapeHtml(timestamp)}</td>
                <td>${escapeHtml(s.period)}</td>
                <td class="skip-reason">${escapeHtml(s.reason)}</td>
                <td class="number">${s.detections}</td>
                <td class="number">${s.species}</td>
            </tr>`;
        });

        html += '</tbody></table>';
        container.innerHTML = html;

    } catch (error) {
        console.error('Error loading skipped reports:', error);
        container.innerHTML = '<div class="error">Kon overgeslagen rapporten niet laden</div>';
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

// =============================================================================
// REVIEW TAB
// =============================================================================

let currentReviewReport = null;
let pendingReports = [];

function setupReviewTab() {
    // Load data when review tab is shown
    document.querySelectorAll('.main-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            if (tab.dataset.tab === 'review') {
                loadPendingReports();
                loadReviewHistory();
            }
        });
    });
}

// Load pending count for badge
async function loadPendingCount() {
    try {
        const response = await fetch(getApiUrl('api/pending', false));
        const data = await response.json();

        const badge = document.getElementById('pending-count');
        if (badge) {
            const count = data.count || 0;
            badge.textContent = count;
            if (count > 0) {
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        }
    } catch (error) {
        console.error('Error loading pending count:', error);
    }
}

// Load pending reports list
async function loadPendingReports() {
    const container = document.getElementById('pending-reports-list');
    if (!container) return;

    container.innerHTML = '<div class="loading">Laden...</div>';

    try {
        const response = await fetch(getApiUrl('api/pending', false));
        const data = await response.json();

        pendingReports = data.pending_reports || [];

        if (pendingReports.length === 0) {
            container.innerHTML = '<p class="no-data">Geen rapporten wachten op review</p>';
            return;
        }

        let html = '';
        pendingReports.forEach(report => {
            const createdDate = new Date(report.created_at);
            const dateStr = createdDate.toLocaleDateString('nl-NL', {
                day: 'numeric',
                month: 'short',
                hour: '2-digit',
                minute: '2-digit'
            });

            // Calculate time remaining if expires_at is set
            let timeRemaining = '';
            if (report.hours_until_expiry !== null) {
                const hours = Math.round(report.hours_until_expiry);
                if (hours < 2) {
                    timeRemaining = `<span class="time-remaining urgent">Nog ${hours}u</span>`;
                } else {
                    timeRemaining = `<span class="time-remaining">Nog ${hours}u</span>`;
                }
            }

            const typeLabels = {
                'weekly': 'Wekelijks',
                'monthly': 'Maandelijks',
                'seasonal': 'Seizoen',
                'yearly': 'Jaarlijks'
            };
            const typeLabel = typeLabels[report.report_type] || report.report_type;

            html += `
                <div class="pending-report-card" onclick="openReviewPanel(${report.id})">
                    <div class="pending-report-info">
                        <h4>${escapeHtml(report.report_title || report.report_filename)}</h4>
                        <div class="report-meta">
                            <span class="status-badge pending">${typeLabel}</span>
                            Aangemaakt: ${dateStr}
                            ${report.has_custom_text ? '<span class="badge-new" style="background:#fbbf24;">Tekst</span>' : ''}
                            ${timeRemaining}
                        </div>
                    </div>
                    <div class="pending-report-actions">
                        <button class="btn btn-small btn-primary" onclick="event.stopPropagation(); openReviewPanel(${report.id})">Review</button>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;

    } catch (error) {
        console.error('Error loading pending reports:', error);
        container.innerHTML = '<div class="error">Kon rapporten niet laden</div>';
    }
}

// Open review panel for a specific report
async function openReviewPanel(reportId) {
    const panel = document.getElementById('review-panel');
    if (!panel) return;

    try {
        const response = await fetch(getApiUrl(`api/pending/${reportId}`, false));
        const data = await response.json();

        if (data.error) {
            alert('Fout: ' + data.error);
            return;
        }

        currentReviewReport = data;

        // Update title
        document.getElementById('review-title').textContent = data.report_title || data.report_filename;

        // Load existing custom text if any
        document.getElementById('custom-text').value = data.custom_text || '';
        document.getElementById('custom-text-position').value = data.custom_text_position || 'after_intro';
        document.getElementById('reviewer-notes').value = data.reviewer_notes || '';

        // Clear preview
        document.getElementById('report-preview-content').innerHTML =
            '<p class="no-data">Klik op "Preview" om het rapport met je tekst te bekijken</p>';

        // Show panel
        panel.classList.remove('hidden');
        panel.scrollIntoView({ behavior: 'smooth' });

    } catch (error) {
        console.error('Error loading report:', error);
        alert('Fout bij laden rapport: ' + error.message);
    }
}

// Close review panel
function closeReviewPanel() {
    const panel = document.getElementById('review-panel');
    if (panel) {
        panel.classList.add('hidden');
    }
    currentReviewReport = null;
}

// Preview report with custom text
async function previewReport() {
    if (!currentReviewReport) return;

    const previewContainer = document.getElementById('report-preview-content');
    previewContainer.innerHTML = '<div class="loading">Preview laden...</div>';

    const customText = document.getElementById('custom-text').value;
    const position = document.getElementById('custom-text-position').value;

    try {
        const response = await fetch(getApiUrl(`api/pending/${currentReviewReport.id}/preview?custom_text=${encodeURIComponent(customText)}&position=${position}`, false));
        const data = await response.json();

        if (data.error) {
            previewContainer.innerHTML = `<div class="error">${data.error}</div>`;
            return;
        }

        // Convert markdown to basic HTML (simple conversion)
        let html = data.content || data.preview_content || '';

        // Highlight custom text section
        if (customText && html && html.includes(customText)) {
            html = html.replace(customText, `<div class="custom-text-highlight">${customText}</div>`);
        }

        // Basic markdown to HTML
        html = simpleMarkdownToHtml(html);

        previewContainer.innerHTML = html;

    } catch (error) {
        console.error('Error loading preview:', error);
        previewContainer.innerHTML = `<div class="error">Fout bij laden preview: ${error.message}</div>`;
    }
}

// Simple markdown to HTML converter
function simpleMarkdownToHtml(md) {
    if (!md) return '';

    // Headers
    md = md.replace(/^### (.*$)/gm, '<h3>$1</h3>');
    md = md.replace(/^## (.*$)/gm, '<h2>$1</h2>');
    md = md.replace(/^# (.*$)/gm, '<h1>$1</h1>');

    // Bold and italic
    md = md.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>');
    md = md.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    md = md.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Line breaks
    md = md.replace(/\n\n/g, '</p><p>');
    md = md.replace(/\n/g, '<br>');

    // Wrap in paragraph
    md = '<p>' + md + '</p>';

    return md;
}

// Save review changes
async function saveReviewChanges() {
    if (!currentReviewReport) return;

    const customText = document.getElementById('custom-text').value;
    const position = document.getElementById('custom-text-position').value;
    const notes = document.getElementById('reviewer-notes').value;

    try {
        const response = await fetch(getApiUrl(`api/pending/${currentReviewReport.id}/update`, true), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                custom_text: customText,
                custom_text_position: position,
                reviewer_notes: notes
            })
        });

        const data = await response.json();

        if (data.success) {
            alert('Wijzigingen opgeslagen');
            // Reload pending reports
            loadPendingReports();
        } else {
            alert('Fout: ' + (data.error || 'Onbekende fout'));
        }
    } catch (error) {
        console.error('Error saving changes:', error);
        alert('Fout bij opslaan: ' + error.message);
    }
}

// Approve report
async function approveReport() {
    if (!currentReviewReport) return;

    if (!confirm('Weet je zeker dat je dit rapport wilt goedkeuren en verzenden?')) {
        return;
    }

    try {
        const response = await fetch(getApiUrl(`api/pending/${currentReviewReport.id}/approve`, true), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();

        if (data.success) {
            alert('Rapport goedgekeurd en verzonden!');
            closeReviewPanel();
            loadPendingReports();
            loadReviewHistory();
            loadPendingCount();
        } else {
            alert('Fout: ' + (data.error || 'Onbekende fout'));
        }
    } catch (error) {
        console.error('Error approving report:', error);
        alert('Fout bij goedkeuren: ' + error.message);
    }
}

// Reject report
async function rejectReport() {
    if (!currentReviewReport) return;

    const reason = prompt('Reden voor afwijzing (optioneel):');

    try {
        const response = await fetch(getApiUrl(`api/pending/${currentReviewReport.id}/reject`, true), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason })
        });

        const data = await response.json();

        if (data.success) {
            alert('Rapport afgewezen');
            closeReviewPanel();
            loadPendingReports();
            loadReviewHistory();
            loadPendingCount();
        } else {
            alert('Fout: ' + (data.error || 'Onbekende fout'));
        }
    } catch (error) {
        console.error('Error rejecting report:', error);
        alert('Fout bij afwijzen: ' + error.message);
    }
}

// =============================================================================
// PDF DOWNLOAD WITH PROGRESS
// =============================================================================

// Create progress modal if it doesn't exist
function createDownloadProgressModal() {
    if (document.getElementById('download-progress-modal')) return;

    const modal = document.createElement('div');
    modal.id = 'download-progress-modal';
    modal.className = 'download-modal hidden';
    modal.innerHTML = `
        <div class="download-modal-content">
            <h3>PDF Downloaden</h3>
            <p id="download-filename"></p>
            <div class="download-progress-bar">
                <div id="download-progress-fill" class="download-progress-fill"></div>
            </div>
            <p id="download-status">Verbinding maken...</p>
            <p id="download-size"></p>
        </div>
    `;
    document.body.appendChild(modal);
}

// Download PDF with progress indicator
async function downloadPdfWithProgress(filename) {
    createDownloadProgressModal();

    const modal = document.getElementById('download-progress-modal');
    const filenameEl = document.getElementById('download-filename');
    const progressFill = document.getElementById('download-progress-fill');
    const statusEl = document.getElementById('download-status');
    const sizeEl = document.getElementById('download-size');

    // Show modal
    modal.classList.remove('hidden');
    filenameEl.textContent = filename;
    progressFill.style.width = '0%';
    statusEl.textContent = 'Verbinding maken...';
    sizeEl.textContent = '';

    // Mark report as read
    const readReports = JSON.parse(localStorage.getItem('readReports') || '[]');
    if (!readReports.includes(filename)) {
        readReports.push(filename);
        localStorage.setItem('readReports', JSON.stringify(readReports));
    }

    try {
        const response = await fetch(`api/pdf?file=${encodeURIComponent(filename)}`);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const contentLength = response.headers.get('Content-Length');
        const totalSize = contentLength ? parseInt(contentLength, 10) : null;

        if (totalSize) {
            sizeEl.textContent = `Grootte: ${formatFileSize(totalSize)}`;
        }

        statusEl.textContent = 'Downloaden...';

        // Read the response as a stream
        const reader = response.body.getReader();
        const chunks = [];
        let receivedSize = 0;

        while (true) {
            const { done, value } = await reader.read();

            if (done) break;

            chunks.push(value);
            receivedSize += value.length;

            // Update progress
            if (totalSize) {
                const percent = Math.round((receivedSize / totalSize) * 100);
                progressFill.style.width = `${percent}%`;
                statusEl.textContent = `Downloaden... ${percent}%`;
            } else {
                // No content length, show received size
                statusEl.textContent = `Downloaden... ${formatFileSize(receivedSize)}`;
                // Indeterminate progress animation
                progressFill.style.width = '100%';
                progressFill.classList.add('indeterminate');
            }
        }

        progressFill.classList.remove('indeterminate');
        progressFill.style.width = '100%';
        statusEl.textContent = 'Bestand opslaan...';

        // Combine chunks into blob
        const blob = new Blob(chunks, { type: 'application/pdf' });

        // Create download link
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename.replace('.md', '.pdf');
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        statusEl.textContent = 'Download voltooid!';

        // Hide modal after brief delay
        setTimeout(() => {
            modal.classList.add('hidden');
            // Refresh reports to update "Nieuw" badge
            loadReports();
        }, 1000);

    } catch (error) {
        console.error('Download error:', error);
        progressFill.style.width = '0%';
        progressFill.style.backgroundColor = '#ef4444';
        statusEl.textContent = `Fout: ${error.message}`;
        sizeEl.innerHTML = '<button class="btn btn-small" onclick="document.getElementById(\'download-progress-modal\').classList.add(\'hidden\')">Sluiten</button>';
    }
}

// Format file size
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// Load review history
async function loadReviewHistory() {
    const container = document.getElementById('review-history-list');
    if (!container) return;

    container.innerHTML = '<div class="loading">Laden...</div>';

    try {
        const response = await fetch(getApiUrl('api/pending/history', false));
        const data = await response.json();

        if (data.error) {
            container.innerHTML = `<div class="error">${data.error}</div>`;
            return;
        }

        const history = data.history || [];

        if (history.length === 0) {
            container.innerHTML = '<p class="no-data">Geen recent beoordeelde rapporten</p>';
            return;
        }

        const statusLabels = {
            'approved': 'Goedgekeurd',
            'rejected': 'Afgewezen',
            'sent': 'Verzonden',
            'expired': 'Verlopen'
        };

        let html = '<table class="review-history-table"><thead><tr>';
        html += '<th>Rapport</th><th>Type</th><th>Status</th><th>Beoordeeld</th><th>Notities</th>';
        html += '</tr></thead><tbody>';

        history.forEach(h => {
            const statusClass = h.status;
            const statusLabel = statusLabels[h.status] || h.status;
            const reviewedDate = h.reviewed_at ? new Date(h.reviewed_at).toLocaleDateString('nl-NL', {
                day: 'numeric',
                month: 'short',
                hour: '2-digit',
                minute: '2-digit'
            }) : '-';

            html += `<tr>
                <td>${escapeHtml(h.report_title || h.report_filename)}</td>
                <td>${escapeHtml(h.report_type)}</td>
                <td><span class="status-badge ${statusClass}">${statusLabel}</span></td>
                <td>${reviewedDate}</td>
                <td>${escapeHtml(h.reviewer_notes || '-')}</td>
            </tr>`;
        });

        html += '</tbody></table>';
        container.innerHTML = html;

    } catch (error) {
        console.error('Error loading history:', error);
        container.innerHTML = '<div class="error">Kon geschiedenis niet laden</div>';
    }
}
