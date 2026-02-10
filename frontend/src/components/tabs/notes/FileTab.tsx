import React from 'react';
import { OpenFile } from './NotesTab';
import './FileTab.css';

interface FileTabProps {
  file: OpenFile;
  onSelect: () => void;
  onClose: (e: React.MouseEvent) => void;
}

export const FileTab: React.FC<FileTabProps> = ({ file, onSelect, onClose }) => {
  return (
    <div
      className={`file-tab ${file.isActive ? 'active' : ''}`}
      onClick={onSelect}
    >
      <span className="tab-name">{file.name}</span>
      {file.isModified && <span className="modified-dot">●</span>}
      <button
        className="tab-close-btn"
        onClick={onClose}
        title="Close tab"
      >
        ×
      </button>
    </div>
  );
};