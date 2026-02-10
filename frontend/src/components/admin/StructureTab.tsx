import React, { useState, useCallback } from 'react';
import { api } from '../../services/api';
import { ProposedChange } from '../../types';
import './AdminTabs.css';

export const StructureTab: React.FC = () => {
  const [selectedPrompts, setSelectedPrompts] = useState<string[]>([]);
  const [pipelineId, setPipelineId] = useState<string | null>(null);
  const [proposedChanges, setProposedChanges] = useState<ProposedChange[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const handleStartStructuring = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await api.startStructuringPipeline(
        selectedPrompts.length > 0 ? selectedPrompts : undefined
      );
      setPipelineId(response.pipeline_id);
      // Start the pipeline
      await api.runPipeline(response.pipeline_id);
    } catch (error) {
      console.error('Failed to start structuring:', error);
    } finally {
      setIsLoading(false);
    }
  }, [selectedPrompts]);

  const handleGetChanges = useCallback(async () => {
    if (!pipelineId) return;
    
    try {
      const response = await api.getProposedChanges(pipelineId);
      setProposedChanges(response.changes || []);
    } catch (error) {
      console.error('Failed to get changes:', error);
    }
  }, [pipelineId]);

  const handleApplyChanges = useCallback(async (indices?: number[]) => {
    if (!pipelineId) return;
    
    setIsLoading(true);
    try {
      await api.applyChanges(pipelineId, indices);
      setProposedChanges([]);
      alert('Changes applied successfully');
    } catch (error) {
      console.error('Failed to apply changes:', error);
      alert('Failed to apply changes');
    } finally {
      setIsLoading(false);
    }
  }, [pipelineId]);

  return (
    <div className="admin-tab">
      <h3>Structure Notes</h3>
      <p className="tab-description">
        Process prompts/ to generate structured notes in notes/. This analyzes the content,
        extracts entities and relationships, and creates or updates canonical notes.
      </p>

      <div className="form-group">
        <label>Selected Prompts (leave empty to process all)</label>
        <input
          type="text"
          value={selectedPrompts.join(', ')}
          onChange={(e) => setSelectedPrompts(e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
          placeholder="prompts/file1.md, prompts/file2.md"
        />
      </div>

      <button
        onClick={handleStartStructuring}
        disabled={isLoading}
        className="btn-primary"
      >
        {isLoading ? 'Processing...' : 'Start Structuring Pipeline'}
      </button>

      {pipelineId && (
        <div className="pipeline-info">
          <p>Pipeline ID: {pipelineId}</p>
          <button onClick={handleGetChanges} className="btn-secondary">
            View Proposed Changes
          </button>
        </div>
      )}

      {proposedChanges.length > 0 && (
        <div className="changes-list">
          <h4>Proposed Changes ({proposedChanges.length})</h4>
          {proposedChanges.map((change, index) => (
            <div key={index} className="change-item">
              <div className="change-header">
                <span className={`operation ${change.operation}`}>{change.operation}</span>
                <span className="target">{change.target_path}</span>
              </div>
              <p className="change-reason">{change.reason}</p>
              <div className="change-actions">
                <button 
                  onClick={() => handleApplyChanges([index])}
                  className="btn-small"
                >
                  Apply This
                </button>
              </div>
            </div>
          ))}
          <button 
            onClick={() => handleApplyChanges()}
            className="btn-primary"
            disabled={isLoading}
          >
            Apply All Changes
          </button>
        </div>
      )}
    </div>
  );
};