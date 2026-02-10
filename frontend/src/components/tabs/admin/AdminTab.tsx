import React, { useState } from 'react';
import { AdminTab as AdminTabType } from '../../../types';
import { ImportTab } from '../../admin/ImportTab';
import { StructureTab } from '../../admin/StructureTab';
import { WikiTab } from '../../admin/WikiTab';
import { EmbeddingsTab } from '../../admin/EmbeddingsTab';
import { CostsTab } from '../../admin/CostsTab';
import { DiffTab } from '../../admin/DiffTab';
import { GitTab } from '../../admin/GitTab';
import './AdminTab.css';

export const AdminTab: React.FC = () => {
  const [activeTab, setActiveTab] = useState<AdminTabType>('import');

  const tabs: { id: AdminTabType; label: string; icon: string }[] = [
    { id: 'import', label: 'Import', icon: '📥' },
    { id: 'structure', label: 'Structure', icon: '🏗️' },
    { id: 'wiki', label: 'Wiki', icon: '📚' },
    { id: 'embeddings', label: 'Embeddings', icon: '🔮' },
    { id: 'costs', label: 'Costs', icon: '💰' },
    { id: 'diff', label: 'Diff', icon: '📝' },
    { id: 'git', label: 'Git', icon: '⚡' },
  ];

  const renderTab = () => {
    switch (activeTab) {
      case 'import':
        return <ImportTab />;
      case 'structure':
        return <StructureTab />;
      case 'wiki':
        return <WikiTab />;
      case 'embeddings':
        return <EmbeddingsTab />;
      case 'costs':
        return <CostsTab />;
      case 'diff':
        return <DiffTab />;
      case 'git':
        return <GitTab />;
      default:
        return null;
    }
  };

  return (
    <div className="admin-tab-container">
      <div className="admin-sidebar">
        <div className="admin-sidebar-header">
          <h2>⚙️ Admin</h2>
          <p className="admin-subtitle">Tavern Management</p>
        </div>
        
        <div className="admin-tabs">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={`admin-tab-btn ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <span className="tab-icon">{tab.icon}</span>
              <span className="tab-label">{tab.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="admin-content">
        {renderTab()}
      </div>
    </div>
  );
};
