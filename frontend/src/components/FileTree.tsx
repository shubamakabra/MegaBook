import React, { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../services/api';
import { FileTreeNode } from '../types';
import './FileTree.css';

interface FileTreeProps {
  onFileSelect: (path: string, layer: string) => void; // Single click - preview
  onFileOpen: (path: string, layer: string) => void;   // Double click - open
  selectedFile: string | null;
  activeFile: string | null; // Currently open in editor
}

interface TreeNodeProps {
  name: string;
  node: FileTreeNode;
  path: string;
  layer: string;
  level: number;
  selectedFile: string | null;
  activeFile: string | null;
  expandedFolders: Set<string>;
  onToggleFolder: (path: string) => void;
  onFileSelect: (path: string, layer: string) => void;
  onFileOpen: (path: string, layer: string) => void;
}

const TreeNode: React.FC<TreeNodeProps> = ({
  name,
  node,
  path,
  layer,
  level,
  selectedFile,
  activeFile,
  expandedFolders,
  onToggleFolder,
  onFileSelect,
  onFileOpen,
}) => {
  const isSelected = node.path === selectedFile;
  const isActive = node.path === activeFile;
  const isExpanded = expandedFolders.has(path);
  const isDirectory = node.type === 'directory';

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isDirectory) {
      onToggleFolder(path);
    } else if (node.path) {
      onFileSelect(node.path, layer);
    }
  };

  const handleDoubleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!isDirectory && node.path) {
      onFileOpen(node.path, layer);
    }
  };

  const paddingLeft = level * 12 + 8;

  return (
    <div className="tree-node">
      <div
        className={`tree-item ${node.type} ${isSelected ? 'selected' : ''} ${isActive ? 'active' : ''}`}
        style={{ paddingLeft }}
        onClick={handleClick}
        onDoubleClick={handleDoubleClick}
        title={isDirectory ? 'Click to expand/collapse' : 'Click to select, double-click to open'}
      >
        {/* Expand/chevron icon for folders */}
        {isDirectory && (
          <span className={`tree-chevron ${isExpanded ? 'expanded' : ''}`}>
            ▶
          </span>
        )}
        
        {/* File/folder icon */}
        <span className="tree-icon">
          {isDirectory ? (isExpanded ? '📂' : '📁') : getFileIcon(name)}
        </span>
        
        {/* Label */}
        <span className="tree-label">{name}</span>
        
        {/* Active indicator */}
        {isActive && <span className="active-indicator" title="Open in editor">●</span>}
      </div>
      
      {/* Render children if expanded */}
      {isDirectory && isExpanded && node.children && (
        <div className="tree-children">
          {Object.entries(node.children).map(([childName, childNode]) => (
            <TreeNode
              key={childName}
              name={childName}
              node={childNode}
              path={`${path}/${childName}`}
              layer={layer}
              level={level + 1}
              selectedFile={selectedFile}
              activeFile={activeFile}
              expandedFolders={expandedFolders}
              onToggleFolder={onToggleFolder}
              onFileSelect={onFileSelect}
              onFileOpen={onFileOpen}
            />
          ))}
        </div>
      )}
    </div>
  );
};

// Get appropriate icon based on file extension
function getFileIcon(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase();
  switch (ext) {
    case 'md': return '📝';
    case 'txt': return '📄';
    case 'json': return '📋';
    case 'yaml':
    case 'yml': return '⚙️';
    default: return '📄';
  }
}

