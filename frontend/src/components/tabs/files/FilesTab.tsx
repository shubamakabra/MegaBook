import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { api } from '../../../services/api';
import { VaultInfo } from '../../../types';
import { FilePreview, getFileType, isPreviewable, getFileIcon, formatSize } from '../../common';
import './FilesTab.css';

// Types
interface FileItem {
  name: string;
  type: 'file' | 'folder';
  path: string;
  children?: FileItem[];
}

// Transform backend file tree to FileItem structure
const transformFileTree = (tree: any[]): FileItem[] => {
  return tree.map(item => ({
    name: item.name,
    type: item.type === 'directory' ? 'folder' : 'file',
    path: item.path,
    children: item.children ? transformFileTree(item.children) : undefined,
  }));
};

// Sort: folders first, then alphabetical
const sortItems = (items: FileItem[]): FileItem[] => {
  return [...items].sort((a, b) => {
    if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
    return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
  });
};

// Recursively filter tree items by search query
const filterTreeItems = (items: FileItem[], query: string): FileItem[] => {
  if (!query.trim()) return items;
  const lowerQuery = query.toLowerCase();
  const results: FileItem[] = [];
  for (const item of items) {
    const nameMatches = item.name.toLowerCase().includes(lowerQuery);
    if (item.type === 'folder' && item.children) {
      const filteredChildren = filterTreeItems(item.children, query);
      if (nameMatches || filteredChildren.length > 0) {
        results.push({ ...item, children: filteredChildren.length > 0 ? filteredChildren : item.children });
      }
    } else if (nameMatches) {
      results.push(item);
    }
  }
  return results;
};

// Find an item in the tree by path
const findItemByPath = (items: FileItem[], path: string): FileItem | null => {
  for (const item of items) {
    if (item.path === path) return item;
    if (item.children) {
      const found = findItemByPath(item.children, path);
      if (found) return found;
    }
  }
  return null;
};

// Get the parent path of a given path
const getParentPath = (path: string): string => {
  const lastSlash = path.lastIndexOf('/');
  return lastSlash > 0 ? path.substring(0, lastSlash) : '';
};

// ============================================================================
// TreeItem component — renders a single node with expand/collapse
// ============================================================================
interface TreeItemProps {
  item: FileItem;
  depth: number;
  expandedPaths: Set<string>;
  selectedPath: string | null;
  renamingPath: string | null;
  renameValue: string;
  creatingFolderInPath: string | null;
  newFolderName: string;
  searchQuery: string;
  onToggleExpand: (path: string) => void;
  onSelect: (item: FileItem) => void;
  onContextMenu: (e: React.MouseEvent, item: FileItem) => void;
  onRenameChange: (value: string) => void;
  onRenameSubmit: () => void;
  onRenameCancel: () => void;
  onNewFolderNameChange: (value: string) => void;
  onCreateFolderSubmit: () => void;
  onCreateFolderCancel: () => void;
  onDragStart: (e: React.DragEvent, item: FileItem) => void;
  onDragEnd: () => void;
  draggingItem: FileItem | null;
}

