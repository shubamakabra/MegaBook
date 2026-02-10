import React, { useState } from 'react';
import './AppLayout.css';

export type TabType = 'chat' | 'notes' | 'wiki' | 'files' | 'imagegen' | 'admin';

interface AppLayoutProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
  onSettingsClick: () => void;
  children: React.ReactNode;
}

const tabs: { id: TabType; label: string; icon: string; description: string }[] = [
  { id: 'chat', label: 'Chat', icon: '💬', description: 'Speak with the grimoire' },
  { id: 'notes', label: 'Notes', icon: '📝', description: 'Inscribe your tales' },
  { id: 'wiki', label: 'Wiki', icon: '📚', description: 'Browse the archives' },
  { id: 'files', label: 'Files', icon: '📁', description: 'Manage scrolls' },
  { id: 'imagegen', label: 'ImageGen', icon: '🎨', description: 'Create images' },
  { id: 'admin', label: 'Admin', icon: '⚙️', description: 'Tavern master' },
];

export const AppLayout: React.FC<AppLayoutProps> = ({
  activeTab,
  onTabChange,
  onSettingsClick,
  children,
}) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  return (
    <div className="app-container">
      {/* Collapsible Left Sidebar */}
      <aside className={`sidebar ${isSidebarOpen ? 'open' : 'collapsed'}`}>
        <div className="sidebar-header">
          <div className="app-brand">
            <span className="brand-icon">📖</span>
            {isSidebarOpen && (
              <div className="brand-text">
                <span className="brand-name">MegaBook</span>
                <span className="brand-subtitle">The Tavern Grimoire</span>
              </div>
            )}
          </div>
        </div>

        <nav className="sidebar-nav">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={`nav-item ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => onTabChange(tab.id)}
              title={!isSidebarOpen ? tab.label : undefined}
            >
              <span className="nav-icon">{tab.icon}</span>
              {isSidebarOpen && (
                <div className="nav-content">
                  <span className="nav-label">{tab.label}</span>
                  <span className="nav-description">{tab.description}</span>
                </div>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <button 
            className="settings-btn"
            onClick={onSettingsClick}
            title="Settings"
          >
            <span className="nav-icon">⚙️</span>
            {isSidebarOpen && <span className="nav-label">Settings</span>}
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        {/* Toggle Sidebar Button */}
        <button 
          className="sidebar-toggle"
          onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          title={isSidebarOpen ? 'Hide sidebar' : 'Show sidebar'}
        >
          {isSidebarOpen ? '◀' : '▶'}
        </button>

        {/* Content */}
        <div className="content-area">
          {children}
        </div>
      </main>
    </div>
  );
};
