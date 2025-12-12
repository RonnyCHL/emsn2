// EMSN Reports Web Interface
let allReports = [];
let currentFilter = 'all';

// Load reports on page load
document.addEventListener('DOMContentLoaded', () => {
    loadReports();
    setupFilters();
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

    container.innerHTML = reports.map(report => createReportCard(report)).join('');
}

function createReportCard(report) {
    const detections = report.total_detections ? report.total_detections.toLocaleString('nl-NL') : 'N/A';
    const species = report.unique_species || 'N/A';
    const period = report.period || 'Onbekend';

    return `
        <div class="report-card" data-type="${report.type}">
            <div class="report-header">
                <span class="report-type ${report.type}">
                    ${report.type === 'week' ? 'Wekelijks' : 'Maandelijks'}
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
                    📖 Bekijk
                </a>
                <a href="api/pdf?file=${encodeURIComponent(report.filename)}" class="btn btn-secondary" download>
                    📥 PDF
                </a>
            </div>
        </div>
    `;
}

function showError(message) {
    const container = document.getElementById('reports-list');
    container.innerHTML = `<div class="error">${message}</div>`;
}
