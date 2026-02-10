import React, { useState, useCallback, useEffect } from 'react';
import { api } from '../../../services/api';
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
  const [fileTree, setFileTree] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // State for three columns
  const [columns, setColumns] = useState<ColumnData[]>([
    { items: [], selectedPath: null, title: 'Root' },
    { items: [], selectedPath: null, title: '' },
    { items: [], selectedPath: null, title: '' }
  ]);

  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; item: FileItem | null } | null>(null);
  const [totalSize, setTotalSize] = useState('0 KB');

  // Load file tree from backend
  const loadFileTree = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Get file tree from backend
      const treeData = await api.getFileTree();
      const transformedTree = transformFileTree(treeData);
      setFileTree(transformedTree);
      
      // Set first column to show root items
      setColumns(prev => [
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

  // Format bytes to human readable
  const formatSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  // Initial load
  useEffect(() => {
    loadFileTree();
  }, [loadFileTree]);

  // Handle folder/file click
  const handleItemClick = useCallback((item: FileItem, columnIndex: number) => {
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
      }

      return newColumns;
    });

    // Close context menu
    setContextMenu(null);
  }, []);

  // Handle RAG checkbox toggle
  const handleRagToggle = useCallback((e: React.MouseEvent, item: FileItem) => {
    e.stopPropagation();
    setSelectedFiles(prev => {
      const newSet = new Set(prev);
      if (newSet.has(item.path)) {
        newSet.delete(item.path);
      } else {
        newSet.add(item.path);
      }
      return newSet;
    });
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

  // Context menu actions
  const handleOpenFile = () => {
    if (contextMenu?.item) {
      console.log('Opening file:', contextMenu.item.path);
      // TODO: Open file in Notes tab - emit event or use global state
      alert(`Opening ${contextMenu.item.path} in Notes tab (TODO)`);
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

  const getFileIcon = (item: FileItem) => {
    if (item.type === 'folder') {
      return item.path === columns[0].selectedPath || 
             item.path === columns[1].selectedPath ? 
             '📂' : '📁';
    }
    if (item.name.endsWith('.md')) return '📝';
    if (item.name.endsWith('.txt')) return '📄';
    return '📎';
  };

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

  return (
    <div className="files-tab" onClick={closeContextMenu}>
      <div className="files-toolbar">
        <div className="files-toolbar-left">
          <span className="files-toolbar-title">📂 File Library</span>
          <span className="files-toolbar-subtitle">
            {selectedFiles.size} files in RAG context
          </span>
        </div>
        <div className="files-toolbar-right">
          <button className="files-toolbar-btn" onClick={() => setSelectedFiles(new Set())}>
            Clear Selection
          </button>
          <button className="files-toolbar-btn primary" onClick={loadFileTree}>
            Refresh
          </button>
        </div>
      </div>

      <div className="miller-columns">
        {columns.map((column, columnIndex) => (
          <div 
            key={columnIndex} 
            className={`miller-column ${columnIndex < 2 ? 'has-next' : ''}`}
            style={{ opacity: column.items.length > 0 ? 1 : 0.5 }}
          >
            <div className="miller-column-header">
              <span className="column-title">{column.title || 'Select a folder'}</span>
              <span className="column-count">
                {column.items.length} {column.items.length === 1 ? 'item' : 'items'}
              </span>
            </div>
            
            <div className="miller-column-content">
              {column.items.map(item => (
                <div
                  key={item.path}
                  className={`miller-item ${column.selectedPath === item.path ? 'selected' : ''} ${item.type}`}
                  onClick={() => handleItemClick(item, columnIndex)}
                  onContextMenu={(e) => handleContextMenu(e, item)}
                >
                  <span className="item-icon">{getFileIcon(item)}</span>
                  <span className="item-name">{item.name}</span>
                  
                  {item.type === 'file' && (
                    <label 
                      className="rag-checkbox"
                      onClick={(e) => e.stopPropagation()}
                      title="Include in RAG context"
                    >
                      <input
                        type="checkbox"
                        checked={selectedFiles.has(item.path)}
                        onChange={(e) => handleRagToggle(e as unknown as React.MouseEvent, item)}
                      />
                      <span className="checkmark"></span>
                    </label>
                  )}
                  
                  {item.type === 'folder' && columnIndex < 2 && (
                    <span className="item-arrow">›</span>
                  )}
                </div>
              ))}
              
              {column.items.length === 0 && columnIndex > 0 && (
                <div className="miller-empty">
                  <span className="empty-icon">📂</span>
                  <span>Select a folder to view contents</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Context Menu */}
      {contextMenu && contextMenu.item && (
        <div 
          className="files-context-menu"
          style={{ left: contextMenu.x, top: contextMenu.y }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="context-menu-header">
            {getFileIcon(contextMenu.item)} {contextMenu.item.name}
          </div>
          <div className="context-menu-divider" />
          
          {contextMenu.item.type === 'file' && (
            <>
              <button className="context-menu-item" onClick={handleOpenFile}>
                <span className="menu-icon">📖</span>
                <span>Open in Notes</span>
              </button>
              <button className="context-menu-item" onClick={handleOpenInSplit}>
                <span className="menu-icon">⚡</span>
                <span>Open in Split View</span>
              </button>
            </>
          )}
          
          {contextMenu.item.type === 'file' && (
            <>
              <div className="context-menu-divider" />
              <label className="context-menu-item checkbox-item">
                <input
                  type="checkbox"
                  checked={selectedFiles.has(contextMenu.item.path)}
                  onChange={(e) => handleRagToggle(e as unknown as React.MouseEvent, contextMenu.item)}
                />
                <span>Include in RAG</span>
              </label>
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
          <span className="status-label">Selected:</span>
          <span className="status-value">{selectedFiles.size} files</span>
        </div>
        <div className="status-divider" />
        <div className="status-section">
          <span className="status-label">Total Size:</span>
          <span className="status-value">{totalSize}</span>
        </div>
        <div className="status-divider" />
        <div className="status-section">
          <span className="status-hint">💡 Right-click for context menu</span>
        </div>
      </div>
    </div>
  );
};
