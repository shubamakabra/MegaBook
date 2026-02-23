import React, { useState, useCallback, useEffect } from 'react';
import { api } from '../../../services/api';
import { FilePreview, getFileType, isPreviewable, getFileIcon, formatSize } from '../../common';
import './FilesTab.css';

// Types
interface FileItem {
  name: string;
  type: 'file' | 'folder';
  path: string;
  children?: FileItem[];
  includeInRag?: boolean;
}

interface ColumnData {
  items: FileItem[];
  selectedPath: string | null;
  title: string;
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

// Helper to find folder contents recursively
const findFolderContents = (items: FileItem[], path: string): FileItem[] | null => {
  for (const item of items) {
    if (item.path === path && item.type === 'folder' && item.children) {
      return item.children;
    }
    if (item.children) {
      const found = findFolderContents(item.children, path);
      if (found) return found;
    }
  }
  return null;
};

export const FilesTab: React.FC = () => {
  // State for file tree from backend
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // State for three columns
  const [columns, setColumns] = useState<ColumnData[]>([
    { items: [], selectedPath: null, title: 'Root' },
    { items: [], selectedPath: null, title: '' },
    { items: [], selectedPath: null, title: '' }
  ]);


  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; item: FileItem | null } | null>(null);
  const [totalSize, setTotalSize] = useState('0 KB');
  
  // Rename state
  const [renamingItem, setRenamingItem] = useState<FileItem | null>(null);
  const [renameValue, setRenameValue] = useState('');
  
  // Create folder state
  const [creatingFolderColumn, setCreatingFolderColumn] = useState<number | null>(null);
  const [newFolderName, setNewFolderName] = useState('');
  
  // Upload state
  const [dragOverColumn, setDragOverColumn] = useState<number | null>(null);
  const [uploadProgress, setUploadProgress] = useState<{ [key: string]: number }>({});
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  // Search/filter state
  const [searchQuery, setSearchQuery] = useState('');

