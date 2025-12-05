const agents = [
    {
        id: 'planning_kb',
        name: 'Planning Agent',
        role: 'Query Routing & Orchestration',
        icon: '🎯',
        description: 'Analyzes queries and coordinates specialist agents',
        color: '#8b5cf6'
    },
    {
        id: 'interface_kb',
        name: 'Interface Specialist',
        role: 'UI/UX & HMI',
        icon: '🎨',
        description: 'Expert in user interfaces and control systems',
        color: '#3b82f6'
    },
    {
        id: 'motion_kb',
        name: 'Motion Specialist',
        role: 'Actuators & Kinematics',
        icon: '⚙️',
        description: 'Expert in motion systems and servo control',
        color: '#10b981'
    },
    {
        id: 'vibration_kb',
        name: 'Vibration Specialist',
        role: 'Analysis & Damping',
        icon: '📊',
        description: 'Expert in vibration analysis and frequency response',
        color: '#f59e0b'
    },
    {
        id: 'visual_kb',
        name: 'Visual Specialist',
        role: 'Display & Graphics',
        icon: '🖼️',
        description: 'Expert in visual systems and rendering',
        color: '#ec4899'
    },
    {
        id: 'computer_kb',
        name: 'Computer Specialist',
        role: 'Hardware & Software',
        icon: '💻',
        description: 'Expert in computing systems and networking',
        color: '#06b6d4'
    },
    {
        id: 'redteam_kb',
        name: 'Red Team Agent',
        role: 'Security & Threats',
        icon: '🔒',
        description: 'Expert in security and vulnerability assessment',
        color: '#ef4444'
    },

    {
        id: 'inventory_kb',
        name: 'Inventory Agent',
        role: 'Parts & Stock',
        icon: '📦',
        description: 'Expert in parts management and supply chain',
        color: '#84cc16'
    },
    {
        id: 'synthesis_kb',
        name: 'Synthesizer Agent',
        role: 'Response Integration',
        icon: '🧩',
        description: 'Combines insights from multiple specialists',
        color: '#a855f7'
    }
];

let currentAgent = null;

document.addEventListener('DOMContentLoaded', () => {
    renderAgents();
    setupModal();
    setupFileUpload();
});

function renderAgents() {
    const grid = document.getElementById('agents-grid');
    grid.innerHTML = agents.map((agent, index) => `
        <div class="agent-card animate-fade-in" 
             style="animation-delay: ${index * 50}ms; --agent-color: ${agent.color}" 
             onclick="openAgent('${agent.id}')">
            <div class="agent-status-indicator" style="background-color: ${agent.color}"></div>
            <div class="agent-header">
                <div class="agent-icon" style="border-color: ${agent.color}30">
                    ${agent.icon}
                </div>
                <div class="agent-info">
                    <h3>${agent.name}</h3>
                    <div class="agent-role">${agent.role}</div>
                </div>
            </div>
            <p class="agent-description">${agent.description}</p>
            <div class="agent-stats">
                <span id="doc-count-${agent.id}" class="loading-count">Loading...</span>
                <span style="color: ${agent.color}">Manage →</span>
            </div>
        </div>
    `).join('');

    // Load document counts for all agents
    agents.forEach(agent => loadDocumentCount(agent.id));
}

async function loadDocumentCount(agentId) {
    try {
        const data = await api.listDocuments(agentId);
        const count = data.returned_count || (data.documents || []).length;
        const countEl = document.getElementById(`doc-count-${agentId}`);
        if (countEl) {
            countEl.textContent = `${count} document${count !== 1 ? 's' : ''}`;
            countEl.classList.remove('loading-count');
        }
    } catch (error) {
        const countEl = document.getElementById(`doc-count-${agentId}`);
        if (countEl) {
            countEl.textContent = 'Error loading';
            countEl.classList.remove('loading-count');
        }
    }
}

