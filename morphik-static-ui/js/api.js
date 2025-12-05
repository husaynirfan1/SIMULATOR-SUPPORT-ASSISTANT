const API_BASE_URL = 'http://localhost:8000'; // Adjust if your backend runs elsewhere

const api = {
    /**
     * List all documents in a folder
     * @param {string} folderName - The folder name to list documents from
     * @returns {Promise<Object>} - Object with documents array and count
     */
    async listDocuments(folderName) {
        try {
            // Build URL with folder_name as QUERY PARAMETER (not in body)
            const url = folderName
                ? `${API_BASE_URL}/documents?folder_name=${encodeURIComponent(folderName)}`
                : `${API_BASE_URL}/documents`;

            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    document_filters: {},
                    skip: 0,
                    limit: 1000
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const documents = await response.json();

            // The API returns an array of Document objects directly
            return {
                documents: Array.isArray(documents) ? documents : [],
                returned_count: Array.isArray(documents) ? documents.length : 0
            };
        } catch (error) {
            console.error('Error listing documents:', error);
            throw error;
        }
    },

    /**
     * Upload a file to a specific folder
     * @param {File} file - The file to upload
     * @param {string} folderName - The folder to upload to
     * @returns {Promise<Object>} - Upload response with document ID
     */
    async ingestFile(file, folderName) {
        try {
            const formData = new FormData();
            formData.append('file', file);

            // Add folder_name as FORM FIELD (not query parameter)
            if (folderName) {
                formData.append('folder_name', folderName);
            }

            // Add empty metadata as required by API
            formData.append('metadata', '{}');

            const response = await fetch(`${API_BASE_URL}/ingest/file`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();

            // After successful ingestion, create or update the graph if folderName is provided
            if (folderName && result.external_id) {
                try {
                    const graphName = `${folderName}_graph`;
                    console.log(`📊 Starting graph operation for ${graphName}, document: ${result.external_id}`);

                    // Check if graph exists
                    const existingGraph = await this.getGraph(graphName, folderName);
                    console.log(`📊 Graph exists check result:`, existingGraph ? 'EXISTS' : 'NOT FOUND');

                    if (!existingGraph) {
                        // Create new graph with this document
                        console.log(`📊 Creating new graph: ${graphName} with document: ${result.external_id}`);
                        const createResult = await this.createGraph(graphName, folderName, [result.external_id]);
                        console.log(`✅ Graph created successfully:`, createResult);
                    } else {
                        // Update existing graph
                        console.log(`📊 Updating graph: ${graphName} with document: ${result.external_id}`);
                        const updateResult = await this.updateGraph(graphName, [result.external_id], folderName);
                        console.log(`✅ Graph updated successfully:`, updateResult);
                    }
                } catch (graphError) {
                    console.error('❌ Graph operation failed:', graphError);
                    console.error('❌ Error details:', {
                        message: graphError.message,
                        stack: graphError.stack
                    });
                    // Don't fail the entire operation if graph operation fails
                }
            }

            return result;
        } catch (error) {
            console.error('Error uploading file:', error);
            throw error;
        }
    },

    /**
     * Update a graph with new documents
     * @param {string} graphName - The name of the graph to update (e.g., 'planning_kb_graph')
     * @param {Array<string>} documentIds - Array of document IDs to add to the graph
     * @param {string} folderName - The folder name for scoping (e.g., 'planning_kb')
     * @param {Object} additionalFilters - Optional metadata filters
     * @returns {Promise<Object>} - Updated graph details
     */
    async updateGraph(graphName, documentIds = null, folderName = null, additionalFilters = null) {
        try {
            const payload = {
                additional_documents: documentIds
            };

            // Only include additional_filters if provided
            if (additionalFilters) {
                payload.additional_filters = additionalFilters;
            }

            // NOTE: DO NOT include folder_name in payload - causes backend to not find the graph
            // Graph names are already unique (e.g., "motion_kb_graph")

            const response = await fetch(`${API_BASE_URL}/graph/${encodeURIComponent(graphName)}/update`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                const errorMessage = errorData.detail || `HTTP ${response.status}: ${response.statusText}`;

                // Special handling for 404 - graph doesn't exist
                if (response.status === 404) {
                    throw new Error(`Graph "${graphName}" not found. Create the graph first before updating.`);
                }

                throw new Error(errorMessage);
            }

            return await response.json();
        } catch (error) {
            console.error('Error updating graph:', error);
            throw error;
        }
    },

    /**
     * Delete a document by ID
     * @param {string} documentId - The document ID to delete
     * @returns {Promise<Object>} - Delete response
     */
    async deleteDocument(documentId) {
        try {
            const response = await fetch(`${API_BASE_URL}/documents/${documentId}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error deleting document:', error);
            throw error;
        }
    },

    /**
     * Query documents with RAG
     * @param {string} query - The query string
     * @param {string} folderName - Optional folder to scope the query
     * @param {number} k - Number of chunks to retrieve
     * @returns {Promise<Object>} - Query response with completion and sources
     */
    async query(query, folderName = null, k = 4) {
        try {
            const payload = {
                query: query,
                k: k
            };

            // Build URL with folder_name as query parameter if provided
            let url = `${API_BASE_URL}/query`;
            if (folderName) {
                url += `?folder_name=${encodeURIComponent(folderName)}`;
            }

            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error querying:', error);
            throw error;
        }
    },

    /**
     * Get a specific document by ID
     * @param {string} documentId - The document ID
     * @returns {Promise<Object>} - Document details
     */
    async getDocument(documentId) {
        try {
            const response = await fetch(`${API_BASE_URL}/documents/${documentId}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error getting document:', error);
            throw error;
        }
    },

    /**
     * Get the processing status of a document
     * @param {string} documentId - The document ID
     * @returns {Promise<Object>} - Status object with processing state
     */
    async getDocumentStatus(documentId) {
        try {
            const response = await fetch(`${API_BASE_URL}/documents/${documentId}/status`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error getting document status:', error);
            throw error;
        }
    },

    /**
     * List all folders
     * @returns {Promise<Array>} - List of folders
     */
    async listFolders() {
        try {
            const response = await fetch(`${API_BASE_URL}/folders`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error listing folders:', error);
            throw error;
        }
    },

    /**
     * Create a new folder
     * @param {string} folderName - Name for the new folder
     * @returns {Promise<Object>} - Created folder details
     */
    async createFolder(folderName) {
        try {
            const response = await fetch(`${API_BASE_URL}/folders`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: folderName
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error creating folder:', error);
            throw error;
        }
    },

    /**
     * Create a new graph for a folder
     * @param {string} graphName - Name for the graph (e.g., 'planning_kb_graph')
     * @param {string} folderName - The folder name to scope the graph to
     * @param {Array<string>} documentIds - Optional list of specific document IDs
     * @param {Object} filters - Optional metadata filters
     * @returns {Promise<Object>} - Created graph details
     */
    async createGraph(graphName, folderName = null, documentIds = null, filters = null) {
        try {
            const payload = {
                name: graphName
            };

            // Add folder_name as TOP-LEVEL parameter (not in filters!)
            if (folderName) {
                payload.folder_name = folderName;
            }

            // Add optional document IDs
            if (documentIds && documentIds.length > 0) {
                payload.documents = documentIds;
            }

            // Add optional metadata filters
            if (filters) {
                payload.filters = filters;
            }

            const response = await fetch(`${API_BASE_URL}/graph/create`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error creating graph:', error);
            throw error;
        }
    },

    /**
     * Get a graph by name
     * @param {string} graphName - The name of the graph
     * @param {string} folderName - Optional folder name for scoping
     * @returns {Promise<Object|null>} - Graph details or null if not found
     */
    async getGraph(graphName, folderName = null) {
        // Build URL - DO NOT include folder_name as query param (causes backend error)
        // Graph names already include folder context (e.g., "motion_kb_graph")
        let url = `${API_BASE_URL}/graph/${encodeURIComponent(graphName)}`;

        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        // Return null if graph doesn't exist (404) - this is expected and not an error!
        if (response.status === 404) {
            return null;
        }

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));

            // Check if error message indicates graph not found (backend wraps 404 in 500)
            const errorMessage = errorData.detail || '';
            if (errorMessage.includes('404') && errorMessage.includes('not found')) {
                // Graph doesn't exist - return null instead of throwing
                return null;
            }

            // Backend has a bug with folder_name query param - if we see entity_id error, treat as not found
            if (errorMessage.includes('entity_id') || response.status === 500) {
                console.log(`Graph check failed (backend error), assuming graph doesn't exist: ${graphName}`);
                return null;
            }

            // For other errors, throw as normal
            console.error(`❌ getGraph error - Status: ${response.status}, Error:`, errorData);
            throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    },

    /**
     * Get graph visualization data
     * @param {string} graphName - The name of the graph
     * @param {string} folderName - Optional folder name for scoping
     * @returns {Promise<Object>} - Visualization data with nodes and links
     */
    async getGraphVisualization(graphName, folderName = null) {
        try {
            // Build URL - DO NOT include folder_name query param (causes backend errors)
            // Graph names are already unique (e.g., "motion_kb_graph")
            let url = `${API_BASE_URL}/graph/${encodeURIComponent(graphName)}/visualization`;

            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error getting graph visualization:', error);
            throw error;
        }
    }
};

// Export for module systems if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
}