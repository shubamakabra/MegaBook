import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../services/api';
import { GitStatus, CommitInfo } from '../../types';
import './AdminTabs.css';

export const GitTab: React.FC = () => {
  const [status, setStatus] = useState<GitStatus | null>(null);
  const [history, setHistory] = useState<CommitInfo[]>([]);
  const [commitMessage, setCommitMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api.getGitStatus();
      setStatus(data);
    } catch (error) {
      console.error('Failed to fetch git status:', error);
    }
  }, []);

  const fetchHistory = useCallback(async () => {
    try {
      const data = await api.getGitHistory();
      setHistory(data);
    } catch (error) {
      console.error('Failed to fetch git history:', error);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    fetchHistory();
  }, [fetchStatus, fetchHistory]);

  const handleStageAll = async () => {
    setIsLoading(true);
    try {
      await api.stageAll();
      await fetchStatus();
    } catch (error) {
      console.error('Failed to stage files:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCommit = async () => {
    if (!commitMessage.trim()) return;
    
    setIsLoading(true);
    try {
      await api.createCommit(commitMessage);
      setCommitMessage('');
      await fetchStatus();
      await fetchHistory();
    } catch (error) {
      console.error('Failed to commit:', error);
      alert('Failed to create commit. Make sure there are staged changes.');
    } finally {
      setIsLoading(false);
    }
  };

  if (!status) {
    return <div className="admin-tab">Loading git status...</div>;
  }

  return (
    <div className="admin-tab">
      <h3>Git Operations</h3>
      
      <div className="git-status">
        <h4>Repository Status</h4>
        <p>Branch: <strong>{status.active_branch}</strong></p>
        <p>Commits: {status.commit_count}</p>
        <p className={status.is_dirty ? 'dirty' : 'clean'}>
          Status: {status.is_dirty ? 'Dirty' : 'Clean'}
        </p>
      </div>

      {status.is_dirty && (
        <div className="git-changes">
          <h4>Changes</h4>
          {status.modified_files.length > 0 && (
            <div>
              <strong>Modified:</strong>
              <ul>
                {status.modified_files.map((file, i) => (
                  <li key={i}>{file}</li>
                ))}
              </ul>
            </div>
          )}
          {status.untracked_files.length > 0 && (
            <div>
              <strong>Untracked:</strong>
              <ul>
                {status.untracked_files.map((file, i) => (
                  <li key={i}>{file}</li>
                ))}
              </ul>
            </div>
          )}
          
          <div className="git-actions">
            <button onClick={handleStageAll} disabled={isLoading}>
              Stage All Changes
            </button>
          </div>

          <div className="commit-form">
            <input
              type="text"
              placeholder="Commit message"
              value={commitMessage}
              onChange={(e) => setCommitMessage(e.target.value)}
            />
            <button 
              onClick={handleCommit} 
              disabled={isLoading || !commitMessage.trim()}
              className="btn-primary"
            >
              Commit
            </button>
          </div>
        </div>
      )}

      <div className="git-history">
        <h4>Recent Commits</h4>
        <ul>
          {history.map((commit) => (
            <li key={commit.hash} className="commit-item">
              <span className="commit-hash">{commit.short_hash}</span>
              <span className="commit-message">{commit.message}</span>
              <span className="commit-date">{new Date(commit.date).toLocaleDateString()}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};