async function openAgent(agentId) {
    currentAgent = agents.find(a => a.id === agentId);
    if (!currentAgent) return;

    const modal = document.getElementById('agent-modal');
    const modalHeader = modal.querySelector('.modal-header');

    // Update modal header with agent color
    document.getElementById('modal-agent-name').textContent = currentAgent.name;
    document.getElementById('modal-agent-role').textContent = currentAgent.role;
    document.getElementById('modal-agent-description').textContent = currentAgent.description;
    modalHeader.style.borderBottom = `2px solid ${currentAgent.color}`;

    // Add refresh button if not exists
    let refreshBtn = document.getElementById('refresh-docs-btn');
    if (!refreshBtn) {
        refreshBtn = document.createElement('button');
        refreshBtn.id = 'refresh-docs-btn';
        refreshBtn.className = 'action-btn';
        refreshBtn.innerHTML = '🔄 Refresh';
        refreshBtn.style.marginLeft = 'auto';
        refreshBtn.onclick = () => loadDocuments(currentAgent.id);

        // Insert before close button
        const closeBtn = modalHeader.querySelector('.close-btn');
        modalHeader.insertBefore(refreshBtn, closeBtn);
    }

    modal.classList.add('active');

    // Ensure graph exists for this agent's knowledge base (run in background)
    ensureGraphExists(agentId).catch(err =>
        console.warn(`Graph initialization failed for ${agentId}:`, err)
    );

    await loadDocuments(agentId);
    await loadGraphVisualization(agentId);

    // Setup refresh button
    const refreshGraphBtn = document.getElementById('refresh-graph-btn');
    refreshGraphBtn.style.display = 'block';
    refreshGraphBtn.onclick = () => loadGraphVisualization(agentId);
}

function closeModal() {
    const modal = document.getElementById('agent-modal');
    modal.classList.remove('active');
    modal.querySelector('.modal-header').style.borderBottom = '';
    currentAgent = null;
}

