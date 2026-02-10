import React, { useState, useCallback, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import { FileTab } from './FileTab';
import { SplitContainer } from './SplitContainer';
import { MetaNotesPanel } from './MetaNotesPanel';
import { api } from '../../../services/api';
import './NotesTab.css';

export interface OpenFile {
  id: string;
  path: string;
  name: string;
  content: string;
  originalContent: string;
  isModified: boolean;
  isActive: boolean;
}

export interface SplitPane {
  id: string;
  type: 'leaf' | 'split';
  direction?: 'vertical' | 'horizontal'; // horizontal for future
  fileId?: string; // For leaf nodes
  children?: [SplitPane, SplitPane]; // For split nodes
  sizes?: [number, number]; // Percentages
}

// Generate unique IDs
const generateId = () => Math.random().toString(36).substr(2, 9);

export const NotesTab: React.FC = () => {
  const [files, setFiles] = useState<OpenFile[]>([]);
  const [splitRoot, setSplitRoot] = useState<SplitPane>({
    id: generateId(),
    type: 'leaf',
  });
  const [showMetaNotes, setShowMetaNotes] = useState(true);
  const [activeFileId, setActiveFileId] = useState<string | null>(null);

  // Sync status and processing state
  const [syncStatus, setSyncStatus] = useState<{ is_synced: boolean; content_changed: boolean; last_processed: string | null } | null>(null);
  const [lastProcessed, setLastProcessed] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [showProcessModal, setShowProcessModal] = useState(false);
  const [processingResult, setProcessingResult] = useState<{ success: boolean; message: string } | null>(null);

  // Debounced auto-save
  const debouncedSave = useCallback((fileId: string, content: string) => {
    // TODO: Implement actual API save
    console.log('Auto-saving file:', fileId, content.substring(0, 50) + '...');
    
    setFiles(prev => prev.map(f => 
      f.id === fileId 
        ? { ...f, content, isModified: content !== f.originalContent }
        : f
    ));
  }, []);

  const handleFileOpen = useCallback((path: string, name: string, content: string) => {
    // Check if already open
    const existingFile = files.find(f => f.path === path);
    if (existingFile) {
      setFiles(prev => prev.map(f => ({ ...f, isActive: f.id === existingFile.id })));
      setActiveFileId(existingFile.id);
      return;
    }

    // Create new file entry
    const newFile: OpenFile = {
      id: generateId(),
      path,
      name,
      content,
      originalContent: content,
      isModified: false,
      isActive: true,
    };

    setFiles(prev => {
      // Deactivate all others
      const updated = prev.map(f => ({ ...f, isActive: false }));
      return [...updated, newFile];
    });
    setActiveFileId(newFile.id);
  }, [files]);

  const handleFileClose = useCallback((fileId: string) => {
    setFiles(prev => {
      const file = prev.find(f => f.id === fileId);
      if (file?.isModified) {
        // TODO: Show confirmation dialog
        const confirmed = window.confirm(`Save changes to ${file.name}?`);
        if (confirmed) {
          // Save logic here
        }
      }
      
      const filtered = prev.filter(f => f.id !== fileId);
      
      // Activate another file if this was active
      if (file?.isActive && filtered.length > 0) {
        filtered[filtered.length - 1].isActive = true;
        setActiveFileId(filtered[filtered.length - 1].id);
      } else if (filtered.length === 0) {
        setActiveFileId(null);
      }
      
      return filtered;
    });
  }, []);

  const handleFileSelect = useCallback((fileId: string) => {
    setFiles(prev => prev.map(f => ({ ...f, isActive: f.id === fileId })));
    setActiveFileId(fileId);
  }, []);

  const handleContentChange = useCallback((fileId: string, content: string) => {
    setFiles(prev => prev.map(f => 
      f.id === fileId ? { ...f, content, isModified: content !== f.originalContent } : f
    ));
  }, []);

  const handleSplit = useCallback((direction: 'vertical' | 'horizontal') => {
    // Find active pane and split it
    setSplitRoot(prev => {
      const newPane: SplitPane = {
        id: generateId(),
        type: 'split',
        direction,
        children: [
          { ...prev },
          { id: generateId(), type: 'leaf' }
        ],
        sizes: [50, 50],
      };
      return newPane;
    });
  }, []);

  const handleNewFile = useCallback(() => {
    // TODO: Implement new file creation
    // For now, create a dummy file
    const newFile: OpenFile = {
      id: generateId(),
      path: `untitled-${files.length + 1}.md`,
      name: `untitled-${files.length + 1}.md`,
      content: '',
      originalContent: '',
      isModified: false,
      isActive: true,
    };

    setFiles(prev => {
      const updated = prev.map(f => ({ ...f, isActive: false }));
      return [...updated, newFile];
    });
    setActiveFileId(newFile.id);
  }, [files.length]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault();
        handleNewFile();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'w') {
        e.preventDefault();
        if (activeFileId) {
          handleFileClose(activeFileId);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleNewFile, handleFileClose, activeFileId]);

  const activeFile = files.find(f => f.id === activeFileId);

  // Poll sync status for active file
  useEffect(() => {
    if (!activeFile) {
      setSyncStatus(null);
      return;
    }

    const checkSyncStatus = async () => {
      try {
        const status = await api.getSyncStatus(activeFile.path);
        setSyncStatus(status);
        setLastProcessed(status.last_processed);
      } catch (error) {
        console.error('Failed to check sync status:', error);
      }
    };

    checkSyncStatus();
    const interval = setInterval(checkSyncStatus, 5000);

    return () => clearInterval(interval);
  }, [activeFile]);

  // Handle file processing for entity extraction
  const handleProcessFile = async () => {
    if (!activeFile) return;

    setIsProcessing(true);
    setProcessingResult(null);

    try {
      // Start entity extraction pipeline
      const startResult = await api.startEntityExtraction(activeFile.path);
      
      if (startResult.pipeline_id) {
        // Run the extraction
        await api.runEntityExtraction(startResult.pipeline_id);
        
        setProcessingResult({
          success: true,
          message: 'Entity extraction completed successfully!'
        });
        
        // Update sync status
        const status = await api.getSyncStatus(activeFile.path);
        setSyncStatus(status);
        setLastProcessed(status.last_processed);
      }
    } catch (error) {
      console.error('Failed to process file:', error);
      setProcessingResult({
        success: false,
        message: error instanceof Error ? error.message : 'Failed to process file'
      });
    } finally {
      setIsProcessing(false);
      setShowProcessModal(false);
    }
  };

  // Format relative time
  const formatRelativeTime = (timestamp: string | null): string => {
    if (!timestamp) return 'Never';
    
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
  };

  return (
    <div className="notes-tab">
      {/* Toolbar */}
      <div className="notes-toolbar">
        <div className="toolbar-left">
          <button className="toolbar-btn" onClick={handleNewFile} title="New File (Ctrl+N)">
            📝 New
          </button>
          <div className="toolbar-divider" />
          <button className="toolbar-btn" onClick={() => handleSplit('vertical')} title="Split Vertical">
            ↔️ Split
          </button>
          <button 
            className={`toolbar-btn ${showMetaNotes ? 'active' : ''}`} 
            onClick={() => setShowMetaNotes(!showMetaNotes)}
            title="Toggle MetaNotes"
          >
            💬 MetaNotes
          </button>
          <button 
            className="toolbar-btn" 
            onClick={() => setShowProcessModal(true)}
            disabled={!activeFile}
            title="Process for Entity Extraction"
          >
            🔄 Process
          </button>
        </div>
        <div className="toolbar-right">
          {activeFile && syncStatus && (
            <div className="sync-status">
              <span 
                className={`sync-indicator ${
                  syncStatus.is_synced 
                    ? 'synced' 
                    : syncStatus.content_changed 
                      ? 'unsynced' 
                      : 'never'
                }`}
              />
              <span className="sync-text">
                {syncStatus.is_synced 
                  ? `Synced ${formatRelativeTime(syncStatus.last_processed)}`
                  : syncStatus.content_changed 
                    ? 'Unsynced - content changed'
                    : 'Never processed'
                }
              </span>
            </div>
          )}
          {activeFile?.isModified && (
            <span className="modified-indicator">● Modified</span>
          )}
        </div>
      </div>

      {/* File Tabs */}
      {files.length > 0 && (
        <div className="file-tabs">
          {files.map(file => (
            <FileTab
              key={file.id}
              file={file}
              onSelect={() => handleFileSelect(file.id)}
              onClose={() => handleFileClose(file.id)}
            />
          ))}
        </div>
      )}

      {/* Editor Area */}
      <div className="editor-area">
        {files.length === 0 ? (
          <div className="empty-state">
            <h3>✨ The Grimoire Awaits</h3>
            <p>MegaBook - the cosmic grimoire - opens its pages to you. Create a new scroll or retrieve one from the Files tab.</p>
            <button className="btn-primary" onClick={handleNewFile}>
              Inscribe New Page
            </button>
          </div>
        ) : (
          <div className="editor-container">
            <SplitContainer
              pane={splitRoot}
              files={files}
              activeFileId={activeFileId}
              onFileSelect={handleFileSelect}
              onContentChange={handleContentChange}
              onDebouncedSave={debouncedSave}
            />
            
            {showMetaNotes && (
              <MetaNotesPanel
                activeFile={activeFile}
                onApplyChanges={(changes) => {
                  if (activeFileId) {
                    handleContentChange(activeFileId, changes);
                  }
                }}
              />
            )}
          </div>
        )}
      </div>

      {/* Process Modal */}
      {showProcessModal && (
        <div className="process-modal-overlay" onClick={() => !isProcessing && setShowProcessModal(false)}>
          <div className="process-modal" onClick={e => e.stopPropagation()}>
            <h3>Process Note for Extraction</h3>
            
            <div className="process-modal-content">
              <div className="process-info-row">
                <span className="process-label">File:</span>
                <span className="process-value">{activeFile?.path}</span>
              </div>
              
              <div className="process-info-row">
                <span className="process-label">Status:</span>
                <span className="process-value">
                  {syncStatus?.is_synced 
                    ? 'Synced' 
                    : syncStatus?.content_changed 
                      ? 'Unsynced' 
                      : 'Never processed'
                  }
                </span>
              </div>
              
              <div className="process-warning">
                <span className="warning-icon">⚠️</span>
                <span>This will use AI to extract entities (~$0.02 cost)</span>
              </div>
              
              {processingResult && (
                <div className={`process-result ${processingResult.success ? 'success' : 'error'}`}>
                  {processingResult.message}
                </div>
              )}
            </div>
            
            <div className="process-modal-actions">
              <button 
                className="toolbar-btn" 
                onClick={() => setShowProcessModal(false)}
                disabled={isProcessing}
              >
                Cancel
              </button>
              <button 
                className="toolbar-btn btn-primary" 
                onClick={handleProcessFile}
                disabled={isProcessing}
              >
                {isProcessing ? 'Processing...' : 'Process Anyway'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};