import React, { useState, useCallback } from 'react';
import { api } from '../../services/api';
import './AdminTabs.css';

export const ImportTab: React.FC = () => {
  const [sourcePath, setSourcePath] = useState('');
  const [targetSubdir, setTargetSubdir] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handleImport = useCallback(async () => {
    setIsLoading(true);
    setResult(null);
    try {
      const response = await api.startImportPipeline(
        sourcePath || undefined,
        targetSubdir
      );
      setResult(`Import pipeline started: ${response.pipeline_id}`);
    } catch (error) {
      setResult(`Error: ${error}`);
    } finally {
      setIsLoading(false);
    }
  }, [sourcePath, targetSubdir]);

  const handleFileUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsLoading(true);
    setResult(null);
    try {
      const response = await api.uploadFile(file, targetSubdir);
      setResult(`File imported: ${response.data?.imported_files?.[0] || 'success'}`);
    } catch (error) {
      setResult(`Error: ${error}`);
    } finally {
      setIsLoading(false);
    }
  }, [targetSubdir]);

  return (
    <div className="admin-tab">
      <h3>Import Files</h3>
      <p className="tab-description">
        Import markdown files into the prompts/ directory. This is useful for importing
        Milanote exports or other markdown files.
      </p>

      <div className="form-group">
        <label>Target Subdirectory (optional)</label>
        <input
          type="text"
          value={targetSubdir}
          onChange={(e) => setTargetSubdir(e.target.value)}
          placeholder="e.g., imports/milanote"
        />
        <small>Files will be placed in prompts/{targetSubdir || '(root)'}</small>
      </div>

      <div className="import-section">
        <h4>Upload Single File</h4>
        <input
          type="file"
          accept=".md,.txt"
          onChange={handleFileUpload}
          disabled={isLoading}
        />
      </div>

      <div className="import-section">
        <h4>Import from Directory</h4>
        <div className="form-group">
          <label>Source Directory Path</label>
          <input
            type="text"
            value={sourcePath}
            onChange={(e) => setSourcePath(e.target.value)}
            placeholder="/path/to/exported/files"
          />
        </div>
        <button
          onClick={handleImport}
          disabled={isLoading || !sourcePath}
          className="btn-primary"
        >
          {isLoading ? 'Starting...' : 'Start Import Pipeline'}
        </button>
      </div>

      {result && (
        <div className={`result ${result.startsWith('Error') ? 'error' : 'success'}`}>
          {result}
        </div>
      )}
    </div>
  );
};