async function loadDocuments(folderName) {
    const listEl = document.getElementById('doc-list');
    const countEl = document.getElementById('doc-count');

    listEl.innerHTML = '<li style="text-align:center; padding: 1rem; color: var(--text-secondary);"><div class="loading-spinner"></div> Loading documents...</li>';

    try {
        const data = await api.listDocuments(folderName);
        const docs = data.documents || [];
        const count = data.returned_count || docs.length;

        countEl.textContent = `${count} document${count !== 1 ? 's' : ''}`;

        if (docs.length === 0) {
            listEl.innerHTML = `
                <li style="text-align:center; padding: 2rem; color: var(--text-secondary);">
                    <div style="font-size: 3rem; margin-bottom: 1rem; opacity: 0.3;">📁</div>
                    <div>No documents in knowledge base yet.</div>
                    <div style="font-size: 0.9rem; margin-top: 0.5rem;">Upload files to get started.</div>
                </li>
            `;
            return;
        }

        listEl.innerHTML = docs.map((doc, index) => {
            // Morphik uses 'external_id' not 'id'
            const docId = doc.external_id || doc.id || 'unknown';
            const uploadDate = doc.system_metadata?.created_at || doc.created_at
                ? new Date(doc.system_metadata?.created_at || doc.created_at).toLocaleDateString()
                : 'Unknown';
            const fileSize = doc.metadata?.file_size ? formatFileSize(doc.metadata.file_size) : '';
            const safeFilename = (doc.filename || 'Untitled Document').replace(/'/g, "\\'");

            // Get document status from system_metadata or root
            const status = doc.system_metadata?.status || doc.status || 'unknown';
            const statusInfo = getStatusBadge(status);

            return `
                <li class="doc-item" style="animation-delay: ${index * 30}ms">
                    <div style="display: flex; align-items: center; gap: 0.75rem; flex: 1;">
                        <span style="font-size: 1.5rem;">${getFileIcon(doc.filename)}</span>
                        <div style="flex: 1; min-width: 0;">
                            <div style="display: flex; align-items: center; gap: 0.5rem;">
                                <span style="font-weight: 500; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                                    ${doc.filename || 'Untitled Document'}
                                </span>
                                <span class="status-badge status-${status}" title="${statusInfo.tooltip}">
                                    ${statusInfo.icon} ${statusInfo.label}
                                </span>
                            </div>
                            <div style="font-size: 0.8rem; color: var(--text-secondary); display: flex; gap: 1rem; margin-top: 0.25rem; flex-wrap: wrap;">
                                <span title="Document ID">ID: ${docId.substring(0, 12)}...</span>
                                ${uploadDate !== 'Unknown' ? `<span>📅 ${uploadDate}</span>` : ''}
                                ${fileSize ? `<span>💾 ${fileSize}</span>` : ''}
                            </div>
                        </div>
                    </div>
                    <button class="delete-btn" onclick="deleteDoc('${docId}', '${safeFilename}')" title="Delete document">
                        🗑️
                    </button>
                </li>
            `;
        }).join('');
    } catch (error) {
        console.error('Error loading documents:', error);
        listEl.innerHTML = `
            <li style="text-align:center; padding: 2rem; color: #ef4444;">
                <div style="font-size: 2rem; margin-bottom: 1rem;">⚠️</div>
                <div>Error loading documents</div>
                <div style="font-size: 0.9rem; margin-top: 0.5rem; color: var(--text-secondary);">${error.message}</div>
            </li>
        `;
    }
}

function getFileIcon(filename) {
    if (!filename) return '📄';
    const ext = filename.split('.').pop().toLowerCase();
    const iconMap = {
        'pdf': '📕',
        'doc': '📘',
        'docx': '📘',
        'txt': '📝',
        'md': '📝',
        'xls': '📊',
        'xlsx': '📊',
        'csv': '📊',
        'ppt': '📙',
        'pptx': '📙',
        'jpg': '🖼️',
        'jpeg': '🖼️',
        'png': '🖼️',
        'gif': '🖼️',
        'zip': '🗜️',
        'rar': '🗜️',
        'json': '⚙️',
        'xml': '⚙️',
        'html': '🌐',
        'css': '🎨',
        'js': '⚡',
        'py': '🐍',
        'java': '☕',
        'cpp': '⚙️',
        'c': '⚙️'
    };
    return iconMap[ext] || '📄';
}

function formatFileSize(bytes) {
    if (!bytes) return '';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function getStatusBadge(status) {
    const statusMap = {
        'completed': {
            icon: '✓',
            label: 'Ready',
            tooltip: 'Document processed and ready for queries',
            color: '#22c55e'
        },
        'processing': {
            icon: '⏳',
            label: 'Processing',
            tooltip: 'Document is being processed',
            color: '#f59e0b'
        },
        'failed': {
            icon: '✗',
            label: 'Failed',
            tooltip: 'Document processing failed',
            color: '#ef4444'
        },
        'pending': {
            icon: '⏸',
            label: 'Pending',
            tooltip: 'Document queued for processing',
            color: '#3b82f6'
        },
        'unknown': {
            icon: '?',
            label: 'Unknown',
            tooltip: 'Status unavailable',
            color: '#6b7280'
        }
    };

    return statusMap[status] || statusMap['unknown'];
}

async function deleteDoc(docId, filename) {
    if (!currentAgent) return;

    if (!confirm(`Are you sure you want to delete "${filename}"?\n\nThis action cannot be undone.`)) {
        return;
    }

    try {
        await api.deleteDocument(docId);
        // Refresh the document list
        await loadDocuments(currentAgent.id);
        // Update the count on the main grid
        await loadDocumentCount(currentAgent.id);
    } catch (error) {
        alert(`Failed to delete document: ${error.message}`);
    }
}

function setupModal() {
    // Close on click outside
    document.getElementById('agent-modal').addEventListener('click', (e) => {
        if (e.target.id === 'agent-modal') closeModal();
    });

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && currentAgent) {
            closeModal();
        }
    });
}

