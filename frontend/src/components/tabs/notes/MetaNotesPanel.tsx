import React, { useState } from 'react';
import { OpenFile } from './NotesTab';
import './MetaNotesPanel.css';

interface MetaNotesPanelProps {
  activeFile: OpenFile | undefined;
  onApplyChanges: (changes: string) => void;
}

// TODO: Replace with real LLM integration
const MOCK_METANOTES_RESPONSES = [
  "I've analyzed your text and suggest adding a table of contents at the beginning. Would you like me to insert it?",
  "This section could benefit from bullet points. Shall I reformat the list items?",
  "I noticed some inconsistencies with character names. I suggest standardizing them throughout the document.",
  "Great content! I can help organize this into sections with headers. Should I proceed?",
  "I can add wiki links to mentioned characters and locations. This will make the document more connected!"
];

export const MetaNotesPanel: React.FC<MetaNotesPanelProps> = ({
  activeFile,
  onApplyChanges,
}) => {
  const [prompt, setPrompt] = useState('');
  const [response, setResponse] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [suggestedChanges, setSuggestedChanges] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!prompt.trim() || !activeFile) return;

    setIsLoading(true);
    setResponse(null);
    setSuggestedChanges(null);

    // TODO: Replace with real API call
    setTimeout(() => {
      const mockResponse = MOCK_METANOTES_RESPONSES[Math.floor(Math.random() * MOCK_METANOTES_RESPONSES.length)];
      setResponse(mockResponse);
      
      // Mock suggested changes
      const mockChanges = activeFile.content + '\n\n<!-- MetaNotes suggested addition -->\n*[Suggested changes would appear here in real implementation]*';
      setSuggestedChanges(mockChanges);
      
      setIsLoading(false);
    }, 1500);
  };

  const handleApply = () => {
    if (suggestedChanges) {
      onApplyChanges(suggestedChanges);
      setResponse(null);
      setSuggestedChanges(null);
      setPrompt('');
    }
  };

  const handleDismiss = () => {
    setResponse(null);
    setSuggestedChanges(null);
  };

  return (
    <div className="metanotes-panel">
      <div className="metanotes-header">
        <h3>💫 MetaNotes</h3>
        <p className="metanotes-subtitle">Consult the cosmic grimoire for wisdom</p>
      </div>

      <div className="metanotes-content">
        {!activeFile ? (
          <div className="metanotes-empty">
            <p>Open a scroll to consult the grimoire's wisdom</p>
          </div>
        ) : (
          <>
            <div className="metanotes-input-area">
              <textarea
                className="metanotes-input"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="e.g., 'Make this into bullet points' or 'Add a summary section'"
                disabled={isLoading}
              />
              <button
                className="metanotes-submit"
                onClick={handleSubmit}
                disabled={isLoading || !prompt.trim()}
              >
                {isLoading ? 'Thinking...' : 'Submit'}
              </button>
            </div>

            {isLoading && (
              <div className="metanotes-loading">
                <div className="loading-spinner" />
                <span>AI is analyzing...</span>
              </div>
            )}

            {response && (
              <div className="metanotes-response">
                <div className="response-text">{response}</div>
                
                <div className="response-actions">
                  <button 
                    className="btn-apply" 
                    onClick={handleApply}
                    title="Apply suggested changes"
                  >
                    ✓ Apply
                  </button>
                  <button 
                    className="btn-dismiss" 
                    onClick={handleDismiss}
                    title="Dismiss suggestion"
                  >
                    ✗ Dismiss
                  </button>
                </div>

                <div className="changes-preview">
                  <small>Preview of changes:</small>
                  <pre className="changes-diff">
                    {suggestedChanges?.substring(suggestedChanges.length - 200)}
                  </pre>
                </div>
              </div>
            )}

            <div className="metanotes-examples">
              <small>Try asking:</small>
              <ul>
                <li onClick={() => setPrompt('Format this as a table')}>
                  "Format this as a table"
                </li>
                <li onClick={() => setPrompt('Add [[wiki links]] to character names')}>
                  "Add [[wiki links]] to character names"
                </li>
                <li onClick={() => setPrompt('Create a summary section')}>
                  "Create a summary section"
                </li>
                <li onClick={() => setPrompt('Fix spelling and grammar')}>
                  "Fix spelling and grammar"
                </li>
              </ul>
            </div>
          </>
        )}
      </div>

      <div className="metanotes-footer">
        <small>
          // TODO: Implement real LLM integration for MetaNotes
        </small>
      </div>
    </div>
  );
};