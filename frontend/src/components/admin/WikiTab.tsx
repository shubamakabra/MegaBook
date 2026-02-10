import React, { useState, useCallback } from 'react';
import { api } from '../../services/api';
import './AdminTabs.css';

export const WikiTab: React.FC = () => {
  const [selectedNotes, setSelectedNotes] = useState<string[]>([]);
  const [audienceLevels, setAudienceLevels] = useState<string[]>(['dm']);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handleGenerateWiki = useCallback(async () => {
    setIsLoading(true);
    setResult(null);
    try {
      const response = await api.startWikiPipeline(
        selectedNotes.length > 0 ? selectedNotes : undefined,
        audienceLevels
      );
      await api.runPipeline(response.pipeline_id);
      setResult(`Wiki generation started: ${response.pipeline_id}`);
    } catch (error) {
      setResult(`Error: ${error}`);
    } finally {
      setIsLoading(false);
    }
  }, [selectedNotes, audienceLevels]);

  return (
    <div className="admin-tab">
      <h3>Generate Wiki</h3>
      <p className="tab-description">
        Generate wiki pages from structured notes. You can create both DM-level (full detail)
        and player-level (spoiler-free) versions.
      </p>

      <div className="form-group">
        <label>Audience Levels</label>
        <div className="checkbox-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={audienceLevels.includes('dm')}
              onChange={(e) => {
                if (e.target.checked) {
                  setAudienceLevels([...audienceLevels, 'dm']);
                } else {
                  setAudienceLevels(audienceLevels.filter(l => l !== 'dm'));
                }
              }}
            />
            DM Level (full detail, spoilers)
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={audienceLevels.includes('player')}
              onChange={(e) => {
                if (e.target.checked) {
                  setAudienceLevels([...audienceLevels, 'player']);
                } else {
                  setAudienceLevels(audienceLevels.filter(l => l !== 'player'));
                }
              }}
            />
            Player Level (spoiler-free)
          </label>
        </div>
      </div>

      <div className="form-group">
        <label>Selected Notes (leave empty to process all)</label>
        <input
          type="text"
          value={selectedNotes.join(', ')}
          onChange={(e) => setSelectedNotes(e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
          placeholder="notes/characters/hero.md, notes/locations/town.md"
        />
      </div>

      <button
        onClick={handleGenerateWiki}
        disabled={isLoading || audienceLevels.length === 0}
        className="btn-primary"
      >
        {isLoading ? 'Generating...' : 'Generate Wiki'}
      </button>

      {result && (
        <div className={`result ${result.startsWith('Error') ? 'error' : 'success'}`}>
          {result}
        </div>
      )}
    </div>
  );
};