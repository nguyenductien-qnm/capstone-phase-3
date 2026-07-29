import React, { useState, useEffect, useRef } from 'react';
import SessionGateway from '../../gateways/Session.gateway';
import { useQueryClient } from '@tanstack/react-query';
import { TraceCitationPanel } from '../TraceCitationPanel';

interface PendingConfirmation {
  toolName: string;
  argumentsJson: string;
  humanPrompt: string;
  confirmationToken: string;
  expiresAtUnix: number;
}
interface Citation {
  reviewId: string;
  snippet: string;
  score: string;
}
interface Message {
  id: string;
  text: string;
  isUser: boolean;
  pendingAction?: PendingConfirmation | null;
  citations?: Citation[];
  traceId?: string;
  traceSteps?: any[];
}

export default function CopilotChat() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      text: 'Hi there! I am your Shopping Copilot. How can I help you find the perfect product today?',
      isUser: false,
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const queryClient = useQueryClient();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setSessionId(SessionGateway.getSession().userId);
  }, []);
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const sendMessage = async (text: string, token = '') => {
    if (!text && !token) return;
    if (text) setMessages(p => [...p, { id: Date.now().toString(), text, isUser: true }]);
    setInputValue('');
    setIsLoading(true);
    try {
      const res = await fetch('/api/copilot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text, user_id: sessionId, session_id: sessionId, confirmation_token: token }),
      });
      const data = await res.json();
      queryClient.invalidateQueries({ queryKey: ['cart'] });
      setMessages(p => [
        ...p,
        {
          id: Date.now().toString(),
          text: data.response || (data.pendingConfirmation ? '' : 'I am sorry.'),
          isUser: false,
          pendingAction: data.pendingConfirmation || null,
          citations: data.citations || [],
          traceId: data.traceId || '',
          traceSteps: data.traceSteps || [],
        },
      ]);
    } catch {
      setMessages(p => [...p, { id: Date.now().toString(), text: 'Connection error.', isUser: false }]);
    } finally {
      setIsLoading(false);
    }
  };

  const iconChat = (
    <svg viewBox="0 0 24 24" className="h-7 w-7 fill-current">
      <path d="M20 2H4C2.9 2 2 2.9 2 4V22L6 18H20c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12zM7 9h10v2H7zm0 4h7v2H7zm0-8h10v2H7z" />
    </svg>
  );
  const iconClose = (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-current">
      <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
    </svg>
  );
  const iconSend = (
    <svg viewBox="0 0 24 24" className="ml-0.5 h-[18px] w-[18px] fill-current">
      <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
    </svg>
  );

  return (
    <div className="fixed bottom-6 right-[30px] z-[9999]">
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="flex h-[65px] w-[65px] items-center justify-center rounded-full bg-gradient-to-br from-gray-900 to-black text-white shadow-xl transition-transform hover:scale-110"
        >
          {iconChat}
        </button>
      )}
      <div
        className={`absolute bottom-0 right-0 w-[380px] h-[600px] max-h-[calc(100vh-100px)] rounded-3xl border border-white/20 bg-white/85 backdrop-blur-xl shadow-2xl flex flex-col overflow-hidden transition-all duration-400 origin-bottom-right ${isOpen ? 'scale-100 opacity-100 pointer-events-auto' : 'scale-80 opacity-0 pointer-events-none'}`}
      >
        <div className="flex items-center justify-between bg-gradient-to-br from-gray-900 to-gray-700 px-6 py-5 text-white">
          <div>
            <h3 className="text-base font-semibold">Shopping Copilot</h3>
            <span className="flex items-center gap-1.5 text-xs text-white/70">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-green-400" />
              Online
            </span>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10 hover:bg-white/20"
          >
            {iconClose}
          </button>
        </div>
        <div className="flex-1 space-y-4 overflow-y-auto p-6">
          {messages.map(msg => (
            <div key={msg.id} className={`flex flex-col ${msg.isUser ? 'items-end' : 'items-start'}`}>
              {msg.text && (
                <div
                  className={`max-w-[85%] rounded-[20px] px-[18px] py-[14px] text-sm shadow-sm ${msg.isUser ? 'rounded-br-[4px] bg-gradient-to-br from-gray-900 to-gray-800 text-white' : 'rounded-bl-[4px] border border-black/5 bg-white/90 text-gray-900'}`}
                >
                  {msg.text}
                </div>
              )}
              {msg.pendingAction && !msg.isUser && (
                <div className="mt-3 w-[90%] rounded-2xl border border-black/5 bg-white/95 p-4 shadow-md">
                  <div className="mb-4 text-sm font-medium">{msg.pendingAction.humanPrompt}</div>
                  <div className="flex gap-3">
                    <button
                      onClick={() => {
                        setMessages(p => [...p, { id: Date.now().toString(), text: 'Confirmed', isUser: true }]);
                        sendMessage('', msg.pendingAction!.confirmationToken);
                      }}
                      className="flex-1 rounded-lg bg-gray-900 py-2.5 text-xs font-semibold text-white hover:bg-gray-700"
                    >
                      Confirm
                    </button>
                    <button
                      onClick={() =>
                        setMessages(p => [...p, { id: Date.now().toString(), text: 'Cancelled', isUser: true }])
                      }
                      className="flex-1 rounded-lg border py-2.5 text-xs font-semibold hover:bg-gray-50"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
              {!msg.isUser && msg.traceId && (
                <TraceCitationPanel traceId={msg.traceId} citations={msg.citations} traceSteps={msg.traceSteps} />
              )}
            </div>
          ))}
          {isLoading && (
            <div className="flex flex-col items-start">
              <div className="max-w-[85%] rounded-[20px] rounded-bl-[4px] border border-black/5 bg-white/90 px-[18px] py-[14px] text-sm font-bold text-gray-900 animate-pulse">
                Thinking...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        <form
          onSubmit={e => {
            e.preventDefault();
            sendMessage(inputValue);
          }}
          className="flex gap-3 border-t border-black/5 bg-white/90 px-6 py-4"
        >
          <input
            value={inputValue}
            onChange={e => setInputValue(e.target.value)}
            placeholder="Ask about products..."
            disabled={isLoading}
            className="flex-1 rounded-full border border-black/10 bg-white/80 px-5 py-3.5 text-sm outline-none transition focus:border-gray-900 disabled:bg-black/[0.02] disabled:text-gray-400"
          />
          <button
            type="submit"
            disabled={isLoading || !inputValue.trim()}
            className="flex h-11 w-11 items-center justify-center rounded-full bg-gray-900 text-white hover:bg-gray-700 disabled:bg-gray-300"
          >
            {iconSend}
          </button>
        </form>
      </div>
    </div>
  );
}
