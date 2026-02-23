import React, { useState, useEffect, useCallback } from 'react';
import Editor from '@monaco-editor/react';
import { api } from '../services/api';
import './MarkdownEditor.css';

interface MarkdownEditorProps {
  filePath: string | null;
  onSave?: () => void;
}

export const MarkdownEditor: React.FC<MarkdownEditorProps> = ({ filePath, onSave }) => {
  const [content, setContent] = useState('');
  const [originalContent, setOriginalContent] = useState('');
  const [isDirty, setIsDirty] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const loadFile = useCallback(async () => {
    if (!filePath) {
      setContent('');
      setOriginalContent('');
      setIsDirty(false);
      return;
    }

    setIsLoading(true);
    try {
      const data = await api.readFile(filePath);
      setContent(data.content);
      setOriginalContent(data.content);
      setIsDirty(false);
    } catch (error) {
      console.error('Failed to load file:', error);
      setContent('');
      setOriginalContent('');
    } finally {
      setIsLoading(false);
    }
  }, [filePath]);

  useEffect(() => {
    loadFile();
  }, [loadFile]);

  const handleChange = (value: string | undefined) => {
    const newContent = value || '';
    setContent(newContent);
    setIsDirty(newContent !== originalContent);
  };

  const handleSave = async () => {
    if (!filePath || !isDirty) return;

    setIsSaving(true);
    try {
      await api.writeFile(filePath, content);
      setOriginalContent(content);
      setIsDirty(false);
      onSave?.();
    } catch (error) {
      console.error('Failed to save file:', error);
      alert('Failed to save file. Check console for details.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      handleSave();
    }
  };

  if (!filePath) {
    return (
      <div className="markdown-editor empty">
        <div className="empty-message">
          <p>Select a file from the sidebar to edit</p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="markdown-editor loading">
        <div className="loading-message">Loading...</div>
      </div>
    );
  }

  return (
    <div className="markdown-editor" onKeyDown={handleKeyDown}>
      <div className="editor-header">
        <div className="file-info">
          <span className="file-path">{filePath}</span>
          {isDirty && <span className="dirty-indicator">•</span>}
        </div>
        <div className="editor-actions">
          <button
            onClick={handleSave}
            disabled={!isDirty || isSaving}
            className="btn-save"
          >
            {isSaving ? 'Saving...' : 'Save (Ctrl+S)'}
          </button>
        </div>
      </div>

      <div className="editor-container">
        <Editor
          height="100%"
          defaultLanguage="markdown"
          value={content}
          onChange={handleChange}
          theme="vs-dark"
          options={{
            minimap: { enabled: false },
            fontSize: 14,
            wordWrap: 'on',
            automaticLayout: true,
            scrollBeyondLastLine: false,
            lineNumbers: 'on',
            folding: true,
            renderWhitespace: 'selection',
          }}
        />
      </div>
    </div>
  );
};
