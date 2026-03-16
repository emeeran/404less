/**
 * 404scout - Broken Link Scanner
 *
 * @spec FEAT-001 - Frontend SPA
 * @spec FEAT-001/AC-008 - Minimalist UI < 50KB gzipped
 */

class ScannerApp {
    constructor() {
        this.scanId = null;
        this.eventSource = null;
        this.currentPage = 1;
        this.currentFilter = '';

        // DOM elements
        this.elements = {
            form: document.getElementById('url-form'),
            urlInput: document.getElementById('url'),
            depthSelect: document.getElementById('depth'),
            respectRobots: document.getElementById('respect-robots'),
            scanBtn: document.getElementById('scan-btn'),
            stopBtn: document.getElementById('stop-btn'),
            refreshBtn: document.getElementById('refresh-btn'),
            urlError: document.getElementById('url-error'),
            progressSection: document.getElementById('progress-section'),
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

        this.bindEvents();
    }

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
        });

        this.elements.nextPage.addEventListener('click', () => {
            this.currentPage++;
            this.loadLinks();
        });

        // Export
        this.elements.exportJson.addEventListener('click', () => this.exportScan('json'));
        this.elements.exportCsv.addEventListener('click', () => this.exportScan('csv'));

        // URL validation
        this.elements.urlInput.addEventListener('input', () => {
            this.elements.urlError.textContent = '';
        });
    }

    /**
     * Start a new scan
     * @spec FEAT-001/AC-001 - Start scan with URL input
     */
    async startScan() {
        const url = this.elements.urlInput.value.trim();
        const depth = parseInt(this.elements.depthSelect.value, 10);
        const respectRobots = this.elements.respectRobots.checked;

        // @spec FEAT-001/EC-006 - Validate URL format
        if (!url) {
            this.elements.urlError.textContent = 'Please enter a URL';
            return;
        }

        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            this.elements.urlError.textContent =
                'Please enter a valid URL starting with http:// or https://';
            return;
        }

        // Clear previous results
        this.resetUI();

        // Disable form
        this.setFormEnabled(false);
        this.elements.scanBtn.textContent = 'Starting...';

        try {
            const response = await fetch('/api/scans', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url,
                    depth,
                    respect_robots: respectRobots,
                }),
            });

            const payload = await this.parseResponsePayload(response);
            if (!response.ok) {
                throw new Error(this.getErrorMessage(payload, 'Failed to start scan'));
            }

            this.scanId = payload.scan_id;
            this.elements.refreshBtn.disabled = false;

            // Show progress section
            this.elements.progressSection.classList.remove('hidden');
            this.elements.stopBtn.disabled = false;
            this.elements.scanBtn.textContent = 'Scanning...';

            // Connect to SSE stream
            this.connectSSE();

        } catch (error) {
            this.elements.urlError.textContent = error.message;
            this.setFormEnabled(true);
            this.elements.scanBtn.textContent = 'Start Scan';
        }
    }

    /**
     * Connect to SSE stream for real-time updates
     * @spec FEAT-001/AC-002 - Real-time progress display
     * @spec FEAT-001/API-006 - SSE endpoint
     */
    connectSSE() {
        this.eventSource = new EventSource(`/api/scans/${this.scanId}/stream`);

        // @spec FEAT-001/AC-002 - Progress event
        this.eventSource.addEventListener('progress', (e) => {
            const data = JSON.parse(e.data);
            this.updateProgress(data);
        });

        // Link checked event
        this.eventSource.addEventListener('link_checked', (e) => {
            // Could update a live list here
        });

        // Completed event
        this.eventSource.addEventListener('completed', (e) => {
            const data = JSON.parse(e.data);
            this.onScanCompleted(data);
        });

        // Stopped event
        this.eventSource.addEventListener('stopped', () => {
            this.onScanStopped();
        });

        // Error event
        this.eventSource.addEventListener('error', (e) => {
            if (e.data) {
                const data = JSON.parse(e.data);
                this.elements.urlError.textContent = data.error || 'Scan failed';
            }
            this.onScanStopped();
        });

        this.eventSource.onerror = () => {
            // Connection error - might be normal completion
            if (this.eventSource.readyState === EventSource.CLOSED) {
                this.onScanStopped();
            }
        };
    }

    /**
     * Update progress display
     * @spec FEAT-001/AC-002 - UI updates within 100ms
     */
    updateProgress(data) {
        this.elements.totalLinks.textContent = data.total_links || 0;
        this.elements.checkedLinks.textContent = data.checked_links || 0;
        this.elements.brokenLinks.textContent = data.broken_links || 0;

        // Update progress bar
        const percentage = data.total_links > 0
            ? (data.checked_links / data.total_links) * 100
            : 0;
        this.elements.progressFill.style.width = `${Math.min(percentage, 100)}%`;

        // Update current URL
        // @spec FEAT-001/C-004 - Sanitize URLs for XSS prevention
        this.elements.currentUrl.textContent = this.sanitizeURL(data.current_url || '');
    }

    /**
     * Update summary cards from a scan status response.
     */
    updateScanSummary(data) {
        this.elements.totalLinks.textContent = data.total_links || 0;
        this.elements.checkedLinks.textContent = data.checked_links || 0;
        this.elements.brokenLinks.textContent = data.broken_links || 0;

        const percentage = data.total_links > 0
            ? (data.checked_links / data.total_links) * 100
            : 0;
        this.elements.progressFill.style.width = `${Math.min(percentage, 100)}%`;

        const statusMessages = {
            pending: 'Scan queued',
            running: 'Scan is running',
            completed: 'Scan completed!',
            stopped: 'Scan stopped',
            failed: 'Scan failed',
        };

        this.elements.currentUrl.textContent = statusMessages[data.status] || 'Scan updated';
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
        this.elements.currentUrl.textContent = 'Scan completed!';

        // Show results section
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
        this.elements.currentUrl.textContent = 'Scan stopped';

        // Show results if we have a scan ID
        if (this.scanId) {
            this.elements.resultsSection.classList.remove('hidden');
            this.loadLinks();
        }
    }

    /**
     * Stop the current scan
     * @spec FEAT-001/AC-007 - Stop in-progress scan
     */
    async stopScan() {
        if (!this.scanId) return;

        this.elements.stopBtn.disabled = true;
        this.elements.stopBtn.textContent = 'Stopping...';

        try {
            await fetch(`/api/scans/${this.scanId}`, { method: 'DELETE' });
        } catch (error) {
            console.error('Failed to stop scan:', error);
        }

        this.elements.stopBtn.textContent = 'Stop Scan';
    }

    /**
     * Refresh the latest scan status and currently visible results.
     */
    async refreshScanData() {
        if (!this.scanId) return;

        this.elements.urlError.textContent = '';
        const originalLabel = this.elements.refreshBtn.textContent;
        this.elements.refreshBtn.disabled = true;
        this.elements.refreshBtn.textContent = 'Refreshing...';

        try {
            const response = await fetch(`/api/scans/${this.scanId}`);
            const payload = await this.parseResponsePayload(response);

            if (!response.ok) {
                throw new Error(this.getErrorMessage(payload, 'Failed to refresh scan'));
            }

            this.elements.progressSection.classList.remove('hidden');
            this.updateScanSummary(payload);

            if (payload.status === 'completed') {
                this.onScanCompleted(payload);
                return;
            }

            if (payload.status === 'stopped' || payload.status === 'failed') {
                this.onScanStopped();
                if (payload.status === 'failed') {
                    this.elements.urlError.textContent = 'Scan failed';
                }
                return;
            }

            if (!this.elements.resultsSection.classList.contains('hidden')) {
                await this.loadLinks();
            }
        } catch (error) {
            console.error('Failed to refresh scan:', error);
            this.elements.urlError.textContent = error.message;
        } finally {
            this.elements.refreshBtn.disabled = !this.scanId;
            this.elements.refreshBtn.textContent = originalLabel;
        }
    }

    /**
     * Load paginated links
     * @spec FEAT-001/API-003 - Paginated link retrieval
     * @spec FEAT-001/EC-002 - Pagination for thousands of links
     */
    async loadLinks() {
        if (!this.scanId) return;

        const params = new URLSearchParams({
            page: this.currentPage.toString(),
            per_page: '50',
        });

        if (this.currentFilter) {
            params.set('status', this.currentFilter);
        }

        try {
            const response = await fetch(`/api/scans/${this.scanId}/links?${params}`);
            const payload = await this.parseResponsePayload(response);

            if (!response.ok) {
                throw new Error(this.getErrorMessage(payload, 'Failed to load links'));
            }

            this.renderLinks(payload.links || []);
            this.renderPagination(payload.pagination || { page: 1, total_pages: 1 });
        } catch (error) {
            console.error('Failed to load links:', error);
            this.elements.urlError.textContent = error.message;
        }
    }

    /**
     * Render links list
     * @spec FEAT-001/C-004 - Sanitize URLs for XSS prevention
     */
    renderLinks(links) {
        this.elements.linksContainer.innerHTML = links.map(link => `
            <div class="link-item">
                <span class="link-url">${this.escapeHTML(link.url)}</span>
                <span class="link-status ${link.status}">${link.status}</span>
                ${link.status_code ? `<span class="link-code">${link.status_code}</span>` : ''}
            </div>
        `).join('');
    }

    /**
     * Render pagination controls
     */
    renderPagination(pagination) {
        const { page, total_pages } = pagination;

        if (total_pages <= 1) {
            this.elements.pagination.classList.add('hidden');
            return;
        }

        this.elements.pagination.classList.remove('hidden');
        this.elements.prevPage.disabled = page <= 1;
        this.elements.nextPage.disabled = page >= total_pages;
        this.elements.pageInfo.textContent = `Page ${page} of ${total_pages}`;
    }

    /**
     * Export scan results
     * @spec FEAT-001/AC-006 - Export scan results
     * @spec FEAT-001/API-005 - Export endpoint
     */
    exportScan(format) {
        if (!this.scanId) return;
        window.location.href = `/api/scans/${this.scanId}/export?format=${format}`;
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
     * Parse API response body safely for JSON and plain text payloads.
     */
    async parseResponsePayload(response) {
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            return response.json();
        }

        const text = await response.text();
        return { detail: { message: text || '' } };
    }

    /**
     * Extract a user-friendly error message from an API response payload.
     */
    getErrorMessage(payload, fallback) {
        if (!payload) return fallback;
        if (typeof payload === 'string') return payload || fallback;
        return payload.detail?.message || payload.message || fallback;
    }

    /**
     * Disconnect SSE
     */
    disconnectSSE() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }

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
    }

    /**
     * Enable/disable form elements
     */
    setFormEnabled(enabled) {
        this.elements.urlInput.disabled = !enabled;
        this.elements.depthSelect.disabled = !enabled;
        this.elements.respectRobots.disabled = !enabled;
        this.elements.scanBtn.disabled = !enabled;
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.scannerApp = new ScannerApp();
});
