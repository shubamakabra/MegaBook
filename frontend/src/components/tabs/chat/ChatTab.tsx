import React, { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../../../services/api';
import { useAccess } from '../../../contexts/AccessContext';
import './ChatTab.css';
import { ObsidianMarkdown } from '../../common';

interface ToolUsage {
  tool_name: string;
  arguments: Record<string, any>;
  result_preview: string;
}

interface Message {
  id: string;
  type: 'user' | 'ai';
  content: string;
  timestamp: Date;
  toolUsage?: ToolUsage[];
  agentIterations?: number;
}

interface ConversationMessage {
  role: string;
  content: string;
}

interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  preview: string;
}

// Context window usage thresholds (percentage of context window used)
type ContextLevel = 'green' | 'yellow' | 'orange' | 'red' | 'black';

const CONTEXT_THRESHOLDS = {
  green: 0,       // 0-50%: All good
  yellow: 0.50,   // 50-70%: Getting there
  orange: 0.70,   // 70-85%: Watch out
  red: 0.85,      // 85-95%: Danger zone
  black: 0.95,    // 95%+: Context full, must summarize
};

function getContextLevel(ratio: number): ContextLevel {
  if (ratio >= CONTEXT_THRESHOLDS.black) return 'black';
  if (ratio >= CONTEXT_THRESHOLDS.red) return 'red';
  if (ratio >= CONTEXT_THRESHOLDS.orange) return 'orange';
  if (ratio >= CONTEXT_THRESHOLDS.yellow) return 'yellow';
  return 'green';
}

function getContextLabel(level: ContextLevel): string {
  switch (level) {
    case 'green': return 'Context OK';
    case 'yellow': return 'Context filling up';
    case 'orange': return 'Context getting large';
    case 'red': return 'Context nearly full';
    case 'black': return 'Context full - summarize to continue';
  }
}

const WELCOME_MESSAGES = [
  {
    title: "Welcome to MegaBook",
    text: "I am your AI companion for D&D and worldbuilding. Ask me anything about creating characters, locations, plot ideas, or world lore!"
  },
  {
    title: "Greetings, Storyteller!",
    text: "Ready to craft your next adventure? I can help you develop NPCs, describe settings, brainstorm encounters, or refine your campaign ideas."
  },
  {
    title: "Let Your Imagination Soar",
    text: "Whether you need help fleshing out a character backstory, designing a dungeon, or planning plot twists - I'm here to help you build worlds!"
  }
];

const STORAGE_KEY = 'megabook_chat_session';

/** Format a relative time string from an ISO date string. */
function formatRelativeTime(isoString: string): string {
  if (!isoString) return '';
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  } catch {
    return '';
  }
}