const TreeItem: React.FC<TreeItemProps> = ({
  item, depth, expandedPaths, selectedPath, renamingPath, renameValue,
  creatingFolderInPath, newFolderName, searchQuery,
  onToggleExpand, onSelect, onContextMenu,
  onRenameChange, onRenameSubmit, onRenameCancel,
  onNewFolderNameChange, onCreateFolderSubmit, onCreateFolderCancel,
  onDragStart, onDragEnd, draggingItem,
}) => {
  const isExpanded = expandedPaths.has(item.path);
  const isSelected = selectedPath === item.path;
  const isRenaming = renamingPath === item.path;
  const isDragging = draggingItem?.path === item.path;
  const isFolder = item.type === 'folder';
  const isCreatingFolderHere = creatingFolderInPath === item.path;

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isFolder) {
      onToggleExpand(item.path);
    }
    onSelect(item);
  };

  const getItemIcon = () => {
    if (isFolder) return isExpanded ? '📂' : '📁';
    return getFileIcon(getFileType(item.name));
  };

  const children = isFolder && item.children ? sortItems(item.children) : [];

  return (
    <>
      <div
        className={`tree-item ${isSelected ? 'selected' : ''} ${isFolder ? 'folder' : 'file'} ${isDragging ? 'dragging' : ''} ${isPreviewable(item.name) ? 'previewable' : ''}`}
        style={{ paddingLeft: `${12 + depth * 18}px` }}
        onClick={handleClick}
        onContextMenu={(e) => onContextMenu(e, item)}
        draggable={!isRenaming}
        onDragStart={(e) => onDragStart(e, item)}
        onDragEnd={onDragEnd}
      >
        {isFolder && (
          <span className={`tree-chevron ${isExpanded ? 'expanded' : ''}`}>&#9656;</span>
        )}
        {!isFolder && <span className="tree-chevron-spacer" />}
        <span className="item-icon">{getItemIcon()}</span>

        {isRenaming ? (
          <input
            type="text"
            className="rename-input"
            value={renameValue}
            onChange={(e) => onRenameChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') onRenameSubmit();
              if (e.key === 'Escape') onRenameCancel();
            }}
            onBlur={onRenameCancel}
            autoFocus
            onClick={(e) => e.stopPropagation()}
          />
        ) : (
          <span className="item-name">{item.name}</span>
        )}

        {item.type === 'file' && isPreviewable(item.name) && (
          <span className="item-preview-indicator">&#128065;</span>
        )}
      </div>

      {/* Expanded children */}
      {isFolder && isExpanded && (
        <>
          {children.map(child => (
            <TreeItem
              key={child.path}
              item={child}
              depth={depth + 1}
              expandedPaths={expandedPaths}
              selectedPath={selectedPath}
              renamingPath={renamingPath}
              renameValue={renameValue}
              creatingFolderInPath={creatingFolderInPath}
              newFolderName={newFolderName}
              searchQuery={searchQuery}
              onToggleExpand={onToggleExpand}
              onSelect={onSelect}
              onContextMenu={onContextMenu}
              onRenameChange={onRenameChange}
              onRenameSubmit={onRenameSubmit}
              onRenameCancel={onRenameCancel}
              onNewFolderNameChange={onNewFolderNameChange}
              onCreateFolderSubmit={onCreateFolderSubmit}
              onCreateFolderCancel={onCreateFolderCancel}
              onDragStart={onDragStart}
              onDragEnd={onDragEnd}
              draggingItem={draggingItem}
            />
          ))}

          {/* Inline new-folder input */}
          {isCreatingFolderHere && (
            <div className="tree-item creating-folder" style={{ paddingLeft: `${12 + (depth + 1) * 18}px` }}>
              <span className="item-icon">&#128193;</span>
              <input
                type="text"
                className="rename-input"
                value={newFolderName}
                onChange={(e) => onNewFolderNameChange(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') onCreateFolderSubmit();
                  if (e.key === 'Escape') onCreateFolderCancel();
                }}
                onBlur={onCreateFolderCancel}
                autoFocus
                onClick={(e) => e.stopPropagation()}
                placeholder="Folder name..."
              />
            </div>
          )}

          {children.length === 0 && !isCreatingFolderHere && (
            <div className="tree-empty" style={{ paddingLeft: `${12 + (depth + 1) * 18}px` }}>
              Empty folder
            </div>
          )}
        </>
      )}
    </>
  );
};

