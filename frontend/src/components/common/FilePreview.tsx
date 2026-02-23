import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './FilePreview.css';

export type PreviewFileType = 'image' | 'audio' | 'markdown' | 'text' | 'pdf' | 'unknown';

export interface FilePreviewProps {
  path: string;
  name: string;
  content?: string;
  size?: number;
  className?: string;
}

// Supported file extensions
const SUPPORTED_EXTENSIONS: Record<PreviewFileType, string[]> = {
  image: ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.ico'],
  audio: ['.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac'],
  markdown: ['.md', '.markdown'],
  text: ['.txt', '.json', '.yaml', '.yml', '.xml', '.csv', '.log', '.ini', '.conf', '.cfg', '.properties', '.sql', '.js', '.ts', '.jsx', '.tsx', '.css', '.scss', '.less', '.html', '.htm'],
  pdf: ['.pdf'],
  unknown: []
};

export const getFileType = (filename: string): PreviewFileType => {
  const lowerName = filename.toLowerCase();
  const ext = lowerName.substring(lowerName.lastIndexOf('.'));
  
  for (const [type, extensions] of Object.entries(SUPPORTED_EXTENSIONS)) {
    if (extensions.includes(ext)) {
      return type as PreviewFileType;
    }
  }
  return 'unknown';
};

export const isPreviewable = (filename: string): boolean => {
  return getFileType(filename) !== 'unknown';
};

export const FilePreview: React.FC<FilePreviewProps> = ({ 
  path, 
  name, 
  content,
  size,
  className = '' 
}) => {
  const fileType = getFileType(name);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load file content for images and PDFs
  useEffect(() => {
    const loadFile = async () => {
      try {
        setError(null);
        
        if (fileType === 'image') {
          // Fetch image as blob URL
          const response = await fetch(`/api/filesystem/download/${encodeURIComponent(path)}`);
          if (!response.ok) throw new Error('Failed to load image');
          const blob = await response.blob();
          setImageUrl(URL.createObjectURL(blob));
        } else if (fileType === 'pdf') {
          // Fetch PDF as blob URL
          const response = await fetch(`/api/filesystem/download/${encodeURIComponent(path)}`);
          if (!response.ok) throw new Error('Failed to load PDF');
          const blob = await response.blob();
          setPdfUrl(URL.createObjectURL(blob));
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load file');
      }
    };

    if (fileType === 'image' || fileType === 'pdf') {
      loadFile();
    }

    // Cleanup
    return () => {
      if (imageUrl) URL.revokeObjectURL(imageUrl);
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    };
  }, [path, fileType]);

  const renderContent = () => {
    switch (fileType) {
      case 'image':
        if (error) return <div className="preview-error">❌ {error}</div>;
        if (!imageUrl) return <div className="preview-loading">Loading image...</div>;
        return (
          <div className="preview-image-container">
            <img 
              src={imageUrl} 
              alt={name} 
              className="preview-image"
              onError={() => setError('Failed to display image')}
            />
          </div>
        );

      case 'audio':
        return (
          <div className="preview-audio-container">
            <div className="audio-icon">🎵</div>
            <div className="audio-filename">{name}</div>
            <audio 
              controls 
              className="preview-audio"
              src={`/api/filesystem/download/${encodeURIComponent(path)}`}
            >
              Your browser does not support the audio element.
            </audio>
          </div>
        );

      case 'markdown':
        return (
          <div className="preview-markdown">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {content || '*Empty file*'}
            </ReactMarkdown>
          </div>
        );

      case 'text':
        return (
          <div className="preview-text">
            <pre className="text-content">{content || '*Empty file*'}</pre>
          </div>
        );

      case 'pdf':
        if (error) return <div className="preview-error">❌ {error}</div>;
        if (!pdfUrl) return <div className="preview-loading">Loading PDF...</div>;
        return (
          <div className="preview-pdf-container">
            <iframe 
              src={pdfUrl} 
              className="preview-pdf"
              title={name}
            />
          </div>
        );

      default:
        return (
          <div className="preview-unknown">
            <div className="unknown-icon">📄</div>
            <div className="unknown-message">
              <p>Cannot preview this file type</p>
              <p className="unknown-hint">{name}</p>
            </div>
          </div>
        );
    }
  };

  return (
    <div className={`file-preview ${fileType} ${className}`}>
      <div className="preview-header">
        <span className="preview-icon">{getFileIcon(fileType)}</span>
        <span className="preview-name">{name}</span>
        {size !== undefined && (
          <span className="preview-size">({formatSize(size)})</span>
        )}
      </div>
      <div className="preview-content">
        {renderContent()}
      </div>
    </div>
  );
};

// Helper function to get icon for file type
const getFileIcon = (fileType: PreviewFileType): string => {
  switch (fileType) {
    case 'image': return '🖼️';
    case 'audio': return '🎵';
    case 'markdown': return '📝';
    case 'text': return '📄';
    case 'pdf': return '📑';
    default: return '📎';
  }
};

// Helper function to format file size
const formatSize = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
};

// Re-export for convenience
export { getFileIcon, formatSize };
