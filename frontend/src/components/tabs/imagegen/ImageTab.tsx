import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../../services/api';
import './ImageTab.css';

// Types
interface StyleTemplate {
  id: string;
  name: string;
  category: string;
  description: string;
  base_prompt: string;
  style_suffix?: string;
  negative_prompt?: string;
}

interface TokenCount {
  total_tokens: number;
  formatted_total: string;
  max_tokens: number;
  percentage: number;
  breakdown: Record<string, number>;
}

interface GeneratedImage {
  image_data: string;
  image_path: string;
  revised_prompt: string;
  tokens_used: number;
  timestamp: string;
  prompt: string;
}

interface ImageHistoryItem {
  image_path: string;
  prompt: string;
  revised_prompt: string;
  tokens_used: number;
  timestamp: string;
}

interface NewPromptForm {
  name: string;
  category: string;
  description: string;
  base_prompt: string;
  style_suffix: string;
  negative_prompt: string;
}

export const ImageTab: React.FC = () => {
  // State
  const [styleTemplates, setStyleTemplates] = useState<StyleTemplate[]>([]);
  const [selectedStyle, setSelectedStyle] = useState<string>('');
  const [contextFiles, setContextFiles] = useState<string[]>([]);
  const [tokenCount, setTokenCount] = useState<TokenCount>({
    total_tokens: 0,
    formatted_total: '0',
    max_tokens: 600000,
    percentage: 0,
    breakdown: {},
  });
  const [prompt, setPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedImage, setGeneratedImage] = useState<GeneratedImage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showContextModal, setShowContextModal] = useState(false);
  const [availableNotes, setAvailableNotes] = useState<string[]>([]);
  const [imageHistory, setImageHistory] = useState<ImageHistoryItem[]>([]);
  const [showHistory, setShowHistory] = useState(true);
  const [selectedHistoryItem, setSelectedHistoryItem] = useState<ImageHistoryItem | null>(null);
  
  // New prompt creation state
  const [showCreatePrompt, setShowCreatePrompt] = useState(false);
  const [newPromptForm, setNewPromptForm] = useState<NewPromptForm>({
    name: '',
    category: 'characters',
    description: '',
    base_prompt: '',
    style_suffix: '',
    negative_prompt: '',
  });

  // Load data on mount
  useEffect(() => {
    loadStyleTemplates();
    loadAvailableNotes();
    loadImageHistory();
  }, []);

  // Update token count when context files change
  useEffect(() => {
    if (contextFiles.length > 0) {
      updateTokenCount();
    } else {
      setTokenCount({
        total_tokens: 0,
        formatted_total: '0',
        max_tokens: 600000,
        percentage: 0,
        breakdown: {},
      });
    }
  }, [contextFiles]);

  const loadStyleTemplates = async () => {
    try {
      const response = await api.getStyleTemplates();
      setStyleTemplates(response.templates || []);
    } catch (err) {
      console.error('Failed to load style templates:', err);
    }
  };

  const loadAvailableNotes = async () => {
    try {
      const files = await api.listFiles('notes');
      const notePaths = files.map((f: any) => f.relative_path);
      setAvailableNotes(notePaths);
    } catch (err) {
      console.error('Failed to load notes:', err);
    }
  };

  const loadImageHistory = async () => {
    try {
      const response = await api.getImageHistory(20);
      setImageHistory(response.history || []);
    } catch (err) {
      console.error('Failed to load image history:', err);
    }
  };

  const updateTokenCount = async () => {
    if (contextFiles.length === 0) return;
    
    try {
      const result = await api.countImageTokens(contextFiles);
      setTokenCount(result);
    } catch (err) {
      console.error('Failed to count tokens:', err);
    }
  };

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      setError('Please enter a prompt');
      return;
    }

    setIsGenerating(true);
    setError(null);
    setSelectedHistoryItem(null);

    try {
      const result = await api.generateImage({
        prompt: prompt.trim(),
        context_files: contextFiles,
        style_template_id: selectedStyle || undefined,
      });

      if (result.success) {
        const newImage: GeneratedImage = {
          image_data: result.image_data,
          image_path: result.image_path,
          revised_prompt: result.revised_prompt,
          tokens_used: result.tokens_used,
          timestamp: new Date().toISOString(),
          prompt: prompt.trim(),
        };
        setGeneratedImage(newImage);
        loadImageHistory();
      } else {
        setError(result.error || 'Generation failed');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to generate image');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownload = useCallback(() => {
    const imageToDownload = selectedHistoryItem || generatedImage;
    if (!imageToDownload) return;

    let imageData: string;
    let filename: string;

    if ('image_data' in imageToDownload && imageToDownload.image_data) {
      imageData = imageToDownload.image_data;
      filename = `megabook_${Date.now()}.png`;
    } else if ('image_path' in imageToDownload && imageToDownload.image_path) {
      filename = imageToDownload.image_path.split('/').pop() || 'image.png';
      const link = document.createElement('a');
      link.href = `/api/filesystem/download/${encodeURIComponent(imageToDownload.image_path)}`;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      return;
    } else {
      return;
    }

    const link = document.createElement('a');
    link.href = `data:image/png;base64,${imageData}`;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [generatedImage, selectedHistoryItem]);

  const handleHistoryItemClick = (item: ImageHistoryItem) => {
    setSelectedHistoryItem(item);
    setGeneratedImage(null);
    loadHistoryImage(item.image_path);
  };

  const loadHistoryImage = async (imagePath: string) => {
    try {
      const response = await fetch(`/api/filesystem/download/${encodeURIComponent(imagePath)}`);
      if (response.ok) {
        const blob = await response.blob();
        const reader = new FileReader();
        reader.onloadend = () => {
          const base64data = reader.result as string;
          const base64 = base64data.split(',')[1];
          setGeneratedImage({
            image_data: base64,
            image_path: imagePath,
            revised_prompt: selectedHistoryItem?.revised_prompt || '',
            tokens_used: selectedHistoryItem?.tokens_used || 0,
            timestamp: selectedHistoryItem?.timestamp || '',
            prompt: selectedHistoryItem?.prompt || '',
          });
        };
        reader.readAsDataURL(blob);
      }
    } catch (err) {
      console.error('Failed to load history image:', err);
    }
  };

  const handleSavePrompt = async () => {
    if (!newPromptForm.name.trim() || !newPromptForm.base_prompt.trim()) {
      setError('Name and base prompt are required');
      return;
    }

    try {
      await api.createImagePrompt(newPromptForm);
      setShowCreatePrompt(false);
      setNewPromptForm({
        name: '',
        category: 'characters',
        description: '',
        base_prompt: '',
        style_suffix: '',
        negative_prompt: '',
      });
      loadStyleTemplates();
    } catch (err: any) {
      setError(err.message || 'Failed to save prompt');
    }
  };

  const handleDeletePrompt = async (promptId: string) => {
    if (!confirm('Are you sure you want to delete this prompt?')) return;
    
    try {
      await api.deleteImagePrompt(promptId);
      loadStyleTemplates();
      if (selectedStyle === promptId) {
        setSelectedStyle('');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to delete prompt');
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const toggleContextFile = (path: string) => {
    setContextFiles(prev => 
      prev.includes(path) 
        ? prev.filter(p => p !== path)
        : [...prev, path]
    );
  };

  const removeContextFile = (path: string) => {
    setContextFiles(prev => prev.filter(p => p !== path));
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'characters': return '👤';
      case 'environments': return '🏞️';
      case 'items': return '⚔️';
      case 'scenes': return '🎬';
      case 'creatures': return '🐉';
      default: return '🎨';
    }
  };

  const clearCurrentImage = () => {
    setGeneratedImage(null);
    setSelectedHistoryItem(null);
  };

  const selectedTemplate = styleTemplates.find(s => s.id === selectedStyle);

  return (
    <div className="image-tab">
      {/* Left Sidebar - Prompts */}
      <div className="styles-sidebar">
        <div className="sidebar-header-row">
          <h3>🎨 Prompts</h3>
          <button 
            className="create-prompt-btn"
            onClick={() => setShowCreatePrompt(true)}
            title="Create new prompt"
          >
            +
          </button>
        </div>
        <div className="styles-list">
          {styleTemplates.map(template => (
            <div key={template.id} className="style-item-wrapper">
              <button
                className={`style-item ${selectedStyle === template.id ? 'active' : ''}`}
                onClick={() => setSelectedStyle(selectedStyle === template.id ? '' : template.id)}
              >
                <span className="style-icon">{getCategoryIcon(template.category)}</span>
                <div className="style-info">
                  <span className="style-name">{template.name}</span>
                  <span className="style-category">{template.category}</span>
                </div>
              </button>
              <div className="style-actions">
                {!['character-portrait-realistic', 'character-portrait-painted', 'character-fullbody', 
                   'fantasy-landscape', 'dungeon-interior', 'item-artifact', 'battle-scene',
                   'settlement-city', 'monster-creature', 'atmospheric-scene'].includes(template.id) && (
                  <button 
                    className="delete-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeletePrompt(template.id);
                    }}
                    title="Delete prompt"
                  >
                    🗑️
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="main-content">
        {/* Prompt Section */}
        <div className="prompt-section">
          {selectedTemplate && (
            <div className="selected-style-badge">
              {getCategoryIcon(selectedTemplate.category)}{' '}
              {selectedTemplate.name}
              <button onClick={() => setSelectedStyle('')}>✕</button>
            </div>
          )}
          
          {/* Selected Prompt Details */}
          {selectedTemplate && (
            <div className="selected-prompt-details">
              <div className="prompt-detail-field">
                <label>Base Prompt:</label>
                <div className="prompt-detail-text">{selectedTemplate.base_prompt}</div>
              </div>
              {selectedTemplate.style_suffix && (
                <div className="prompt-detail-field">
                  <label>Style Suffix:</label>
                  <div className="prompt-detail-text">{selectedTemplate.style_suffix}</div>
                </div>
              )}
              {selectedTemplate.negative_prompt && (
                <div className="prompt-detail-field">
                  <label>Negative Prompt:</label>
                  <div className="prompt-detail-text negative">{selectedTemplate.negative_prompt}</div>
                </div>
              )}
              {selectedTemplate.description && (
                <div className="prompt-detail-field">
                  <label>Description:</label>
                  <div className="prompt-detail-description">{selectedTemplate.description}</div>
                </div>
              )}
            </div>
          )}
          
          <textarea
            className="prompt-input"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe the image you want to generate..."
            rows={4}
          />

          {/* Token Counter */}
          <div className="token-counter">
            <span className="token-count">
              {tokenCount.formatted_total}/{tokenCount.max_tokens / 1000}k tokens
            </span>
            <div className="token-bar">
              <div 
                className="token-bar-fill" 
                style={{ width: `${Math.min(tokenCount.percentage, 100)}%` }}
              />
            </div>
          </div>

          {/* Generate Button */}
          <button 
            className="generate-btn"
            onClick={handleGenerate}
            disabled={isGenerating || !prompt.trim()}
          >
            {isGenerating ? '🎨 Generating...' : '🎨 Generate Image'}
          </button>

          {error && (
            <div className="error-message">
              ⚠️ {error}
            </div>
          )}
        </div>

        {/* Image Preview */}
        {(generatedImage || isGenerating || selectedHistoryItem) && (
          <div className="image-preview-section">
            {isGenerating ? (
              <div className="generating-spinner">
                <div className="spinner"></div>
                <p>Consulting the AI artist...</p>
              </div>
            ) : generatedImage ? (
              <>
                <div className="image-container">
                  <img 
                    src={`data:image/png;base64,${generatedImage.image_data}`}
                    alt="Generated"
                    className="generated-image"
                  />
                </div>
                <div className="image-meta">
                  <p><strong>Tokens used:</strong> {generatedImage.tokens_used}</p>
                  {generatedImage.revised_prompt && (
                    <p><strong>Revised prompt:</strong> {generatedImage.revised_prompt}</p>
                  )}
                </div>
                <div className="image-actions">
                  <button onClick={handleDownload} title="Download image">
                    💾 Download
                  </button>
                  <button onClick={() => handleGenerate()} title="Regenerate with same settings">
                    🔄 Regenerate
                  </button>
                  <button onClick={clearCurrentImage} title="Clear image">
                    🗑️ Clear
                  </button>
                </div>
              </>
            ) : selectedHistoryItem ? (
              <div className="generating-spinner">
                <div className="spinner"></div>
                <p>Loading image...</p>
              </div>
            ) : null}
          </div>
        )}
      </div>

      {/* Right Sidebar - Context & History */}
      <div className="context-sidebar">
        {/* Context Section */}
        <div className="context-section">
          <h3>📄 Context</h3>
          
          <button 
            className="add-context-btn"
            onClick={() => setShowContextModal(true)}
          >
            + Add Notes
          </button>

          {/* Selected Files */}
          {contextFiles.length > 0 && (
            <div className="selected-files">
              <h4>Selected ({contextFiles.length})</h4>
              {contextFiles.map(path => (
                <div key={path} className="selected-file">
                  <span className="file-name">{path.split('/').pop()}</span>
                  <button onClick={() => removeContextFile(path)}>✕</button>
                </div>
              ))}
            </div>
          )}

          {/* Token Summary */}
          {contextFiles.length > 0 && (
            <div className="token-summary">
              <span>{tokenCount.formatted_total} tokens</span>
            </div>
          )}
        </div>

        {/* History Section */}
        <div className="history-section">
          <h3 onClick={() => setShowHistory(!showHistory)} style={{ cursor: 'pointer' }}>
            📸 History {showHistory ? '▼' : '▶'}
          </h3>
          
          {showHistory && (
            <div className="history-list">
              {imageHistory.length === 0 ? (
                <p className="no-history">No images generated yet</p>
              ) : (
                imageHistory.map((item, index) => (
                  <div 
                    key={index}
                    className={`history-item ${selectedHistoryItem?.image_path === item.image_path ? 'active' : ''}`}
                    onClick={() => handleHistoryItemClick(item)}
                  >
                    <div className="history-thumb">
                      <span>🖼️</span>
                    </div>
                    <div className="history-info">
                      <span className="history-prompt" title={item.prompt}>
                        {item.prompt.substring(0, 30)}{item.prompt.length > 30 ? '...' : ''}
                      </span>
                      <span className="history-time">{formatTimestamp(item.timestamp)}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* Context Selection Modal */}
      {showContextModal && (
        <div className="modal-overlay" onClick={() => setShowContextModal(false)}>
          <div className="context-modal" onClick={(e) => e.stopPropagation()}>
            <h3>Select Notes for Context</h3>
            <div className="context-file-list">
              {availableNotes.map(path => (
                <label key={path} className="context-file-item">
                  <input
                    type="checkbox"
                    checked={contextFiles.includes(path)}
                    onChange={() => toggleContextFile(path)}
                  />
                  <span>{path}</span>
                </label>
              ))}
            </div>
            <div className="modal-actions">
              <button onClick={() => setShowContextModal(false)}>Done</button>
            </div>
          </div>
        </div>
      )}

      {/* Create New Prompt Modal */}
      {showCreatePrompt && (
        <div className="modal-overlay" onClick={() => setShowCreatePrompt(false)}>
          <div className="create-prompt-modal" onClick={(e) => e.stopPropagation()}>
            <h3>✨ Create New Prompt</h3>
            <div className="create-prompt-form">
              <div className="form-field">
                <label>Name *</label>
                <input
                  type="text"
                  value={newPromptForm.name}
                  onChange={(e) => setNewPromptForm({...newPromptForm, name: e.target.value})}
                  placeholder="e.g., Epic Dragon Portrait"
                />
              </div>
              <div className="form-field">
                <label>Category *</label>
                <select
                  value={newPromptForm.category}
                  onChange={(e) => setNewPromptForm({...newPromptForm, category: e.target.value})}
                >
                  <option value="characters">Characters</option>
                  <option value="environments">Environments</option>
                  <option value="items">Items</option>
                  <option value="scenes">Scenes</option>
                  <option value="creatures">Creatures</option>
                </select>
              </div>
              <div className="form-field">
                <label>Description</label>
                <input
                  type="text"
                  value={newPromptForm.description}
                  onChange={(e) => setNewPromptForm({...newPromptForm, description: e.target.value})}
                  placeholder="Brief description of this style"
                />
              </div>
              <div className="form-field">
                <label>Base Prompt *</label>
                <textarea
                  value={newPromptForm.base_prompt}
                  onChange={(e) => setNewPromptForm({...newPromptForm, base_prompt: e.target.value})}
                  placeholder="The main style prompt that will be prepended to user input..."
                  rows={3}
                />
              </div>
              <div className="form-field">
                <label>Style Suffix (Optional)</label>
                <textarea
                  value={newPromptForm.style_suffix}
                  onChange={(e) => setNewPromptForm({...newPromptForm, style_suffix: e.target.value})}
                  placeholder="Additional style elements appended to the end..."
                  rows={2}
                />
              </div>
              <div className="form-field">
                <label>Negative Prompt (Optional)</label>
                <textarea
                  value={newPromptForm.negative_prompt}
                  onChange={(e) => setNewPromptForm({...newPromptForm, negative_prompt: e.target.value})}
                  placeholder="Things to avoid in the generated image..."
                  rows={2}
                />
              </div>
            </div>
            <div className="modal-actions">
              <button onClick={handleSavePrompt}>Save Prompt</button>
              <button onClick={() => setShowCreatePrompt(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
