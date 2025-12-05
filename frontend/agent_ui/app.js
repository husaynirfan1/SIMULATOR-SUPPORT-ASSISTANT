// Configuration
const API_URLS = {
    agent: 'http://localhost:8002',
    computer: 'http://localhost:8034',
    pilot: 'http://localhost:8035'
};

const API_KEY = '01HTM6R2E3-HUSAYN-K8Z5W9XG'; // Hardcoded for demo, ideally from env/config

// DOM Elements
const tabs = document.querySelectorAll('.nav-btn');
const tabContents = document.querySelectorAll('.tab-content');
const chatHistory = document.getElementById('chat-history');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const kbSelect = document.getElementById('kb-select');
const ingestTextBtn = document.getElementById('ingest-text-btn');
const ingestTextInput = document.getElementById('ingest-text');
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const fileInfo = document.getElementById('file-name');
const ingestFileBtn = document.getElementById('ingest-file-btn');
const ingestStatus = document.getElementById('ingest-status');

// Document Elements
const docKbSelect = document.getElementById('doc-kb-select');
const documentsList = document.getElementById('documents-list');
const docStatusMsg = document.getElementById('doc-status-msg');

// Graph Elements
const graphKbSelect = document.getElementById('graph-kb-select');
const refreshGraphBtn = document.getElementById('refresh-graph-btn');
const graphContainer = document.getElementById('graph-container');
let network = null;

// Tab Switching
tabs.forEach(tab => {
    tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        tabContents.forEach(c => c.classList.remove('active'));

        tab.classList.add('active');
        document.getElementById(`${tab.dataset.tab}-tab`).classList.add('active');

        // Load content based on tab
        if (tab.dataset.tab === 'documents') {
            fetchDocuments();
        } else if (tab.dataset.tab === 'graph') {
            fetchGraph();
        }
    });
});

// Chat Functionality
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    // Add user message
    appendMessage('user', message);
    userInput.value = '';

    // Show loading state (optional)
    const loadingId = appendMessage('system', 'Thinking...');

    try {
        const response = await fetch(`${API_URLS.agent}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });

        const data = await response.json();

        // Remove loading message
        document.getElementById(loadingId).remove();

        if (data.response) {
            appendMessage('system', data.response);
        } else {
            appendMessage('system', 'Error: No response from agent.');
        }
    } catch (error) {
        document.getElementById(loadingId).remove();
        appendMessage('system', `Error: ${error.message}`);
    }
}

function appendMessage(role, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;
    msgDiv.id = `msg-${Date.now()}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = text;

    msgDiv.appendChild(contentDiv);
    chatHistory.appendChild(msgDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;

    return msgDiv.id;
}

sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Knowledge Base Ingestion

// Text Ingestion
ingestTextBtn.addEventListener('click', async () => {
    const text = ingestTextInput.value.trim();
    const targetKb = kbSelect.value;

    if (!text) return;

    setIngestStatus('Ingesting text...', 'info');

    try {
        const response = await fetch(`${API_URLS[targetKb]}/insert`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY
            },
            body: JSON.stringify({ text })
        });

        const data = await response.json();

        if (response.ok) {
            setIngestStatus(`Success: ${data.message}`, 'success');
            ingestTextInput.value = '';
        } else {
            throw new Error(data.detail || 'Ingestion failed');
        }
    } catch (error) {
        setIngestStatus(`Error: ${error.message}`, 'error');
    }
});

// File Upload Handling
dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.style.borderColor = 'var(--accent-color)';
});

dropZone.addEventListener('dragleave', () => {
    dropZone.style.borderColor = 'var(--border-color)';
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.style.borderColor = 'var(--border-color)';

    if (e.dataTransfer.files.length) {
        handleFileSelect(e.dataTransfer.files[0]);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
        handleFileSelect(e.target.files[0]);
    }
});

function handleFileSelect(file) {
    fileInfo.textContent = file.name;
    ingestFileBtn.disabled = false;
    // Store file for upload
    ingestFileBtn.onclick = () => uploadFile(file);
}

async function uploadFile(file) {
    const targetKb = kbSelect.value;
    const formData = new FormData();
    formData.append('file', file);

    setIngestStatus('Uploading file...', 'info');

    try {
        const response = await fetch(`${API_URLS[targetKb]}/insert/file`, {
            method: 'POST',
            headers: {
                'X-API-Key': API_KEY
            },
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            setIngestStatus(`Success: ${data.message}`, 'success');
            fileInfo.textContent = '';
            fileInput.value = '';
            ingestFileBtn.disabled = true;
        } else {
            throw new Error(data.detail || 'Upload failed');
        }
    } catch (error) {
        setIngestStatus(`Error: ${error.message}`, 'error');
    }
}

function setIngestStatus(message, type) {
    ingestStatus.textContent = message;
    ingestStatus.className = `status-message ${type}`;

    if (type === 'info') {
        ingestStatus.style.display = 'block';
        ingestStatus.style.color = 'var(--text-primary)';
        ingestStatus.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
        ingestStatus.style.borderColor = 'var(--border-color)';
    }
}

// Document Management
docKbSelect.addEventListener('change', fetchDocuments);

async function fetchDocuments() {
    const targetKb = docKbSelect.value;
    documentsList.innerHTML = '<div style="padding:1rem; text-align:center;">Loading...</div>';

    try {
        const response = await fetch(`${API_URLS[targetKb]}/documents/paginated`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY
            },
            body: JSON.stringify({
                page: 1,
                page_size: 100,
                sort_field: "updated_at",
                sort_direction: "desc"
            })
        });

        const data = await response.json();

        if (response.ok) {
            renderDocuments(data.documents);
        } else {
            throw new Error(data.detail || 'Failed to fetch documents');
        }
    } catch (error) {
        documentsList.innerHTML = `<div style="padding:1rem; color:var(--error-color);">Error: ${error.message}</div>`;
    }
}

