import React from 'react';

export const WikiTab: React.FC = () => {
  return (
    <div style={{ 
      padding: '40px', 
      textAlign: 'center',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center'
    }}>
      <h2>📚 Wiki Tab</h2>
      <p style={{ color: '#888', marginTop: '16px' }}>
        Browse your generated wiki with [[links]] and player/DM views
      </p>
      <div style={{ 
        marginTop: '24px',
        padding: '20px',
        background: '#252526',
        borderRadius: '8px',
        maxWidth: '600px'
      }}>
        <h3 style={{ marginBottom: '16px' }}>Features Coming:</h3>
        <ul style={{ textAlign: 'left', color: '#aaa', lineHeight: '1.8' }}>
          <li>📖 Markdown rendering with [[Wiki Links]]</li>
          <li>🗂️ Folder navigation sidebar</li>
          <li>👁️ DM / Player view toggle</li>
          <li>🔍 Search within wiki</li>
          <li>🔗 Click links to navigate between pages</li>
        </ul>
        <p style={{ marginTop: '16px', color: '#666', fontSize: '13px' }}>
          // TODO: Implement wiki rendering and navigation
        </p>
      </div>
    </div>
  );
};