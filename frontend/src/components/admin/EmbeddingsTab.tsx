import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../services/api';
import './AdminTabs.css';

export const EmbeddingsTab: React.FC = () => {
  const [selectedNotes, setSelectedNotes] = useState<string[]>([]);
  const [rebuild, setRebuild] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [stats, setStats] = useState<{ count: number; collection_name: string } | null>(null);
  const [result, setResult] = useState<string | null>(null);

  const fetchStats = useCallback(async () => {
    try {
      const data = await api.getEmbeddingStats();
      setStats(data);
    } catch (error) {
      console.error('Failed to fetch embedding stats:', error);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  const handleGenerateEmbeddings = useCallback(async () => {
    setIsLoading(true);
    setResult(null);
    try {
      const response = await api.startEmbeddingPipeline(
        selectedNotes.length > 0 ? selectedNotes : undefined,
        rebuild
      );
      await api.runPipeline(response.pipeline_id);
      setResult(`Embedding generation started: ${response.pipeline_id}`);
    } catch (error) {
      setResult(`Error: ${error}`);
    } finally {
      setIsLoading(false);
    }
  }, [selectedNotes, rebuild]);

  return (
    <div className="admin-tab">
      <h3>Generate Embeddings</h3>
      <p className="tab-description">
        Generate vector embeddings from notes for RAG (Retrieval Augmented Generation).
        This enables semantic search and AI-powered queries.
      </p>

      {stats && (
        <div className="stats-box">
          <h4>Current Embeddings</h4>
          <p>Collection: {stats.collection_name}</p>
          <p>Total documents: {stats.count}</p>
        </div>
      )}

      <div className="form-group">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={rebuild}
            onChange={(e) => setRebuild(e.target.checked)}
          />
          Rebuild all embeddings (clears existing)
        </label>
      </div>

      <div className="form-group">
        <label>Selected Notes (leave empty to process all)</label>
        <input
          type="text"
          value={selectedNotes.join(', ')}
          onChange={(e) => setSelectedNotes(e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
          placeholder="notes/characters/hero.md"
        />
      </div>

      <button
        onClick={handleGenerateEmbeddings}
        disabled={isLoading}
        className="btn-primary"
      >
        {isLoading ? 'Generating...' : 'Generate Embeddings'}
      </button>

      {result && (
        <div className={`result ${result.startsWith('Error') ? 'error' : 'success'}`}>
          {result}
        </div>
      )}
    </div>
  );
};