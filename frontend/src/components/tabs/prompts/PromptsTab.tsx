import React, { useState, useCallback, useEffect } from 'react';
import { api } from '../../../services/api';
import './PromptsTab.css';

interface FileItem {
  name: string;
  type: 'file' | 'folder';
  path: string;
  children?: FileItem[];
  isVirtual?: boolean;
  source?: 'filesystem' | 'imagegen';
  template?: ImageGenTemplate;
}

interface ColumnData {
  items: FileItem[];
  selectedPath: string | null;
  title: string;
}

interface ImageGenTemplate {
  id: string;
  name: string;
  category: string;
  description: string;
  base_prompt: string;
  style_suffix?: string;
  negative_prompt?: string;
}

const transformFileTree = (tree: any[]): FileItem[] => {
  return tree.map(item => ({
    name: item.name,
    type: item.type === 'directory' ? 'folder' : 'file',
    path: item.path,
    children: item.children ? transformFileTree(item.children) : undefined,
    source: 'filesystem',
  }));
};

const transformTemplatesToFiles = (templates: ImageGenTemplate[]): FileItem[] => {
  return templates.map(template => ({
    name: template.name,
    type: 'file',
    path: `imagegen://${template.id}`,
    source: 'imagegen',
    template,
  }));
};

export const PromptsTab: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [columns, setColumns] = useState<ColumnData[]>([]);
  const [selectedItem, setSelectedItem] = useState<FileItem | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<ImageGenTemplate | null>(null);
  const [fileContent, setFileContent] = useState<string>('');
  const [isEditing, setIsEditing] = useState(false);
  const [newFileName, setNewFileName] = useState('');
  const [newFileContent, setNewFileContent] = useState('');
  const [isEditingTemplate, setIsEditingTemplate] = useState(false);
  const [templateForm, setTemplateForm] = useState<Partial<ImageGenTemplate>>({});
  
  // Unified create modal state
  const [showUnifiedCreateModal, setShowUnifiedCreateModal] = useState(false);
  const [createType, setCreateType] = useState<'file' | 'template'>('file');
  const [createLocation, setCreateLocation] = useState<string>('');

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [treeData, templatesData] = await Promise.all([
        api.getFileTree('prompts'),
        api.getStyleTemplates()
      ]);
      
      const fileItems = transformFileTree(treeData);
      const templates = templatesData.templates || [];
      
      // Create root with two virtual folders
      const rootItems: FileItem[] = [
        {
          name: '📝 Generic Prompts',
          type: 'folder',
          path: '__generic__',
          children: fileItems,
          isVirtual: true,
          source: 'filesystem',
        },
        {
          name: '🎨 ImageGen Templates',
          type: 'folder',
          path: '__imagegen__',
          children: transformTemplatesToFiles(templates),
          isVirtual: true,
          source: 'imagegen',
        }
      ];
      
      setColumns([
        { items: rootItems, selectedPath: null, title: 'Prompt Library' },
        { items: [], selectedPath: null, title: '' },
        { items: [], selectedPath: null, title: '' }
      ]);
    } catch (err: any) {
      console.error('Failed to load prompts:', err);
      setError(err.message || 'Failed to load prompts');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleItemClick = useCallback(async (item: FileItem, columnIndex: number) => {
    setColumns(prev => {
      const newColumns = [...prev];
      newColumns[columnIndex] = {
        ...newColumns[columnIndex],
        selectedPath: item.path
      };

      // Handle folder navigation
      if (item.type === 'folder' && item.children && columnIndex < 2) {
        newColumns[columnIndex + 1] = {
          items: item.children,
          selectedPath: null,
          title: item.name.replace(/^[📝🎨] /, '')
        };
        for (let i = columnIndex + 2; i < 3; i++) {
          newColumns[i] = { items: [], selectedPath: null, title: '' };
        }
      } else if (item.type === 'folder' && columnIndex === 0) {
        // Root folder selected - populate second column
        newColumns[1] = {
          items: item.children || [],
          selectedPath: null,
          title: item.name.replace(/^[📝🎨] /, '')
        };
        newColumns[2] = { items: [], selectedPath: null, title: '' };
      }

      return newColumns;
    });

    // Handle file selection
    if (item.type === 'file') {
      setSelectedItem(item);
      
      if (item.source === 'imagegen' && item.template) {
        setSelectedTemplate(item.template);
        setIsEditing(false);
      } else if (item.source === 'filesystem') {
        try {
          const response = await api.readFile(item.path);
          setSelectedTemplate(null);
          setFileContent(response.content || '');
          setIsEditing(false);
        } catch (err: any) {
          console.error('Failed to load file:', err);
          setError('Failed to load file: ' + err.message);
        }
      }
    }
  }, []);

  const handleSaveFile = async () => {
    if (!selectedItem || selectedItem.source !== 'filesystem') return;
    
    try {
      await api.writeFile(selectedItem.path, fileContent);
      setIsEditing(false);
      setError(null);
    } catch (err: any) {
      console.error('Failed to save file:', err);
      setError('Failed to save: ' + err.message);
    }
  };

  const handleSaveTemplate = async () => {
    if (!selectedTemplate || !templateForm.name) return;
    
    try {
      await api.updateImagePrompt(selectedTemplate.id, {
        name: templateForm.name,
        category: templateForm.category || 'general',
        description: templateForm.description || '',
        base_prompt: templateForm.base_prompt || '',
        style_suffix: templateForm.style_suffix,
        negative_prompt: templateForm.negative_prompt,
      });
      
      setIsEditingTemplate(false);
      setError(null);
      await loadData();
    } catch (err: any) {
      console.error('Failed to save template:', err);
      setError('Failed to save template: ' + err.message);
    }
  };

  const handleCreateFile = async () => {
    if (!newFileName.trim()) return;
    
    let fileName = newFileName.trim();
    if (!fileName.endsWith('.md')) {
      fileName += '.md';
    }
    
    const fullPath = `prompts/${fileName}`;
    
    try {
      await api.writeFile(fullPath, newFileContent);
      setNewFileName('');
      setNewFileContent('');
      await loadData();
    } catch (err: any) {
      console.error('Failed to create file:', err);
      setError('Failed to create file: ' + err.message);
    }
  };

  const handleCreateTemplate = async () => {
    if (!templateForm.name || !templateForm.base_prompt) return;
    
    try {
      await api.createImagePrompt({
        name: templateForm.name,
        category: templateForm.category || 'general',
        description: templateForm.description || '',
        base_prompt: templateForm.base_prompt,
        style_suffix: templateForm.style_suffix,
        negative_prompt: templateForm.negative_prompt,
      });
      
      setTemplateForm({});
      await loadData();
    } catch (err: any) {
      console.error('Failed to create template:', err);
      setError('Failed to create template: ' + err.message);
    }
  };

  const handleDelete = async () => {
    if (!selectedItem) return;
    
    if (!confirm(`Delete "${selectedItem.name}"?`)) return;
    
    try {
      if (selectedItem.source === 'filesystem') {
        await api.deleteFile(selectedItem.path);
      } else if (selectedItem.source === 'imagegen' && selectedTemplate) {
        await api.deleteImagePrompt(selectedTemplate.id);
      }
      
      setSelectedItem(null);
      setSelectedTemplate(null);
      setFileContent('');
      await loadData();
    } catch (err: any) {
      console.error('Failed to delete:', err);
      setError('Failed to delete: ' + err.message);
    }
  };

  const startEditing = () => {
    if (selectedTemplate) {
      setTemplateForm({ ...selectedTemplate });
      setIsEditingTemplate(true);
    } else {
      setIsEditing(true);
    }
  };

  const getFileIcon = (item: FileItem) => {
    if (item.isVirtual) return item.path === '__imagegen__' ? '🎨' : '📝';
    if (item.type === 'folder') return '📁';
    if (item.source === 'imagegen') return '🖼️';
    if (item.name.endsWith('.md')) return '📝';
    return '📄';
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

  if (loading) {
    return (
      <div className="prompts-tab">
        <div className="prompts-loading">
          <div className="loading-spinner"></div>
          <p>Loading prompts...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="prompts-tab">
      <div className="prompts-toolbar">
        <div className="prompts-toolbar-left">
          <span className="prompts-toolbar-title">🎨 Prompt Library</span>
          <span className="prompts-toolbar-subtitle">
            {selectedItem ? selectedItem.name : 'Select a prompt to edit'}
          </span>
        </div>
        <div className="prompts-toolbar-right">
          <button className="prompts-toolbar-btn" onClick={() => setShowUnifiedCreateModal(true)}>
            + Create Prompt
          </button>
          <button className="prompts-toolbar-btn primary" onClick={loadData}>
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="prompts-error">
          {error}
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

      <div className="prompts-content">
        <div className="prompts-browser">
          <div className="miller-columns">
            {columns.filter((column, index) => index === 0 || column.items.length > 0).map((column, columnIndex, filteredColumns) => (
              <div 
                key={columnIndex} 
                className={`miller-column ${columnIndex < filteredColumns.length - 1 ? 'has-next' : ''}`}
              >
                <div className="miller-column-header">
                  <span className="column-title">{column.title}</span>
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
                    >
                      <span className="item-icon">{getFileIcon(item)}</span>
                      <span className="item-name">
                        {item.isVirtual ? item.name.replace(/^[📝🎨] /, '') : item.name}
                      </span>
                      {item.type === 'folder' && columnIndex < filteredColumns.length - 1 && (
                        <span className="item-arrow">›</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="prompts-editor">
          {selectedTemplate ? (
            <>
              <div className="editor-header">
                <h3>
                  {getCategoryIcon(selectedTemplate.category)} {selectedTemplate.name}
                  <span className="template-badge">ImageGen</span>
                </h3>
                <div className="editor-actions">
                  {isEditingTemplate ? (
                    <>
                      <button className="btn-secondary" onClick={() => setIsEditingTemplate(false)}>
                        Cancel
                      </button>
                      <button className="btn-primary" onClick={handleSaveTemplate}>
                        Save
                      </button>
                    </>
                  ) : (
                    <>
                      <button className="btn-danger" onClick={handleDelete}>
                        Delete
                      </button>
                      <button className="btn-primary" onClick={startEditing}>
                        Edit
                      </button>
                    </>
                  )}
                </div>
              </div>
              <div className="editor-content">
                {isEditingTemplate ? (
                  <div className="template-edit-form">
                    <div className="form-row">
                      <div className="form-field">
                        <label>Name</label>
                        <input
                          type="text"
                          value={templateForm.name || ''}
                          onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })}
                        />
                      </div>
                      <div className="form-field">
                        <label>Category</label>
                        <select
                          value={templateForm.category || 'characters'}
                          onChange={(e) => setTemplateForm({ ...templateForm, category: e.target.value })}
                        >
                          <option value="characters">Characters</option>
                          <option value="environments">Environments</option>
                          <option value="items">Items</option>
                          <option value="scenes">Scenes</option>
                          <option value="creatures">Creatures</option>
                          <option value="general">General</option>
                        </select>
                      </div>
                    </div>
                    <div className="form-field">
                      <label>Description</label>
                      <input
                        type="text"
                        value={templateForm.description || ''}
                        onChange={(e) => setTemplateForm({ ...templateForm, description: e.target.value })}
                      />
                    </div>
                    <div className="form-field">
                      <label>Base Prompt</label>
                      <textarea
                        value={templateForm.base_prompt || ''}
                        onChange={(e) => setTemplateForm({ ...templateForm, base_prompt: e.target.value })}
                        rows={4}
                        className="code-textarea"
                      />
                    </div>
                    <div className="form-field">
                      <label>Style Suffix (Optional)</label>
                      <textarea
                        value={templateForm.style_suffix || ''}
                        onChange={(e) => setTemplateForm({ ...templateForm, style_suffix: e.target.value })}
                        rows={2}
                        className="code-textarea"
                      />
                    </div>
                    <div className="form-field">
                      <label>Negative Prompt (Optional)</label>
                      <textarea
                        value={templateForm.negative_prompt || ''}
                        onChange={(e) => setTemplateForm({ ...templateForm, negative_prompt: e.target.value })}
                        rows={2}
                        className="code-textarea"
                      />
                    </div>
                  </div>
                ) : (
                  <div className="template-view">
                    <div className="template-field">
                      <label>Category</label>
                      <div className="template-value">
                        {getCategoryIcon(selectedTemplate.category)} {selectedTemplate.category}
                      </div>
                    </div>
                    <div className="template-field">
                      <label>Description</label>
                      <div className="template-value">{selectedTemplate.description}</div>
                    </div>
                    <div className="template-field">
                      <label>Base Prompt</label>
                      <div className="template-value code">{selectedTemplate.base_prompt}</div>
                    </div>
                    {selectedTemplate.style_suffix && (
                      <div className="template-field">
                        <label>Style Suffix</label>
                        <div className="template-value code">{selectedTemplate.style_suffix}</div>
                      </div>
                    )}
                    {selectedTemplate.negative_prompt && (
                      <div className="template-field">
                        <label>Negative Prompt</label>
                        <div className="template-value code negative">{selectedTemplate.negative_prompt}</div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          ) : selectedItem && selectedItem.source === 'filesystem' ? (
            <>
              <div className="editor-header">
                <h3>📝 {selectedItem.name}</h3>
                <div className="editor-actions">
                  {isEditing ? (
                    <>
                      <button className="btn-secondary" onClick={() => setIsEditing(false)}>
                        Cancel
                      </button>
                      <button className="btn-primary" onClick={handleSaveFile}>
                        Save
                      </button>
                    </>
                  ) : (
                    <>
                      <button className="btn-danger" onClick={handleDelete}>
                        Delete
                      </button>
                      <button className="btn-primary" onClick={startEditing}>
                        Edit
                      </button>
                    </>
                  )}
                </div>
              </div>
              <div className="editor-content">
                {isEditing ? (
                  <textarea
                    className="editor-textarea"
                    value={fileContent}
                    onChange={(e) => setFileContent(e.target.value)}
                    spellCheck={false}
                  />
                ) : (
                  <div className="editor-preview">
                    <pre>{fileContent}</pre>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="editor-empty">
              <span className="empty-icon">🎨</span>
              <h3>No Prompt Selected</h3>
              <p>Select a file from the browser to view or edit it</p>
            </div>
          )}
        </div>
      </div>

      {/* Unified Create Prompt Modal */}
      {showUnifiedCreateModal && (
        <div className="modal-overlay" onClick={() => setShowUnifiedCreateModal(false)}>
          <div className="create-modal unified-modal" onClick={(e) => e.stopPropagation()}>
            <h3>Create New Prompt</h3>
            
            {/* Step 1: Choose Type */}
            <div className="form-field">
              <label>Prompt Type</label>
              <div className="type-selector">
                <button 
                  className={`type-option ${createType === 'file' ? 'active' : ''}`}
                  onClick={() => setCreateType('file')}
                >
                  <span className="type-icon">📝</span>
                  <span className="type-label">Generic Prompt</span>
                  <span className="type-desc">Free-form text file for any purpose</span>
                </button>
                <button 
                  className={`type-option ${createType === 'template' ? 'active' : ''}`}
                  onClick={() => setCreateType('template')}
                >
                  <span className="type-icon">🎨</span>
                  <span className="type-label">ImaGen Template</span>
                  <span className="type-desc">Structured template for image generation</span>
                </button>
              </div>
            </div>
            
            {/* Step 2: Location (for file type) */}
            {createType === 'file' && (
              <>
                <div className="form-field">
                  <label>Location</label>
                  <select 
                    value={createLocation} 
                    onChange={(e) => setCreateLocation(e.target.value)}
                  >
                    <option value="">prompts/ (root)</option>
                    {columns[0]?.items
                      .filter(item => item.type === 'folder' && item.path !== '__imagegen__')
                      .map(folder => (
                        <option key={folder.path} value={folder.path}>
                          {folder.path.replace('__generic__', 'Generic Prompts')}
                        </option>
                      ))}
                  </select>
                </div>
                <div className="form-field">
                  <label>File Name</label>
                  <input
                    type="text"
                    value={newFileName}
                    onChange={(e) => setNewFileName(e.target.value)}
                    placeholder="my-prompt.md"
                    autoFocus
                  />
                </div>
                <div className="form-field">
                  <label>Content</label>
                  <textarea
                    value={newFileContent}
                    onChange={(e) => setNewFileContent(e.target.value)}
                    placeholder="Enter your prompt text here..."
                    rows={6}
                    className="modal-textarea"
                  />
                </div>
              </>
            )}
            
            {/* Step 2: Template Fields (for template type) */}
            {createType === 'template' && (
              <>
                <div className="form-row">
                  <div className="form-field">
                    <label>Name *</label>
                    <input
                      type="text"
                      value={templateForm.name || ''}
                      onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })}
                      placeholder="Template name"
                      autoFocus
                    />
                  </div>
                  <div className="form-field">
                    <label>Category</label>
                    <select
                      value={templateForm.category || 'characters'}
                      onChange={(e) => setTemplateForm({ ...templateForm, category: e.target.value })}
                    >
                      <option value="characters">Characters</option>
                      <option value="environments">Environments</option>
                      <option value="items">Items</option>
                      <option value="scenes">Scenes</option>
                      <option value="creatures">Creatures</option>
                      <option value="general">General</option>
                    </select>
                  </div>
                </div>
                <div className="form-field">
                  <label>Description</label>
                  <input
                    type="text"
                    value={templateForm.description || ''}
                    onChange={(e) => setTemplateForm({ ...templateForm, description: e.target.value })}
                    placeholder="Brief description of this template"
                  />
                </div>
                <div className="form-field">
                  <label>Base Prompt *</label>
                  <textarea
                    value={templateForm.base_prompt || ''}
                    onChange={(e) => setTemplateForm({ ...templateForm, base_prompt: e.target.value })}
                    placeholder="The main prompt that will be used..."
                    rows={4}
                    className="code-textarea"
                  />
                </div>
                <div className="form-field">
                  <label>Style Suffix (Optional)</label>
                  <textarea
                    value={templateForm.style_suffix || ''}
                    onChange={(e) => setTemplateForm({ ...templateForm, style_suffix: e.target.value })}
                    placeholder="Additional style elements appended to the prompt..."
                    rows={2}
                    className="code-textarea"
                  />
                </div>
                <div className="form-field">
                  <label>Negative Prompt (Optional)</label>
                  <textarea
                    value={templateForm.negative_prompt || ''}
                    onChange={(e) => setTemplateForm({ ...templateForm, negative_prompt: e.target.value })}
                    placeholder="Things to avoid in generated images..."
                    rows={2}
                    className="code-textarea"
                  />
                </div>
              </>
            )}
            
            <div className="modal-actions">
              <button 
                className="btn-primary" 
                onClick={() => {
                  if (createType === 'file') {
                    handleCreateFile();
                  } else {
                    handleCreateTemplate();
                  }
                  setShowUnifiedCreateModal(false);
                }}
                disabled={createType === 'file' ? !newFileName.trim() : !templateForm.name || !templateForm.base_prompt}
              >
                Create {createType === 'file' ? 'File' : 'Template'}
              </button>
              <button className="btn-secondary" onClick={() => setShowUnifiedCreateModal(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