function setupFileUpload() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', async (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');

        if (e.dataTransfer.files.length > 0) {
            await handleFiles(e.dataTransfer.files);
        }
    });

    fileInput.addEventListener('change', async () => {
        if (fileInput.files.length > 0) {
            await handleFiles(fileInput.files);
            fileInput.value = ''; // Reset input
        }
    });
}

async function handleFiles(files) {
    if (!currentAgent) return;

    const dropZone = document.getElementById('drop-zone');
    const originalContent = dropZone.innerHTML;
    const agentId = currentAgent.id; // Capture agent ID before any async operations

    // Show upload progress
    dropZone.innerHTML = `
        <div class="upload-progress">
            <div class="loading-spinner"></div>
            <p>Uploading ${files.length} file${files.length > 1 ? 's' : ''}...</p>
        </div>
    `;
    dropZone.style.pointerEvents = 'none';

    let successCount = 0;
    let failCount = 0;
    const uploadedDocs = [];

    for (const file of files) {
        try {
            console.log(`Uploading ${file.name} to ${agentId}...`);
            const result = await api.ingestFile(file, agentId);
            successCount++;
            uploadedDocs.push({
                name: file.name,
                id: result.external_id || result.id
            });
        } catch (error) {
            console.error(`Failed to upload ${file.name}:`, error);
            failCount++;
        }
    }

    // Restore drop zone
    dropZone.innerHTML = originalContent;
    dropZone.style.pointerEvents = '';

    // Show result
    if (failCount > 0) {
        showToast(`Upload complete: ${successCount} succeeded, ${failCount} failed`, 'warning');
    } else if (successCount > 0) {
        showToast(`${successCount} file${successCount > 1 ? 's' : ''} uploaded! Processing...`, 'info');
    }

    // Refresh list immediately to show uploaded files
    await loadDocuments(agentId);
    await loadDocumentCount(agentId);

    // Start polling for all successfully uploaded documents
    // Pass agentId so polling works even if modal is closed
    if (uploadedDocs.length > 0) {
        // Don't await - let it run in background
        pollDocumentStatus(uploadedDocs, agentId);
    }
}

function showToast(message, type = 'info') {
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    // Add to body
    document.body.appendChild(toast);

    // Trigger animation
    setTimeout(() => toast.classList.add('show'), 10);

    // Remove after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

async function pollDocumentStatus(docs, agentId) {
    // Poll document status for up to 60 seconds (20 attempts x 3 seconds)
    const maxAttempts = 20;
    const pollInterval = 3000; // 3 seconds

    console.log(`Starting status polling for ${docs.length} document(s)...`);

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
        await new Promise(resolve => setTimeout(resolve, pollInterval));

        let allCompleted = true;
        let statusCounts = {
            completed: 0,
            processing: 0,
            failed: 0,
            pending: 0
        };

        // Check status of each uploaded document
        for (const doc of docs) {
            try {
                const statusResponse = await api.getDocumentStatus(doc.id);
                const status = statusResponse.status || 'unknown';

                console.log(`Document ${doc.name}: ${status}`);

                // Count statuses
                if (status === 'completed') {
                    statusCounts.completed++;
                } else if (status === 'processing') {
                    statusCounts.processing++;
                    allCompleted = false;
                } else if (status === 'failed') {
                    statusCounts.failed++;
                } else if (status === 'pending') {
                    statusCounts.pending++;
                    allCompleted = false;
                } else {
                    allCompleted = false;
                }
            } catch (error) {
                console.log(`Could not check status for ${doc.name}:`, error.message);
                allCompleted = false;
            }
        }

        // Update UI with current status
        const statusMessage = buildStatusMessage(statusCounts, docs.length);
        updateStatusToast(statusMessage, statusCounts);

        // If all completed or failed, stop polling
        if (allCompleted || (statusCounts.completed + statusCounts.failed === docs.length)) {
            console.log('All documents finished processing');

            // Final refresh - use agentId parameter instead of currentAgent
            if (currentAgent && currentAgent.id === agentId) {
                // Only refresh if modal is still open for the same agent
                await loadDocuments(agentId);
            }
            await loadDocumentCount(agentId);

            // Show final status
            if (statusCounts.failed > 0) {
                showToast(
                    `Processing complete: ${statusCounts.completed} succeeded, ${statusCounts.failed} failed`,
                    'warning'
                );
            } else {
                showToast('All documents processed successfully!', 'success');
            }

            // Remove the status toast
            removeStatusToast();

            break;
        }

        // Refresh document list periodically to show status updates
        // Only if modal is still open for the same agent
        if (attempt % 2 === 0 && currentAgent && currentAgent.id === agentId) {
            await loadDocuments(agentId);
        }
    }

    // Clean up status toast after polling ends
    removeStatusToast();
}

