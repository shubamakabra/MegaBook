import React, { useState, useEffect } from 'react';
import { useAccess } from '../../contexts/AccessContext';
import './SettingsMenu.css';

interface Settings {
  llmProvider: 'mock' | 'azure' | 'openai';
  azureEndpoint: string;
  azureApiKey: string;
  azureDeployment: string;
  costLimitNok: number;
  theme: 'dark' | 'light' | 'system';
}

interface SettingsMenuProps {
  isOpen: boolean;
  onClose: () => void;
}

const defaultSettings: Settings = {
  llmProvider: 'mock',
  azureEndpoint: '',
  azureApiKey: '',
  azureDeployment: 'gpt-4',
  costLimitNok: 10,
  theme: 'dark',
};

export const SettingsMenu: React.FC<SettingsMenuProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<'identity' | 'llm' | 'costs' | 'theme'>('identity');
  const [settings, setSettings] = useState<Settings>(defaultSettings);
  const [currentCost] = useState({ nok: 0, usd: 0 });
  const { accessMode, characterName, setAccessMode, setCharacterName } = useAccess();

  useEffect(() => {
    // Load settings from localStorage
    const saved = localStorage.getItem('megabook-settings');
    if (saved) {
      setSettings({ ...defaultSettings, ...JSON.parse(saved) });
    }
  }, []);

  const saveSettings = () => {
    localStorage.setItem('megabook-settings', JSON.stringify(settings));
    onClose();
  };

  const updateSetting = <K extends keyof Settings>(key: K, value: Settings[K]) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  if (!isOpen) return null;

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={e => e.stopPropagation()}>
        <div className="settings-header">
          <h2>⚙️ Grimoire Configuration</h2>
          <button className="btn-close" onClick={onClose}>×</button>
        </div>

        <div className="settings-tabs">
          <button
            className={`settings-tab ${activeTab === 'identity' ? 'active' : ''}`}
            onClick={() => setActiveTab('identity')}
          >
            Identity
          </button>
          <button
            className={`settings-tab ${activeTab === 'llm' ? 'active' : ''}`}
            onClick={() => setActiveTab('llm')}
          >
            LLM Configuration
          </button>
          <button
            className={`settings-tab ${activeTab === 'costs' ? 'active' : ''}`}
            onClick={() => setActiveTab('costs')}
          >
            Cost Limits
          </button>
          <button
            className={`settings-tab ${activeTab === 'theme' ? 'active' : ''}`}
            onClick={() => setActiveTab('theme')}
          >
            Theme
          </button>
        </div>

        <div className="settings-content">
          {activeTab === 'identity' && (
            <div className="settings-section">
              <h3>Role</h3>
              <div className="form-group">
                <label>Access Mode</label>
                <div className="identity-role-toggle">
                  <button
                    className={`identity-role-btn ${accessMode === 'dm' ? 'active' : ''}`}
                    onClick={() => setAccessMode('dm')}
                  >
                    Dungeon Master
                  </button>
                  <button
                    className={`identity-role-btn ${accessMode === 'player' ? 'active' : ''}`}
                    onClick={() => setAccessMode('player')}
                  >
                    Player
                  </button>
                </div>
                <small>
                  {accessMode === 'dm'
                    ? 'Full access to all vault content. The Grimoire serves you as Master.'
                    : 'Restricted access based on your character. The Grimoire addresses you by name.'}
                </small>
              </div>

              {accessMode === 'player' && (
                <div className="form-group">
                  <label>Character Name</label>
                  <input
                    type="text"
                    value={characterName}
                    onChange={e => setCharacterName(e.target.value)}
                    placeholder="e.g. Thorin, Elara, Raynor..."
                  />
                  <small>The Grimoire will address you by this name and restrict vault access to your character's permissions.</small>
                </div>
              )}
            </div>
          )}

          {activeTab === 'llm' && (
            <>
              <div className="settings-section">
                <h3>LLM Provider</h3>
                <div className="form-group">
                  <label>Provider</label>
                  <select
                    value={settings.llmProvider}
                    onChange={(e) => updateSetting('llmProvider', e.target.value as any)}
                  >
                    <option value="mock">Mock (Testing)</option>
                    <option value="azure">Azure OpenAI</option>
                    <option value="openai">OpenAI</option>
                  </select>
                  <small>Mock provider returns fake responses for testing without API costs</small>
                </div>
              </div>

              {settings.llmProvider === 'azure' && (
                <div className="settings-section">
                  <h3>Azure Configuration</h3>
                  <div className="form-group">
                    <label>Endpoint URL</label>
                    <input
                      type="text"
                      value={settings.azureEndpoint}
                      onChange={(e) => updateSetting('azureEndpoint', e.target.value)}
                      placeholder="https://your-resource.openai.azure.com/"
                    />
                  </div>
                  <div className="form-group">
                    <label>API Key</label>
                    <input
                      type="password"
                      value={settings.azureApiKey}
                      onChange={(e) => updateSetting('azureApiKey', e.target.value)}
                      placeholder="your-api-key"
                    />
                  </div>
                  <div className="form-group">
                    <label>Deployment Name</label>
                    <input
                      type="text"
                      value={settings.azureDeployment}
                      onChange={(e) => updateSetting('azureDeployment', e.target.value)}
                      placeholder="gpt-4"
                    />
                  </div>
                </div>
              )}
            </>
          )}

          {activeTab === 'costs' && (
            <div className="settings-section">
              <h3>Cost Tracking</h3>
              <div className="form-group">
                <label>Cost Limit (NOK)</label>
                <div className="slider-container">
                  <input
                    type="range"
                    min="1"
                    max="100"
                    value={settings.costLimitNok}
                    onChange={(e) => updateSetting('costLimitNok', parseInt(e.target.value))}
                  />
                  <span className="slider-value">{settings.costLimitNok} NOK</span>
                </div>
                <small>Processing will pause when this limit is reached</small>
              </div>

              <div className="form-group">
                <label>Current Session Costs</label>
                <div className="cost-display">
                  <div className="cost-item">
                    <label>NOK</label>
                    <span>{currentCost.nok.toFixed(2)}</span>
                  </div>
                  <div className="cost-item">
                    <label>USD</label>
                    <span>${currentCost.usd.toFixed(4)}</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'theme' && (
            <div className="settings-section">
              <h3>Appearance</h3>
              <div className="form-group">
                <label>Theme</label>
                <select
                  value={settings.theme}
                  onChange={(e) => updateSetting('theme', e.target.value as any)}
                >
                  <option value="dark">Dark</option>
                  <option value="light">Light</option>
                  <option value="system">System Default</option>
                </select>
              </div>
            </div>
          )}

          <div className="settings-footer" style={{ marginTop: '30px', paddingTop: '20px', borderTop: '1px solid rgba(255, 215, 0, 0.1)', textAlign: 'center' }}>
            <p style={{ margin: '0 0 8px 0', fontFamily: 'var(--font-display)', fontSize: '14px', color: 'var(--accent-gold)' }}>✨ MegaBook - The Cosmic Grimoire</p>
            <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-stardust)', opacity: 0.7 }}>Forged in starlight for worldbuilders and dungeon masters</p>
          </div>

          <button onClick={saveSettings} className="btn-primary" style={{ marginTop: '20px' }}>
            Save Settings
          </button>
        </div>
      </div>
    </div>
  );
};