export const FileTree: React.FC<FileTreeProps> = ({ 
  onFileSelect, 
  onFileOpen, 
  selectedFile,
  activeFile 
}) => {
  const [trees, setTrees] = useState<Record<string, FileTreeNode>>({});
  const [activeLayer, setActiveLayer] = useState<string>('all');
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set(['prompts', 'notes', 'wiki']));
  const [isLoading, setIsLoading] = useState(false);

  const fetchTrees = useCallback(async () => {
    setIsLoading(true);
    try {
      if (activeLayer === 'all') {
        const [prompts, notes, wiki] = await Promise.all([
          api.getFileTree('prompts').catch(() => ({})),
          api.getFileTree('notes').catch(() => ({})),
          api.getFileTree('wiki').catch(() => ({})),
        ]);
        setTrees({ prompts, notes, wiki });
      } else {
        const tree = await api.getFileTree(activeLayer);
        setTrees({ [activeLayer]: tree });
      }
    } catch (error) {
      console.error('Failed to fetch file tree:', error);
    } finally {
      setIsLoading(false);
    }
  }, [activeLayer]);

  useEffect(() => {
    fetchTrees();
  }, [fetchTrees]);

  const handleToggleFolder = useCallback((path: string) => {
    setExpandedFolders(prev => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  const handleCollapseAll = () => {
    setExpandedFolders(new Set());
  };

  const handleExpandAll = () => {
    const allPaths = new Set<string>();
    const collectPaths = (obj: Record<string, FileTreeNode>, prefix: string) => {
      Object.entries(obj).forEach(([name, node]) => {
        const path = `${prefix}/${name}`;
        if (node.type === 'directory') {
          allPaths.add(path);
          if (node.children) {
            collectPaths(node.children, path);
          }
        }
      });
    };
    
    if (activeLayer === 'all') {
      ['prompts', 'notes', 'wiki'].forEach(layer => {
        allPaths.add(layer);
        if (trees[layer]) {
          collectPaths(trees[layer], layer);
        }
      });
    } else {
      allPaths.add(activeLayer);
      if (trees[activeLayer]) {
        collectPaths(trees[activeLayer], activeLayer);
      }
    }
    
    setExpandedFolders(allPaths);
  };

  return (
    <div className="file-tree">
      <div className="file-tree-header">
        <h3>Explorer</h3>
        <div className="file-tree-actions">
          <button 
            className="icon-btn" 
            onClick={handleCollapseAll}
            title="Collapse All"
          >
            ⬆️
          </button>
          <button 
            className="icon-btn" 
            onClick={handleExpandAll}
            title="Expand All"
          >
            ⬇️
          </button>
          <button 
            className="icon-btn" 
            onClick={fetchTrees}
            title="Refresh"
            disabled={isLoading}
          >
            🔄
          </button>
        </div>
      </div>

      <div className="layer-tabs">
        {['all', 'prompts', 'notes', 'wiki'].map((layer) => (
          <button
            key={layer}
            className={`layer-tab ${activeLayer === layer ? 'active' : ''}`}
            onClick={() => setActiveLayer(layer)}
          >
            {layer === 'all' ? 'All' : layer.charAt(0).toUpperCase() + layer.slice(1)}
          </button>
        ))}
      </div>

      <div className="file-tree-content">
        {isLoading ? (
          <div className="loading">Loading...</div>
        ) : activeLayer === 'all' ? (
          <>
            <LayerSection
              title="Prompts"
              layer="prompts"
              tree={trees.prompts || {}}
              selectedFile={selectedFile}
              activeFile={activeFile}
              expandedFolders={expandedFolders}
              onToggleFolder={handleToggleFolder}
              onFileSelect={onFileSelect}
              onFileOpen={onFileOpen}
            />
            <LayerSection
              title="Notes"
              layer="notes"
              tree={trees.notes || {}}
              selectedFile={selectedFile}
              activeFile={activeFile}
              expandedFolders={expandedFolders}
              onToggleFolder={handleToggleFolder}
              onFileSelect={onFileSelect}
              onFileOpen={onFileOpen}
            />
            <LayerSection
              title="Wiki"
              layer="wiki"
              tree={trees.wiki || {}}
              selectedFile={selectedFile}
              activeFile={activeFile}
              expandedFolders={expandedFolders}
              onToggleFolder={handleToggleFolder}
              onFileSelect={onFileSelect}
              onFileOpen={onFileOpen}
            />
          </>
        ) : (
          <LayerSection
            title={activeLayer.charAt(0).toUpperCase() + activeLayer.slice(1)}
            layer={activeLayer}
            tree={trees[activeLayer] || {}}
            selectedFile={selectedFile}
            activeFile={activeFile}
            expandedFolders={expandedFolders}
            onToggleFolder={handleToggleFolder}
            onFileSelect={onFileSelect}
            onFileOpen={onFileOpen}
          />
        )}
      </div>
    </div>
  );
};

// Helper component for layer sections
interface LayerSectionProps {
  title: string;
  layer: string;
  tree: Record<string, FileTreeNode>;
  selectedFile: string | null;
  activeFile: string | null;
  expandedFolders: Set<string>;
  onToggleFolder: (path: string) => void;
  onFileSelect: (path: string, layer: string) => void;
  onFileOpen: (path: string, layer: string) => void;
}

const LayerSection: React.FC<LayerSectionProps> = ({
  title,
  layer,
  tree,
  selectedFile,
  activeFile,
  expandedFolders,
  onToggleFolder,
  onFileSelect,
  onFileOpen,
}) => {
  if (Object.keys(tree).length === 0) return null;

  return (
    <div className="layer-section">
      <div className="layer-header">
        <span className="layer-title">{title}</span>
      </div>
      {Object.entries(tree).map(([name, node]) => (
        <TreeNode
          key={name}
          name={name}
          node={node}
          path={`${layer}/${name}`}
          layer={layer}
          level={0}
          selectedFile={selectedFile}
          activeFile={activeFile}
          expandedFolders={expandedFolders}
          onToggleFolder={onToggleFolder}
          onFileSelect={onFileSelect}
          onFileOpen={onFileOpen}
        />
      ))}
    </div>
  );
};