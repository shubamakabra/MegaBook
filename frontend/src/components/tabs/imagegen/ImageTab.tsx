import React, { useState, useEffect, useCallback } from 'react';
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
  image_path?: string;
  thumbnail_url?: string;
  prompt: string;
  revised_prompt?: string;
  tokens_used?: number;
  timestamp: string;
  status: 'loading' | 'success' | 'error';
  error?: string;
}

export const ImageTab: React.FC = () => {
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [selectedPrompt, setSelectedPrompt] = useState<PromptTemplate | null>(null);
  const [sceneDescription, setSceneDescription] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  
  const [galleryImages, setGalleryImages] = useState<GalleryImage[]>([]);
  const [selectedImageIndex, setSelectedImageIndex] = useState<number | null>(null);
  const [activeJobs, setActiveJobs] = useState<number>(0);

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
      const images = (response.images || []).map((img: any) => ({
        ...img,
        status: 'success' as const,
      }));
      setGalleryImages(images);
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
    if (!fullPrompt.trim()) return;

    // Create a loading preview immediately
    const jobId = Date.now().toString();
    const loadingImage: GalleryImage = {
      id: jobId,
      prompt: fullPrompt,
      timestamp: new Date().toISOString(),
      status: 'loading',
    };
    
    setGalleryImages(prev => [loadingImage, ...prev]);
    setActiveJobs(prev => prev + 1);

    // Start generation in background
    try {
      const result = await api.generateImage({
        prompt: fullPrompt,
        context_files: [],
        style_template_id: selectedPrompt?.id || undefined,
      });

      setGalleryImages(prev => prev.map(img => {
        if (img.id === jobId) {
          if (result.success) {
            return {
              ...img,
              image_data: result.image_data,
              image_path: result.image_path,
              revised_prompt: result.revised_prompt,
              tokens_used: result.tokens_used,
              status: 'success',
            };
          } else {
            return {
              ...img,
              status: 'error',
              error: result.error || 'Generation failed',
            };
          }
        }
        return img;
      }));
    } catch (err: any) {
      setGalleryImages(prev => prev.map(img => {
        if (img.id === jobId) {
          return {
            ...img,
            status: 'error',
            error: err.message || 'Failed to generate',
          };
        }
        return img;
      }));
    } finally {
      setActiveJobs(prev => prev - 1);
    }
  };

  const handleDownload = (image: GalleryImage) => {
    if (image.image_data) {
      const link = document.createElement('a');
      link.href = `data:image/png;base64,${image.image_data}`;
      link.download = `megabook_${Date.now()}.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } else if (image.thumbnail_url) {
      const link = document.createElement('a');
      link.href = `http://localhost:8000${image.thumbnail_url}`;
      link.download = `megabook_${Date.now()}.png`;
      link.target = '_blank';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  // Open image modal by index
  const openImageModal = (index: number) => {
    setSelectedImageIndex(index);
  };

  // Close modal
  const closeModal = () => {
    setSelectedImageIndex(null);
  };

  // Navigate to next image (RIGHT arrow = increment index)
  const goToNextImage = useCallback(() => {
    if (selectedImageIndex === null || galleryImages.length <= 1) return;
    // Right arrow = next = increment index
    const newIndex = (selectedImageIndex + 1) % galleryImages.length;
    setSelectedImageIndex(newIndex);
  }, [selectedImageIndex, galleryImages.length]);

  // Navigate to previous image (LEFT arrow = decrement index)
  const goToPrevImage = useCallback(() => {
    if (selectedImageIndex === null || galleryImages.length <= 1) return;
    // Left arrow = previous = decrement index
    const newIndex = (selectedImageIndex - 1 + galleryImages.length) % galleryImages.length;
    setSelectedImageIndex(newIndex);
  }, [selectedImageIndex, galleryImages.length]);

  // Keyboard navigation
  useEffect(() => {
    if (selectedImageIndex === null) return;
    
    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'Escape':
          closeModal();
          break;
        case 'ArrowRight':
          e.preventDefault();
          goToNextImage();
          break;
        case 'ArrowLeft':
          e.preventDefault();
          goToPrevImage();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedImageIndex, goToNextImage, goToPrevImage]);

  const promptsByCategory = prompts.reduce((acc, prompt) => {
    if (!acc[prompt.category]) acc[prompt.category] = [];
    acc[prompt.category].push(prompt);
    return acc;
  }, {} as Record<string, PromptTemplate[]>);

  // Get currently selected image
  const selectedImage = selectedImageIndex !== null ? galleryImages[selectedImageIndex] : null;

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
          onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
        />

        <button 
          className="generate-btn"
          onClick={handleGenerate}
        >
          {activeJobs > 0 ? `${activeJobs} generating...` : 'Generate'}
        </button>
      </div>

      {/* GALLERY */}
      <div className="gallery-section">
        <div className="gallery-grid">
          {galleryImages.length === 0 ? (
            <div className="empty-gallery">
              <p>No images generated yet</p>
              <p className="hint">Select a style, describe your scene, and click Generate</p>
            </div>
          ) : (
            galleryImages.map((image, index) => (
              <div 
                key={image.id}
                className={`gallery-thumb ${image.status}`}
                onClick={() => openImageModal(index)}
              >
                <div className="image-number">{index + 1}</div>
                {image.status === 'loading' && (
                  <div className="loading-overlay">
                    <div className="spinner"></div>
                    <span>Generating...</span>
                  </div>
                )}
                {image.status === 'error' && (
                  <div className="error-overlay">
                    <span className="error-icon">⚠️</span>
                    <span>Failed</span>
                  </div>
                )}
                {image.status === 'success' && image.image_data && (
                  <img src={`data:image/png;base64,${image.image_data}`} alt="" />
                )}
                {image.status === 'success' && image.thumbnail_url && (
                  <img src={`http://localhost:8000${image.thumbnail_url}`} alt="" />
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* IMAGE MODAL */}
      {selectedImage && selectedImageIndex !== null && (
        <div className="image-modal" onClick={closeModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            {/* Navigation arrows */}
            {galleryImages.length > 1 && (
              <>
                <button 
                  className="nav-arrow nav-prev" 
                  onClick={(e) => { e.stopPropagation(); goToPrevImage(); }}
                  title="Previous image (←)"
                >
                  ‹
                </button>
                <button 
                  className="nav-arrow nav-next" 
                  onClick={(e) => { e.stopPropagation(); goToNextImage(); }}
                  title="Next image (→)"
                >
                  ›
                </button>
              </>
            )}
            
            <button className="close-btn" onClick={closeModal} title="Close (Esc)">×</button>
            
            {/* Image counter */}
            {galleryImages.length > 1 && (
              <div className="image-counter">
                {selectedImageIndex + 1}/{galleryImages.length}
              </div>
            )}
            
            {/* Error State */}
            {selectedImage.status === 'error' && (
              <div className="error-detail">
                <span className="error-icon-large">⚠️</span>
                <h3>Generation Failed</h3>
                <p className="error-message">{selectedImage.error || 'Unknown error occurred'}</p>
                <div className="error-prompt">
                  <label>Prompt:</label>
                  <p>{selectedImage.prompt}</p>
                </div>
              </div>
            )}
            
            {/* Loading State */}
            {selectedImage.status === 'loading' && (
              <div className="loading-detail">
                <div className="spinner-large"></div>
                <h3>Generating Image...</h3>
                <p className="loading-prompt">{selectedImage.prompt}</p>
              </div>
            )}
            
            {/* Success State */}
            {selectedImage.status === 'success' && selectedImage.image_data && (
              <img src={`data:image/png;base64,${selectedImage.image_data}`} alt="" />
            )}
            {selectedImage.status === 'success' && selectedImage.thumbnail_url && (
              <img src={`http://localhost:8000${selectedImage.thumbnail_url}`} alt="" />
            )}
            
            {selectedImage.status === 'success' && (
              <div className="modal-info">
                <p className="prompt">{selectedImage.prompt}</p>
                <div className="modal-actions">
                  <button onClick={() => handleDownload(selectedImage)}>Download</button>
                  <span className="keyboard-hint">ESC to close • ← → to navigate</span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
