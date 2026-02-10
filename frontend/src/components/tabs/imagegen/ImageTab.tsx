import React, { useState, useEffect } from 'react';
import { api } from '../../../services/api';
import './ImageTab.css';

interface PromptTemplate {
  id: string;
  name: string;
  category: string;
  base_prompt: string;
  style_suffix?: string;
}

interface GalleryImage {
  id: string;
  image_data?: string;
  image_path: string;
  thumbnail_url?: string;
  prompt: string;
  revised_prompt?: string;
  tokens_used: number;
  timestamp: string;
}

export const ImageTab: React.FC = () => {
  // Prompt selection
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [selectedPrompt, setSelectedPrompt] = useState<PromptTemplate | null>(null);
  const [sceneDescription, setSceneDescription] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  
  // Generation
  const [isGenerating, setIsGenerating] = useState(false);
  const [galleryImages, setGalleryImages] = useState<GalleryImage[]>([]);
  const [selectedImage, setSelectedImage] = useState<GalleryImage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadPrompts();
    loadGallery();
  }, []);

  const loadPrompts = async () => {
    try {
      const response = await api.getStyleTemplates();
      setPrompts(response.templates || []);
    } catch (err) {
      console.error('Failed to load prompts:', err);
    }
  };

  const loadGallery = async () => {
    try {
      const response = await api.getImageGallery(50);
      setGalleryImages(response.images || []);
    } catch (err) {
      console.error('Failed to load gallery:', err);
    }
  };

  const buildFullPrompt = () => {
    if (!selectedPrompt) return sceneDescription;
    const parts = [selectedPrompt.base_prompt];
    if (sceneDescription) parts.push(sceneDescription);
    if (selectedPrompt.style_suffix) parts.push(selectedPrompt.style_suffix);
    return parts.join(' ');
  };

  const handleGenerate = async () => {
    const fullPrompt = buildFullPrompt();
    if (!fullPrompt.trim()) {
      setError('Select a style and describe your scene');
      return;
    }

    setIsGenerating(true);
    setError(null);

    try {
      const result = await api.generateImage({
        prompt: fullPrompt,
        style_template_id: selectedPrompt?.id || undefined,
      });

      if (result.success) {
        const newImage: GalleryImage = {
          id: Date.now().toString(),
          image_data: result.image_data,
          image_path: result.image_path,
          prompt: fullPrompt,
          revised_prompt: result.revised_prompt,
          tokens_used: result.tokens_used,
          timestamp: new Date().toISOString(),
        };
        setGalleryImages(prev => [newImage, ...prev]);
        setSelectedImage(newImage);
      } else {
        setError(result.error || 'Generation failed');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to generate');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownload = (image: GalleryImage) => {
    if (image.image_data) {
      // Download from base64
      const link = document.createElement('a');
      link.href = `data:image/png;base64,${image.image_data}`;
      link.download = `megabook_${Date.now()}.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } else if (image.thumbnail_url) {
      // Download from URL
      const link = document.createElement('a');
      link.href = `http://localhost:8000${image.thumbnail_url}`;
      link.download = `megabook_${Date.now()}.png`;
      link.target = '_blank';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  const promptsByCategory = prompts.reduce((acc, prompt) => {
    if (!acc[prompt.category]) acc[prompt.category] = [];
    acc[prompt.category].push(prompt);
    return acc;
  }, {} as Record<string, PromptTemplate[]>);

  return (
    <div className="image-tab-v2">
      {/* SLEEK TOP BAR */}
      <div className="top-bar">
        <div className="prompt-dropdown">
          <button 
            className="dropdown-trigger"
            onClick={() => setShowDropdown(!showDropdown)}
          >
            {selectedPrompt ? selectedPrompt.name : 'Select Style'}
            <span className="arrow">{showDropdown ? '^' : 'v'}</span>
          </button>
          
          {showDropdown && (
            <div className="dropdown-menu">
              <div className="dropdown-item" onClick={() => { setSelectedPrompt(null); setShowDropdown(false); }}>
                Custom (No Style)
              </div>
              {Object.entries(promptsByCategory).map(([category, items]) => (
                <div key={category}>
                  <div className="dropdown-category">{category}</div>
                  {items.map(p => (
                    <div 
                      key={p.id}
                      className={`dropdown-item ${selectedPrompt?.id === p.id ? 'active' : ''}`}
                      onClick={() => { setSelectedPrompt(p); setShowDropdown(false); }}
                    >
                      {p.name}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>

        <input
          type="text"
          className="scene-input"
          value={sceneDescription}
          onChange={(e) => setSceneDescription(e.target.value)}
          placeholder="Describe your scene..."
          onKeyDown={(e) => e.key === 'Enter' && !isGenerating && handleGenerate()}
        />

        <button 
          className="generate-btn"
          onClick={handleGenerate}
          disabled={isGenerating}
        >
          {isGenerating ? '...' : 'Generate'}
        </button>
      </div>

      {error && (
        <div className="error-toast">
          {error}
          <button onClick={() => setError(null)}>X</button>
        </div>
      )}

      {/* GALLERY */}
      <div className="gallery-section">
        <div className="gallery-grid">
          {galleryImages.length === 0 ? (
            <div className="empty-gallery">
              <p>No images generated yet</p>
              <p className="hint">Select a style, describe your scene, and click Generate</p>
            </div>
          ) : (
              galleryImages.map((image) => (
              <div 
                key={image.id}
                className="gallery-thumb"
                onClick={() => setSelectedImage(image)}
              >
                {image.image_data ? (
                  <img src={`data:image/png;base64,${image.image_data}`} alt="" />
                ) : image.thumbnail_url ? (
                  <img src={`http://localhost:8000${image.thumbnail_url}`} alt="" />
                ) : (
                  <div className="placeholder">IMG</div>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* IMAGE MODAL */}
      {selectedImage && (
        <div className="image-modal" onClick={() => setSelectedImage(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="close-btn" onClick={() => setSelectedImage(null)}>X</button>
            {selectedImage.image_data ? (
              <img src={`data:image/png;base64,${selectedImage.image_data}`} alt="" />
            ) : selectedImage.thumbnail_url ? (
              <img src={`http://localhost:8000${selectedImage.thumbnail_url}`} alt="" />
            ) : null}
            <div className="modal-info">
              <p className="prompt">{selectedImage.prompt}</p>
              <button onClick={() => handleDownload(selectedImage)}>Download</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