function renderDocuments(docs) {
    if (!docs || docs.length === 0) {
        documentsList.innerHTML = '<div style="padding:1rem; text-align:center; color:var(--text-secondary);">No documents found</div>';
        return;
    }

    documentsList.innerHTML = docs.map(doc => `
        <div class="doc-item">
            <div class="doc-name" title="${doc.content_summary || 'No summary'}">${doc.file_path || doc.id}</div>
            <div><span class="doc-status ${doc.status.toLowerCase()}">${doc.status}</span></div>
            <div style="text-align:right;">
                <button class="delete-btn" onclick="deleteDocument('${doc.id}')">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `).join('');
}

async function deleteDocument(docId) {
    if (!confirm('Are you sure you want to delete this document?')) return;

    const targetKb = docKbSelect.value;

    try {
        const response = await fetch(`${API_URLS[targetKb]}/documents/delete_by_id`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY
            },
            body: JSON.stringify({ doc_ids: [docId] })
        });

        if (response.ok) {
            fetchDocuments(); // Refresh list
        } else {
            const data = await response.json();
            alert(`Failed to delete: ${data.detail || 'Unknown error'}`);
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}
// Expose deleteDocument to global scope for onclick handler
window.deleteDocument = deleteDocument;

// Graph Visualization
refreshGraphBtn.addEventListener('click', fetchGraph);
graphKbSelect.addEventListener('change', fetchGraph);

async function fetchGraph() {
    const targetKb = graphKbSelect.value;

    if (network) {
        network.destroy();
        network = null;
    }

    graphContainer.innerHTML = '<div style="display:flex; justify-content:center; align-items:center; height:100%;">Loading graph...</div>';

    try {
        // Fetch popular labels to build the graph
        const response = await fetch(`${API_URLS[targetKb]}/graph/label/popular?limit=50`, {
            headers: { 'X-API-Key': API_KEY }
        });

        const labels = await response.json();

        if (!response.ok) throw new Error('Failed to fetch graph data');

        // Now fetch graph for these labels (simplified approach: get graph for top label)
        if (labels.length > 0) {
            const graphResponse = await fetch(`${API_URLS[targetKb]}/graphs?label=${encodeURIComponent(labels[0])}&max_depth=2&max_nodes=100`, {
                headers: { 'X-API-Key': API_KEY }
            });

            const graphData = await graphResponse.json();
            renderGraph(graphData);
        } else {
            graphContainer.innerHTML = '<div style="display:flex; justify-content:center; align-items:center; height:100%; color:var(--text-secondary);">No graph data available</div>';
        }
    } catch (error) {
        graphContainer.innerHTML = `<div style="display:flex; justify-content:center; align-items:center; height:100%; color:var(--error-color);">Error: ${error.message}</div>`;
    }
}

function renderGraph(data) {
    // Transform data for vis-network
    // LightRAG returns { "node_label": ["connected_node_1", "connected_node_2"] } or possibly other formats

    const nodes = new vis.DataSet();
    const edges = new vis.DataSet();
    const addedNodes = new Set();

    // Handle different possible data formats
    if (typeof data === 'object' && data !== null) {
        // Check if it's an adjacency list format
        Object.entries(data).forEach(([source, targets]) => {
            // Add source node if not already added
            if (!addedNodes.has(source)) {
                nodes.add({ id: source, label: source, color: '#97c2fc' });
                addedNodes.add(source);
            }

            // Handle targets - could be array or single value
            if (Array.isArray(targets)) {
                targets.forEach(target => {
                    if (!addedNodes.has(target)) {
                        nodes.add({ id: target, label: target, color: '#97c2fc' });
                        addedNodes.add(target);
                    }
                    edges.add({ from: source, to: target });
                });
            } else if (typeof targets === 'string') {
                // Single target as string
                if (!addedNodes.has(targets)) {
                    nodes.add({ id: targets, label: targets, color: '#97c2fc' });
                    addedNodes.add(targets);
                }
                edges.add({ from: source, to: targets });
            }
        });
    }

    // If no nodes were added, show empty state
    if (nodes.length === 0) {
        graphContainer.innerHTML = '<div style="display:flex; justify-content:center; align-items:center; height:100%; color:var(--text-secondary);">No graph data to display</div>';
        return;
    }

    const container = document.getElementById('graph-container');
    const graphData = { nodes: nodes, edges: edges };
    const options = {
        nodes: {
            shape: 'dot',
            size: 16,
            font: { color: '#f8fafc' },
            borderWidth: 2
        },
        edges: {
            width: 1,
            color: { color: '#334155', highlight: '#3b82f6' },
            smooth: { type: 'continuous' }
        },
        physics: {
            stabilization: false,
            barnesHut: {
                gravitationalConstant: -8000,
                springConstant: 0.04,
                springLength: 95
            }
        },
        interaction: {
            hover: true,
            tooltipDelay: 200
        }
    };

    network = new vis.Network(container, graphData, options);
}
