import { useState, useCallback, useEffect } from 'react';
import { api } from '../../../services/api';
import { FilePreview } from '../../common';
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

// Generate unique IDs
const generateId = () => Math.random().toString(36).substr(2, 9);

export const NotesTab: React.FC = () => {
  const [files, setFiles] = useState<OpenFile[]>([]);
  const [activeFileId, setActiveFileId] = useState<string | null>(null);
  const [isPreviewMode, setIsPreviewMode] = useState(false);

  const activeFile = files.find(f => f.id === activeFileId);

  // Debounced auto-save
  const debouncedSave = useCallback(async (fileId: string, content: string) => {
    const file = files.find(f => f.id === fileId);
    if (!file) return;
    
    try {
      await api.writeFile(file.path, content);
      console.log('File saved:', file.path);
      
      setFiles(prev => prev.map(f => 
        f.id === fileId 
          ? { ...f, content, isModified: false, originalContent: content }
          : f
      ));
    } catch (error) {
      console.error('Failed to save file:', error);
    }
  }, [files]);

  const handleFileClose = useCallback(async (fileId: string) => {
    const file = files.find(f => f.id === fileId);
    if (file?.isModified) {
      const confirmed = window.confirm(`Save changes to ${file.name}?`);
      if (confirmed) {
        await debouncedSave(fileId, file.content);
      }
    }
    
    setFiles(prev => {
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
  }, [files, debouncedSave]);

  const handleFileSelect = useCallback((fileId: string) => {
    setFiles(prev => prev.map(f => ({ ...f, isActive: f.id === fileId })));
    setActiveFileId(fileId);
    setIsPreviewMode(false); // Reset to edit mode when switching files
  }, []);

  const handleContentChange = useCallback((fileId: string, content: string) => {
    setFiles(prev => prev.map(f => 
      f.id === fileId ? { ...f, content, isModified: content !== f.originalContent } : f
    ));
  }, []);

  const handleNewFile = useCallback(() => {
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
    setIsPreviewMode(false);
  }, [files.length]);

  const handleSaveFile = useCallback(async () => {
    if (activeFileId) {
      const file = files.find(f => f.id === activeFileId);
      if (file?.isModified) {
        await debouncedSave(activeFileId, file.content);
      }
    }
  }, [activeFileId, files, debouncedSave]);

  // Listen for file open events from FilesTab
  useEffect(() => {
    const handleOpenFile = (e: CustomEvent) => {
      const { path, name, content } = e.detail;
      
      // Check if file is already open
      const existingFile = files.find(f => f.path === path);
      if (existingFile) {
        handleFileSelect(existingFile.id);
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
        const updated = prev.map(f => ({ ...f, isActive: false }));
        return [...updated, newFile];
      });
      setActiveFileId(newFile.id);
      setIsPreviewMode(false);
    };

    window.addEventListener('openFileInNotes', handleOpenFile as EventListener);
    return () => window.removeEventListener('openFileInNotes', handleOpenFile as EventListener);
  }, [files, handleFileSelect]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = async (e: KeyboardEvent) => {
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
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        await handleSaveFile();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'p') {
        e.preventDefault();
        if (activeFile && (activeFile.name.endsWith('.md') || activeFile.name.endsWith('.txt'))) {
          setIsPreviewMode(prev => !prev);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleNewFile, handleFileClose, activeFileId, handleSaveFile, activeFile]);

  const canPreview = activeFile && (activeFile.name.endsWith('.md') || activeFile.name.endsWith('.txt'));

  return (
    <div className="notes-tab">
      {/* Toolbar */}
      <div className="notes-toolbar">
        <div className="toolbar-left">
          <button className="toolbar-btn" onClick={handleNewFile} title="New File (Ctrl+N)">
            📝 New
          </button>
          <div className="toolbar-divider" />
          <button 
            className="toolbar-btn" 
            onClick={handleSaveFile}
            disabled={!activeFile?.isModified}
            title="Save (Ctrl+S)"
          >
            💾 Save
          </button>
          {canPreview && (
            <>
              <div className="toolbar-divider" />
              <button 
                className={`toolbar-btn ${isPreviewMode ? '' : 'active'}`}
                onClick={() => setIsPreviewMode(false)}
                title="Edit mode"
              >
                ✏️ Edit
              </button>
              <button 
                className={`toolbar-btn ${isPreviewMode ? 'active' : ''}`}
                onClick={() => setIsPreviewMode(true)}
                title="Preview mode (Ctrl+P)"
              >
                👁️ Preview
              </button>
            </>
          )}
        </div>
        <div className="toolbar-right">
          {activeFile?.isModified && (
            <span className="modified-indicator">● Modified</span>
          )}
        </div>
      </div>

      {/* Tab Bar */}
      {files.length > 0 && (
        <div className="tab-bar">
          {files.map(file => (
            <div
              key={file.id}
              className={`file-tab ${file.isActive ? 'active' : ''}`}
              onClick={() => handleFileSelect(file.id)}
            >
              <span className="tab-name">{file.name}</span>
              {file.isModified && <span className="modified-dot">●</span>}
              <button
                className="tab-close-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  handleFileClose(file.id);
                }}
                title="Close tab"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Editor Area */}
      <div className="editor-container">
        {!activeFile ? (
          <div className="empty-state">
            <div className="empty-icon">📜</div>
            <h3>The Grimoire Awaits</h3>
            <p>Create a new scroll or open one from the Files tab</p>
            <button className="btn-primary" onClick={handleNewFile}>
              Create New Note
            </button>
          </div>
        ) : isPreviewMode && canPreview ? (
          <div className="preview-container">
            <FilePreview
              path={activeFile.path}
              name={activeFile.name}
              content={activeFile.content}
            />
          </div>
        ) : (
          <textarea
            className="notepad-editor"
            value={activeFile.content}
            onChange={(e) => handleContentChange(activeFile.id, e.target.value)}
            spellCheck={false}
            placeholder="Start writing your tale..."
          />
        )}
      </div>

      {/* Status Bar */}
      <div className="status-bar">
        <div className="status-left">
          {activeFile ? (
            <>
              <span className="status-item">{activeFile.name}</span>
              <span className="status-separator">|</span>
              <span className="status-item">
                {activeFile.content.length} characters
              </span>
              <span className="status-separator">|</span>
              <span className="status-item">
                {activeFile.content.split('\n').length} lines
              </span>
            </>
          ) : (
            <span className="status-item">No file open</span>
          )}
        </div>
        <div className="status-right">
          <span className="status-item">Markdown supported</span>
        </div>
      </div>
    </div>
  );
};
