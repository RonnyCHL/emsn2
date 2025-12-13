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

    cards.forEach(card => {
        const type = card.dataset.type;

        if (currentFilter === 'all' || currentFilter === type) {
            card.classList.remove('hidden');
        } else {
            card.classList.add('hidden');
        }
    });
}

function displayReports(reports) {
    const container = document.getElementById('reports-list');

    if (reports.length === 0) {
        container.innerHTML = '<div class="error">Geen rapporten gevonden</div>';
        return;
    }

    // Sort reports: newest first (by generated date, fallback to modified)
    const sortedReports = [...reports].sort((a, b) => {
        const dateA = new Date(a.generated || a.modified);
        const dateB = new Date(b.generated || b.modified);
        return dateB - dateA;
    });

    container.innerHTML = sortedReports.map(report => createReportCard(report)).join('');
}

function createReportCard(report) {
    const detections = report.total_detections ? report.total_detections.toLocaleString('nl-NL') : 'N/A';
    const species = report.unique_species || 'N/A';
    const period = report.period || 'Onbekend';

    const typeLabels = {
        'week': 'Wekelijks',
        'month': 'Maandelijks',
        'season': 'Seizoen',
        'year': 'Jaarlijks'
    };
    const typeLabel = typeLabels[report.type] || report.type;

    return `
        <div class="report-card" data-type="${report.type}">
            <div class="report-header">
                <span class="report-type ${report.type}">
                    ${typeLabel}
                </span>
            </div>

            <h2 class="report-title">
                ${report.year} - ${report.title}
            </h2>

            <p class="report-period">${period}</p>

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
                <a href="view.html?report=${encodeURIComponent(report.filename)}" class="btn btn-primary">
                    Bekijk
                </a>
                <a href="api/pdf?file=${encodeURIComponent(report.filename)}" class="btn btn-secondary" download>
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
