import React, { useState, useCallback } from 'react';
import { api } from '../../services/api';
import './AdminTabs.css';

export const DiffTab: React.FC = () => {
  const [diff, setDiff] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [filterPath, setFilterPath] = useState('');

  const fetchDiff = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await api.getDiff(filterPath || undefined);
      setDiff(response.diff);
    } catch (error) {
      console.error('Failed to fetch diff:', error);
      setDiff('Error fetching diff');
    } finally {
      setIsLoading(false);
    }
  }, [filterPath]);

  return (
    <div className="admin-tab">
      <h3>Git Diff</h3>
      <p className="tab-description">
        View uncommitted changes in the repository.
      </p>

      <div className="diff-controls">
        <input
          type="text"
          placeholder="Filter by path (optional)"
          value={filterPath}
          onChange={(e) => setFilterPath(e.target.value)}
        />
        <button onClick={fetchDiff} disabled={isLoading}>
          {isLoading ? 'Loading...' : 'Refresh Diff'}
        </button>
      </div>

      <div className="diff-content">
        {diff ? (
          <pre className="diff-output">{diff}</pre>
        ) : (
          <p className="no-diff">No changes to display. Click "Refresh Diff" to check.</p>
        )}
      </div>
    </div>
  );
};