import React, { useState, useCallback } from 'react';
import { api } from '../services/api';
import './SessionEditor.css';

interface SessionEditorProps {
  onProcessingStart?: (pipelineId: string) => void;
}

export const SessionEditor: React.FC<SessionEditorProps> = ({ onProcessingStart }) => {
  const [content, setContent] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [sessionId, setSessionId] = useState('');

  const handleSubmit = useCallback(async () => {
    if (!content.trim()) return;

    setIsProcessing(true);
    try {
      const response = await api.processSessionNotes(content, sessionId || undefined);
      if (response.pipeline_id) {
        onProcessingStart?.(response.pipeline_id);
        // Clear editor after successful submission
        setContent('');
        setSessionId('');
      }
    } catch (error) {
      console.error('Failed to process session notes:', error);
      alert('Failed to process session notes. Check console for details.');
    } finally {
      setIsProcessing(false);
    }
  }, [content, sessionId, onProcessingStart]);

  const handleClear = () => {
    if (content && !confirm('Are you sure you want to clear the editor?')) {
      return;
    }
    setContent('');
  };

  return (
    <div className="session-editor">
      <div className="session-editor-header">
        <h2>Session Notes</h2>
        <div className="session-controls">
          <input
            type="text"
            placeholder="Session ID (optional)"
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            className="session-id-input"
          />
          <button 
            onClick={handleClear}
            className="btn-clear"
            disabled={isProcessing}
          >
            Clear
          </button>
          <button 
            onClick={handleSubmit}
            className="btn-submit"
            disabled={isProcessing || !content.trim()}
          >
            {isProcessing ? 'Processing...' : 'Process with LLM'}
          </button>
        </div>
      </div>

      <textarea
        className="session-textarea"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="Enter your session notes here...&#10;&#10;This is a plain text editor like Notepad++. Write freely during your D&D session, then click 'Process with LLM' to have the system analyze and structure your notes into the knowledge base."
        spellCheck={false}
      />

      <div className="session-editor-footer">
        <span className="char-count">
          {content.length} characters | {content.split(/\s+/).filter(Boolean).length} words
        </span>
        <span className="hint">
          Tip: Just write freely. The LLM will organize and structure this for you.
        </span>
      </div>
    </div>
  );
};