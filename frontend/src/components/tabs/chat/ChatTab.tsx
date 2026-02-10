import React, { useState, useEffect, useRef } from 'react';
import { api } from '../../../services/api';
import './ChatTab.css';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Message {
  id: string;
  type: 'user' | 'ai';
  content: string;
  timestamp: Date;
}

interface ConversationMessage {
  role: string;
  content: string;
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

export const ChatTab: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [welcomeMessage, setWelcomeMessage] = useState(WELCOME_MESSAGES[0]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [chatId, setChatId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Check backend status on mount and load saved chat
  useEffect(() => {
    checkBackendStatus();
    const randomIndex = Math.floor(Math.random() * WELCOME_MESSAGES.length);
    setWelcomeMessage(WELCOME_MESSAGES[randomIndex]);
    loadSavedChat();
  }, []);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadSavedChat = () => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const session = JSON.parse(saved);
        if (session.chatId && session.messages) {
          setChatId(session.chatId);
          // Convert saved messages back to Message format
          const restoredMessages: Message[] = session.messages.map((msg: any) => ({
            id: msg.id || Date.now().toString() + Math.random(),
            type: msg.type,
            content: msg.content,
            timestamp: new Date(msg.timestamp),
          }));
          setMessages(restoredMessages);
          console.log('[Chat] Restored conversation with', restoredMessages.length, 'messages');
        }
      }
    } catch (err) {
      console.error('Failed to load saved chat:', err);
    }
  };

  const saveChat = (currentChatId: string, currentMessages: Message[]) => {
    try {
      const session = {
        chatId: currentChatId,
        messages: currentMessages.map(msg => ({
          id: msg.id,
          type: msg.type,
          content: msg.content,
          timestamp: msg.timestamp.toISOString(),
        })),
        lastUpdated: new Date().toISOString(),
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    } catch (err) {
      console.error('Failed to save chat:', err);
    }
  };

  const clearChat = () => {
    setMessages([]);
    setChatId(null);
    localStorage.removeItem(STORAGE_KEY);
    console.log('[Chat] Conversation cleared');
  };

  const checkBackendStatus = async () => {
    try {
      await api.healthCheck();
      setBackendStatus('online');
    } catch (err) {
      setBackendStatus('offline');
      setError('Backend is offline. Please start the backend server.');
    }
  };

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
      // Convert messages to conversation format for API
      const conversationHistory: ConversationMessage[] = messages.map(msg => ({
        role: msg.type === 'user' ? 'user' : 'assistant',
        content: msg.content,
      }));

      // Call conversation API with history
      const response = await api.generateConversationChat(
        inputValue,
        chatId || undefined,
        conversationHistory.length > 0 ? conversationHistory : undefined
      );

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'ai',
        content: response.content || 'I apologize, but I could not generate a response.',
        timestamp: new Date(),
      };

      const finalMessages = [...updatedMessages, aiMessage];
      setMessages(finalMessages);

      // Save chat session
      if (response.chat_id) {
        setChatId(response.chat_id);
        saveChat(response.chat_id, finalMessages);
      }

      console.log(`[Chat] Saved conversation with ${finalMessages.length} messages`);
    } catch (err: any) {
      console.error('Failed to get AI response:', err);
      setError(err.message || 'Failed to communicate with the backend.');
      
      // Add error message to chat
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

  return (
    <div className="chat-tab simple">
      <div className="chat-main">
        <div className="chat-welcome">
          <div className="welcome-header">
            <h2>{welcomeMessage.title}</h2>
            {messages.length > 0 && (
              <button 
                className="clear-chat-btn"
                onClick={clearChat}
                title="Clear conversation"
              >
                Clear
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
                {chatId && <span> • Session: {chatId.slice(0, 8)}...</span>}
              </small>
            </div>
          )}
        </div>

        <div className="chat-messages">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`message ${message.type}`}
            >
              <div className="message-content markdown-content">
                {message.type === 'ai' ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {message.content}
                  </ReactMarkdown>
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
            placeholder={backendStatus === 'online' ? "Ask me anything..." : "Backend offline - start server to chat"}
            disabled={isLoading || backendStatus === 'offline'}
          />
          <button
            className="chat-send-btn"
            onClick={handleSend}
            disabled={isLoading || !inputValue.trim() || backendStatus === 'offline'}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
};
