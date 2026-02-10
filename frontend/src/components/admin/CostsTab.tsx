import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../services/api';
import { CostStats } from '../../types';
import './AdminTabs.css';

export const CostsTab: React.FC = () => {
  const [stats, setStats] = useState<CostStats | null>(null);
  const [newLimit, setNewLimit] = useState(10);
  const [isLoading, setIsLoading] = useState(false);

  const fetchStats = useCallback(async () => {
    try {
      const data = await api.getCostStats();
      setStats(data);
      setNewLimit(data.cost_limit_nok);
    } catch (error) {
      console.error('Failed to fetch cost stats:', error);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 10000); // Refresh every 10 seconds
    return () => clearInterval(interval);
  }, [fetchStats]);

  const handleUpdateLimit = async () => {
    setIsLoading(true);
    try {
      await api.updateCostLimit(newLimit);
      await fetchStats();
    } catch (error) {
      console.error('Failed to update limit:', error);
    } finally {
      setIsLoading(false);
    }
  };

  if (!stats) {
    return <div className="admin-tab">Loading cost statistics...</div>;
  }

  return (
    <div className="admin-tab">
      <h3>Cost Dashboard</h3>
      <p className="tab-description">
        Monitor LLM usage costs. Processing will automatically pause when the limit is reached.
      </p>

      <div className="cost-cards">
        <div className="cost-card warning">
          <h4>Current Session</h4>
          <div className="cost-value">
            {stats.current_session_cost_nok.toFixed(4)} NOK
          </div>
          <div className="cost-subvalue">
            ${stats.current_session_cost_usd.toFixed(4)} USD
          </div>
          {stats.is_limit_reached && (
            <div className="limit-warning">⚠️ Limit Reached!</div>
          )}
        </div>

        <div className="cost-card">
          <h4>Cost Limit</h4>
          <div className="cost-value">{stats.cost_limit_nok} NOK</div>
          <div className="limit-controls">
            <input
              type="number"
              value={newLimit}
              onChange={(e) => setNewLimit(parseFloat(e.target.value))}
              step="1"
              min="1"
            />
            <button onClick={handleUpdateLimit} disabled={isLoading}>
              Update
            </button>
          </div>
        </div>

        <div className="cost-card">
          <h4>Last 7 Days</h4>
          <div className="cost-value">
            {parseFloat(stats.total_costs_7d.nok).toFixed(4)} NOK
          </div>
          <div className="cost-subvalue">
            ${parseFloat(stats.total_costs_7d.usd).toFixed(4)} USD
          </div>
        </div>

        <div className="cost-card">
          <h4>Last 30 Days</h4>
          <div className="cost-value">
            {parseFloat(stats.total_costs_30d.nok).toFixed(4)} NOK
          </div>
          <div className="cost-subvalue">
            ${parseFloat(stats.total_costs_30d.usd).toFixed(4)} USD
          </div>
        </div>
      </div>
    </div>
  );
};