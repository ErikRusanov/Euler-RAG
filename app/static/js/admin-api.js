/** Admin API utilities for making authenticated requests to the backend API. */

/**
 * Get a cookie value by name.
 * @param {string} name - Cookie name.
 * @returns {string|null} Cookie value or null if not found.
 */
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) {
        return parts.pop().split(';').shift();
    }
    return null;
}

/**
 * Get API key from cookie.
 * @returns {string|null} API key or null if not found.
 */
function getApiKey() {
    return getCookie('euler_api_key');
}

/**
 * Make an authenticated API request.
 * @param {string} url - API endpoint URL.
 * @param {RequestInit} options - Fetch options.
 * @returns {Promise<Response>} Fetch response.
 */
async function apiRequest(url, options = {}) {
    const apiKey = getApiKey();
    if (!apiKey) {
        throw new Error('API key not found in cookies. Please log in again.');
    }

    const headers = {
        'X-API-KEY': apiKey,
        ...options.headers,
    };

    // Don't set Content-Type for DELETE requests without body
    if (options.method !== 'DELETE' || options.body) {
        headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(url, {
        ...options,
        headers,
    });

    if (!response.ok) {
        let errorData;
        try {
            const text = await response.text();
            errorData = text ? JSON.parse(text) : { error: 'Unknown error' };
        } catch {
            errorData = { error: 'Unknown error' };
        }
        throw new Error(errorData.message || errorData.error || `HTTP ${response.status}`);
    }

    return response;
}

/**
 * Get document by ID.
 * @param {number} documentId - Document ID.
 * @returns {Promise<Object>} Document data.
 */
async function getDocument(documentId) {
    const response = await apiRequest(`/api/documents/${documentId}`);
    return await response.json();
}

/**
 * Update document.
 * @param {number} documentId - Document ID.
 * @param {Object} data - Update data.
 * @returns {Promise<Object>} Updated document data.
 */
async function updateDocument(documentId, data) {
    const response = await apiRequest(`/api/documents/${documentId}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
    });
    return await response.json();
}

/**
 * Delete document via API.
 * @param {number} documentId - Document ID.
 * @returns {Promise<void>}
 */
async function deleteDocumentApi(documentId) {
    await apiRequest(`/api/documents/${documentId}`, {
        method: 'DELETE',
    });
}

/**
 * Start processing a document (update status to PENDING).
 * @param {number} documentId - Document ID.
 * @returns {Promise<Object>} Updated document data.
 */
async function startProcessing(documentId) {
    return await updateDocument(documentId, { status: 'pending' });
}

/**
 * Reload the documents table by making a GET request to the current page.
 * @param {Object} queryParams - Optional query parameters to include in the request.
 */
function reloadDocumentsTable(queryParams = null) {
    const url = new URL(window.location.href);
    url.pathname = '/admin/documents';

    // If queryParams provided, use them; otherwise preserve current query params
    if (queryParams) {
        // Clear existing params and set new ones
        url.search = '';
        Object.entries(queryParams).forEach(([key, value]) => {
            if (value !== null && value !== undefined && value !== '') {
                url.searchParams.set(key, value);
            }
        });
    }

    fetch(url.toString())
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.text();
        })
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newContent = doc.getElementById('documents-content');
            const currentContent = document.getElementById('documents-content');

            if (newContent && currentContent) {
                currentContent.outerHTML = newContent.outerHTML;
                // Re-initialize filter event listeners after content update
                initializeFilterHandlers();
            } else {
                window.location.reload();
            }
        })
        .catch(error => {
            console.error('Failed to reload documents table:', error);
            window.location.reload();
        });
}

/**
 * Handle filter changes and reload table with new filter values.
 * This is a fallback for when HTMX doesn't work.
 */
function handleFilterChange() {
    const statusSelect = document.getElementById('status');
    const subjectSelect = document.getElementById('subject_id');
    const teacherSelect = document.getElementById('teacher_id');
    const pageSizeSelect = document.getElementById('page_size');

    const queryParams = {};

    if (statusSelect && statusSelect.value) {
        queryParams.status = statusSelect.value;
    }
    if (subjectSelect && subjectSelect.value) {
        queryParams.subject_id = subjectSelect.value;
    }
    if (teacherSelect && teacherSelect.value) {
        queryParams.teacher_id = teacherSelect.value;
    }
    if (pageSizeSelect && pageSizeSelect.value) {
        queryParams.page_size = pageSizeSelect.value;
    }

    reloadDocumentsTable(queryParams);
}

/**
 * Initialize filter change handlers as fallback for HTMX.
 * Uses event delegation to avoid issues with element replacement.
 */
function initializeFilterHandlers() {
    // Use event delegation on document to handle filter changes
    // This works even if filter elements are replaced
    const handler = function(event) {
        const target = event.target;
        // Only handle changes on filter selects
        if (target && target.matches && target.matches('#status, #subject_id, #teacher_id, #page_size')) {
            handleFilterChange();
        }
    };

    // Remove existing listener if any
    if (document._filterChangeHandler) {
        document.removeEventListener('change', document._filterChangeHandler);
    }

    // Store handler reference and add listener
    document._filterChangeHandler = handler;
    document.addEventListener('change', handler, true); // Use capture phase to catch all changes
}

/**
 * View document by ID - opens modal with document details.
 * @param {number} documentId - Document ID.
 */
async function viewDocument(documentId) {
    try {
        const document = await getDocument(documentId);
        if (!document) {
            throw new Error('Document not found');
        }
        showDocumentModal(document);
    } catch (error) {
        alert(`Failed to load document: ${error.message}`);
        console.error('Error loading document:', error);
    }
}

/**
 * Delete document with confirmation.
 * @param {number} documentId - Document ID.
 * @param {HTMLElement} button - Button element with data-document-filename.
 */
async function deleteDocumentWithConfirm(documentId, button) {
    if (!button) {
        console.error('Delete button not found');
        return;
    }

    const filename = button.getAttribute('data-document-filename') || `document #${documentId}`;

    if (!confirm(`Are you sure you want to delete '${filename}'?`)) {
        return;
    }

    try {
        console.log(`Deleting document ${documentId}...`);
        await deleteDocumentApi(documentId);
        console.log(`Document ${documentId} deleted successfully`);
        reloadDocumentsTable();
    } catch (error) {
        console.error('Delete error:', error);
        alert(`Failed to delete document: ${error.message}`);
    }
}

/**
 * Start document processing.
 * @param {number} documentId - Document ID.
 */
async function startDocumentProcessing(documentId) {
    try {
        await startProcessing(documentId);
        reloadDocumentsTable();
    } catch (error) {
        alert(`Failed to start processing: ${error.message}`);
        console.error('Error starting processing:', error);
    }
}

/**
 * Show document modal with details.
 * @param {Object} docData - Document data from API.
 */
function showDocumentModal(docData) {
    // Format dates
    const formatDate = (dateStr) => {
        if (!dateStr) return 'N/A';
        const date = new Date(dateStr);
        return date.toLocaleString('en-US', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
    };

    // Create modal HTML
    const modalHTML = `
        <div class="modal-overlay" onclick="this.remove()">
            <div class="modal-container" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <h2 class="modal-title">${escapeHtml(docData.filename)}</h2>
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
                <div class="modal-body">
                    <div class="modal-pdf">
                        <embed
                            src="${escapeHtml(docData.url)}"
                            type="application/pdf"
                            width="100%"
                            height="100%" />
                    </div>
                    <div class="modal-details">
                        <div class="detail-section">
                            <div class="detail-label">Document ID</div>
                            <div class="detail-value">#${docData.id}</div>
                        </div>
                        <div class="detail-section">
                            <div class="detail-label">Filename</div>
                            <div class="detail-value">${escapeHtml(docData.filename)}</div>
                        </div>
                        <div class="detail-section">
                            <div class="detail-label">Status</div>
                            <div class="detail-value">
                                <span class="status-badge ${docData.status.value || docData.status}">${docData.status.value || docData.status}</span>
                            </div>
                        </div>
                        ${docData.subject_id ? `
                        <div class="detail-section">
                            <div class="detail-label">Subject ID</div>
                            <div class="detail-value">${docData.subject_id}</div>
                        </div>
                        ` : ''}
                        ${docData.teacher_id ? `
                        <div class="detail-section">
                            <div class="detail-label">Teacher ID</div>
                            <div class="detail-value">${docData.teacher_id}</div>
                        </div>
                        ` : ''}
                        <div class="detail-section">
                            <div class="detail-label">S3 Key</div>
                            <div class="detail-value" style="font-family: monospace; font-size: 0.75rem;">${escapeHtml(docData.s3_key)}</div>
                        </div>
                        <div class="detail-section">
                            <div class="detail-label">Uploaded At</div>
                            <div class="detail-value">${formatDate(docData.created_at)}</div>
                        </div>
                        <div class="detail-section">
                            <div class="detail-label">Last Updated</div>
                            <div class="detail-value">${formatDate(docData.updated_at)}</div>
                        </div>
                        ${docData.processed_at ? `
                        <div class="detail-section">
                            <div class="detail-label">Processed At</div>
                            <div class="detail-value">${formatDate(docData.processed_at)}</div>
                        </div>
                        ` : ''}
                        ${docData.error ? `
                        <div class="detail-section">
                            <div class="detail-label">Error</div>
                            <div class="detail-value" style="color: var(--error);">${escapeHtml(docData.error)}</div>
                        </div>
                        ` : ''}
                        ${docData.progress ? `
                        <div class="detail-section">
                            <div class="detail-label">Progress</div>
                            <div class="detail-value">
                                Page ${docData.progress.page} of ${docData.progress.total}
                            </div>
                        </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        </div>
    `;

    // Insert modal into body (wait for DOM if needed)
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            document.body.insertAdjacentHTML('beforeend', modalHTML);
        });
    } else {
        document.body.insertAdjacentHTML('beforeend', modalHTML);
    }
}

/**
 * Escape HTML to prevent XSS.
 * @param {string} text - Text to escape.
 * @returns {string} Escaped text.
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Show loading overlay during file upload.
 */
function showLoadingOverlay() {
    const overlay = document.getElementById('upload-loading-overlay');
    if (overlay) {
        overlay.style.display = 'flex';
    }
}

/**
 * Hide loading overlay after file upload completes.
 */
function hideLoadingOverlay() {
    const overlay = document.getElementById('upload-loading-overlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
}

/**
 * Upload a document file to the server.
 * @param {File} file - File to upload.
 * @returns {Promise<Object>} Uploaded document data.
 */
async function uploadDocument(file) {
    const apiKey = getApiKey();
    if (!apiKey) {
        throw new Error('API key not found in cookies. Please log in again.');
    }

    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch('/api/documents', {
        method: 'POST',
        headers: {
            'X-API-KEY': apiKey,
        },
        body: formData,
    });

    if (!response.ok) {
        let errorData;
        try {
            const text = await response.text();
            errorData = text ? JSON.parse(text) : { error: 'Unknown error' };
        } catch {
            errorData = { error: 'Unknown error' };
        }
        throw new Error(errorData.message || errorData.error || `HTTP ${response.status}`);
    }

    return await response.json();
}

/**
 * Handle file upload when file is selected.
 * @param {Event} event - File input change event.
 */
async function handleFileUpload(event) {
    const fileInput = event.target;
    const file = fileInput.files[0];

    if (!file) {
        return;
    }

    // Validate file type
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
        alert('Please select a PDF file.');
        fileInput.value = '';
        return;
    }

    try {
        showLoadingOverlay();
        await uploadDocument(file);
        // Reset file input
        fileInput.value = '';
        // Reload table to show new document
        reloadDocumentsTable();
    } catch (error) {
        console.error('Upload error:', error);
        alert(`Failed to upload document: ${error.message}`);
    } finally {
        hideLoadingOverlay();
    }
}

/**
 * Initialize file upload handler.
 */
function initializeFileUpload() {
    const fileInput = document.getElementById('document-upload-input');
    if (fileInput) {
        fileInput.addEventListener('change', handleFileUpload);
    }
}

// Export functions for use in other scripts
window.AdminAPI = {
    getCookie,
    getApiKey,
    apiRequest,
    getDocument,
    updateDocument,
    deleteDocument: deleteDocumentApi,
    startProcessing,
    reloadDocumentsTable,
    viewDocument,
    deleteDocumentWithConfirm,
    startDocumentProcessing,
    showDocumentModal,
    handleFilterChange,
    initializeFilterHandlers,
    uploadDocument,
    showLoadingOverlay,
    hideLoadingOverlay,
    handleFileUpload,
    initializeFileUpload,
};

// Global functions for onclick handlers
window.viewDocument = viewDocument;
window.deleteDocument = deleteDocumentWithConfirm;
window.startDocumentProcessing = startDocumentProcessing;

// Initialize handlers when DOM is ready
function initializeAllHandlers() {
    initializeFilterHandlers();
    initializeFileUpload();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeAllHandlers);
} else {
    initializeAllHandlers();
}
