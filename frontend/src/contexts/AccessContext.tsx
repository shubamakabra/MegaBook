import React, { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

export type AccessMode = 'dm' | 'player';

interface AccessContextValue {
  accessMode: AccessMode;
  characterName: string;
  setAccessMode: (mode: AccessMode) => void;
  setCharacterName: (name: string) => void;
  /** True when the user is in DM mode. */
  isDM: boolean;
}

const ACCESS_MODE_KEY = 'megabook_access_mode';
const CHARACTER_NAME_KEY = 'megabook_character_name';

const AccessContext = createContext<AccessContextValue | null>(null);

export const AccessProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [accessMode, setAccessModeState] = useState<AccessMode>(() => {
    return (localStorage.getItem(ACCESS_MODE_KEY) as AccessMode) || 'dm';
  });
  const [characterName, setCharacterNameState] = useState<string>(() => {
    return localStorage.getItem(CHARACTER_NAME_KEY) || '';
  });

  useEffect(() => {
    localStorage.setItem(ACCESS_MODE_KEY, accessMode);
  }, [accessMode]);

  useEffect(() => {
    localStorage.setItem(CHARACTER_NAME_KEY, characterName);
  }, [characterName]);

  const value: AccessContextValue = {
    accessMode,
    characterName,
    setAccessMode: setAccessModeState,
    setCharacterName: setCharacterNameState,
    isDM: accessMode === 'dm',
  };

  return (
    <AccessContext.Provider value={value}>
      {children}
    </AccessContext.Provider>
  );
};

/** Hook to consume the global access mode (DM / Player + character name). */
export function useAccess(): AccessContextValue {
  const ctx = useContext(AccessContext);
  if (!ctx) {
    throw new Error('useAccess must be used within an <AccessProvider>');
  }
  return ctx;
}
