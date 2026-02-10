import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';
import { FileTreeNode, PipelineStatus } from '../types';
import './Layout.css';

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const [activePipelines, setActivePipelines] = useState<PipelineStatus[]>([]);
  const [showNotifications, setShowNotifications] = useState(false);

  const fetchActivePipelines = useCallback(async () => {
    try {
      const response = await api.listActivePipelines();
      const pipelines = response.pipelines || [];
      
      // Get detailed status for each pipeline
      const detailedPipelines = await Promise.all(
        pipelines.map(async (p: { id: string }) => {
          try {
            return await api.getPipelineStatus(p.id);
          } catch {
            return null;
          }
        })
      );
      
      setActivePipelines(detailedPipelines.filter(Boolean));
    } catch (error) {
      console.error('Failed to fetch pipelines:', error);
    }
  }, []);

  useEffect(() => {
    fetchActivePipelines();
    const interval = setInterval(fetchActivePipelines, 5000); // Poll every 5 seconds
    return () => clearInterval(interval);
  }, [fetchActivePipelines]);

  const runningPipelines = activePipelines.filter(p => p.state === 'running');
  const pausedPipelines = activePipelines.filter(p => p.state === 'paused');

  return (
    <div className="layout">
      {/* Background notifications */}
      {(runningPipelines.length > 0 || pausedPipelines.length > 0) && (
        <div className="notification-bar">
          <button 
            className="notification-toggle"
            onClick={() => setShowNotifications(!showNotifications)}
          >
            {runningPipelines.length > 0 && (
              <span className="badge running">{runningPipelines.length} running</span>
            )}
            {pausedPipelines.length > 0 && (
              <span className="badge paused">{pausedPipelines.length} paused</span>
            )}
          </button>
          
          {showNotifications && (
            <div className="notification-dropdown">
              {activePipelines.map(pipeline => (
                <div key={pipeline.pipeline_id} className={`pipeline-item ${pipeline.state}`}>
                  <div className="pipeline-header">
                    <span className="pipeline-type">{pipeline.pipeline_type}</span>
                    <span className={`pipeline-state ${pipeline.state}`}>
                      {pipeline.state}
                    </span>
                  </div>
                  <div className="pipeline-progress">
                    <div className="progress-bar">
                      <div 
                        className="progress-fill"
                        style={{ width: `${pipeline.progress_percentage}%` }}
                      />
                    </div>
                    <span className="progress-text">
                      {pipeline.current_step} / {pipeline.total_steps}
                    </span>
                  </div>
                  {pipeline.current_item && (
                    <div className="pipeline-item-current">{pipeline.current_item}</div>
                  )}
                  <div className="pipeline-actions">
                    {pipeline.state === 'running' && (
                      <button 
                        onClick={() => api.pausePipeline(pipeline.pipeline_id)}
                        className="btn-pause"
                      >
                        Pause
                      </button>
                    )}
                    {pipeline.state === 'paused' && (
                      <button 
                        onClick={() => api.resumePipeline(pipeline.pipeline_id)}
                        className="btn-resume"
                      >
                        Resume
                      </button>
                    )}
                    <button 
                      onClick={() => api.stopPipeline(pipeline.pipeline_id)}
                      className="btn-stop"
                    >
                      Stop
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Main content */}
      <div className="layout-content">
        {children}
      </div>
    </div>
  );
};