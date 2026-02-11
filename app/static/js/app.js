/**
 * Insurance Document Intelligence Assistant
 * Frontend Application
 */

// ==========================================================================
// State Management
// ==========================================================================

const state = {
    documents: [],
    messages: [],
    isLoading: false,
};

// ==========================================================================
// DOM Elements
// ==========================================================================

const elements = {
    uploadZone: document.getElementById('uploadZone'),
    fileInput: document.getElementById('fileInput'),
    uploadFilesBtn: document.getElementById('uploadFilesBtn'),
    folderPathInput: document.getElementById('folderPathInput'),
    loadFolderBtn: document.getElementById('loadFolderBtn'),
    documentsList: document.getElementById('documentsList'),
    messagesContainer: document.getElementById('messagesContainer'),
    welcomeMessage: document.getElementById('welcomeMessage'),
    typingIndicator: document.getElementById('typingIndicator'),
    messageInput: document.getElementById('messageInput'),
    sendBtn: document.getElementById('sendBtn'),
    ingestBtn: document.getElementById('ingestBtn'),
    clearChatBtn: document.getElementById('clearChatBtn'),
    loadingOverlay: document.getElementById('loadingOverlay'),
    statusIndicator: document.getElementById('statusIndicator'),
    statusText: document.getElementById('statusText'),
    chatContainer: document.getElementById('chatContainer'),
};

// ==========================================================================
// API Functions
// ==========================================================================

const api = {
    baseUrl: '/api',

    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${this.baseUrl}/upload`, {
            method: 'POST',
            body: formData
        });

        return response.json();
    },

    async ingestFolder() {
        const response = await fetch(`${this.baseUrl}/ingest-folder`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });

        return response.json();
    },

    async loadFolderPath(folderPath) {
        const response = await fetch(`${this.baseUrl}/load-folder-path`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_path: folderPath })
        });

        return response.json();
    },

    async refreshUploads() {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        try {
            const response = await fetch(`${this.baseUrl}/refresh-uploads`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                signal: controller.signal
            });
            return response.json();
        } finally {
            clearTimeout(timeoutId);
        }
    },

    async getDocuments() {
        const response = await fetch(`${this.baseUrl}/documents`);
        return response.json();
    },

    async sendMessage(message) {
        const controller = new AbortController();
        // 3-minute timeout: first request loads ML model which is slow
        const timeoutId = setTimeout(() => controller.abort(), 180000);
        try {
            const response = await fetch(`${this.baseUrl}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message }),
                signal: controller.signal
            });
            return response.json();
        } finally {
            clearTimeout(timeoutId);
        }
    },

    async clearChat() {
        const response = await fetch(`${this.baseUrl}/chat/clear`, {
            method: 'POST'
        });

        return response.json();
    }
};

// ==========================================================================
// UI Functions
// ==========================================================================

function setLoading(loading, message = 'Processing...') {
    state.isLoading = loading;
    elements.loadingOverlay.classList.toggle('visible', loading);
    elements.loadingOverlay.querySelector('p').textContent = message;
}

// Folder path history (localStorage)
const FOLDER_HISTORY_KEY = 'insuranceAI_folderPaths';

function getFolderPathHistory() {
    try {
        return JSON.parse(localStorage.getItem(FOLDER_HISTORY_KEY)) || [];
    } catch {
        return [];
    }
}

function saveFolderPath(path) {
    const history = getFolderPathHistory();
    // Remove if already exists, then add to front
    const filtered = history.filter(p => p !== path);
    filtered.unshift(path);
    // Keep last 10 paths
    localStorage.setItem(FOLDER_HISTORY_KEY, JSON.stringify(filtered.slice(0, 10)));
    populateFolderPathDropdown();
}

function populateFolderPathDropdown() {
    const datalist = document.getElementById('folderPathHistory');
    if (!datalist) return;
    let history = getFolderPathHistory();
    // Pre-seed with default upload path if no history
    if (history.length === 0) {
        history = ['C:\\Users\\aksal\\Documents\\project\\insurance_ai_analyzer\\data\\uploads'];
    }
    datalist.innerHTML = history.map(p => `<option value="${p}">`).join('');
}

function setStatus(text, isActive = true) {
    elements.statusText.textContent = text;
    elements.statusIndicator.style.background = isActive ? 'var(--success)' : 'var(--gray-500)';
}

function showTyping(show) {
    elements.typingIndicator.classList.toggle('visible', show);
    if (show) {
        scrollToBottom();
    }
}

function scrollToBottom() {
    elements.chatContainer.scrollTop = elements.chatContainer.scrollHeight;
}

function hideWelcome() {
    elements.welcomeMessage.style.display = 'none';
}

// ==========================================================================
// Document List
// ==========================================================================

