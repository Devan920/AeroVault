/**
 * AeroVault — Modern Cloud Drive Application
 * Sleek SaaS Slate Interface with Electric Indigo / Violet Gradients
 */

(() => {
  // Application State
  const state = {
    currentFolderId: null,
    currentCategory: 'all', // 'all', 'recent', 'media', 'trash', 'settings'
    filterType: 'all',      // 'all', 'audio', 'video', 'image', 'document'
    sortBy: 'date_desc',
    searchQuery: '',
    viewMode: localStorage.getItem('aerovault_view_mode') || 'grid',
    density: localStorage.getItem('aerovault_density') || 'comfortable',
    theme: localStorage.getItem('aerovault_theme') || 'dark',
    folders: [],
    files: [],
    breadcrumbs: [{ id: null, name: 'AeroVault' }],
    activeAudio: null,
    moveTargetItem: null,
    storageStats: {},
  };

  // DOM Elements
  const elements = {
    themeToggleBtn: document.getElementById('themeToggleBtn'),
    sunIcon: document.querySelector('.sun-icon'),
    moonIcon: document.querySelector('.moon-icon'),
    gridViewBtn: document.getElementById('gridViewBtn'),
    listViewBtn: document.getElementById('listViewBtn'),
    brandLogo: document.getElementById('brandLogo'),
    globalSearchInput: document.getElementById('globalSearchInput'),
    clearSearchBtn: document.getElementById('clearSearchBtn'),
    refreshBtn: document.getElementById('refreshBtn'),
    emptyTrashBtn: document.getElementById('emptyTrashBtn'),
    newActionBtn: document.getElementById('newActionBtn'),
    newMenuDropdown: document.getElementById('newMenuDropdown'),
    menuNewFolderBtn: document.getElementById('menuNewFolderBtn'),
    menuUploadFileBtn: document.getElementById('menuUploadFileBtn'),
    menuUploadFolderBtn: document.getElementById('menuUploadFolderBtn'),
    fileInputHidden: document.getElementById('fileInputHidden'),
    folderInputHidden: document.getElementById('folderInputHidden'),
    bottomNavBar: document.getElementById('bottomNavBar'),
    fabNewBtn: document.getElementById('fabNewBtn'),
    breadcrumbsNav: document.getElementById('breadcrumbsNav'),
    filterChipsBar: document.getElementById('filterChipsBar'),
    sortSelect: document.getElementById('sortSelect'),
    workspaceSubbar: document.getElementById('workspaceSubbar'),
    vaultScrollCanvas: document.getElementById('vaultScrollCanvas'),
    contentLoader: document.getElementById('contentLoader'),
    emptyState: document.getElementById('emptyState'),
    emptyStateTitle: document.getElementById('emptyStateTitle'),
    emptyStateDesc: document.getElementById('emptyStateDesc'),
    emptyStateUploadBtn: document.getElementById('emptyStateUploadBtn'),
    foldersSection: document.getElementById('foldersSection'),
    foldersGrid: document.getElementById('foldersGrid'),
    filesSection: document.getElementById('filesSection'),
    filesGrid: document.getElementById('filesGrid'),
    filesListContainer: document.getElementById('filesListContainer'),
    filesListBody: document.getElementById('filesListBody'),
    // Settings View Elements
    settingsView: document.getElementById('settingsView'),
    themeDarkCard: document.getElementById('themeDarkCard'),
    themeLightCard: document.getElementById('themeLightCard'),
    settingsViewModeGroup: document.getElementById('settingsViewModeGroup'),
    settingsDensityGroup: document.getElementById('settingsDensityGroup'),
    settingsStorageMeterBar: document.getElementById('settingsStorageMeterBar'),
    settingsUsedSize: document.getElementById('settingsUsedSize'),
    settingsFileCount: document.getElementById('settingsFileCount'),
    settingsChunkCount: document.getElementById('settingsChunkCount'),
    dragDropOverlay: document.getElementById('dragDropOverlay'),
    uploadManager: document.getElementById('uploadManager'),
    uploadManagerTitle: document.getElementById('uploadManagerTitle'),
    uploadItemsList: document.getElementById('uploadItemsList'),
    minimizeUploadBtn: document.getElementById('minimizeUploadBtn'),
    closeUploadBtn: document.getElementById('closeUploadBtn'),
    // Lightbox Modal
    mediaModal: document.getElementById('mediaModal'),
    previewFilename: document.getElementById('previewFilename'),
    previewBadge: document.getElementById('previewBadge'),
    previewSize: document.getElementById('previewSize'),
    previewContentContainer: document.getElementById('previewContentContainer'),
    previewShareBtn: document.getElementById('previewShareBtn'),
    closePreviewBtn: document.getElementById('closePreviewBtn'),
    // Create Folder Dialog
    folderModal: document.getElementById('folderModal'),
    folderNameInput: document.getElementById('folderNameInput'),
    submitFolderBtn: document.getElementById('submitFolderBtn'),
    cancelFolderBtn: document.getElementById('cancelFolderBtn'),
    closeFolderModalBtn: document.getElementById('closeFolderModalBtn'),
    // Rename Dialog
    renameModal: document.getElementById('renameModal'),
    renameModalTitle: document.getElementById('renameModalTitle'),
    renameInput: document.getElementById('renameInput'),
    submitRenameBtn: document.getElementById('submitRenameBtn'),
    cancelRenameBtn: document.getElementById('cancelRenameBtn'),
    closeRenameModalBtn: document.getElementById('closeRenameModalBtn'),
    // Move Dialog
    moveModal: document.getElementById('moveModal'),
    moveFoldersList: document.getElementById('moveFoldersList'),
    submitMoveBtn: document.getElementById('submitMoveBtn'),
    cancelMoveBtn: document.getElementById('cancelMoveBtn'),
    closeMoveModalBtn: document.getElementById('closeMoveModalBtn'),
    toastContainer: document.getElementById('toastContainer'),
  };

  // Utilities
  function formatBytes(bytes, decimals = 1) {
    if (!+bytes) return '0.0 B';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
  }

  function formatDate(isoStr) {
    if (!isoStr) return '';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return isoStr;
    }
  }

  function getFileCategory(mime, filename) {
    const ext = (filename || '').split('.').pop().toLowerCase();
    if (mime.startsWith('image/') || ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp'].includes(ext)) return 'image';
    if (mime.startsWith('video/') || ['mp4', 'webm', 'mov', 'mkv', 'avi'].includes(ext)) return 'video';
    if (mime.startsWith('audio/') || ['mp3', 'wav', 'flac', 'ogg', 'm4a', 'aac'].includes(ext)) return 'audio';
    if (mime === 'application/pdf' || ext === 'pdf') return 'pdf';
    if (['txt', 'json', 'py', 'js', 'css', 'html', 'md', 'xml', 'log'].includes(ext)) return 'text';
    if (['zip', 'rar', '7z', 'tar', 'gz'].includes(ext)) return 'archive';
    return 'document';
  }

  function getFileIcon(category) {
    switch (category) {
      case 'image': return '🖼️';
      case 'video': return '🎬';
      case 'audio': return '🎵';
      case 'pdf': return '📕';
      case 'text': return '📝';
      case 'archive': return '📦';
      default: return '📄';
    }
  }

  function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'vault-toast';
    toast.innerHTML = `<span>⚡</span><span>${escapeHtml(message)}</span>`;
    elements.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(12px)';
      toast.style.transition = '0.2s ease';
      setTimeout(() => toast.remove(), 250);
    }, 3200);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g, tag => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#39;',
      '"': '&quot;'
    }[tag] || tag));
  }

  // ===================================================================
  // THEME MANAGEMENT
  // ===================================================================
  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    state.theme = theme;
    localStorage.setItem('aerovault_theme', theme);

    if (elements.sunIcon && elements.moonIcon) {
      if (theme === 'dark') {
        elements.sunIcon.classList.remove('hidden');
        elements.moonIcon.classList.add('hidden');
      } else {
        elements.sunIcon.classList.add('hidden');
        elements.moonIcon.classList.remove('hidden');
      }
    }

    // Synchronize settings theme cards if present
    if (elements.themeDarkCard && elements.themeLightCard) {
      elements.themeDarkCard.classList.toggle('active', theme === 'dark');
      elements.themeLightCard.classList.toggle('active', theme === 'light');
    }
  }

  function toggleTheme() {
    const newTheme = state.theme === 'dark' ? 'light' : 'dark';
    applyTheme(newTheme);
  }

  // ===================================================================
  // DENSITY MANAGEMENT (COMFORTABLE vs COMPACT)
  // ===================================================================
  function applyDensity(density) {
    document.documentElement.setAttribute('data-density', density);
    state.density = density;
    localStorage.setItem('aerovault_density', density);

    if (elements.settingsDensityGroup) {
      elements.settingsDensityGroup.querySelectorAll('.settings-toggle-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.density === density);
      });
    }
  }

  // ===================================================================
  // VIEW MODE (GRID vs LIST)
  // ===================================================================
  function applyViewMode(mode) {
    state.viewMode = mode;
    localStorage.setItem('aerovault_view_mode', mode);

    if (mode === 'grid') {
      elements.gridViewBtn.classList.add('active');
      elements.listViewBtn.classList.remove('active');
      elements.filesGrid.classList.remove('hidden');
      elements.filesListContainer.classList.add('hidden');
    } else {
      elements.gridViewBtn.classList.remove('active');
      elements.listViewBtn.classList.add('active');
      elements.filesGrid.classList.add('hidden');
      elements.filesListContainer.classList.remove('hidden');
    }

    if (elements.settingsViewModeGroup) {
      elements.settingsViewModeGroup.querySelectorAll('.settings-toggle-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === mode);
      });
    }
  }

  // ===================================================================
  // SYSTEM INFO & STORAGE STATS
  // ===================================================================
  function updateStorageUI() {
    const stats = state.storageStats || {};
    const activeBytes = stats.active_bytes || 0;
    const activeCount = stats.active_count || 0;
    const totalChunks = stats.total_chunks || 0;

    if (elements.settingsUsedSize) elements.settingsUsedSize.textContent = formatBytes(activeBytes);
    if (elements.settingsFileCount) elements.settingsFileCount.textContent = `${activeCount}`;
    if (elements.settingsChunkCount) elements.settingsChunkCount.textContent = `${totalChunks}`;

    if (elements.settingsStorageMeterBar) {
      const pct = Math.min(Math.max((activeBytes / (1024 * 1024 * 500)) * 100, 4), 96);
      elements.settingsStorageMeterBar.style.width = `${pct}%`;
    }
  }

  async function fetchSystemInfo() {
    try {
      const res = await fetch('/api/info');
      if (!res.ok) throw new Error('Info request failed');
      const data = await res.json();
      state.storageStats = data.stats || {};
      updateStorageUI();
    } catch (err) {
      console.error('fetchSystemInfo error:', err);
    }
  }

  // ===================================================================
  // BREADCRUMBS
  // ===================================================================
  async function loadBreadcrumbs() {
    if (state.currentCategory !== 'all') {
      let title = 'AeroVault';
      if (state.currentCategory === 'recent') title = 'Recent Uploads';
      if (state.currentCategory === 'media') title = 'Media & Audio';
      if (state.currentCategory === 'trash') title = 'Trash';
      elements.breadcrumbsNav.innerHTML = `<span class="breadcrumb-node active">${title}</span>`;
      return;
    }

    try {
      const fid = state.currentFolderId || 'root';
      const res = await fetch(`/api/folders/${fid}/breadcrumbs`);
      if (!res.ok) throw new Error('Breadcrumb error');
      const data = await res.json();
      state.breadcrumbs = data.breadcrumbs || [];

      elements.breadcrumbsNav.innerHTML = '';
      state.breadcrumbs.forEach((b, index) => {
        if (index > 0) {
          const sep = document.createElement('span');
          sep.className = 'breadcrumb-divider';
          sep.textContent = '/';
          elements.breadcrumbsNav.appendChild(sep);
        }

        const item = document.createElement('span');
        item.className = `breadcrumb-node ${index === state.breadcrumbs.length - 1 ? 'active' : ''}`;
        item.textContent = (b.name === 'My Drive' || b.name === 'All Files') ? 'AeroVault' : b.name;
        item.dataset.id = b.id || '';
        item.addEventListener('click', () => {
          if (index !== state.breadcrumbs.length - 1) {
            navigateToFolder(b.id);
          }
        });
        elements.breadcrumbsNav.appendChild(item);
      });
    } catch (err) {
      console.error('loadBreadcrumbs error:', err);
    }
  }

  // ===================================================================
  // LOAD CONTENTS (FOLDERS & FILES)
  // ===================================================================
  async function loadContents() {
    elements.contentLoader.classList.remove('hidden');
    elements.emptyState.classList.add('hidden');
    elements.foldersSection.classList.add('hidden');
    elements.filesSection.classList.add('hidden');

    if (state.currentCategory === 'trash') {
      elements.emptyTrashBtn.classList.remove('hidden');
    } else {
      elements.emptyTrashBtn.classList.add('hidden');
    }

    await loadBreadcrumbs();

    try {
      // 1. Fetch Folders
      if (state.currentCategory === 'all' && !state.searchQuery && state.filterType === 'all') {
        const folderParam = state.currentFolderId ? `?parent_id=${state.currentFolderId}` : '';
        const fRes = await fetch(`/api/folders${folderParam}`);
        if (fRes.ok) {
          const fData = await fRes.json();
          state.folders = fData.folders || [];
        } else {
          state.folders = [];
        }
      } else {
        state.folders = [];
      }

      // 2. Fetch Files
      const params = new URLSearchParams();
      if (state.currentFolderId && state.currentCategory === 'all') {
        params.append('folder_id', state.currentFolderId);
      }
      params.append('category', state.currentCategory);
      if (state.searchQuery) {
        params.append('search', state.searchQuery);
      }

      const filesRes = await fetch(`/api/files?${params.toString()}`);
      if (!filesRes.ok) throw new Error('Failed to load files');
      const filesData = await filesRes.json();
      let files = filesData.files || [];

      // Filter by Type Chip if selected
      if (state.filterType !== 'all') {
        files = files.filter(f => {
          const cat = getFileCategory(f.mime_type, f.filename);
          if (state.filterType === 'document') return ['document', 'text', 'pdf'].includes(cat);
          return cat === state.filterType;
        });
      }

      sortFileList(files);
      state.files = files;

      renderContents();
    } catch (err) {
      console.error('loadContents error:', err);
      showToast(`Error: ${err.message}`);
    } finally {
      elements.contentLoader.classList.add('hidden');
    }
  }

  function sortFileList(files) {
    const s = state.sortBy;
    files.sort((a, b) => {
      if (s === 'name_asc') return a.filename.localeCompare(b.filename);
      if (s === 'name_desc') return b.filename.localeCompare(a.filename);
      if (s === 'size_desc') return b.size_bytes - a.size_bytes;
      if (s === 'size_asc') return a.size_bytes - b.size_bytes;
      return new Date(b.created_at) - new Date(a.created_at);
    });
  }

  // ===================================================================
  // RENDER CONTENTS
  // ===================================================================
  function renderContents() {
    const hasFolders = state.folders.length > 0;
    const hasFiles = state.files.length > 0;

    if (!hasFolders && !hasFiles) {
      elements.emptyState.classList.remove('hidden');
      if (state.searchQuery) {
        elements.emptyStateTitle.textContent = 'No matching files found';
        elements.emptyStateDesc.textContent = `No items matched "${state.searchQuery}".`;
        elements.emptyStateUploadBtn.classList.add('hidden');
      } else if (state.currentCategory === 'trash') {
        elements.emptyStateTitle.textContent = 'Trash is empty';
        elements.emptyStateDesc.textContent = 'Deleted items appear here before permanent erasure.';
        elements.emptyStateUploadBtn.classList.add('hidden');
      } else {
        elements.emptyStateTitle.textContent = 'No files in this folder';
        elements.emptyStateDesc.textContent = 'Drag and drop files anywhere or click "+ New Upload" to store them in your Cloud Vault.';
        elements.emptyStateUploadBtn.classList.remove('hidden');
      }
      return;
    }

    elements.emptyState.classList.add('hidden');

    // Render Folders
    if (hasFolders) {
      elements.foldersSection.classList.remove('hidden');
      elements.foldersGrid.innerHTML = '';
      state.folders.forEach(folder => {
        elements.foldersGrid.appendChild(createFolderTile(folder));
      });
    } else {
      elements.foldersSection.classList.add('hidden');
    }

    // Render Files
    if (hasFiles) {
      elements.filesSection.classList.remove('hidden');

      // Grid View
      elements.filesGrid.innerHTML = '';
      state.files.forEach(file => {
        elements.filesGrid.appendChild(createFileTile(file));
      });

      // List View
      elements.filesListBody.innerHTML = '';
      state.files.forEach(file => {
        elements.filesListBody.appendChild(createFileTableRow(file));
      });
    } else {
      elements.filesSection.classList.add('hidden');
    }
  }

  // ===================================================================
  // COMPONENT CREATION
  // ===================================================================
  function createFolderTile(folder) {
    const tile = document.createElement('div');
    tile.className = 'folder-tile';
    tile.innerHTML = `
      <div class="folder-tile-left">
        <svg class="folder-tile-icon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"></path>
        </svg>
        <div class="folder-tile-info">
          <span class="folder-tile-name" title="${escapeHtml(folder.name)}">${escapeHtml(folder.name)}</span>
          <span class="folder-tile-meta">${folder.file_count || 0} items</span>
        </div>
      </div>
      <button class="item-action-btn" title="Folder actions">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="1.5"></circle>
          <circle cx="12" cy="5" r="1.5"></circle>
          <circle cx="12" cy="19" r="1.5"></circle>
        </svg>
      </button>
    `;

    tile.addEventListener('dblclick', () => navigateToFolder(folder.id));
    tile.querySelector('.folder-tile-left').addEventListener('click', () => navigateToFolder(folder.id));

    tile.querySelector('.item-action-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      openFolderContextMenu(folder, e);
    });

    return tile;
  }

  function createFileTile(file) {
    const category = getFileCategory(file.mime_type, file.filename);
    const icon = getFileIcon(category);
    const isTrashed = file.is_trashed === 1;

    const tile = document.createElement('div');
    tile.className = 'file-tile';

    // Preview area: image preview or waveform or category badge
    let previewContent = '';
    if (category === 'image') {
      previewContent = `<img src="/api/files/${file.id}/stream" alt="${escapeHtml(file.filename)}" loading="lazy">`;
    } else if (category === 'audio') {
      previewContent = `
        <div class="audio-waveform-preview">
          <div class="waveform-bar"></div>
          <div class="waveform-bar"></div>
          <div class="waveform-bar"></div>
          <div class="waveform-bar"></div>
          <div class="waveform-bar"></div>
          <div class="waveform-bar"></div>
        </div>
      `;
    } else {
      previewContent = `<span style="font-size:2.8rem;">${icon}</span>`;
    }

    const chunkCount = (file.chunk_message_ids || []).length;
    const chunkBadge = chunkCount > 1 ? `<span class="preview-badge-pill">${chunkCount} chunks</span>` : `<span class="preview-badge-pill">${category}</span>`;

    tile.innerHTML = `
      <div class="file-tile-header">
        <div class="file-tile-title-group">
          <span class="file-tile-icon">${icon}</span>
          <span class="file-tile-name" title="${escapeHtml(file.filename)}">${escapeHtml(file.filename)}</span>
        </div>
        <button class="item-action-btn" title="Actions">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="1.5"></circle>
            <circle cx="12" cy="5" r="1.5"></circle>
            <circle cx="12" cy="19" r="1.5"></circle>
          </svg>
        </button>
      </div>

      <div class="file-tile-preview">
        ${previewContent}
        ${chunkBadge}
      </div>

      <div class="file-tile-footer">
        <span>${formatBytes(file.size_bytes)}</span>
        <span>${formatDate(file.created_at)}</span>
      </div>
    `;

    tile.addEventListener('dblclick', () => {
      if (!isTrashed) openPreviewModal(file);
    });

    tile.querySelector('.file-tile-preview').addEventListener('click', () => {
      if (!isTrashed) openPreviewModal(file);
    });

    tile.querySelector('.item-action-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      openFileContextMenu(file, e);
    });

    return tile;
  }

  function createFileTableRow(file) {
    const category = getFileCategory(file.mime_type, file.filename);
    const icon = getFileIcon(category);
    const isTrashed = file.is_trashed === 1;

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="td-file-wrapper">
        <span>${icon}</span>
        <span title="${escapeHtml(file.filename)}">${escapeHtml(file.filename)}</span>
      </td>
      <td>${category.toUpperCase()}</td>
      <td>${formatDate(file.created_at)}</td>
      <td>${formatBytes(file.size_bytes)}</td>
      <td class="td-acts">
        <div class="row-actions-group">
          ${!isTrashed ? `
            <button class="item-action-btn act-share" title="Copy share link">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
              </svg>
            </button>
            <button class="item-action-btn act-download" title="Download">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
              </svg>
            </button>
            <button class="item-action-btn act-dots" title="More actions">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="1.5"></circle>
                <circle cx="12" cy="5" r="1.5"></circle>
                <circle cx="12" cy="19" r="1.5"></circle>
              </svg>
            </button>
          ` : `
            <button class="item-action-btn act-restore" title="Restore file">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="1 4 1 10 7 10"></polyline>
                <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path>
              </svg>
            </button>
            <button class="item-action-btn act-delete" title="Delete permanently" style="color: #EF4444;">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          `}
        </div>
      </td>
    `;

    tr.addEventListener('dblclick', () => {
      if (!isTrashed) openPreviewModal(file);
    });

    if (!isTrashed) {
      tr.querySelector('.act-share').onclick = (e) => { e.stopPropagation(); copyShareLink(file.id); };
      tr.querySelector('.act-download').onclick = (e) => { e.stopPropagation(); downloadFileDirect(file.id); };
      tr.querySelector('.act-dots').onclick = (e) => { e.stopPropagation(); openFileContextMenu(file, e); };
    } else {
      tr.querySelector('.act-restore').onclick = (e) => { e.stopPropagation(); restoreFile(file.id); };
      tr.querySelector('.act-delete').onclick = (e) => { e.stopPropagation(); deletePermanently(file.id); };
    }

    return tr;
  }

  // ===================================================================
  // NAVIGATION & FILTERING
  // ===================================================================
  function navigateToFolder(folderId) {
    state.currentFolderId = folderId || null;
    state.currentCategory = 'all';
    state.searchQuery = '';
    if (elements.globalSearchInput) elements.globalSearchInput.value = '';
    if (elements.clearSearchBtn) elements.clearSearchBtn.classList.add('hidden');

    if (elements.bottomNavBar) {
      elements.bottomNavBar.querySelectorAll('.bottom-nav-tab').forEach(el => {
        if (el.dataset.category === 'all') el.classList.add('active');
        else el.classList.remove('active');
      });
    }

    if (elements.settingsView) elements.settingsView.classList.add('hidden');
    if (elements.vaultScrollCanvas) elements.vaultScrollCanvas.classList.remove('hidden');
    if (elements.workspaceSubbar) elements.workspaceSubbar.classList.remove('hidden');

    loadContents();
  }

  function setCategory(category) {
    state.currentCategory = category;

    if (elements.bottomNavBar) {
      elements.bottomNavBar.querySelectorAll('.bottom-nav-tab').forEach(el => {
        if (el.dataset.category === category) el.classList.add('active');
        else el.classList.remove('active');
      });
    }

    if (category === 'settings') {
      if (elements.vaultScrollCanvas) elements.vaultScrollCanvas.classList.add('hidden');
      if (elements.workspaceSubbar) elements.workspaceSubbar.classList.add('hidden');
      if (elements.settingsView) elements.settingsView.classList.remove('hidden');
      updateStorageUI();
      return;
    }

    if (elements.settingsView) elements.settingsView.classList.add('hidden');
    if (elements.vaultScrollCanvas) elements.vaultScrollCanvas.classList.remove('hidden');
    if (elements.workspaceSubbar) elements.workspaceSubbar.classList.remove('hidden');

    state.currentFolderId = null;
    state.searchQuery = '';
    if (elements.globalSearchInput) elements.globalSearchInput.value = '';
    if (elements.clearSearchBtn) elements.clearSearchBtn.classList.add('hidden');

    loadContents();
  }

  // ===================================================================
  // CONTEXT MENUS (FILE & FOLDER)
  // ===================================================================
  let activeContextMenu = null;

  function closeContextMenu() {
    if (activeContextMenu) {
      activeContextMenu.remove();
      activeContextMenu = null;
    }
  }

  window.addEventListener('click', closeContextMenu);
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeContextMenu();
      closeAllModals();
    }
  });

  function openFileContextMenu(file, event) {
    closeContextMenu();
    const isTrashed = file.is_trashed === 1;

    const menu = document.createElement('div');
    menu.className = 'action-dropdown';
    menu.style.position = 'fixed';
    menu.style.left = `${Math.min(event.clientX, window.innerWidth - 210)}px`;
    menu.style.top = `${Math.min(event.clientY, window.innerHeight - 250)}px`;

    if (!isTrashed) {
      menu.innerHTML = `
        <button class="dropdown-item" id="ctxPreview">👁️ Preview</button>
        <button class="dropdown-item" id="ctxDownload">⬇️ Download</button>
        <button class="dropdown-item" id="ctxShare">🔗 Copy Share Link</button>
        <div class="dropdown-sep"></div>
        <button class="dropdown-item" id="ctxRename">✏️ Rename</button>
        <button class="dropdown-item" id="ctxMove">📁 Move to...</button>
        <div class="dropdown-sep"></div>
        <button class="dropdown-item" id="ctxTrash" style="color: #EF4444;">🗑️ Move to Trash</button>
      `;

      document.body.appendChild(menu);
      activeContextMenu = menu;

      menu.querySelector('#ctxPreview').onclick = () => openPreviewModal(file);
      menu.querySelector('#ctxDownload').onclick = () => downloadFileDirect(file.id);
      menu.querySelector('#ctxShare').onclick = () => copyShareLink(file.id);
      menu.querySelector('#ctxRename').onclick = () => openRenameModal('file', file.id, file.filename);
      menu.querySelector('#ctxMove').onclick = () => openMoveModal('file', file.id);
      menu.querySelector('#ctxTrash').onclick = () => trashFile(file.id);
    } else {
      menu.innerHTML = `
        <button class="dropdown-item" id="ctxRestore">🔄 Restore File</button>
        <button class="dropdown-item" id="ctxDelete" style="color: #EF4444;">❌ Delete Forever</button>
      `;

      document.body.appendChild(menu);
      activeContextMenu = menu;

      menu.querySelector('#ctxRestore').onclick = () => restoreFile(file.id);
      menu.querySelector('#ctxDelete').onclick = () => deletePermanently(file.id);
    }
  }

  function openFolderContextMenu(folder, event) {
    closeContextMenu();
    const menu = document.createElement('div');
    menu.className = 'action-dropdown';
    menu.style.position = 'fixed';
    menu.style.left = `${Math.min(event.clientX, window.innerWidth - 200)}px`;
    menu.style.top = `${Math.min(event.clientY, window.innerHeight - 180)}px`;

    menu.innerHTML = `
      <button class="dropdown-item" id="ctxOpenFolder">📂 Open Folder</button>
      <button class="dropdown-item" id="ctxRenameFolder">✏️ Rename</button>
      <div class="dropdown-sep"></div>
      <button class="dropdown-item" id="ctxDeleteFolder" style="color: #EF4444;">🗑️ Delete Folder</button>
    `;

    document.body.appendChild(menu);
    activeContextMenu = menu;

    menu.querySelector('#ctxOpenFolder').onclick = () => navigateToFolder(folder.id);
    menu.querySelector('#ctxRenameFolder').onclick = () => openRenameModal('folder', folder.id, folder.name);
    menu.querySelector('#ctxDeleteFolder').onclick = () => deleteFolder(folder.id);
  }

  // ===================================================================
  // UPLOADS & CHUNKING
  // ===================================================================
  async function handleFilesUpload(fileList) {
    if (!fileList || fileList.length === 0) return;

    elements.uploadManager.classList.remove('hidden', 'minimized');
    elements.uploadManagerTitle.textContent = `Uploading ${fileList.length} file(s)...`;

    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i];
      await uploadSingleFile(file);
    }

    elements.uploadManagerTitle.textContent = 'All uploads complete!';
    await fetchSystemInfo();
    await loadContents();
  }

  function uploadSingleFile(file) {
    return new Promise((resolve) => {
      const uploadId = `upl_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
      const numChunks = Math.max(1, Math.ceil(file.size / (19 * 1024 * 1024)));

      const itemCard = document.createElement('div');
      itemCard.className = 'upload-item-card';
      itemCard.id = uploadId;
      itemCard.innerHTML = `
        <div class="upload-card-top">
          <span class="upload-card-name" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</span>
          <span class="upload-card-status">0%</span>
        </div>
        <div class="upload-card-track">
          <div class="upload-card-fill" style="width: 0%;"></div>
        </div>
      `;
      elements.uploadItemsList.prepend(itemCard);

      const statusEl = itemCard.querySelector('.upload-card-status');
      const fillEl = itemCard.querySelector('.upload-card-fill');

      const formData = new FormData();
      formData.append('file', file);
      if (state.currentFolderId) {
        formData.append('folder_id', state.currentFolderId);
      }

      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/upload', true);

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          const percent = Math.round((e.loaded / e.total) * 95);
          fillEl.style.width = `${percent}%`;
          if (numChunks > 1) {
            statusEl.textContent = `${percent}% (${numChunks} storage chunks)`;
          } else {
            statusEl.textContent = `${percent}%`;
          }
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          fillEl.style.width = '100%';
          fillEl.style.background = '#10B981';
          statusEl.textContent = 'Uploaded ✓';
          statusEl.style.color = '#10B981';
          showToast(`Uploaded "${file.name}" to AeroVault`);
        } else {
          fillEl.style.background = '#EF4444';
          statusEl.textContent = 'Failed ✗';
          statusEl.style.color = '#EF4444';
          showToast(`Upload failed for "${file.name}"`);
        }
        resolve();
      };

      xhr.onerror = () => {
        fillEl.style.background = '#EF4444';
        statusEl.textContent = 'Error ✗';
        statusEl.style.color = '#EF4444';
        showToast(`Network error uploading "${file.name}"`);
        resolve();
      };

      xhr.send(formData);
    });
  }

  // ===================================================================
  // BUILT-IN MEDIA LIGHTBOX
  // ===================================================================
  function openPreviewModal(file) {
    if (state.activeAudio) {
      state.activeAudio.pause();
      state.activeAudio = null;
    }

    elements.previewFilename.textContent = file.filename;
    elements.previewSize.textContent = formatBytes(file.size_bytes);
    const category = getFileCategory(file.mime_type, file.filename);
    elements.previewBadge.textContent = category.toUpperCase();

    const streamUrl = `/api/files/${file.id}/stream`;
    elements.previewContentContainer.innerHTML = '';
    elements.previewContentContainer.setAttribute('oncontextmenu', 'return false;');
    elements.previewContentContainer.oncontextmenu = (e) => { e.preventDefault(); return false; };

    if (category === 'image') {
      const img = document.createElement('img');
      img.className = 'stage-img';
      img.setAttribute('oncontextmenu', 'return false;');
      img.oncontextmenu = (e) => { e.preventDefault(); return false; };
      img.src = streamUrl;
      img.alt = file.filename;
      elements.previewContentContainer.appendChild(img);
    } else if (category === 'video') {
      const video = document.createElement('video');
      video.className = 'stage-video';
      video.controls = true;
      video.autoplay = true;
      video.setAttribute('controlsList', 'nodownload noplaybackrate');
      video.setAttribute('oncontextmenu', 'return false;');
      video.oncontextmenu = (e) => { e.preventDefault(); return false; };
      video.src = streamUrl;
      elements.previewContentContainer.appendChild(video);
    } else if (category === 'audio') {
      // Modern AeroVault Audio Player
      const audioWrap = document.createElement('div');
      audioWrap.className = 'vault-audio-player';
      audioWrap.setAttribute('oncontextmenu', 'return false;');
      audioWrap.oncontextmenu = (e) => { e.preventDefault(); return false; };
      audioWrap.innerHTML = `
        <div class="vault-audio-meta">
          <div class="vault-audio-disc">🎵</div>
          <div class="vault-audio-track">
            <span class="vault-audio-name">${escapeHtml(file.filename)}</span>
            <span class="vault-audio-sub">Audio Track • ${formatBytes(file.size_bytes)}</span>
          </div>
        </div>

        <div class="vault-audio-slider-wrap">
          <input type="range" class="vault-audio-scrubber" value="0" min="0" max="100" step="0.1">
          <div class="vault-audio-times">
            <span class="audio-cur">0:00</span>
            <span class="audio-dur">--:--</span>
          </div>
        </div>

        <div class="vault-audio-ctrls">
          <button class="vault-audio-play" title="Play">
            <svg class="play-svg" width="26" height="26" viewBox="0 0 24 24" fill="currentColor">
              <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
            <svg class="pause-svg hidden" width="26" height="26" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="4" width="4" height="16"></rect>
              <rect x="14" y="4" width="4" height="16"></rect>
            </svg>
          </button>
        </div>
      `;

      elements.previewContentContainer.appendChild(audioWrap);

      const audio = new Audio(streamUrl);
      audio.setAttribute('controlsList', 'nodownload noplaybackrate');
      audio.setAttribute('oncontextmenu', 'return false;');
      audio.oncontextmenu = (e) => { e.preventDefault(); return false; };
      state.activeAudio = audio;

      const playBtn = audioWrap.querySelector('.vault-audio-play');
      const playSvg = audioWrap.querySelector('.play-svg');
      const pauseSvg = audioWrap.querySelector('.pause-svg');
      const scrubber = audioWrap.querySelector('.vault-audio-scrubber');
      const curEl = audioWrap.querySelector('.audio-cur');
      const durEl = audioWrap.querySelector('.audio-dur');

      function fmtTime(s) {
        if (!+s || isNaN(s)) return '0:00';
        const mins = Math.floor(s / 60);
        const secs = Math.floor(s % 60);
        return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
      }

      audio.onloadedmetadata = () => { durEl.textContent = fmtTime(audio.duration); };
      audio.ontimeupdate = () => {
        if (audio.duration) {
          scrubber.value = (audio.currentTime / audio.duration) * 100;
          curEl.textContent = fmtTime(audio.currentTime);
        }
      };
      scrubber.oninput = () => {
        if (audio.duration) audio.currentTime = (scrubber.value / 100) * audio.duration;
      };

      playBtn.onclick = () => {
        if (audio.paused) {
          audio.play();
          playSvg.classList.add('hidden');
          pauseSvg.classList.remove('hidden');
        } else {
          audio.pause();
          playSvg.classList.remove('hidden');
          pauseSvg.classList.add('hidden');
        }
      };

      audio.onended = () => {
        playSvg.classList.remove('hidden');
        pauseSvg.classList.add('hidden');
        scrubber.value = 0;
      };

      audio.play().then(() => {
        playSvg.classList.add('hidden');
        pauseSvg.classList.remove('hidden');
      }).catch(() => {});
    } else if (category === 'pdf') {
      const iframe = document.createElement('iframe');
      iframe.className = 'stage-pdf';
      iframe.src = streamUrl;
      elements.previewContentContainer.appendChild(iframe);
    } else {
      fetch(streamUrl)
        .then(r => r.text())
        .then(text => {
          const pre = document.createElement('pre');
          pre.className = 'stage-code';
          pre.textContent = text.slice(0, 100000);
          elements.previewContentContainer.appendChild(pre);
        })
        .catch(() => {
          elements.previewContentContainer.innerHTML = `
            <div style="text-align:center; color:#FFFFFF; padding: 24px;">
              <p style="font-size: 1.1rem; font-weight: 600; margin-bottom: 8px;">Preview not available for this file type.</p>
              <p style="font-size: 0.85rem; color: #94A3B8;">Use the download option from the file list menu in your drive.</p>
            </div>
          `;
        });
    }

    elements.previewShareBtn.onclick = () => copyShareLink(file.id);

    elements.mediaModal.classList.remove('hidden');
  }

  function closePreviewModal() {
    if (state.activeAudio) {
      state.activeAudio.pause();
      state.activeAudio = null;
    }
    elements.previewContentContainer.innerHTML = '';
    elements.mediaModal.classList.add('hidden');
  }

  // ===================================================================
  // ACTIONS: DOWNLOAD & SHARE
  // ===================================================================
  window.downloadFileDirect = function(fileId) {
    const a = document.createElement('a');
    a.href = `/api/files/${fileId}/download`;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    a.remove();
    showToast('Download started');
  };

  window.copyShareLink = function(fileId) {
    const shareUrl = `${window.location.origin}/api/share/${fileId}`;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(shareUrl).then(() => {
        showToast('Share link copied to clipboard');
      }).catch(() => fallbackCopy(shareUrl));
    } else {
      fallbackCopy(shareUrl);
    }
  };

  function fallbackCopy(text) {
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
    showToast('Share link copied to clipboard');
  }

  // ===================================================================
  // TRASH, RESTORE & DELETE
  // ===================================================================
  async function trashFile(fileId) {
    try {
      const res = await fetch(`/api/files/${fileId}/trash`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to move to trash');
      showToast('Moved to trash');
      await fetchSystemInfo();
      await loadContents();
    } catch (err) {
      showToast(err.message);
    }
  }

  async function restoreFile(fileId) {
    try {
      const res = await fetch(`/api/files/${fileId}/restore`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to restore file');
      showToast('File restored');
      await fetchSystemInfo();
      await loadContents();
    } catch (err) {
      showToast(err.message);
    }
  }

  async function deletePermanently(fileId) {
    if (!confirm('Permanently delete this file? Storage chunks will be permanently deleted.')) return;
    try {
      const res = await fetch(`/api/files/${fileId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete file');
      showToast('File permanently deleted');
      await fetchSystemInfo();
      await loadContents();
    } catch (err) {
      showToast(err.message);
    }
  }

  async function emptyTrash() {
    if (!confirm('Permanently empty all items in trash?')) return;
    try {
      const res = await fetch('/api/trash/empty', { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to empty trash');
      showToast('Trash emptied');
      await fetchSystemInfo();
      await loadContents();
    } catch (err) {
      showToast(err.message);
    }
  }

  // ===================================================================
  // FOLDER CREATION & DELETION
  // ===================================================================
  function openFolderModal() {
    elements.folderNameInput.value = '';
    elements.folderModal.classList.remove('hidden');
    setTimeout(() => elements.folderNameInput.focus(), 60);
  }

  async function submitCreateFolder() {
    const name = elements.folderNameInput.value.trim();
    if (!name) return;

    try {
      const res = await fetch('/api/folders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name,
          parent_id: state.currentFolderId
        })
      });

      if (!res.ok) throw new Error('Failed to create folder');
      elements.folderModal.classList.add('hidden');
      showToast(`Created folder "${name}"`);
      await loadContents();
    } catch (err) {
      showToast(err.message);
    }
  }

  async function deleteFolder(folderId) {
    if (!confirm('Delete folder and move contained items to trash?')) return;
    try {
      const res = await fetch(`/api/folders/${folderId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete folder');
      showToast('Folder deleted');
      await loadContents();
    } catch (err) {
      showToast(err.message);
    }
  }

  // ===================================================================
  // RENAME MODAL
  // ===================================================================
  let renameTarget = null;

  function openRenameModal(type, id, currentName) {
    renameTarget = { type, id };
    elements.renameModalTitle.textContent = type === 'folder' ? 'Rename Folder' : 'Rename File';
    elements.renameInput.value = currentName;
    elements.renameModal.classList.remove('hidden');
    setTimeout(() => {
      elements.renameInput.focus();
      elements.renameInput.select();
    }, 60);
  }

  async function submitRename() {
    if (!renameTarget) return;
    const newName = elements.renameInput.value.trim();
    if (!newName) return;

    try {
      const endpoint = renameTarget.type === 'folder' ? `/api/folders/${renameTarget.id}` : `/api/files/${renameTarget.id}`;
      const payload = renameTarget.type === 'folder' ? { name: newName } : { filename: newName };

      const res = await fetch(endpoint, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) throw new Error('Rename failed');
      elements.renameModal.classList.add('hidden');
      showToast('Renamed successfully');
      await loadContents();
    } catch (err) {
      showToast(err.message);
    }
  }

  // ===================================================================
  // MOVE MODAL
  // ===================================================================
  let moveTarget = null;
  let selectedDestinationFolderId = null;

  async function openMoveModal(type, id) {
    moveTarget = { type, id };
    selectedDestinationFolderId = null;
    elements.moveFoldersList.innerHTML = '<div style="padding:10px;text-align:center;">Loading destinations...</div>';
    elements.moveModal.classList.remove('hidden');

    try {
      const res = await fetch('/api/folders/tree');
      if (!res.ok) throw new Error('Failed to load folders');
      const data = await res.json();
      const allFolders = data.folders || [];

      elements.moveFoldersList.innerHTML = '';

      const rootItem = document.createElement('div');
      rootItem.className = 'tree-folder-node selected';
      rootItem.innerHTML = '📁 <strong>AeroVault (Root)</strong>';
      rootItem.onclick = () => {
        document.querySelectorAll('.tree-folder-node').forEach(el => el.classList.remove('selected'));
        rootItem.classList.add('selected');
        selectedDestinationFolderId = null;
      };
      elements.moveFoldersList.appendChild(rootItem);

      allFolders.forEach(f => {
        if (type === 'folder' && f.id === id) return;

        const fItem = document.createElement('div');
        fItem.className = 'tree-folder-node';
        fItem.innerHTML = `📁 <span>${escapeHtml(f.name)}</span>`;
        fItem.onclick = () => {
          document.querySelectorAll('.tree-folder-node').forEach(el => el.classList.remove('selected'));
          fItem.classList.add('selected');
          selectedDestinationFolderId = f.id;
        };
        elements.moveFoldersList.appendChild(fItem);
      });
    } catch (err) {
      elements.moveFoldersList.innerHTML = `<div style="color:#EF4444;padding:10px;">Error: ${err.message}</div>`;
    }
  }

  async function submitMove() {
    if (!moveTarget) return;

    try {
      const endpoint = moveTarget.type === 'folder' ? `/api/folders/${moveTarget.id}` : `/api/files/${moveTarget.id}`;
      const payload = moveTarget.type === 'folder' ? { parent_id: selectedDestinationFolderId } : { folder_id: selectedDestinationFolderId };

      const res = await fetch(endpoint, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) throw new Error('Move failed');
      elements.moveModal.classList.add('hidden');
      showToast('Moved successfully');
      await loadContents();
    } catch (err) {
      showToast(err.message);
    }
  }

  function closeAllModals() {
    closePreviewModal();
    elements.folderModal.classList.add('hidden');
    elements.renameModal.classList.add('hidden');
    elements.moveModal.classList.add('hidden');
  }

  // ===================================================================
  // DRAG & DROP HANDLING
  // ===================================================================
  let dragCounter = 0;

  window.addEventListener('dragenter', (e) => {
    e.preventDefault();
    dragCounter++;
    if (e.dataTransfer.types && e.dataTransfer.types.includes('Files')) {
      elements.dragDropOverlay.classList.remove('hidden');
    }
  });

  window.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dragCounter--;
    if (dragCounter <= 0) {
      dragCounter = 0;
      elements.dragDropOverlay.classList.add('hidden');
    }
  });

  window.addEventListener('dragover', (e) => {
    e.preventDefault();
  });

  window.addEventListener('drop', (e) => {
    e.preventDefault();
    dragCounter = 0;
    elements.dragDropOverlay.classList.add('hidden');

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFilesUpload(e.dataTransfer.files);
    }
  });

  // ===================================================================
  // EVENT LISTENERS
  // ===================================================================
  function bindEventListeners() {
    // Theme toggle
    elements.themeToggleBtn.addEventListener('click', toggleTheme);

    // Layout Toggle
    elements.gridViewBtn.addEventListener('click', () => applyViewMode('grid'));
    elements.listViewBtn.addEventListener('click', () => applyViewMode('list'));

    // Refresh & Brand Click
    elements.refreshBtn.addEventListener('click', () => {
      fetchSystemInfo();
      loadContents();
      showToast('Vault refreshed');
    });

    elements.brandLogo.addEventListener('click', () => navigateToFolder(null));

    // Empty Trash
    elements.emptyTrashBtn.addEventListener('click', emptyTrash);

    // "+ New Upload" Dropdown
    elements.newActionBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      elements.newMenuDropdown.classList.toggle('hidden');
    });

    window.addEventListener('click', () => {
      elements.newMenuDropdown.classList.add('hidden');
    });

    elements.menuNewFolderBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      elements.newMenuDropdown.classList.add('hidden');
      openFolderModal();
    });

    elements.menuUploadFileBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      elements.newMenuDropdown.classList.add('hidden');
      elements.fileInputHidden.click();
    });

    elements.menuUploadFolderBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      elements.newMenuDropdown.classList.add('hidden');
      elements.folderInputHidden.click();
    });

    elements.fileInputHidden.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFilesUpload(e.target.files);
        e.target.value = '';
      }
    });

    elements.folderInputHidden.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFilesUpload(e.target.files);
        e.target.value = '';
      }
    });

    elements.emptyStateUploadBtn.addEventListener('click', () => {
      elements.fileInputHidden.click();
    });

    // Bottom Nav Tabs
    if (elements.bottomNavBar) {
      elements.bottomNavBar.querySelectorAll('.bottom-nav-tab').forEach(btn => {
        btn.addEventListener('click', () => {
          const cat = btn.dataset.category;
          setCategory(cat);
        });
      });
    }

    // FAB Button (Mobile / Quick Upload)
    if (elements.fabNewBtn) {
      elements.fabNewBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        elements.newMenuDropdown.classList.toggle('hidden');
      });
    }

    // Settings Theme Selector Cards
    if (elements.themeDarkCard) {
      elements.themeDarkCard.addEventListener('click', () => applyTheme('dark'));
    }
    if (elements.themeLightCard) {
      elements.themeLightCard.addEventListener('click', () => applyTheme('light'));
    }

    // Settings View Mode & Density
    if (elements.settingsViewModeGroup) {
      elements.settingsViewModeGroup.querySelectorAll('.settings-toggle-btn').forEach(btn => {
        btn.addEventListener('click', () => applyViewMode(btn.dataset.view));
      });
    }
    if (elements.settingsDensityGroup) {
      elements.settingsDensityGroup.querySelectorAll('.settings-toggle-btn').forEach(btn => {
        btn.addEventListener('click', () => applyDensity(btn.dataset.density));
      });
    }

    // Filter Pills
    elements.filterChipsBar.querySelectorAll('.filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        elements.filterChipsBar.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.filterType = btn.dataset.type;
        loadContents();
      });
    });

    // Sort Select
    elements.sortSelect.addEventListener('change', (e) => {
      state.sortBy = e.target.value;
      sortFileList(state.files);
      renderContents();
    });

    // Global Search Input
    let searchDebounce = null;
    elements.globalSearchInput.addEventListener('input', (e) => {
      const q = e.target.value.trim();
      state.searchQuery = q;
      elements.clearSearchBtn.classList.toggle('hidden', !q);

      clearTimeout(searchDebounce);
      searchDebounce = setTimeout(() => {
        loadContents();
      }, 250);
    });

    elements.clearSearchBtn.addEventListener('click', () => {
      elements.globalSearchInput.value = '';
      state.searchQuery = '';
      elements.clearSearchBtn.classList.add('hidden');
      loadContents();
    });

    // Keyboard shortcut: 'Ctrl+K' or '/' focuses search
    window.addEventListener('keydown', (e) => {
      if ((e.key === '/' && document.activeElement !== elements.globalSearchInput) ||
          (e.ctrlKey && e.key.toLowerCase() === 'k')) {
        e.preventDefault();
        elements.globalSearchInput.focus();
      }
    });

    // Folder Modal
    elements.submitFolderBtn.addEventListener('click', submitCreateFolder);
    elements.cancelFolderBtn.addEventListener('click', () => elements.folderModal.classList.add('hidden'));
    elements.closeFolderModalBtn.addEventListener('click', () => elements.folderModal.classList.add('hidden'));
    elements.folderNameInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') submitCreateFolder();
    });

    // Rename Modal
    elements.submitRenameBtn.addEventListener('click', submitRename);
    elements.cancelRenameBtn.addEventListener('click', () => elements.renameModal.classList.add('hidden'));
    elements.closeRenameModalBtn.addEventListener('click', () => elements.renameModal.classList.add('hidden'));
    elements.renameInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') submitRename();
    });

    // Move Modal
    elements.submitMoveBtn.addEventListener('click', submitMove);
    elements.cancelMoveBtn.addEventListener('click', () => elements.moveModal.classList.add('hidden'));
    elements.closeMoveModalBtn.addEventListener('click', () => elements.moveModal.classList.add('hidden'));

    // Lightbox Modal
    elements.closePreviewBtn.addEventListener('click', closePreviewModal);

    // Upload Drawer
    elements.minimizeUploadBtn.addEventListener('click', () => {
      elements.uploadManager.classList.toggle('minimized');
    });

    elements.closeUploadBtn.addEventListener('click', () => {
      elements.uploadManager.classList.add('hidden');
    });
  }

  // ===================================================================
  // INITIALIZATION
  // ===================================================================
  async function init() {
    applyTheme(state.theme);
    applyDensity(state.density);
    applyViewMode(state.viewMode);
    bindEventListeners();
    await fetchSystemInfo();
    await loadContents();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