// ============================================================================
// FilesTab — main component
// ============================================================================
export const FilesTab: React.FC = () => {
  // Vault state
  const [vaultInfo, setVaultInfo] = useState<VaultInfo | null>(null);
  const [vaultLoading, setVaultLoading] = useState(true);
  const [vaultPathInput, setVaultPathInput] = useState('');
  const [vaultError, setVaultError] = useState<string | null>(null);
  const [settingVault, setSettingVault] = useState(false);
  const [browsingVault, setBrowsingVault] = useState(false);

  // File tree state
  const [allItems, setAllItems] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Tree interaction state
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [totalSize, setTotalSize] = useState('0 KB');

  // Context menu
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; item: FileItem } | null>(null);

  // Rename
  const [renamingPath, setRenamingPath] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');

  // Create folder
  const [creatingFolderInPath, setCreatingFolderInPath] = useState<string | null>(null);
  const [newFolderName, setNewFolderName] = useState('');

  // Drag
  const [draggingItem, setDraggingItem] = useState<FileItem | null>(null);
  const [dragOverTree, setDragOverTree] = useState(false);

  // Upload
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  // Search
  const [searchQuery, setSearchQuery] = useState('');

  // Preview
  const [previewItem, setPreviewItem] = useState<FileItem | null>(null);
  const [previewContent, setPreviewContent] = useState<string>('');
  const [previewLoading, setPreviewLoading] = useState(false);

  // Filtered tree
  const displayItems = useMemo(
    () => sortItems(filterTreeItems(allItems, searchQuery)),
    [allItems, searchQuery]
  );

  // Auto-expand folders when searching
  useEffect(() => {
    if (searchQuery.trim()) {
      const pathsToExpand = new Set<string>();
      const collectPaths = (items: FileItem[]) => {
        for (const item of items) {
          if (item.type === 'folder' && item.children) {
            pathsToExpand.add(item.path);
            collectPaths(item.children);
          }
        }
      };
      collectPaths(displayItems);
      setExpandedPaths(pathsToExpand);
    }
  }, [searchQuery, displayItems]);

  // ---- Data loading ----

  const loadFileTree = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const treeData = await api.getFileTree();
      const transformed = transformFileTree(treeData);
      setAllItems(transformed);

      const files = await api.listFiles();
      const totalBytes = files.reduce((sum: number, f: any) => sum + (f.size || 0), 0);
      setTotalSize(formatSize(totalBytes));
    } catch (err: any) {
      console.error('Failed to load file tree:', err);
      setError(err.message || 'Failed to load files from backend');
    } finally {
      setLoading(false);
    }
  }, []);

  // ---- Vault management ----

  const loadVaultInfo = useCallback(async () => {
    setVaultLoading(true);
    setVaultError(null);
    try {
      const info = await api.getVault();
      setVaultInfo(info);
      return info;
    } catch (err: any) {
      console.error('Failed to load vault info:', err);
      setVaultError(err.message || 'Failed to load vault info');
      return null;
    } finally {
      setVaultLoading(false);
    }
  }, []);

  const handleSetVault = useCallback(async () => {
    if (!vaultPathInput.trim()) return;
    setSettingVault(true);
    setVaultError(null);
    try {
      const info = await api.setVault(vaultPathInput.trim());
      setVaultInfo(info);
      setVaultPathInput('');
      loadFileTree();
    } catch (err: any) {
      console.error('Failed to set vault:', err);
      setVaultError(err.response?.data?.detail || err.message || 'Failed to set vault path');
    } finally {
      setSettingVault(false);
    }
  }, [vaultPathInput, loadFileTree]);

  const handleOpenExplorer = useCallback(async () => {
    try {
      await api.openVaultInExplorer();
    } catch (err: any) {
      console.error('Failed to open explorer:', err);
      alert('Failed to open file explorer: ' + (err.response?.data?.detail || err.message));
    }
  }, []);

  const handleBrowseVault = useCallback(async () => {
    setBrowsingVault(true);
    setVaultError(null);
    try {
      const result = await api.browseForVault();
      if (!result.cancelled && result.path) {
        setVaultPathInput(result.path);
      }
    } catch (err: any) {
      console.error('Failed to browse for vault:', err);
      setVaultError(err.response?.data?.detail || err.message || 'Failed to open folder dialog');
    } finally {
      setBrowsingVault(false);
    }
  }, []);

  const vaultConnected = vaultInfo?.path && vaultInfo?.exists;

  // Initial load
  useEffect(() => {
    const init = async () => {
      const info = await loadVaultInfo();
      if (info?.path && info?.exists) {
        loadFileTree();
      } else {
        setLoading(false);
      }
    };
    init();
  }, [loadVaultInfo, loadFileTree]);

  // ---- Tree interaction ----

  const handleToggleExpand = useCallback((path: string) => {
    setExpandedPaths(prev => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  const handleSelect = useCallback(async (item: FileItem) => {
    setSelectedPath(item.path);
    setContextMenu(null);

    if (item.type === 'file' && isPreviewable(item.name)) {
      setPreviewItem(item);
      setPreviewLoading(true);
      try {
        const fileType = getFileType(item.name);
        if (fileType === 'markdown' || fileType === 'text') {
          const response = await api.readFile(item.path);
          setPreviewContent(response.content || '');
        } else {
          setPreviewContent('');
        }
      } catch (err: any) {
        console.error('Failed to load file preview:', err);
        setPreviewContent('');
      } finally {
        setPreviewLoading(false);
      }
    }
  }, []);

  // ---- Context menu ----

  const handleContextMenu = useCallback((e: React.MouseEvent, item: FileItem) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({ x: e.clientX, y: e.clientY, item });
  }, []);

  const closeContextMenu = useCallback(() => setContextMenu(null), []);

  const canOpenInNotes = (item: FileItem): boolean => {
    return item.type === 'file' && (item.name.endsWith('.md') || item.name.endsWith('.txt'));
  };

  const handleOpenFile = async () => {
    if (!contextMenu?.item || !canOpenInNotes(contextMenu.item)) { closeContextMenu(); return; }
    try {
      const response = await api.readFile(contextMenu.item.path);
      window.dispatchEvent(new CustomEvent('openFileInNotes', {
        detail: { path: contextMenu.item.path, name: contextMenu.item.name, content: response.content || '' }
      }));
    } catch (err: any) {
      alert('Failed to open file: ' + err.message);
    }
    closeContextMenu();
  };

  const handleCopyPath = () => {
    if (contextMenu?.item) navigator.clipboard.writeText(contextMenu.item.path);
    closeContextMenu();
  };

  const handleDownload = async () => {
    if (contextMenu?.item && contextMenu.item.type === 'file') {
      try {
        const response = await fetch(`/api/filesystem/download/${encodeURIComponent(contextMenu.item.path)}`);
        if (!response.ok) throw new Error('Download failed');
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = contextMenu.item.name;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      } catch (err: any) {
        alert('Failed to download: ' + err.message);
      }
    }
    closeContextMenu();
  };

  const handleCopy = async () => {
    if (contextMenu?.item) {
      try {
        const item = contextMenu.item;
        const lastDotIndex = item.name.lastIndexOf('.');
        const baseName = lastDotIndex > 0 ? item.name.substring(0, lastDotIndex) : item.name;
        const extension = lastDotIndex > 0 ? item.name.substring(lastDotIndex) : '';
        const copyName = `${baseName} (copy)${extension}`;
        const parentPath = getParentPath(item.path);
        const targetPath = parentPath ? `${parentPath}/${copyName}` : copyName;
        await api.copyFile(item.path, targetPath);
        await loadFileTree();
      } catch (err: any) {
        alert('Failed to copy: ' + err.message);
      }
    }
    closeContextMenu();
  };

  const handleDeleteItem = async () => {
    if (!contextMenu?.item) { closeContextMenu(); return; }
    const item = contextMenu.item;
    if (confirm(`Delete ${item.name}?`)) {
      try {
        await api.deleteFile(item.path);
        if (selectedPath === item.path) {
          setSelectedPath(null);
          setPreviewItem(null);
          setPreviewContent('');
        }
        await loadFileTree();
      } catch (err: any) {
        alert('Failed to delete: ' + err.message);
      }
    }
    closeContextMenu();
  };

  const handleStartRename = () => {
    if (contextMenu?.item) {
      setRenamingPath(contextMenu.item.path);
      setRenameValue(contextMenu.item.name);
    }
    closeContextMenu();
  };

  const handleRenameSubmit = async () => {
    if (!renamingPath || !renameValue) { handleRenameCancel(); return; }
    const item = findItemByPath(allItems, renamingPath);
    if (!item || renameValue === item.name) { handleRenameCancel(); return; }
    try {
      const parentPath = getParentPath(item.path);
      const newPath = parentPath ? `${parentPath}/${renameValue}` : renameValue;
      await api.renameFile(item.path, newPath);
      await loadFileTree();
    } catch (err: any) {
      alert('Failed to rename: ' + err.message);
    }
    setRenamingPath(null);
    setRenameValue('');
  };

  const handleRenameCancel = () => {
    setRenamingPath(null);
    setRenameValue('');
  };

  // ---- Create folder ----

  const handleStartCreateFolder = () => {
    // Create folder inside the currently selected folder, or root
    let parentPath = '';
    if (selectedPath) {
      const item = findItemByPath(allItems, selectedPath);
      if (item?.type === 'folder') {
        parentPath = item.path;
        // Ensure the parent is expanded so user sees the input
        setExpandedPaths(prev => new Set(prev).add(parentPath));
      } else {
        parentPath = getParentPath(selectedPath);
      }
    }
    setCreatingFolderInPath(parentPath || '__root__');
    setNewFolderName('');
  };

  const handleCreateFolderSubmit = async () => {
    if (creatingFolderInPath === null || !newFolderName.trim()) { handleCreateFolderCancel(); return; }
    try {
      const parent = creatingFolderInPath === '__root__' ? '' : creatingFolderInPath;
      const newPath = parent ? `${parent}/${newFolderName}` : newFolderName;
      await api.createFolder(newPath);
      await loadFileTree();
    } catch (err: any) {
      alert('Failed to create folder: ' + err.message);
    }
    setCreatingFolderInPath(null);
    setNewFolderName('');
  };

  const handleCreateFolderCancel = () => {
    setCreatingFolderInPath(null);
    setNewFolderName('');
  };

  // ---- Upload ----

  /** Get the folder path to upload into, based on current selection. */
  const getCurrentUploadTarget = useCallback((): string => {
    if (!selectedPath) return '';
    const item = findItemByPath(allItems, selectedPath);
    if (!item) return '';
    return item.type === 'folder' ? item.path : getParentPath(item.path);
  }, [selectedPath, allItems]);

  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const parentPath = getCurrentUploadTarget();

    for (const file of Array.from(files)) {
      const filePath = parentPath ? `${parentPath}/${file.name}` : file.name;
      try {
        setUploadProgress(prev => ({ ...prev, [file.name]: 0 }));
        await api.uploadFile(file, filePath, (progress) => {
          setUploadProgress(prev => ({ ...prev, [file.name]: progress }));
        });
        setUploadProgress(prev => {
          const next = { ...prev };
          delete next[file.name];
          return next;
        });
      } catch (err: any) {
        alert(`Failed to upload ${file.name}: ${err.message}`);
        setUploadProgress(prev => {
          const next = { ...prev };
          delete next[file.name];
          return next;
        });
      }
    }
    await loadFileTree();
  };

  // ---- Drag and drop (file move + external upload) ----

  const handleDragStart = (e: React.DragEvent, item: FileItem) => {
    e.stopPropagation();
    setDraggingItem(item);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', item.path);
  };

  const handleDragEnd = () => setDraggingItem(null);

  const handleTreeDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOverTree(true);
  };

  const handleTreeDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOverTree(false);
  };

  const handleTreeDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOverTree(false);

    if (draggingItem) {
      // Internal move — drop into current selected folder or root
      const targetFolder = getCurrentUploadTarget();
      const currentParent = getParentPath(draggingItem.path);
      if (currentParent !== targetFolder) {
        const newPath = targetFolder ? `${targetFolder}/${draggingItem.name}` : draggingItem.name;
        try {
          await api.renameFile(draggingItem.path, newPath);
          await loadFileTree();
        } catch (err: any) {
          alert('Failed to move: ' + err.message);
        }
      }
      setDraggingItem(null);
    } else if (e.dataTransfer.files.length > 0) {
      // External file upload
      await handleFileUpload(e.dataTransfer.files);
    }
  };

  // ---- Breadcrumbs ----

  const buildBreadcrumbs = (): { name: string; path: string }[] => {
    if (!selectedPath) return [{ name: 'Root', path: '' }];
    const parts = selectedPath.split('/');
    const crumbs: { name: string; path: string }[] = [{ name: 'Root', path: '' }];
    let accumulated = '';
    for (const part of parts) {
      accumulated = accumulated ? `${accumulated}/${part}` : part;
      crumbs.push({ name: part, path: accumulated });
    }
    return crumbs;
  };

  const navigateToBreadcrumb = (targetPath: string) => {
    if (!targetPath) {
      // Root — collapse all, clear selection
      setExpandedPaths(new Set());
      setSelectedPath(null);
      setPreviewItem(null);
      setPreviewContent('');
      return;
    }
    // Expand all ancestor paths and select the target
    const parts = targetPath.split('/');
    const pathsToExpand = new Set<string>();
    let accumulated = '';
    for (const part of parts) {
      accumulated = accumulated ? `${accumulated}/${part}` : part;
      pathsToExpand.add(accumulated);
    }
    setExpandedPaths(prev => {
      const next = new Set(prev);
      for (const p of pathsToExpand) next.add(p);
      return next;
    });
    setSelectedPath(targetPath);

    // If it's a file, load preview
    const item = findItemByPath(allItems, targetPath);
    if (item && item.type === 'file' && isPreviewable(item.name)) {
      handleSelect(item);
    }
  };

  const breadcrumbs = buildBreadcrumbs();

  // ============================================================================
  // Render — early returns for loading/error/no-vault states
  // ============================================================================

  if (vaultLoading) {
    return (
      <div className="files-tab">
        <div className="files-loading">
          <div className="loading-spinner" />
          <p>Checking vault...</p>
        </div>
      </div>
    );
  }

  if (!vaultConnected) {
    return (
      <div className="files-tab">
        <div className="vault-selector">
          <div className="vault-selector-icon">&#128218;</div>
          <h2 className="vault-selector-title">Connect a Vault</h2>
          <p className="vault-selector-desc">
            Enter the path to an Obsidian vault or any folder to use as your knowledge base.
          </p>
          <div className="vault-selector-form">
            <div className="vault-path-row">
              <input
                type="text"
                className="vault-path-input"
                placeholder="C:\Users\you\Documents\MyVault"
                value={vaultPathInput}
                onChange={(e) => setVaultPathInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleSetVault(); }}
                disabled={settingVault || browsingVault}
              />
              <button
                className="btn-secondary vault-browse-btn"
                onClick={handleBrowseVault}
                disabled={settingVault || browsingVault}
                title="Browse for a folder"
              >
                {browsingVault ? 'Opening...' : 'Browse'}
              </button>
            </div>
            <button
              className="btn-primary vault-connect-btn"
              onClick={handleSetVault}
              disabled={settingVault || browsingVault || !vaultPathInput.trim()}
            >
              {settingVault ? 'Connecting...' : 'Connect'}
            </button>
          </div>
          {vaultError && <p className="vault-selector-error">{vaultError}</p>}
          {vaultInfo?.path && !vaultInfo.exists && (
            <p className="vault-selector-error">
              Previously configured vault path no longer exists: {vaultInfo.path}
            </p>
          )}
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="files-tab">
        <div className="files-loading">
          <div className="loading-spinner" />
          <p>Loading your grimoire...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="files-tab">
        <div className="files-error">
          <h3>Failed to Load Files</h3>
          <p>{error}</p>
          <button className="btn-primary" onClick={loadFileTree}>Try Again</button>
        </div>
      </div>
    );
  }

  const activeContextItem = contextMenu?.item ?? null;

  return (
    <div className="files-tab" onClick={closeContextMenu}>
      {/* Hidden file input — uploads to current folder */}
      <input
        type="file"
        ref={fileInputRef}
        style={{ display: 'none' }}
        multiple
        onChange={(e) => handleFileUpload(e.target.files)}
      />

      {/* Vault Info Bar */}
      <div className="vault-info-bar">
        <div className="vault-info-left">
          <span className="vault-info-path" title={vaultInfo?.path || ''}>
            {vaultInfo?.path}
          </span>
          <div className="vault-info-badges">
            {vaultInfo?.is_obsidian_vault && <span className="vault-badge obsidian">Obsidian</span>}
            {vaultInfo?.has_git && <span className="vault-badge git">Git</span>}
            {vaultInfo?.has_megabook && <span className="vault-badge megabook">.megabook</span>}
          </div>
        </div>
        <div className="vault-info-right">
          <button className="vault-action-btn" onClick={handleOpenExplorer} title="Open in file explorer">
            Open in Explorer
          </button>
          <button className="vault-action-btn" onClick={() => setVaultInfo(null)} title="Change vault">
            Change Vault
          </button>
        </div>
      </div>

      {/* Breadcrumb Navigation */}
      <div className="files-breadcrumb">
        {breadcrumbs.map((crumb, index) => (
          <React.Fragment key={crumb.path || '__root__'}>
            {index > 0 && <span className="breadcrumb-separator">&#8250;</span>}
            <button
              className={`breadcrumb-item ${index === breadcrumbs.length - 1 ? 'active' : ''}`}
              onClick={() => navigateToBreadcrumb(crumb.path)}
            >
              {crumb.name}
            </button>
          </React.Fragment>
        ))}
      </div>

      {/* Toolbar */}
      <div className="files-toolbar">
        <div className="files-toolbar-left">
          <span className="files-toolbar-title">File Library</span>
          <div className="files-search">
            <span className="search-icon">&#128269;</span>
            <input
              type="text"
              className="search-input"
              placeholder="Search files..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button className="search-clear" onClick={() => setSearchQuery('')}>&times;</button>
            )}
          </div>
        </div>
        <div className="files-toolbar-right">
          <button className="files-toolbar-btn" onClick={handleStartCreateFolder} title="New folder">
            + Folder
          </button>
          <button className="files-toolbar-btn" onClick={() => fileInputRef.current?.click()}>
            Upload
          </button>
          <button className="files-toolbar-btn primary" onClick={loadFileTree}>
            Refresh
          </button>
        </div>
      </div>

      {/* Main content: tree + preview */}
      <div className="files-content">
        <div
          className={`file-tree-panel ${dragOverTree ? 'drag-over' : ''}`}
          onDragOver={handleTreeDragOver}
          onDragLeave={handleTreeDragLeave}
          onDrop={handleTreeDrop}
        >
          <div className="file-tree-scroll">
            {displayItems.map(item => (
              <TreeItem
                key={item.path}
                item={item}
                depth={0}
                expandedPaths={expandedPaths}
                selectedPath={selectedPath}
                renamingPath={renamingPath}
                renameValue={renameValue}
                creatingFolderInPath={creatingFolderInPath}
                newFolderName={newFolderName}
                searchQuery={searchQuery}
                onToggleExpand={handleToggleExpand}
                onSelect={handleSelect}
                onContextMenu={handleContextMenu}
                onRenameChange={setRenameValue}
                onRenameSubmit={handleRenameSubmit}
                onRenameCancel={handleRenameCancel}
                onNewFolderNameChange={setNewFolderName}
                onCreateFolderSubmit={handleCreateFolderSubmit}
                onCreateFolderCancel={handleCreateFolderCancel}
                onDragStart={handleDragStart}
                onDragEnd={handleDragEnd}
                draggingItem={draggingItem}
              />
            ))}

            {/* Root-level new-folder input */}
            {creatingFolderInPath === '__root__' && (
              <div className="tree-item creating-folder" style={{ paddingLeft: '12px' }}>
                <span className="item-icon">&#128193;</span>
                <input
                  type="text"
                  className="rename-input"
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleCreateFolderSubmit();
                    if (e.key === 'Escape') handleCreateFolderCancel();
                  }}
                  onBlur={handleCreateFolderCancel}
                  autoFocus
                  placeholder="Folder name..."
                />
              </div>
            )}

            {displayItems.length === 0 && !loading && (
              <div className="tree-empty-root">
                {searchQuery ? 'No files match your search.' : 'This vault is empty. Upload or create files to get started.'}
              </div>
            )}
          </div>

          {/* Upload progress — shown once at the bottom of the tree */}
          {Object.keys(uploadProgress).length > 0 && (
            <div className="upload-progress-container">
              {Object.entries(uploadProgress).map(([filename, progress]) => (
                <div key={filename} className="upload-progress-item">
                  <span className="upload-filename">{filename}</span>
                  <div className="upload-progress-bar">
                    <div className="upload-progress-fill" style={{ width: `${progress}%` }} />
                  </div>
                  <span className="upload-percent">{progress}%</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Preview Panel */}
        {previewItem && (
          <div className="files-preview-panel">
            <div className="preview-panel-header">
              <span className="preview-panel-title">File Preview</span>
              <div className="preview-panel-actions">
                {canOpenInNotes(previewItem) && (
                  <button
                    className="preview-action-btn"
                    onClick={async () => {
                      try {
                        const response = await api.readFile(previewItem.path);
                        window.dispatchEvent(new CustomEvent('openFileInNotes', {
                          detail: { path: previewItem.path, name: previewItem.name, content: response.content || '' }
                        }));
                      } catch (err: any) {
                        alert('Failed to open file: ' + err.message);
                      }
                    }}
                    title="Open in Notes"
                  >
                    Edit
                  </button>
                )}
                <button
                  className="preview-action-btn"
                  onClick={() => { setPreviewItem(null); setPreviewContent(''); }}
                  title="Close preview"
                >
                  &#10005;
                </button>
              </div>
            </div>
            <div className="preview-panel-content">
              {previewLoading ? (
                <div className="preview-loading">Loading preview...</div>
              ) : (
                <FilePreview path={previewItem.path} name={previewItem.name} content={previewContent} />
              )}
            </div>
          </div>
        )}
      </div>

      {/* Context Menu */}
      {contextMenu && activeContextItem && (
        <div
          className="files-context-menu"
          style={{ left: contextMenu.x, top: contextMenu.y }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="context-menu-header">
            {activeContextItem.type === 'folder' ? '&#128193;' : getFileIcon(getFileType(activeContextItem.name))} {activeContextItem.name}
          </div>
          <div className="context-menu-divider" />

          {canOpenInNotes(activeContextItem) && (
            <>
              <button className="context-menu-item" onClick={handleOpenFile}>
                <span className="menu-icon">&#128214;</span>
                <span>Open in Notes</span>
              </button>
              <div className="context-menu-divider" />
            </>
          )}

          <button className="context-menu-item" onClick={handleStartRename}>
            <span className="menu-icon">&#9999;</span>
            <span>Rename</span>
          </button>

          <button className="context-menu-item" onClick={handleCopy}>
            <span className="menu-icon">&#128196;</span>
            <span>Duplicate</span>
          </button>

          {activeContextItem.type === 'file' && (
            <button className="context-menu-item" onClick={handleDownload}>
              <span className="menu-icon">&#11015;</span>
              <span>Download</span>
            </button>
          )}

          <div className="context-menu-divider" />

          <button className="context-menu-item danger" onClick={handleDeleteItem}>
            <span className="menu-icon">&#128465;</span>
            <span>Delete</span>
          </button>

          <div className="context-menu-divider" />
          <button className="context-menu-item" onClick={handleCopyPath}>
            <span className="menu-icon">&#128203;</span>
            <span>Copy Path</span>
          </button>
        </div>
      )}

      {/* Status Bar */}
      <div className="files-status-bar">
        <div className="status-section">
          <span className="status-label">Total Size:</span>
          <span className="status-value">{totalSize}</span>
        </div>
        <div className="status-divider" />
        <div className="status-section">
          <span className="status-hint">Right-click for context menu &bull; Drag files to upload</span>
        </div>
      </div>
    </div>
  );
};