  // Preview panel state
  const [previewItem, setPreviewItem] = useState<FileItem | null>(null);
  const [previewContent, setPreviewContent] = useState<string>('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [showPreview, setShowPreview] = useState(true);

  // Load file tree from backend
  const loadFileTree = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Get file tree from backend
      const treeData = await api.getFileTree();
      const transformedTree = transformFileTree(treeData);
      
      // Set first column to show root items
      setColumns([
        { items: transformedTree, selectedPath: null, title: 'Root' },
        { items: [], selectedPath: null, title: '' },
        { items: [], selectedPath: null, title: '' }
      ]);

      // Get total file info
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

  // Note: formatSize is imported from common/FilePreview

  // Initial load
  useEffect(() => {
    loadFileTree();
  }, [loadFileTree]);

  // Handle folder/file click
  const handleItemClick = useCallback(async (item: FileItem, columnIndex: number) => {
    setColumns(prev => {
      const newColumns = [...prev];
      
      // Update current column selection
      newColumns[columnIndex] = {
        ...newColumns[columnIndex],
        selectedPath: item.path
      };

      // If it's a folder, populate next column
      if (item.type === 'folder' && item.children && columnIndex < 2) {
        newColumns[columnIndex + 1] = {
          items: item.children,
          selectedPath: null,
          title: item.name
        };
        // Clear subsequent columns
        for (let i = columnIndex + 2; i < 3; i++) {
          newColumns[i] = { items: [], selectedPath: null, title: '' };
        }
        // Clear preview when navigating folders
        setPreviewItem(null);
        setPreviewContent('');
      }

        return newColumns;
    });

    // If it's a previewable file, load and show preview
    if (item.type === 'file' && isPreviewable(item.name)) {
      setPreviewItem(item);
      setPreviewLoading(true);
      
      try {
        const fileType = getFileType(item.name);
        // Only load content for text/markdown files
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

    // Close context menu
    setContextMenu(null);
  }, []);

  // Handle context menu (right-click)
  const handleContextMenu = useCallback((e: React.MouseEvent, item: FileItem) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({ x: e.clientX, y: e.clientY, item });
  }, []);

  // Close context menu
  const closeContextMenu = useCallback(() => {
    setContextMenu(null);
  }, []);

  // Check if file can be opened in notes
  const canOpenInNotes = (item: FileItem): boolean => {
    return item.type === 'file' && (item.name.endsWith('.md') || item.name.endsWith('.txt'));
  };

  // Context menu actions
  const handleOpenFile = async () => {
    if (contextMenu?.item && canOpenInNotes(contextMenu.item)) {
      console.log('Opening file in Notes:', contextMenu.item.path);
      try {
        const response = await api.readFile(contextMenu.item.path);
        // Emit custom event for NotesTab to listen to
        window.dispatchEvent(new CustomEvent('openFileInNotes', {
          detail: {
            path: contextMenu.item.path,
            name: contextMenu.item.name,
            content: response.content || ''
          }
        }));
      } catch (err: any) {
        alert('Failed to open file: ' + err.message);
      }
    }
    closeContextMenu();
  };

  const handleOpenInSplit = () => {
    if (contextMenu?.item) {
      console.log('Opening file in split view:', contextMenu.item.path);
      alert(`Opening ${contextMenu.item.path} in split view (TODO)`);
    }
    closeContextMenu();
  };

  const handleCopyPath = () => {
    if (contextMenu?.item) {
      navigator.clipboard.writeText(contextMenu.item.path);
    }
    closeContextMenu();
  };

  const handleDownload = async () => {
    if (contextMenu?.item && contextMenu.item.type === 'file') {
      try {
        // Use the download endpoint
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
        // Generate copy name (e.g., "file.txt" -> "file (copy).txt")
        const item = contextMenu.item;
        const lastDotIndex = item.name.lastIndexOf('.');
        const baseName = lastDotIndex > 0 ? item.name.substring(0, lastDotIndex) : item.name;
        const extension = lastDotIndex > 0 ? item.name.substring(lastDotIndex) : '';
        const copyName = `${baseName} (copy)${extension}`;
        
        // Get parent path
        const parentPath = item.path.substring(0, item.path.lastIndexOf('/'));
        const targetPath = parentPath ? `${parentPath}/${copyName}` : copyName;
        
        await api.copyFile(item.path, targetPath);
        await loadFileTree(); // Refresh
      } catch (err: any) {
        alert('Failed to copy: ' + err.message);
      }
    }
    closeContextMenu();
  };

  const handleDeleteFile = async () => {
    if (contextMenu?.item && contextMenu.item.type === 'file') {
      if (confirm(`Delete ${contextMenu.item.name}?`)) {
        try {
          await api.deleteFile(contextMenu.item.path);
          await loadFileTree(); // Refresh
        } catch (err: any) {
          alert('Failed to delete file: ' + err.message);
        }
      }
    }
    closeContextMenu();
  };

  const handleStartRename = () => {
    if (contextMenu?.item) {
      setRenamingItem(contextMenu.item);
      setRenameValue(contextMenu.item.name);
    }
    closeContextMenu();
  };

  const handleRenameSubmit = async () => {
    if (renamingItem && renameValue && renameValue !== renamingItem.name) {
      try {
        // Get parent path
        const parentPath = renamingItem.path.substring(0, renamingItem.path.lastIndexOf('/'));
        const newPath = parentPath ? `${parentPath}/${renameValue}` : renameValue;
        
        await api.renameFile(renamingItem.path, newPath);
        await loadFileTree(); // Refresh
      } catch (err: any) {
        alert('Failed to rename: ' + err.message);
      }
    }
    setRenamingItem(null);
    setRenameValue('');
  };

  const handleRenameCancel = () => {
    setRenamingItem(null);
    setRenameValue('');
  };

  const handleStartCreateFolder = (columnIndex: number) => {
    setCreatingFolderColumn(columnIndex);
    setNewFolderName('');
  };

  const handleCreateFolderSubmit = async () => {
    if (creatingFolderColumn !== null && newFolderName.trim()) {
      try {
        // Determine parent path based on column
        let parentPath = '';
        if (creatingFolderColumn === 0) {
          // Root level - need to determine which layer
          parentPath = '';
        } else {
          // Get the selected folder from previous column
          const prevColumn = columns[creatingFolderColumn - 1];
          if (prevColumn.selectedPath) {
            parentPath = prevColumn.selectedPath;
          }
        }
        
        const newPath = parentPath ? `${parentPath}/${newFolderName}` : newFolderName;
        await api.createFolder(newPath);
        await loadFileTree(); // Refresh
      } catch (err: any) {
        alert('Failed to create folder: ' + err.message);
      }
    }
    setCreatingFolderColumn(null);
    setNewFolderName('');
  };

  const handleCreateFolderCancel = () => {
    setCreatingFolderColumn(null);
    setNewFolderName('');
  };

  // Upload handlers
  const getColumnPath = (columnIndex: number): string => {
    if (columnIndex === 0) {
      return '';
    }
    const prevColumn = columns[columnIndex - 1];
    return prevColumn.selectedPath || '';
  };

  // Move file handlers
  const [draggingItem, setDraggingItem] = useState<FileItem | null>(null);

  const handleDragStart = (e: React.DragEvent, item: FileItem) => {
    e.stopPropagation();
    setDraggingItem(item);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', item.path);
  };

  const handleDragEnd = () => {
    setDraggingItem(null);
  };

  const handleMoveDrop = async (e: React.DragEvent, targetColumnIndex: number) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOverColumn(null);

    const draggedPath = e.dataTransfer.getData('text/plain');
    if (!draggedPath || !draggingItem) return;

    const targetPath = getColumnPath(targetColumnIndex);
    
    // Don't move if dropping in same location
    const currentParent = draggingItem.path.substring(0, draggingItem.path.lastIndexOf('/'));
    if (currentParent === targetPath) {
      setDraggingItem(null);
      return;
    }

    const itemName = draggingItem.name;
    const newPath = targetPath ? `${targetPath}/${itemName}` : itemName;

    try {
      await api.renameFile(draggedPath, newPath);
      await loadFileTree(); // Refresh
    } catch (err: any) {
      alert('Failed to move: ' + err.message);
    }
    setDraggingItem(null);
  };

  // Get current path from columns for breadcrumb
  const getCurrentPath = (): string => {
    // Find the last column with a selected path
    for (let i = columns.length - 1; i >= 0; i--) {
      if (columns[i].selectedPath) {
        return columns[i].selectedPath!;
      }
    }
    return '';
  };

  // Build breadcrumb items from current path
  const buildBreadcrumbs = (): { name: string; path: string }[] => {
    const currentPath = getCurrentPath();
    if (!currentPath) return [{ name: 'Root', path: '' }];
    
    const parts = currentPath.split('/');
    const breadcrumbs: { name: string; path: string }[] = [{ name: 'Root', path: '' }];
    
    let accumulatedPath = '';
    for (const part of parts) {
      accumulatedPath = accumulatedPath ? `${accumulatedPath}/${part}` : part;
      breadcrumbs.push({ name: part, path: accumulatedPath });
    }
    
    return breadcrumbs;
  };

  // Navigate to breadcrumb path
  const navigateToBreadcrumb = async (targetPath: string) => {
    if (!targetPath) {
      // Navigate to root
      const treeData = await api.getFileTree();
      const transformedTree = transformFileTree(treeData);
      setColumns([
        { items: transformedTree, selectedPath: null, title: 'Root' },
        { items: [], selectedPath: null, title: '' },
        { items: [], selectedPath: null, title: '' }
      ]);
      return;
    }
    
    // Reload tree and navigate to path
    await loadFileTree();
    // TODO: Implement navigation to specific path in tree
  };

  const handleFileUpload = async (files: FileList | null, columnIndex: number) => {
    if (!files || files.length === 0) return;

    const parentPath = getColumnPath(columnIndex);

    for (const file of Array.from(files)) {
      const filePath = parentPath ? `${parentPath}/${file.name}` : file.name;

      try {
        setUploadProgress(prev => ({ ...prev, [file.name]: 0 }));

        await api.uploadFile(file, filePath, (progress) => {
          setUploadProgress(prev => ({ ...prev, [file.name]: progress }));
        });

        // Remove progress after upload completes
        setUploadProgress(prev => {
          const newProgress = { ...prev };
          delete newProgress[file.name];
          return newProgress;
        });
      } catch (err: any) {
        alert(`Failed to upload ${file.name}: ${err.message}`);
        setUploadProgress(prev => {
          const newProgress = { ...prev };
          delete newProgress[file.name];
          return newProgress;
        });
      }
    }

    await loadFileTree(); // Refresh
  };

  // Filter items based on search query
  const filterItems = (items: FileItem[]): FileItem[] => {
    if (!searchQuery.trim()) return items;
    
    const query = searchQuery.toLowerCase();
    return items.filter(item => 
      item.name.toLowerCase().includes(query)
    );
  };

  const handleDragOver = (e: React.DragEvent, columnIndex: number) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOverColumn(columnIndex);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOverColumn(null);
  };

