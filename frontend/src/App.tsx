import { useState, useEffect } from 'react';
import { AppLayout, TabType } from './components/layout/AppLayout';
import { SettingsMenu } from './components/layout/SettingsMenu';
import { ChatTab } from './components/tabs/chat/ChatTab';
import { NotesTab } from './components/tabs/notes/NotesTab';
import { WikiTab } from './components/tabs/wiki/WikiTab';
import { FilesTab } from './components/tabs/files/FilesTab';
import { ImageTab } from './components/tabs/imagegen/ImageTab';
import { PromptsTab } from './components/tabs/prompts/PromptsTab';
import { AdminTab } from './components/tabs/admin/AdminTab';
import './App.css';

const TAB_STORAGE_KEY = 'megabook_active_tab';

function App() {
  const [activeTab, setActiveTab] = useState<TabType>(() => {
    // Restore tab from localStorage on initial load
    const saved = localStorage.getItem(TAB_STORAGE_KEY);
    return (saved as TabType) || 'chat';
  });
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // Persist tab changes to localStorage
  useEffect(() => {
    localStorage.setItem(TAB_STORAGE_KEY, activeTab);
  }, [activeTab]);

  const renderTab = () => {
    switch (activeTab) {
      case 'chat':
        return <ChatTab />;
      case 'notes':
        return <NotesTab />;
      case 'wiki':
        return <WikiTab />;
      case 'files':
        return <FilesTab />;
      case 'imagegen':
        return <ImageTab />;
      case 'prompts':
        return <PromptsTab />;
      case 'admin':
        return <AdminTab />;
      default:
        return <ChatTab />;
    }
  };

  return (
    <>
      <AppLayout
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onSettingsClick={() => setIsSettingsOpen(true)}
      >
        {renderTab()}
      </AppLayout>

      <SettingsMenu
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
    </>
  );
}

export default App;
