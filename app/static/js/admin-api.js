/** Admin API utilities for making authenticated requests to the backend API. */

/**
 * Make an authenticated API request.
 * API key is automatically injected by APIKeyMiddleware from session cookie.
 * @param {string} url - API endpoint URL.
 * @param {RequestInit} options - Fetch options.
 * @returns {Promise<Response>} Fetch response.
 */
async function apiRequest(url, options = {}) {
    const headers = {
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
                // Stop all existing progress tracking
                progressConnections.forEach((_, documentId) => {
                    stopProgressTracking(documentId);
                });
                progressConnections.clear();

                currentContent.outerHTML = newContent.outerHTML;
                // Re-initialize filter event listeners after content update
                initializeFilterHandlers();
                // Re-initialize progress tracking for new content
                initializeProgressTracking();
            } else {
                window.location.reload();
            }
        })
        .catch((error) => {
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
    const pageSizeSelect = document.getElementById('page_size');

    const queryParams = {};

    if (statusSelect && statusSelect.value) {
        queryParams.status = statusSelect.value;
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
        if (target && target.matches && target.matches('#status, #page_size')) {
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
        await deleteDocumentApi(documentId);
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
        // Start progress tracking immediately
        startProgressTracking(documentId);
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
 * Debounce function to limit API calls.
 * @param {Function} func - Function to debounce.
 * @param {number} wait - Wait time in ms.
 * @returns {Function} Debounced function.
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Show edit modal for document.
 * @param {number} documentId - Document ID.
 */
async function editDocument(documentId) {
    try {
        const docData = await getDocument(documentId);
        if (!docData) {
            throw new Error('Document not found');
        }

        showEditModal(docData);
    } catch (error) {
        alert(`Failed to load document: ${error.message}`);
        console.error('Error loading document for edit:', error);
    }
}

/**
 * Show edit modal with document data.
 * @param {Object} docData - Document data from API.
 */
function showEditModal(docData) {
    const formatDate = (dateStr) => {
        if (!dateStr) return 'N/A';
        const date = new Date(dateStr);
        return date.toLocaleString('en-US', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    const statusValue = docData.status.value || docData.status;
    const progressPage = docData.progress ? docData.progress.page : 0;
    const progressTotal = docData.progress ? docData.progress.total : 0;

    // Store initial values if they exist
    if (docData.subject_id) {
        editModalSelectedSubject = {
            id: docData.subject_id,
            name: docData.subject_name || '',
            semester: docData.subject_semester || 0,
        };
    }
    if (docData.teacher_id) {
        editModalSelectedTeacher = {
            id: docData.teacher_id,
            name: docData.teacher_name || '',
        };
    }

    const subjectDisplayValue = editModalSelectedSubject
        ? `${editModalSelectedSubject.name} (Sem ${editModalSelectedSubject.semester})`
        : '';
    const teacherDisplayValue = editModalSelectedTeacher
        ? editModalSelectedTeacher.name
        : '';

    // Build clear button HTML only if there's a selection
    const subjectClearBtn = editModalSelectedSubject ? `
        <button type="button" class="clear-btn" onclick="clearSubjectSelection()" title="Clear selection">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
            </svg>
        </button>
    ` : '';

    const teacherClearBtn = editModalSelectedTeacher ? `
        <button type="button" class="clear-btn" onclick="clearTeacherSelection()" title="Clear selection">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
            </svg>
        </button>
    ` : '';

    // Create modal element using DOM methods for safety
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.id = 'edit-modal-overlay';
    overlay.onclick = closeEditModal;

    const container = document.createElement('div');
    container.className = 'modal-container edit-modal-container';
    container.onclick = (e) => e.stopPropagation();

    container.innerHTML = `
        <div class="modal-header">
            <h2 class="modal-title">Edit Document</h2>
            <button class="modal-close" onclick="closeEditModal()">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
                </svg>
            </button>
        </div>
        <div class="modal-body edit-modal-body">
            <div class="edit-form-section">
                <h3 class="section-title">Editable Fields</h3>
                <form id="edit-document-form" data-document-id="${docData.id}">
                    <div class="form-group">
                        <label class="form-label">Filename</label>
                        <input
                            type="text"
                            id="edit-filename"
                            class="form-input"
                            value="${escapeHtml(docData.filename)}"
                            placeholder="Enter filename">
                    </div>

                    <div class="form-group">
                        <label class="form-label">Subject</label>
                        <div class="input-with-addon">
                            <div class="autocomplete-container">
                                <input
                                    type="text"
                                    id="edit-subject-search"
                                    class="form-input"
                                    value="${escapeHtml(subjectDisplayValue)}"
                                    placeholder="Search subjects..."
                                    autocomplete="off">
                                <input type="hidden" id="edit-subject-id" value="${docData.subject_id || ''}">
                                <div id="subject-autocomplete-results" class="autocomplete-results"></div>
                                ${subjectClearBtn}
                            </div>
                            <button type="button" class="addon-btn" onclick="showCreateSubjectDialog()" title="Create new subject">
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                                </svg>
                            </button>
                        </div>
                    </div>

                    <div class="form-group">
                        <label class="form-label">Teacher</label>
                        <div class="input-with-addon">
                            <div class="autocomplete-container">
                                <input
                                    type="text"
                                    id="edit-teacher-search"
                                    class="form-input"
                                    value="${escapeHtml(teacherDisplayValue)}"
                                    placeholder="Search teachers..."
                                    autocomplete="off">
                                <input type="hidden" id="edit-teacher-id" value="${docData.teacher_id || ''}">
                                <div id="teacher-autocomplete-results" class="autocomplete-results"></div>
                                ${teacherClearBtn}
                            </div>
                            <button type="button" class="addon-btn" onclick="showCreateTeacherDialog()" title="Create new teacher">
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                                </svg>
                            </button>
                        </div>
                    </div>

                    <button type="submit" class="btn btn-primary" style="margin-top: 1rem;">Save Changes</button>
                </form>
            </div>

            <div class="read-only-section">
                <h3 class="section-title">Document Information</h3>
                <div class="detail-section">
                    <div class="detail-label">S3 Key</div>
                    <div class="detail-value" style="font-family: monospace; font-size: 0.75rem; word-break: break-all;">${escapeHtml(docData.s3_key)}</div>
                </div>
                <div class="detail-section">
                    <div class="detail-label">Status</div>
                    <div class="detail-value">
                        <span class="status-badge ${statusValue}">${statusValue}</span>
                    </div>
                </div>
                <div class="detail-section">
                    <div class="detail-label">Progress</div>
                    <div class="detail-value">Page ${progressPage} of ${progressTotal}</div>
                </div>
                ${docData.processed_at ? `
                <div class="detail-section">
                    <div class="detail-label">Processed At</div>
                    <div class="detail-value">${formatDate(docData.processed_at)}</div>
                </div>
                ` : ''}
                <div class="detail-section">
                    <div class="detail-label">Created At</div>
                    <div class="detail-value">${formatDate(docData.created_at)}</div>
                </div>
            </div>
        </div>
    `;

    overlay.appendChild(container);
    document.body.appendChild(overlay);

    // Attach form submit handler
    document
        .getElementById('edit-document-form')
        .addEventListener('submit', handleEditFormSubmit);

    // Attach autocomplete handlers
    initializeAutocomplete();
}


/**
 * Close edit modal.
 */
function closeEditModal() {
    const overlay = document.getElementById('edit-modal-overlay');
    if (overlay) {
        overlay.remove();
    }
}

/**
 * Handle edit form submission.
 * @param {Event} e - Submit event.
 */
async function handleEditFormSubmit(e) {
    e.preventDefault();

    const form = e.target;
    const documentId = parseInt(form.getAttribute('data-document-id'));
    const filename = document.getElementById('edit-filename').value.trim();

    const updateData = {};
    if (filename) {
        updateData.filename = filename;
    }

    try {
        await updateDocument(documentId, updateData);
        closeEditModal();
        reloadDocumentsTable();
    } catch (error) {
        alert(`Failed to update document: ${error.message}`);
        console.error('Error updating document:', error);
    }
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
 * API key is automatically injected by APIKeyMiddleware from session cookie.
 * @param {File} file - File to upload.
 * @returns {Promise<Object>} Uploaded document data.
 */
async function uploadDocument(file) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch('/api/documents', {
        method: 'POST',
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

// Progress tracking via SSE
const progressConnections = new Map(); // documentId -> EventSource

/**
 * Start tracking progress for a document via SSE.
 * @param {number} documentId - Document ID to track.
 */
function startProgressTracking(documentId) {
    // Don't start if already tracking
    if (progressConnections.has(documentId)) {
        return;
    }

    const eventSource = new EventSource(`/admin/api/documents/${documentId}/progress`);

    eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            updateProgressBar(documentId, data.page, data.total);

            // Update status if processing or ready
            if (data.status === 'processing') {
                updateDocumentStatus(documentId, 'processing');
            } else if (data.status === 'ready') {
                updateDocumentStatus(documentId, 'ready');
                stopProgressTracking(documentId);
            }
        } catch (error) {
            console.error('Error parsing progress data:', error);
        }
    };

    eventSource.onerror = (error) => {
        console.error(`SSE error for document ${documentId}:`, error);
        // Close connection on error
        stopProgressTracking(documentId);
    };

    progressConnections.set(documentId, eventSource);
}

/**
 * Stop tracking progress for a document.
 * @param {number} documentId - Document ID to stop tracking.
 */
function stopProgressTracking(documentId) {
    const eventSource = progressConnections.get(documentId);
    if (eventSource) {
        eventSource.close();
        progressConnections.delete(documentId);
    }
}

/**
 * Update progress bar UI for a document.
 * @param {number} documentId - Document ID.
 * @param {number} page - Current page number.
 * @param {number} total - Total pages.
 */
function updateProgressBar(documentId, page, total) {
    const container = document.querySelector(
        `.progress-bar-container[data-document-id="${documentId}"]`
    );
    if (!container) {
        return;
    }

    const fill = container.querySelector('.progress-bar-fill');
    const text = container.querySelector('.progress-text');

    if (fill && text) {
        const percentage = total > 0 ? (page / total) * 100 : 0;
        fill.style.width = `${percentage}%`;
        text.textContent = `${page}/${total}`;
    }
}

/**
 * Update document status badge in the table.
 * @param {number} documentId - Document ID.
 * @param {string} status - New status value.
 */
function updateDocumentStatus(documentId, status) {
    const container = document.querySelector(
        `.progress-bar-container[data-document-id="${documentId}"]`
    );
    if (!container) {
        return;
    }

    const row = container.closest('.table-row');
    if (!row) {
        return;
    }

    const statusBadge = row.querySelector('.status-badge');
    if (statusBadge) {
        // Remove old status class
        statusBadge.className = 'status-badge';
        // Add new status class
        statusBadge.classList.add(status);
        statusBadge.textContent = status;

        // Update tooltip for error status
        if (status === 'error') {
            // Try to get error message from data attribute or keep existing title
            const errorMessage = statusBadge.getAttribute('data-error-message');
            if (errorMessage) {
                statusBadge.setAttribute('title', errorMessage);
            }
        } else {
            // Remove title for non-error statuses
            statusBadge.removeAttribute('title');
        }
    }

    // Update button states based on status
    const viewButton = row.querySelector('button[data-button-type="view"]');
    const deleteButton = row.querySelector('button[data-button-type="delete"]');

    if (status === 'pending' || status === 'processing') {
        // Disable buttons for pending/processing status
        if (viewButton) {
            viewButton.disabled = true;
            viewButton.classList.add('icon-btn-disabled');
            viewButton.title = `View not available (${status})`;
            viewButton.removeAttribute('onclick');
        }
        if (deleteButton) {
            deleteButton.disabled = true;
            deleteButton.classList.add('icon-btn-disabled');
            deleteButton.title = `Delete not available (${status})`;
            deleteButton.removeAttribute('onclick');
        }
    } else {
        // Enable buttons for other statuses (ready, uploaded, etc.)
        if (viewButton) {
            viewButton.disabled = false;
            viewButton.classList.remove('icon-btn-disabled');
            viewButton.title = 'View Document';
            const docId = viewButton.getAttribute('data-document-id') || documentId;
            viewButton.setAttribute('onclick', `viewDocument(${docId})`);
        }
        if (deleteButton) {
            deleteButton.disabled = false;
            deleteButton.classList.remove('icon-btn-disabled');
            deleteButton.title = 'Delete Document';
            const docId = deleteButton.getAttribute('data-document-id') || documentId;
            deleteButton.setAttribute(
                'onclick',
                `deleteDocument(${docId}, this); return false;`
            );
        }
    }
}

/**
 * Initialize progress tracking for all processing documents on page load.
 */
function initializeProgressTracking() {
    // Find all progress containers
    const progressContainers = document.querySelectorAll('.progress-bar-container');

    progressContainers.forEach((container) => {
        const documentId = parseInt(
            container.getAttribute('data-document-id'),
            10
        );
        if (!documentId) {
            return;
        }

        // Get initial progress from data attributes (from database)
        const page = parseInt(container.getAttribute('data-progress-page') || '0', 10);
        const total = parseInt(container.getAttribute('data-progress-total') || '0', 10);

        // Display initial progress if available
        if (total > 0) {
            updateProgressBar(documentId, page, total);
        }

        // Find status badge to check document status
        const row = container.closest('.table-row');
        if (!row) {
            return;
        }

        const statusBadge = row.querySelector('.status-badge');
        if (!statusBadge) {
            return;
        }

        const status = statusBadge.textContent.trim().toLowerCase();

        // Start SSE tracking only for processing or pending documents
        if (status === 'processing' || status === 'pending') {
            // Try to get current progress from Redis first
            fetch(`/admin/api/documents/${documentId}/progress/current`)
                .then((response) => {
                    if (response.ok) {
                        return response.json();
                    }
                    return null;
                })
                .then((progress) => {
                    if (progress) {
                        updateProgressBar(
                            documentId,
                            progress.page,
                            progress.total
                        );
                    }
                    // Start SSE tracking
                    startProgressTracking(documentId);
                })
                .catch((error) => {
                    console.error(
                        `Error fetching current progress for ${documentId}:`,
                        error
                    );
                    // Start SSE tracking anyway
                    startProgressTracking(documentId);
                });
        }
    });
}

// Export functions for use in other scripts
window.AdminAPI = {
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
    editDocument,
    showEditModal,
    closeEditModal,
    handleEditFormSubmit,
    handleFilterChange,
    initializeFilterHandlers,
    uploadDocument,
    showLoadingOverlay,
    hideLoadingOverlay,
    handleFileUpload,
    initializeFileUpload,
    startProgressTracking,
    stopProgressTracking,
    updateProgressBar,
    initializeProgressTracking,
};

// Global functions for onclick handlers
// Must be exported immediately (not in DOMContentLoaded) for inline onclick handlers
window.viewDocument = viewDocument;
window.deleteDocument = deleteDocumentWithConfirm;
window.startDocumentProcessing = startDocumentProcessing;
window.editDocument = editDocument;
window.closeEditModal = closeEditModal;

// Initialize handlers when DOM is ready
function initializeAllHandlers() {
    initializeFilterHandlers();
    initializeFileUpload();
    initializeProgressTracking();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeAllHandlers);
} else {
    initializeAllHandlers();
}