function renderDocuments(documents) {
    if (!documents || documents.length === 0) {
        elements.documentsList.innerHTML = `
            <div class="no-documents">
                <p>No documents uploaded</p>
            </div>
        `;
        return;
    }

    elements.documentsList.innerHTML = documents.map(doc => `
        <div class="document-item" data-id="${doc.id}">
            <div class="document-icon ${doc.type}">
                ${doc.type === 'excel'
            ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 17V7m0 10l3-3m-3 3l-3-3m12 3V7m0 10l-3-3m3 3l3-3"/></svg>'
            : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"/></svg>'
        }
            </div>
            <div class="document-info">
                <div class="document-name">${doc.filename || doc.name}</div>
                <div class="document-meta">${doc.type.toUpperCase()}</div>
            </div>
        </div>
    `).join('');

    // Add click handlers
    document.querySelectorAll('.document-item').forEach(item => {
        item.addEventListener('click', () => {
            const docId = item.dataset.id;
            sendMessage(`Analyze document ${docId}`);
        });
    });
}

async function loadDocuments() {
    try {
        const data = await api.getDocuments();
        state.documents = data.documents || [];
        renderDocuments(state.documents);
    } catch (error) {
        console.error('Failed to load documents:', error);
    }
}

// ==========================================================================
// Messages
// ==========================================================================

