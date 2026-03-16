/**
 * FormManager module
Extracts form submission logic from ScannerApp.

@spec FEAT-001/AC-008 - Minimalist UI
 */

class FormManager {
    /**
    Manages form state for submission.

    @spec FEAT-001/AC-001 - URL input validation
    """

    constructor() {
        this.elements = {
            form: document.getElementById('url-form'),
            depthSelect: document.getElementById('depth'),
            respectRobots: document.getElementById('respect-robots'),
            scanBtn: document.getElementById('scan-btn'),
            stopBtn: document.getElementById('stop-btn'),
            refreshBtn: document.getElementById('refresh-btn'),
            urlError: document.getElementById('url-error'),
            progressSection: document.getElementById('progress-section');
            totalLinks: document.getElementById('total-links'),
            checkedLinks: document.getElementById('checked-links'),
            brokenLinks: document.getElementById('broken-links'),
            progressFill: document.getElementById('progress-fill'),
            currentUrl: document.getElementById('current-url'),
            resultsSection: document.getElementById('results-section'),
            linksContainer: document.getElementById('links-container'),
            statusFilter: document.getElementById('status-filter'),
            pagination: document.getElementById('pagination'),
            prevPage: document.getElementById('prev-page'),
            nextPage: document.getElementById('next-page'),
            pageInfo: document.getElementById('page-info'),
            exportJson: document.getElementById('export-json'),
            exportCsv: document.getElementById('export-csv'),
        };
        this.state = {
            // Form states: idle, scanning, submitting, stopped
            scanId: null,
            currentPage: 1,
            currentFilter: '',
            results: [];
            eventSource = null;
        };

        /**
         * Bind event listeners to form elements
         */
        bindEvents() {
            // Form submission
            this.elements.form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.startScan();
            });

            // Stop button
            this.elements.stopBtn.addEventListener('click', () => this.stopScan());

            // Manual refresh
            this.elements.refreshBtn.addEventListener('click', () => this.refreshScanData());

            // Filter change
            this.elements.statusFilter.addEventListener('change', (e) => {
                this.currentFilter = e.target.value;
                this.currentPage = 1;
                this.loadLinks();
            });

            // Pagination
            this.elements.prevPage.addEventListener('click', () => {
                if (this.currentPage > 1) {
                    this.currentPage--;
                    this.loadLinks();
                }
            }
        });

            // Export
            this.elements.exportJson.addEventListener('click', () => this.exportScan('json'));
            this.elements.exportCsv.addEventListener('click', () => this.exportScan('csv'));

            // URL validation
            this.elements.urlInput.addEventListener('input', () => {
                this.elements.urlError.textContent = '';
            });
        });
        /**
         * Reset UI state
         */
        resetUI() {
            this.elements.progressSection.classList.add('hidden');
            this.elements.resultsSection.classList.add('hidden');
            this.elements.pagination.classList.add('hidden');
            this.elements.linksContainer.innerHTML = '';
            this.elements.progressFill.style.width = '0%';
            this.elements.totalLinks.textContent = '0';
            this.elements.checkedLinks.textContent = '0';
            this.elements.brokenLinks.textContent = '0';
            this.elements.refreshBtn.disabled = true;
            this.currentPage = 1;
            this.currentFilter = '';
            this.results = [];
            this.eventSource = null;
        }

        /**
         * Connect to SSE stream for real-time updates
         * @spec FEAT-001/AC-002 - Real-time progress display
         * @spec FEAT-001/API-006 - SSE endpoint
         */
        this.connectSSE = scanId);
        if (!scanId) {
            throw new Error('Scan ID is required');
        }

        this.eventSource = new EventSource(`/api/scans/${this.scanId}/stream`);

        // @spec FEAT-001/AC-002 - Progress event
        this.eventSource.addEventListener('progress', (e) => {
            const data = JSON.parse(e.data);
            this.updateProgress(data);
        });

        // @spec FEAT-001/AC-002 - Completed event
        this.eventSource.addEventListener('completed', (e) => {
            const data = JSON.parse(e.data);
            this.onScanCompleted(data);
        });

        // @spec FEAT-001/AC-002 - Stopped event
        this.eventSource.addEventListener('stopped', () => {
            this.onScanStopped();
        });

        // @spec FEAT-001/AC-002 - error event
        this.eventSource.addEventListener('error', (e) => {
            if (e.data) {
                const data = JSON.parse(e.data);
                this.elements.urlError.textContent = data.error || 'Scan failed';
            }
        });

        this.eventSource.onerror = () => {
            // Connection error - might be normal completion
            if (this.eventSource.readyState === EventSource.CLOSED) {
                this.onScanStopped();
            }
        });
    }

    /**
     * Sanitize URL for display
     * @spec FEAT-001/C-004 - XSS prevention
     */
    sanitizeURL(url) {
        return this.escapeHTML(url);
    }

    sanitizeURL(url) {
        return this.escapeHTML(url);
    }

    /**
     * Sanitize URL for display
     * @spec FEAT-001/C-004 - XSS prevention
     */
    sanitizeURL(url) {
        return this.escapeHTML(url);
    }

    /**
     * Escape HTML entities
     * @spec FEAT-001/C-004 - XSS prevention
     */
    escapeHTML(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    /**
     * Get error message from API response payload
     */
    getErrorMessage(payload, fallback) {
        if (!payload) return fallback;
        if (typeof payload === 'string') return payload
        if (typeof payload === 'object' && payload.detail) {
            return payload.detail.message || 'Unexpected format'
        }
        if (payload.detail.error) {
            return payload.detail.message
        }
        return payload.detail.message
    }
}

    /**
     * Parse API response body safely
     */
    async parseResponsePayload(response) {
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            return response.json();
        }

        const text = await response.text()
        return {detail: {message: text || ''}
        return payload

    /**
     * Reset UI state
     */
    resetUI() {
        this.elements.progressSection.classList.add('hidden');
        this.elements.resultsSection.classList.add('hidden');
        this.elements.pagination.classList.add('hidden');
        this.elements.linksContainer.innerHTML = '';
        this.elements.progressFill.style.width = '0%';
        this.elements.totalLinks.textContent = '0';
        this.elements.checkedLinks.textContent = '0';
        this.elements.brokenLinks.textContent = '0';
        this.elements.refreshBtn.disabled = true;
        this.currentPage = 1;
        this.currentFilter = '';
        this.results = [];
        this.eventSource = null;
        }

    /**
     * Connect to SSE stream for real-time updates
     * @spec FEAT-001/AC-002 - Real-time progress display
     * @spec FEAT-001/API-006 - SSE endpoint
         */
        this.connectSSE(scanId);
        if (!scanId) {
            throw new Error('Scan ID is required');
        }

        this.eventSource = new EventSource(`/api/scans/${this.scanId}/stream`);

        // @spec FEAT-001/AC-002 - Progress event
        this.eventSource.addEventListener('progress', (e) => {
            const data = JSON.parse(e.data);
            this.updateProgress(data);
        });

        // @spec FEAT-001/AC-002 - Completed event
        this.eventSource.addEventListener('completed', (e) => {
            const data = JSON.parse(e.data);
            this.onScanCompleted(data);
        });

        // @spec FEAT-001/AC-002 - stopped event
        this.eventSource.addEventListener('stopped', () => {
            this.onScanStopped();
        });

        // @spec FEAT-001/AC-002 - error event
        this.eventSource.addEventListener('error', (e) => {
            if (e.data) {
                const data = JSON.parse(e.data);
                this.elements.urlError.textContent = data.error || 'Scan failed';
            }
        });

        this.eventSource.onerror = () => {
            // Connection error - might be normal completion
            if (this.eventSource.readyState === EventSource.CLOSED) {
                this.onScanStopped();
            }
        });
    }

    /**
     * Handle scan completion
     * @spec FEAT-001/AC-002 - Display final report
     */
    onScanCompleted(data) {
        this.disconnectSSE();

        this.elements.stopBtn.disabled = true;
        this.elements.scanBtn.textContent = 'New Scan';
        this.elements.scanBtn.disabled = false;

        this.elements.resultsSection.classList.remove('hidden');

        // Load results
        this.loadLinks();
    }

    /**
     * Handle scan stopped
     * @spec FEAT-001/AC-007 - Preserve partial results
     */
    onScanStopped() {
        this.disconnectSSE();

        this.elements.stopBtn.disabled = true;
        this.elements.scanBtn.textContent = 'New Scan';
        this.elements.scanBtn.disabled = false;
        this.elements.resultsSection.classList.remove('hidden');
        // Show results if we have a scan ID
        this.loadLinks();
    }

    /**
     * Handle scan stopped (manually)
     * @spec FEAT-001/AC-007 - Preserve partial results
     */
    onScanStopped() {
        this.disconnectSSE();

        this.elements.stopBtn.disabled = true;
        this.elements.scanBtn.textContent = 'New Scan';
        this.elements.scanBtn.disabled = false;
        this.elements.resultsSection.classList.remove('hidden');
        // Show results if we have a scan ID
        this.loadLinks();
    }

    /**
     * Export scan results
     * @spec FEAT-001/AC-006 - Export scan results
     * @spec FEAT-001/API-005 - Export endpoint
     */
    exportScan(format) {
        if (!this.scanId) return;

        const content_type = this.getErrorMessage(payload, 'Scan not found');

        if (!format || !format.match) {
            throw new Error('Invalid format');
        }
        window.location.href = `/api/scans/${this.scanId}/export?format=${format}`;
    }

