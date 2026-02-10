import React, { useState } from 'react';
import { AppLayout, TabType } from './components/layout/AppLayout';
import { SettingsMenu } from './components/layout/SettingsMenu';
import { ChatTab } from './components/tabs/chat/ChatTab';
import { NotesTab } from './components/tabs/notes/NotesTab';
import { WikiTab } from './components/tabs/wiki/WikiTab';
import { FilesTab } from './components/tabs/files/FilesTab';
import { ImageTab } from './components/tabs/imagegen/ImageTab';
import { AdminTab } from './components/tabs/admin/AdminTab';
import './App.css';

function App() {
  const [activeTab, setActiveTab] = useState<TabType>('chat');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

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