function addMessage(role, content) {
    state.messages.push({ role, content });

    hideWelcome();

    const messageEl = document.createElement('div');
    messageEl.className = `message ${role}`;

    const avatarSvg = role === 'assistant'
        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>'
        : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>';

    // Parse markdown for assistant messages
    const renderedContent = role === 'assistant'
        ? marked.parse(content)
        : escapeHtml(content);

    messageEl.innerHTML = `
        <div class="message-avatar">${avatarSvg}</div>
        <div class="message-content">${renderedContent}</div>
    `;

    elements.messagesContainer.appendChild(messageEl);
    scrollToBottom();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==========================================================================
// Chat Handling
// ==========================================================================

async function sendMessage(message) {
    if (!message.trim() || state.isLoading) return;

    // Add user message
    addMessage('user', message);

    // Clear input
    elements.messageInput.value = '';
    autoResizeTextarea();

    // Show typing
    showTyping(true);
    setStatus('Analyzing...');

    try {
        const response = await api.sendMessage(message);

        showTyping(false);

        if (response.error) {
            addMessage('assistant', `❌ Error: ${response.error}`);
        } else {
            addMessage('assistant', response.response);
        }

        setStatus('Ready');

    } catch (error) {
        showTyping(false);
        addMessage('assistant', `❌ Failed to get response. Please try again.`);
        setStatus('Error', false);
        console.error('Chat error:', error);
    }
}

// ==========================================================================
// File Upload
// ==========================================================================

// Helper function to recursively get files from a directory entry
async function getFilesFromDirectory(directoryEntry) {
    const files = [];
    const reader = directoryEntry.createReader();

    const readEntries = () => new Promise((resolve, reject) => {
        reader.readEntries(resolve, reject);
    });

    const processEntry = async (entry) => {
        if (entry.isFile) {
            return new Promise((resolve) => {
                entry.file(resolve);
            });
        } else if (entry.isDirectory) {
            const subFiles = await getFilesFromDirectory(entry);
            return subFiles;
        }
    };

    let entries = await readEntries();
    while (entries.length > 0) {
        for (const entry of entries) {
            const result = await processEntry(entry);
            if (Array.isArray(result)) {
                files.push(...result);
            } else if (result) {
                files.push(result);
            }
        }
        entries = await readEntries();
    }

    return files;
}

// Filter files to only include valid extensions
function filterValidFiles(files) {
    const validExtensions = ['.xlsx', '.xls', '.pdf'];
    return Array.from(files).filter(file => {
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        return validExtensions.includes(ext);
    });
}

async function handleFileUpload(files, isFolder = false) {
    if (!files || files.length === 0) return;

    // Filter to only valid file types
    const validFiles = filterValidFiles(files);

    if (validFiles.length === 0) {
        addMessage('assistant', '⚠️ No valid files found. Please upload Excel (.xlsx, .xls) or PDF files.');
        return;
    }

    const uploadType = isFolder ? 'folder' : 'files';
    setLoading(true, `Uploading ${validFiles.length} ${uploadType === 'folder' ? 'file(s) from folder' : 'file(s)'}...`);

    let successCount = 0;
    let failCount = 0;

    try {
        for (const file of validFiles) {
            const result = await api.uploadFile(file);

            if (result.error) {
                failCount++;
                console.error(`Failed to upload ${file.name}:`, result.error);
            } else {
                successCount++;
            }
        }

        // Show summary message
        if (isFolder) {
            addMessage('assistant', `📁 **Folder uploaded:** ${successCount} file(s) added${failCount > 0 ? `, ${failCount} failed` : ''}`);
        } else {
            if (successCount > 0) {
                addMessage('assistant', `✅ Successfully uploaded **${successCount}** file(s)${failCount > 0 ? ` (${failCount} failed)` : ''}`);
            } else {
                addMessage('assistant', `❌ Failed to upload files`);
            }
        }

        // Reload documents
        await loadDocuments();

        // Trigger ingestion
        const ingestResult = await api.ingestFolder();

        if (ingestResult.message) {
            hideWelcome();
            addMessage('assistant', ingestResult.message);
        }

    } catch (error) {
        addMessage('assistant', `❌ Upload failed: ${error.message}`);
        console.error('Upload error:', error);
    } finally {
        setLoading(false);
    }
}

// ==========================================================================
// Event Listeners
// ==========================================================================

function setupEventListeners() {
    // Upload Files button
    elements.uploadFilesBtn.addEventListener('click', () => {
        elements.fileInput.click();
    });

    // File input change
    elements.fileInput.addEventListener('change', (e) => {
        handleFileUpload(e.target.files, false);
        e.target.value = ''; // Reset
    });

    // Load Folder Path button
    elements.loadFolderBtn.addEventListener('click', async () => {
        const folderPath = elements.folderPathInput.value.trim();

        if (!folderPath) {
            addMessage('assistant', '⚠️ Please enter a folder path');
            return;
        }

        setLoading(true, 'Loading files from folder...');

        try {
            const result = await api.loadFolderPath(folderPath);

            if (result.error) {
                addMessage('assistant', `❌ ${result.error}`);
            } else {
                hideWelcome();
                addMessage('assistant', `📁 **Folder loaded:** ${result.files_copied} file(s) copied and analyzed`);

                if (result.message) {
                    addMessage('assistant', result.message);
                }

                // Save path to history and clear input
                saveFolderPath(folderPath);
                elements.folderPathInput.value = '';
            }

            await loadDocuments();

        } catch (error) {
            addMessage('assistant', `❌ Failed to load folder: ${error.message}`);
        } finally {
            setLoading(false);
        }
    });

    // Enter key on folder path input
    elements.folderPathInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            elements.loadFolderBtn.click();
        }
    });

    // Drag and drop files
    elements.uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        elements.uploadZone.classList.add('dragover');
    });

    elements.uploadZone.addEventListener('dragleave', () => {
        elements.uploadZone.classList.remove('dragover');
    });

    elements.uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        elements.uploadZone.classList.remove('dragover');
        handleFileUpload(e.dataTransfer.files, false);
    });

    // Send message
    elements.sendBtn.addEventListener('click', () => {
        sendMessage(elements.messageInput.value);
    });

    // Enter to send
    elements.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage(elements.messageInput.value);
        }
    });

    // Auto-resize textarea
    elements.messageInput.addEventListener('input', autoResizeTextarea);

    // Ingest button
    elements.ingestBtn.addEventListener('click', async () => {
        setLoading(true, 'Analyzing documents...');

        try {
            const result = await api.ingestFolder();

            if (result.message) {
                hideWelcome();
                addMessage('assistant', result.message);
            }

            await loadDocuments();

        } catch (error) {
            addMessage('assistant', `❌ Analysis failed: ${error.message}`);
        } finally {
            setLoading(false);
        }
    });

    // Clear chat button
    elements.clearChatBtn.addEventListener('click', async () => {
        try {
            await api.clearChat();

            state.messages = [];
            elements.messagesContainer.innerHTML = '';
            elements.welcomeMessage.style.display = 'block';

        } catch (error) {
            console.error('Failed to clear chat:', error);
        }
    });

    // Refresh documents button
    const refreshDocsBtn = document.getElementById('refreshDocsBtn');
    if (refreshDocsBtn) {
        refreshDocsBtn.addEventListener('click', async () => {
            try {
                setLoading(true, 'Refreshing documents...');

                const result = await api.refreshUploads();

                if (result.error) {
                    addMessage('assistant', `❌ ${result.error}`);
                } else {
                    // Render documents directly from response (registry may still be processing)
                    if (result.documents && result.documents.length > 0) {
                        const docs = result.documents.map((d, i) => ({
                            id: i + 1,
                            filename: d.name,
                            name: d.name,
                            type: d.type
                        }));
                        state.documents = docs;
                        renderDocuments(docs);
                    }
                    hideWelcome();
                    addMessage('assistant', result.message || `✅ Refreshed ${result.documents_ingested} documents`);
                }
            } catch (error) {
                addMessage('assistant', `❌ Refresh failed: ${error.message}`);
            } finally {
                setLoading(false);
            }
        });
    }
}

function autoResizeTextarea() {
    const textarea = elements.messageInput;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
}

// ==========================================================================
// Initialize
// ==========================================================================

async function init() {
    setupEventListeners();
    await loadDocuments();
    populateFolderPathDropdown();

    // Configure marked
    marked.setOptions({
        breaks: true,
        gfm: true
    });

    console.log('Insurance Document Intelligence Assistant initialized');
}

// Start the app
document.addEventListener('DOMContentLoaded', init);