  const handleDrop = (e: React.DragEvent, columnIndex: number) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOverColumn(null);
    handleFileUpload(e.dataTransfer.files, columnIndex);
  };

  const getItemIcon = (item: FileItem) => {
    if (item.type === 'folder') {
      return item.path === columns[0].selectedPath || 
             item.path === columns[1].selectedPath ? 
             '📂' : '📁';
    }
    return getFileIcon(getFileType(item.name));
  };

  const activeContextItem = contextMenu?.item ?? null;

  if (loading) {
    return (
      <div className="files-tab">
        <div className="files-loading">
          <div className="loading-spinner"></div>
          <p>Loading your grimoire...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="files-tab">
        <div className="files-error">
          <h3>⚠️ Failed to Load Files</h3>
          <p>{error}</p>
          <button className="btn-primary" onClick={loadFileTree}>
            Try Again
          </button>
        </div>
      </div>
    );
  }

  const breadcrumbs = buildBreadcrumbs();

  return (
    <div className="files-tab" onClick={closeContextMenu}>
      <input
        type="file"
        ref={fileInputRef}
        style={{ display: 'none' }}
        multiple
        onChange={(e) => handleFileUpload(e.target.files, 0)}
      />
      
      {/* Breadcrumb Navigation */}
      <div className="files-breadcrumb">
        {breadcrumbs.map((crumb, index) => (
          <React.Fragment key={crumb.path}>
            {index > 0 && <span className="breadcrumb-separator">›</span>}
            <button 
              className={`breadcrumb-item ${index === breadcrumbs.length - 1 ? 'active' : ''}`}
              onClick={() => navigateToBreadcrumb(crumb.path)}
            >
              {crumb.name}
            </button>
          </React.Fragment>
        ))}
      </div>
      
      <div className="files-toolbar">
        <div className="files-toolbar-left">
          <span className="files-toolbar-title">📂 File Library</span>
          <div className="files-search">
            <span className="search-icon">🔍</span>
            <input
              type="text"
              className="search-input"
              placeholder="Search files..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button className="search-clear" onClick={() => setSearchQuery('')}>×</button>
            )}
          </div>
        </div>
        <div className="files-toolbar-right">
          <button className="files-toolbar-btn" onClick={() => fileInputRef.current?.click()}>
            📤 Upload Files
          </button>
          <button className="files-toolbar-btn primary" onClick={loadFileTree}>
            Refresh
          </button>
        </div>
      </div>

      <div className="files-content">
        <div className={`miller-columns ${showPreview && previewItem ? 'with-preview' : ''}`}>
          {columns.filter((column, index) => index === 0 || column.items.length > 0).map((column, columnIndex, filteredColumns) => (
            <div 
              key={columnIndex} 
              className={`miller-column ${columnIndex < filteredColumns.length - 1 ? 'has-next' : ''} ${dragOverColumn === columnIndex ? 'drag-over' : ''}`}
              onDragOver={(e) => handleDragOver(e, columnIndex)}
              onDragLeave={handleDragLeave}
              onDrop={(e) => {
                // Check if it's a file move or file upload
                const draggedPath = e.dataTransfer.getData('text/plain');
                if (draggedPath && draggingItem) {
                  handleMoveDrop(e, columnIndex);
                } else {
                  handleDrop(e, columnIndex);
                }
              }}
            >
              <div className="miller-column-header">
                <span className="column-title">{column.title || 'Select a folder'}</span>
                <div className="column-actions">
                  <span className="column-count">
                    {column.items.length} {column.items.length === 1 ? 'item' : 'items'}
                  </span>
                  <button 
                    className="create-folder-btn" 
                    onClick={() => handleStartCreateFolder(columnIndex)}
                    title="Create new folder"
                  >
                    + 📁
                  </button>
                </div>
              </div>
              
              <div className="miller-column-content">
                {filterItems(column.items).map(item => (
                  <div
                    key={item.path}
                    className={`miller-item ${column.selectedPath === item.path ? 'selected' : ''} ${item.type} ${renamingItem?.path === item.path ? 'renaming' : ''} ${draggingItem?.path === item.path ? 'dragging' : ''} ${isPreviewable(item.name) ? 'previewable' : ''}`}
                    onClick={() => handleItemClick(item, columnIndex)}
                    onContextMenu={(e) => handleContextMenu(e, item)}
                    draggable={renamingItem?.path !== item.path}
                    onDragStart={(e) => handleDragStart(e, item)}
                    onDragEnd={handleDragEnd}
                  >
                    <span className="item-icon">{getItemIcon(item)}</span>

                    {renamingItem?.path === item.path ? (
                      <input
                        type="text"
                        className="rename-input"
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleRenameSubmit();
                          if (e.key === 'Escape') handleRenameCancel();
                        }}
                        onBlur={handleRenameCancel}
                        autoFocus
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <span className="item-name">{item.name}</span>
                    )}

                    {item.type === 'folder' && columnIndex < 2 && (
                      <span className="item-arrow">›</span>
                    )}
                    {item.type === 'file' && isPreviewable(item.name) && (
                      <span className="item-preview-indicator">👁️</span>
                    )}
                  </div>
                ))}
                
                {/* Create folder input */}
                {creatingFolderColumn === columnIndex && (
                  <div className="miller-item creating-folder">
                    <span className="item-icon">📁</span>
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
                      onClick={(e) => e.stopPropagation()}
                      placeholder="Folder name..."
                    />
                  </div>
                )}
                
                {/* Upload progress */}
                {Object.entries(uploadProgress).length > 0 && (
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
            </div>
          ))}
        </div>

        {/* Preview Panel */}
        {showPreview && previewItem && (
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
                          detail: {
                            path: previewItem.path,
                            name: previewItem.name,
                            content: response.content || ''
                          }
                        }));
                      } catch (err: any) {
                        alert('Failed to open file: ' + err.message);
                      }
                    }}
                    title="Open in Notes"
                  >
                    📝 Edit
                  </button>
                )}
                <button 
                  className="preview-action-btn" 
                  onClick={() => setShowPreview(false)}
                  title="Close preview"
                >
                  ✕
                </button>
              </div>
            </div>
            <div className="preview-panel-content">
              {previewLoading ? (
                <div className="preview-loading">Loading preview...</div>
              ) : (
                <FilePreview
                  path={previewItem.path}
                  name={previewItem.name}
                  content={previewContent}
                />
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
            {getItemIcon(activeContextItem)} {activeContextItem.name}
          </div>
          <div className="context-menu-divider" />
          
          {canOpenInNotes(activeContextItem) && (
            <>
              <button className="context-menu-item" onClick={handleOpenFile}>
                <span className="menu-icon">📖</span>
                <span>Open in Notes</span>
              </button>
              <button className="context-menu-item" onClick={handleOpenInSplit}>
                <span className="menu-icon">⚡</span>
                <span>Open in Split View</span>
              </button>
              <div className="context-menu-divider" />
            </>
          )}
          
          <button className="context-menu-item" onClick={handleStartRename}>
            <span className="menu-icon">✏️</span>
            <span>Rename</span>
          </button>
          
          <button className="context-menu-item" onClick={handleCopy}>
            <span className="menu-icon">📄</span>
            <span>Duplicate</span>
          </button>
          
          {activeContextItem.type === 'file' && (
            <>
              <button className="context-menu-item" onClick={handleDownload}>
                <span className="menu-icon">⬇️</span>
                <span>Download</span>
              </button>
              <div className="context-menu-divider" />
              <button className="context-menu-item danger" onClick={handleDeleteFile}>
                <span className="menu-icon">🗑️</span>
                <span>Delete</span>
              </button>
            </>
          )}
          
          <div className="context-menu-divider" />
          <button className="context-menu-item" onClick={handleCopyPath}>
            <span className="menu-icon">📋</span>
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
          <span className="status-hint">💡 Right-click for context menu • Drag files to upload</span>
        </div>
      </div>
    </div>
  );
};
