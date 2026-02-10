import React, { useRef, useCallback, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import { SplitPane, OpenFile } from './NotesTab';
import './SplitContainer.css';

interface SplitContainerProps {
  pane: SplitPane;
  files: OpenFile[];
  activeFileId: string | null;
  onFileSelect: (fileId: string) => void;
  onContentChange: (fileId: string, content: string) => void;
  onDebouncedSave: (fileId: string, content: string) => void;
  depth?: number;
}

export const SplitContainer: React.FC<SplitContainerProps> = ({
  pane,
  files,
  activeFileId,
  onFileSelect,
  onContentChange,
  onDebouncedSave,
  depth = 0,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const isDraggingRef = useRef(false);
  const startPosRef = useRef(0);
  const startSizesRef = useRef<[number, number]>([50, 50]);

  // Debounce timer ref
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  const handleContentChange = useCallback((fileId: string, content: string) => {
    // Immediate state update
    onContentChange(fileId, content);
    
    // Debounced save
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    debounceTimerRef.current = setTimeout(() => {
      onDebouncedSave(fileId, content);
    }, 500); // 500ms debounce
  }, [onContentChange, onDebouncedSave]);

  // Cleanup debounce on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  // Handle resize drag
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (!pane.sizes) return;
    
    isDraggingRef.current = true;
    startPosRef.current = pane.direction === 'vertical' ? e.clientX : e.clientY;
    startSizesRef.current = [...pane.sizes] as [number, number];
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [pane.sizes, pane.direction]);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDraggingRef.current || !containerRef.current || !pane.sizes) return;
    
    const containerRect = containerRef.current.getBoundingClientRect();
    const currentPos = pane.direction === 'vertical' ? e.clientX : e.clientY;
    const containerSize = pane.direction === 'vertical' 
      ? containerRect.width 
      : containerRect.height;
    
    const delta = currentPos - startPosRef.current;
    const deltaPercent = (delta / containerSize) * 100;
    
    let newFirstSize = startSizesRef.current[0] + deltaPercent;
    newFirstSize = Math.max(20, Math.min(80, newFirstSize)); // Clamp between 20% and 80%
    const newSecondSize = 100 - newFirstSize;
    
    // Update pane sizes (in real implementation, this would update state)
    console.log('Resizing panes:', newFirstSize, newSecondSize);
  }, [pane.direction, pane.sizes]);

  const handleMouseUp = useCallback(() => {
    isDraggingRef.current = false;
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
  }, [handleMouseMove]);

  // Render leaf node (single editor)
  if (pane.type === 'leaf') {
    const file = files.find(f => f.id === activeFileId);
    
    if (!file) {
      return (
        <div className="split-leaf empty">
          <p>Select a file to edit</p>
        </div>
      );
    }

    return (
      <div className="split-leaf">
        <Editor
          height="100%"
          defaultLanguage="markdown"
          value={file.content}
          onChange={(value) => handleContentChange(file.id, value || '')}
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
    );
  }

  // Render split node (two panes side by side or top-bottom)
  if (pane.type === 'split' && pane.children) {
    const [first, second] = pane.children;
    const isVertical = pane.direction === 'vertical';
    const sizes = pane.sizes || [50, 50];

    return (
      <div 
        ref={containerRef}
        className={`split-container ${isVertical ? 'vertical' : 'horizontal'}`}
      >
        <div 
          className="split-pane"
          style={{ flex: `0 0 ${sizes[0]}%` }}
        >
          <SplitContainer
            pane={first}
            files={files}
            activeFileId={activeFileId}
            onFileSelect={onFileSelect}
            onContentChange={onContentChange}
            onDebouncedSave={onDebouncedSave}
            depth={depth + 1}
          />
        </div>

        <div 
          className="split-resizer"
          onMouseDown={handleMouseDown}
        />

        <div 
          className="split-pane"
          style={{ flex: `0 0 ${sizes[1]}%` }}
        >
          <SplitContainer
            pane={second}
            files={files}
            activeFileId={activeFileId}
            onFileSelect={onFileSelect}
            onContentChange={onContentChange}
            onDebouncedSave={onDebouncedSave}
            depth={depth + 1}
          />
        </div>
      </div>
    );
  }

  return null;
};