function buildStatusMessage(statusCounts, total) {
    const parts = [];

    if (statusCounts.completed > 0) {
        parts.push(`${statusCounts.completed} ready`);
    }
    if (statusCounts.processing > 0) {
        parts.push(`${statusCounts.processing} processing`);
    }
    if (statusCounts.pending > 0) {
        parts.push(`${statusCounts.pending} pending`);
    }
    if (statusCounts.failed > 0) {
        parts.push(`${statusCounts.failed} failed`);
    }

    return parts.length > 0
        ? `Processing: ${parts.join(', ')}`
        : `Processing ${total} document${total > 1 ? 's' : ''}...`;
}

function updateStatusToast(message, statusCounts) {
    // Find or create a persistent status toast
    let statusToast = document.getElementById('status-toast');

    if (!statusToast) {
        statusToast = document.createElement('div');
        statusToast.id = 'status-toast';
        statusToast.className = 'toast toast-info show';
        statusToast.style.bottom = '2rem';
        statusToast.style.right = '2rem';
        document.body.appendChild(statusToast);
    }

    // Update content with spinner if still processing
    const hasProcessing = statusCounts.processing > 0 || statusCounts.pending > 0;
    statusToast.innerHTML = hasProcessing
        ? `<div style="display: flex; align-items: center; gap: 0.5rem;"><div class="loading-spinner" style="width: 16px; height: 16px; border-width: 2px;"></div><span>${message}</span></div>`
        : message;

    statusToast.classList.add('show');
}

function removeStatusToast() {
    const statusToast = document.getElementById('status-toast');
    if (statusToast) {
        statusToast.classList.remove('show');
        setTimeout(() => statusToast.remove(), 300);
    }
}

/**
 * Ensure a graph exists for the given folder/agent
 * Creates graph if it doesn't exist and folder has documents
 * @param {string} folderName - The folder name (e.g., 'planning_kb')
 */
async function ensureGraphExists(folderName) {
    try {
        const graphName = `${folderName}_graph`;

        // Check if graph already exists
        const existingGraph = await api.getGraph(graphName, folderName);

        if (existingGraph) {
            console.log(`✓ Graph ${graphName} already exists`);
            return;
        }

        // Get documents in folder
        const data = await api.listDocuments(folderName);
        const docs = data.documents || [];

        if (docs.length === 0) {
            console.log(`⚠ No documents in ${folderName}, skipping graph creation`);
            return;
        }

        // Only process completed documents
        const completedDocs = docs.filter(doc => {
            const status = doc.system_metadata?.status || doc.status;
            return status === 'completed';
        });

        if (completedDocs.length === 0) {
            console.log(`⚠ No completed documents in ${folderName}, skipping graph creation`);
            return;
        }

        // Create graph with all completed documents
        console.log(`Creating graph ${graphName} with ${completedDocs.length} completed documents...`);
        const documentIds = completedDocs.map(doc => doc.external_id || doc.id).filter(Boolean);

        await api.createGraph(graphName, folderName, documentIds);
        console.log(`✓ Graph ${graphName} created successfully`);

    } catch (error) {
        console.warn(`Failed to ensure graph exists for ${folderName}:`, error);
        // Don't throw - this is non-critical background operation
    }
}