export const ChatTab: React.FC = () => {
  // -- Session list state --
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');

  // -- Active chat state --
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [welcomeMessage] = useState(() =>
    WELCOME_MESSAGES[Math.floor(Math.random() * WELCOME_MESSAGES.length)]
  );
  const [isLoading, setIsLoading] = useState(false);
  const [isCompacting, setIsCompacting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [chatId, setChatId] = useState<string | null>(null);
  const [promptTokens, setPromptTokens] = useState<number>(0);
  const [contextWindow, setContextWindow] = useState<number>(131072);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);

  // -- Access control state (from global context) --
  const { accessMode, characterName } = useAccess();

  // Derived context state
  const contextRatio = contextWindow > 0 ? promptTokens / contextWindow : 0;
  const contextLevel = getContextLevel(contextRatio);
  const isContextFull = contextLevel === 'black';

  // ---- Load sessions from backend ----
  const loadSessions = useCallback(async () => {
    try {
      setSessionsLoading(true);
      const data = await api.listChatSessions();
      setSessions(data.sessions || []);
    } catch (err) {
      console.error('[Chat] Failed to load sessions:', err);
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  // ---- Initialize ----
  useEffect(() => {
    checkBackendStatus();
    loadSessions();
    loadSavedChat();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus rename input when renaming starts
  useEffect(() => {
    if (renamingId && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [renamingId]);

  // ---- Persistence ----
  const loadSavedChat = () => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const session = JSON.parse(saved);
        if (session.chatId && session.messages) {
          setChatId(session.chatId);
          const restoredMessages: Message[] = session.messages.map((msg: any) => ({
            id: msg.id || Date.now().toString() + Math.random(),
            type: msg.type,
            content: msg.content,
            timestamp: new Date(msg.timestamp),
            toolUsage: msg.toolUsage,
            agentIterations: msg.agentIterations,
          }));
          setMessages(restoredMessages);
          if (session.promptTokens) setPromptTokens(session.promptTokens);
          if (session.contextWindow) setContextWindow(session.contextWindow);
          console.log('[Chat] Restored conversation with', restoredMessages.length, 'messages');
        }
      }
    } catch (err) {
      console.error('Failed to load saved chat:', err);
    }
  };

  const saveChat = (currentChatId: string, currentMessages: Message[], currentPromptTokens?: number, currentContextWindow?: number) => {
    try {
      const session = {
        chatId: currentChatId,
        messages: currentMessages.map(msg => ({
          id: msg.id,
          type: msg.type,
          content: msg.content,
          timestamp: msg.timestamp.toISOString(),
          toolUsage: msg.toolUsage,
          agentIterations: msg.agentIterations,
        })),
        promptTokens: currentPromptTokens ?? promptTokens,
        contextWindow: currentContextWindow ?? contextWindow,
        lastUpdated: new Date().toISOString(),
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    } catch (err) {
      console.error('Failed to save chat:', err);
    }
  };

  // ---- Thread actions ----
  const startNewChat = () => {
    setMessages([]);
    setChatId(null);
    setPromptTokens(0);
    setError(null);
    localStorage.removeItem(STORAGE_KEY);
    console.log('[Chat] Started new conversation');
  };

  const switchToThread = async (sessionId: string) => {
    if (sessionId === chatId) return; // Already active

    try {
      setError(null);
      const history = await api.getChatHistory(sessionId);
      const restoredMessages: Message[] = history.map((msg: ConversationMessage, index: number) => ({
        id: `${sessionId}-${index}`,
        type: msg.role === 'user' ? 'user' as const : 'ai' as const,
        content: msg.content,
        timestamp: new Date(), // No per-message timestamps from backend
      }));
      setChatId(sessionId);
      setMessages(restoredMessages);
      // Reset token tracking (will update on next message)
      setPromptTokens(0);
      saveChat(sessionId, restoredMessages, 0, contextWindow);
      console.log(`[Chat] Switched to thread ${sessionId.slice(0, 8)} with ${restoredMessages.length} messages`);
    } catch (err: any) {
      console.error('[Chat] Failed to switch thread:', err);
      setError('Failed to load chat thread.');
    }
  };

  const deleteThread = async (sessionId: string) => {
    try {
      await api.deleteChatHistory(sessionId);
      // If we deleted the active thread, reset
      if (sessionId === chatId) {
        startNewChat();
      }
      // Remove from local list
      setSessions(prev => prev.filter(s => s.id !== sessionId));
    } catch (err: any) {
      console.error('[Chat] Failed to delete thread:', err);
      setError('Failed to delete chat thread.');
    }
  };

  const startRename = (session: ChatSession) => {
    setRenamingId(session.id);
    setRenameValue(session.title);
  };

  const submitRename = async () => {
    if (!renamingId || !renameValue.trim()) {
      setRenamingId(null);
      return;
    }
    try {
      const updated = await api.renameChatSession(renamingId, renameValue.trim());
      setSessions(prev => prev.map(s =>
        s.id === renamingId ? { ...s, title: updated.title, updated_at: updated.updated_at } : s
      ));
    } catch (err) {
      console.error('[Chat] Failed to rename:', err);
    } finally {
      setRenamingId(null);
    }
  };

  const cancelRename = () => {
    setRenamingId(null);
  };

  // ---- Backend check ----
  const checkBackendStatus = async () => {
    try {
      await api.healthCheck();
      setBackendStatus('online');
    } catch (err) {
      setBackendStatus('offline');
      setError('Backend is offline. Please start the backend server.');
    }
  };

  // ---- Send message ----
  const handleSend = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: inputValue,
      timestamp: new Date(),
    };

    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setInputValue('');
    setIsLoading(true);
    setError(null);

    try {
      const conversationHistory: ConversationMessage[] = messages.map(msg => ({
        role: msg.type === 'user' ? 'user' : 'assistant',
        content: msg.content,
      }));

      const response = await api.generateConversationChat(
        inputValue,
        chatId || undefined,
        conversationHistory.length > 0 ? conversationHistory : undefined,
        accessMode,
        accessMode === 'player' ? characterName || undefined : undefined,
      );

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'ai',
        content: response.content || 'I apologize, but I could not generate a response.',
        timestamp: new Date(),
        toolUsage: response.tool_usage && response.tool_usage.length > 0 ? response.tool_usage : undefined,
        agentIterations: response.agent_iterations > 1 ? response.agent_iterations : undefined,
      };

      const finalMessages = [...updatedMessages, aiMessage];
      setMessages(finalMessages);

      const newPromptTokens = response.prompt_tokens || 0;
      const newContextWindow = response.context_window || contextWindow;
      setPromptTokens(newPromptTokens);
      setContextWindow(newContextWindow);

      if (response.chat_id) {
        setChatId(response.chat_id);
        saveChat(response.chat_id, finalMessages, newPromptTokens, newContextWindow);
      }

      // Refresh session list after sending a message (new thread may have been created)
      loadSessions();

      console.log(`[Chat] Saved conversation with ${finalMessages.length} messages (context: ${newPromptTokens}/${newContextWindow} tokens)`);
    } catch (err: any) {
      console.error('Failed to get AI response:', err);
      setError(err.message || 'Failed to communicate with the backend.');

      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'ai',
        content: 'I apologize, but I encountered an error. Please ensure the backend server is running.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCompact = async () => {
    if (!chatId || isCompacting || isLoading) return;

    setIsCompacting(true);
    setError(null);

    try {
      const result = await api.compactChat(chatId);

      // Build messages from the compacted history
      const restoredMessages: Message[] = result.history.map((msg: ConversationMessage, index: number) => ({
        id: `${result.new_chat_id}-${index}`,
        type: msg.role === 'user' ? 'user' as const : 'ai' as const,
        content: msg.content,
        timestamp: new Date(),
      }));

      // Add a system-style notification message
      const compactionNotice: Message = {
        id: `compact-notice-${Date.now()}`,
        type: 'ai',
        content: `**[Conversation Compacted]**\n\nThe previous conversation (${messages.length} messages) has been summarized into this new thread. The original thread has been preserved. You can continue the conversation from here.`,
        timestamp: new Date(),
      };

      const finalMessages = [...restoredMessages, compactionNotice];

      // Switch to the new compacted thread
      setChatId(result.new_chat_id);
      setMessages(finalMessages);
      setPromptTokens(result.prompt_tokens);
      setContextWindow(result.context_window);
      saveChat(result.new_chat_id, finalMessages, result.prompt_tokens, result.context_window);

      // Refresh session list to show the new thread
      loadSessions();

      console.log(`[Chat] Compaction complete. New thread: ${result.new_chat_id.slice(0, 8)}`);
    } catch (err: any) {
      console.error('[Chat] Compaction failed:', err);
      setError('Failed to compact conversation. Please try again.');
    } finally {
      setIsCompacting(false);
    }
  };

  return (
    <div className="chat-tab simple">
      {/* ---- Sidebar: Thread List ---- */}
      <div className="chat-sidebar">
        <div className="chat-sidebar-header">
          <span className="chat-sidebar-title">Threads</span>
          <button
            className="new-chat-btn"
            onClick={startNewChat}
            title="Start a new conversation"
          >
            + New
          </button>
        </div>

        <div className="chat-sidebar-list">
          {sessionsLoading ? (
            <div className="chat-sidebar-empty">Loading...</div>
          ) : sessions.length === 0 ? (
            <div className="chat-sidebar-empty">No conversations yet</div>
          ) : (
            sessions.map(session => (
              <div
                key={session.id}
                className={`chat-thread-item ${session.id === chatId ? 'active' : ''}`}
                onClick={() => switchToThread(session.id)}
              >
                {renamingId === session.id ? (
                  <input
                    ref={renameInputRef}
                    className="thread-rename-input"
                    value={renameValue}
                    onChange={e => setRenameValue(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter') submitRename();
                      if (e.key === 'Escape') cancelRename();
                    }}
                    onBlur={submitRename}
                    onClick={e => e.stopPropagation()}
                  />
                ) : (
                  <>
                    <div className="thread-title">{session.title}</div>
                    <div className="thread-meta">
                      <span className="thread-count">{session.message_count} msgs</span>
                      <span className="thread-time">{formatRelativeTime(session.updated_at)}</span>
                    </div>
                    <div className="thread-actions">
                      <button
                        className="thread-action-btn"
                        title="Rename"
                        onClick={e => { e.stopPropagation(); startRename(session); }}
                      >
                        R
                      </button>
                      <button
                        className="thread-action-btn danger"
                        title="Delete"
                        onClick={e => { e.stopPropagation(); deleteThread(session.id); }}
                      >
                        X
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* ---- Main Chat Area ---- */}
      <div className="chat-main">
        <div className="chat-welcome">
          <div className="welcome-header">
            <h2>{welcomeMessage.title}</h2>
            {messages.length > 0 && (
              <button
                className="clear-chat-btn"
                onClick={startNewChat}
                title="Start new conversation"
              >
                New Chat
              </button>
            )}
          </div>
          <p>{welcomeMessage.text}</p>
          {backendStatus === 'offline' && (
            <div className="backend-status offline">
              Backend offline - Start the backend server to chat
            </div>
          )}
          {messages.length > 0 && (
            <div className="chat-status">
              <small>
                {messages.length} messages in conversation
                {chatId && <span> &bull; Session: {chatId.slice(0, 8)}...</span>}
              </small>
            </div>
          )}
          {/* Context Window Indicator */}
          {messages.length > 0 && (
            <div className={`context-indicator ${contextLevel}`}>
              <div className="context-bar-track">
                <div
                  className="context-bar-fill"
                  style={{ width: `${Math.min(contextRatio * 100, 100)}%` }}
                />
              </div>
              <div className="context-info">
                <span className="context-label">{getContextLabel(contextLevel)}</span>
                <span className="context-tokens">
                  {promptTokens.toLocaleString()} / {contextWindow.toLocaleString()} tokens
                  ({Math.round(contextRatio * 100)}%)
                </span>
              </div>
              {(contextLevel === 'red' || contextLevel === 'black') && chatId && (
                <button
                  className={`compact-btn ${isCompacting ? 'compacting' : ''}`}
                  onClick={handleCompact}
                  disabled={isCompacting || isLoading}
                  title="Summarize this conversation into a new thread to free up context space"
                >
                  {isCompacting ? 'Compacting...' : 'Compact History'}
                </button>
              )}
            </div>
          )}
        </div>

        <div className="chat-messages">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`message ${message.type}`}
            >
              {message.type === 'ai' && message.toolUsage && message.toolUsage.length > 0 && (
                <div className="tool-usage-indicator">
                  <details>
                    <summary className="tool-usage-summary">
                      Consulted {message.toolUsage.length} vault source{message.toolUsage.length !== 1 ? 's' : ''}
                      {message.agentIterations && message.agentIterations > 1 && (
                        <span className="agent-iterations"> ({message.agentIterations} steps)</span>
                      )}
                    </summary>
                    <ul className="tool-usage-list">
                      {message.toolUsage.map((tool, idx) => (
                        <li key={idx} className="tool-usage-item">
                          <span className="tool-name">{tool.tool_name}</span>
                          {tool.arguments && Object.keys(tool.arguments).length > 0 && (
                            <span className="tool-args">
                              ({Object.entries(tool.arguments).map(([k, v]) => `${k}: ${v}`).join(', ')})
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </details>
                </div>
              )}
              <div className="message-content markdown-content">
                {message.type === 'ai' ? (
                  <ObsidianMarkdown content={message.content} />
                ) : (
                  message.content
                )}
              </div>
              <div className="message-timestamp">
                {message.timestamp.toLocaleTimeString()}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="message ai loading">
              <div className="thinking-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
              <em>Thinking...</em>
            </div>
          )}
          {isCompacting && (
            <div className="message ai loading compacting-message">
              <div className="thinking-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
              <em>Compacting conversation history...</em>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {error && (
          <div className="error-banner">
            {error}
            <button onClick={() => setError(null)}>X</button>
          </div>
        )}

        <div className="chat-input-container">
          <input
            type="text"
            className="chat-input"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              backendStatus !== 'online'
                ? "Backend offline - start server to chat"
                : isContextFull
                ? "Context full - send a summary request to continue..."
                : "Ask me anything..."
            }
            disabled={isLoading || backendStatus === 'offline'}
          />
          <button
            className={`chat-send-btn ${isContextFull ? 'summary-mode' : ''}`}
            onClick={handleSend}
            disabled={isLoading || !inputValue.trim() || backendStatus === 'offline'}
          >
            {isContextFull ? 'Send Summary Request' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
};