/**
 * Load and display knowledge graph visualization for an agent
 * @param {string} folderName - The folder name (e.g., 'planning_kb')
 */
async function loadGraphVisualization(folderName) {
    const container = document.getElementById('graph-container');
    if (!container) return;

    const graphName = `${folderName}_graph`;

    try {
        // Show loading state
        container.innerHTML = '<p style="text-align: center; color: var(--text-secondary);">Loading graph...</p>';

        // Get graph visualization data
        const graphData = await api.getGraphVisualization(graphName, folderName);

        if (!graphData || (!graphData.nodes && !graphData.entities)) {
            container.innerHTML = `
                <div style="text-align: center; padding: 2rem;">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">📊</div>
                    <p style="color: var(--text-secondary); margin-bottom: 0.5rem;">No knowledge graph available</p>
                    <p style="font-size: 0.85rem; color: var(--text-secondary);">Upload documents to build the graph</p>
                </div>
            `;
            return;
        }

        // Extract nodes and links from response
        const nodes = graphData.nodes || graphData.entities || [];
        const links = graphData.links || graphData.relationships || [];

        // Display graph statistics
        container.innerHTML = `
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin-bottom: 1.5rem;">
                <div style="text-align: center; padding: 1rem; background: var(--bg); border-radius: 8px;">
                    <div style="font-size: 2rem; margin-bottom: 0.5rem;">🔵</div>
                    <div style="font-size: 1.5rem; font-weight: 600;">${nodes.length}</div>
                    <div style="font-size: 0.85rem; color: var(--text-secondary);">Entities</div>
                </div>
                <div style="text-align: center; padding: 1rem; background: var(--bg); border-radius: 8px;">
                    <div style="font-size: 2rem; margin-bottom: 0.5rem;">🔗</div>
                    <div style="font-size: 1.5rem; font-weight: 600;">${links.length}</div>
                    <div style="font-size: 0.85rem; color: var(--text-secondary);">Relationships</div>
                </div>
            </div>

            <div style="margin-top: 1.5rem;">
                <h4 style="margin-bottom: 1rem; font-size: 0.95rem;">Key Entities</h4>
                <div id="entities-list" style="max-height: 300px; overflow-y: auto;"></div>
            </div>
        `;

        // Display entities
        const entitiesList = document.getElementById('entities-list');
        if (nodes.length > 0) {
            entitiesList.innerHTML = nodes.slice(0, 20).map(node => {
                const name = node.name || node.label || node.id || 'Unknown';
                const type = node.type || node.entity_type || 'Entity';
                return `
                    <div style="padding: 0.75rem; margin-bottom: 0.5rem; background: var(--bg); border-radius: 6px; border-left: 3px solid #3b82f6;">
                        <div style="font-weight: 500;">${escapeHtml(name)}</div>
                        <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.25rem;">${escapeHtml(type)}</div>
                    </div>
                `;
            }).join('');

            if (nodes.length > 20) {
                entitiesList.innerHTML += `
                    <p style="text-align: center; padding: 1rem; color: var(--text-secondary); font-size: 0.85rem;">
                        Showing 20 of ${nodes.length} entities
                    </p>
                `;
            }
        } else {
            entitiesList.innerHTML = '<p style="text-align: center; color: var(--text-secondary); padding: 2rem;">No entities found</p>';
        }

    } catch (error) {
        console.error('Error loading graph visualization:', error);
        container.innerHTML = `
            <div style="text-align: center; padding: 2rem;">
                <div style="font-size: 3rem; margin-bottom: 1rem;">⚠️</div>
                <p style="color: var(--text-secondary); margin-bottom: 0.5rem;">Failed to load knowledge graph</p>
                <p style="font-size: 0.85rem; color: var(--text-secondary);">${escapeHtml(error.message)}</p>
            </div>
        `;
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}