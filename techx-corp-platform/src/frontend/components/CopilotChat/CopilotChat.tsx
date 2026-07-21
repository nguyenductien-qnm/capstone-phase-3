import React, { useState, useEffect, useRef } from 'react';
import styled, { keyframes, css } from 'styled-components';

const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(20px) scale(0.95); }
  to { opacity: 1; transform: translateY(0) scale(1); }
`;

const slideUp = keyframes`
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
`;

const pulse = keyframes`
  0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(0, 0, 0, 0.4); }
  70% { transform: scale(1.05); box-shadow: 0 0 0 10px rgba(0, 0, 0, 0); }
  100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(0, 0, 0, 0); }
`;

const loadingDots = keyframes`
  0%, 20% { content: "."; }
  40% { content: ".."; }
  60%, 100% { content: "..."; }
`;

const ChatWrapper = styled.div`
  position: fixed;
  bottom: 30px;
  right: 30px;
  z-index: 9999;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
`;

const ChatToggleBtn = styled.button<{ isOpen: boolean }>`
  width: 65px;
  height: 65px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1e1e1e 0%, #000000 100%);
  color: white;
  border: none;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
  transform: ${props => (props.isOpen ? 'scale(0)' : 'scale(1)')};
  opacity: ${props => (props.isOpen ? 0 : 1)};
  
  &:hover {
    transform: ${props => (props.isOpen ? 'scale(0)' : 'scale(1.1)')};
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.3);
  }
  
  svg {
    width: 28px;
    height: 28px;
    fill: currentColor;
  }
`;

const ChatContainer = styled.div<{ isOpen: boolean }>`
  position: absolute;
  bottom: 0;
  right: 0;
  width: 380px;
  height: 600px;
  max-height: calc(100vh - 100px);
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: 24px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1), 0 1px 3px rgba(0,0,0,0.05);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transform-origin: bottom right;
  transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  transform: ${props => (props.isOpen ? 'scale(1)' : 'scale(0.8)')};
  opacity: ${props => (props.isOpen ? 1 : 0)};
  pointer-events: ${props => (props.isOpen ? 'auto' : 'none')};
`;

const ChatHeader = styled.div`
  background: linear-gradient(135deg, #111 0%, #333 100%);
  color: #fff;
  padding: 20px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
`;

const HeaderTitle = styled.div`
  display: flex;
  flex-direction: column;
  
  h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    letter-spacing: 0.3px;
  }
  
  span {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.7);
    margin-top: 4px;
    display: flex;
    align-items: center;
    
    &::before {
      content: '';
      display: inline-block;
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #4ade80;
      margin-right: 6px;
      box-shadow: 0 0 8px #4ade80;
    }
  }
`;

const CloseButton = styled.button`
  background: rgba(255, 255, 255, 0.1);
  border: none;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
  
  &:hover {
    background: rgba(255, 255, 255, 0.2);
  }
  
  svg {
    width: 14px;
    height: 14px;
    fill: currentColor;
  }
`;

const MessagesContainer = styled.div`
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: transparent;
  scroll-behavior: smooth;
  
  &::-webkit-scrollbar {
    width: 6px;
  }
  &::-webkit-scrollbar-thumb {
    background: rgba(0, 0, 0, 0.1);
    border-radius: 10px;
  }
`;

const MessageGroup = styled.div<{ isUser: boolean }>`
  display: flex;
  flex-direction: column;
  align-items: ${props => (props.isUser ? 'flex-end' : 'flex-start')};
  animation: ${slideUp} 0.3s ease-out forwards;
`;

const MessageBubble = styled.div<{ isUser: boolean }>`
  max-width: 85%;
  padding: 14px 18px;
  border-radius: 20px;
  background: ${props => (props.isUser ? 'linear-gradient(135deg, #111, #222)' : 'rgba(255, 255, 255, 0.9)')};
  color: ${props => (props.isUser ? '#fff' : '#111')};
  border-bottom-right-radius: ${props => (props.isUser ? '4px' : '20px')};
  border-bottom-left-radius: ${props => (props.isUser ? '20px' : '4px')};
  box-shadow: ${props => (props.isUser ? '0 4px 12px rgba(0,0,0,0.15)' : '0 4px 12px rgba(0,0,0,0.05)')};
  border: ${props => (props.isUser ? 'none' : '1px solid rgba(0,0,0,0.05)')};
  font-size: 14px;
  line-height: 1.5;
  letter-spacing: 0.2px;
`;

const LoadingBubble = styled(MessageBubble)`
  font-weight: bold;
  &::after {
    content: ".";
    animation: ${loadingDots} 1.5s infinite steps(1);
  }
`;

const ActionGateCard = styled.div`
  margin-top: 12px;
  padding: 16px;
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.95);
  box-shadow: 0 8px 24px rgba(0,0,0,0.06);
  color: #111;
  width: 90%;
  animation: ${fadeIn} 0.4s ease-out forwards;
`;

const ActionPrompt = styled.div`
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 16px;
  line-height: 1.4;
`;

const ButtonRow = styled.div`
  display: flex;
  gap: 12px;
`;

const ActionButton = styled.button<{ primary?: boolean }>`
  flex: 1;
  padding: 10px 0;
  border: ${props => (props.primary ? 'none' : '1px solid #ddd')};
  border-radius: 10px;
  cursor: pointer;
  background: ${props => (props.primary ? '#111' : '#fff')};
  color: ${props => (props.primary ? '#fff' : '#111')};
  font-weight: 600;
  font-size: 13px;
  transition: all 0.2s;
  
  &:hover {
    background: ${props => (props.primary ? '#333' : '#f5f5f5')};
    transform: translateY(-1px);
  }
  
  &:active {
    transform: translateY(1px);
  }
`;

const SourcesPanel = styled.details`
  margin-top: 6px;
  max-width: 85%;
  font-size: 12px;
  color: #555;

  summary {
    cursor: pointer;
    user-select: none;
    font-weight: 600;
  }
`;

const SourceItem = styled.div`
  padding: 6px 0;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  line-height: 1.4;

  &:first-of-type {
    border-top: none;
  }
`;

const TraceIdLabel = styled.button`
  margin-top: 4px;
  align-self: flex-start;
  background: none;
  border: none;
  padding: 0;
  font-size: 10px;
  font-family: 'SFMono-Regular', Consolas, monospace;
  color: #aaa;
  cursor: pointer;

  &:hover {
    color: #666;
  }
`;

const InputContainer = styled.form`
  display: flex;
  padding: 16px 24px;
  background: rgba(255, 255, 255, 0.9);
  border-top: 1px solid rgba(0, 0, 0, 0.05);
  align-items: center;
  gap: 12px;
`;

const Input = styled.input`
  flex: 1;
  padding: 14px 20px;
  border: 1px solid rgba(0,0,0,0.1);
  background: rgba(255,255,255,0.8);
  border-radius: 24px;
  outline: none;
  font-size: 14px;
  transition: all 0.3s;
  
  &:focus {
    border-color: #111;
    box-shadow: 0 0 0 3px rgba(0,0,0,0.05);
  }
  
  &:disabled {
    background: rgba(0,0,0,0.02);
    color: #999;
  }
`;

const SendBtn = styled.button`
  background: #111;
  color: #fff;
  border: none;
  border-radius: 50%;
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover:not(:disabled) {
    background: #333;
    transform: scale(1.05);
  }
  
  &:disabled {
    background: #ccc;
    cursor: not-allowed;
  }
  
  svg {
    width: 18px;
    height: 18px;
    fill: currentColor;
    margin-left: 2px;
  }
`;

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
}

export default function CopilotChat() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { id: '1', text: 'Hi there! I am your Shopping Copilot. How can I help you find the perfect product today?', isUser: false }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Generate simple session ID per tab
    setSessionId(Math.random().toString(36).substring(7));
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const sendMessage = async (text: string, token: string = '') => {
    if (!text && !token) return;

    if (text) {
      setMessages(prev => [...prev, { id: Date.now().toString(), text, isUser: true }]);
    }
    
    setInputValue('');
    setIsLoading(true);

    try {
      const res = await fetch('/api/copilot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: text,
          user_id: 'user-' + sessionId,
          session_id: sessionId,
          confirmation_token: token
        })
      });

      const data = await res.json();
      
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        text: data.response || (data.pendingConfirmation ? '' : 'I am sorry, I could not process that request.'),
        isUser: false,
        pendingAction: data.pendingConfirmation || null,
        citations: data.citations || [],
        traceId: data.traceId || ''
      }]);
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { id: Date.now().toString(), text: 'Connection error. Please try again.', isUser: false }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirmAction = (token: string, actionDesc: string) => {
    setMessages(prev => [...prev, { id: Date.now().toString(), text: `Confirmed: ${actionDesc}`, isUser: true }]);
    sendMessage('', token);
  };

  const handleRejectAction = () => {
    setMessages(prev => [...prev, { id: Date.now().toString(), text: 'Action cancelled.', isUser: true }]);
  };

  return (
    <ChatWrapper>
      <ChatToggleBtn isOpen={isOpen} onClick={() => setIsOpen(true)}>
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path d="M20 2H4C2.9 2 2 2.9 2 4V22L6 18H20C21.1 18 22 17.1 22 16V4C22 2.9 21.1 2 20 2ZM20 16H5.17L4 17.17V4H20V16Z"/>
          <path d="M7 9H17V11H7V9Z"/>
          <path d="M7 13H14V15H7V13Z"/>
          <path d="M7 5H17V7H7V5Z"/>
        </svg>
      </ChatToggleBtn>
      
      <ChatContainer isOpen={isOpen}>
        <ChatHeader>
          <HeaderTitle>
            <h3>Shopping Copilot</h3>
            <span>Online and ready to assist</span>
          </HeaderTitle>
          <CloseButton onClick={() => setIsOpen(false)}>
            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path d="M19 6.41L17.59 5L12 10.59L6.41 5L5 6.41L10.59 12L5 17.59L6.41 19L12 13.41L17.59 19L19 17.59L13.41 12L19 6.41Z"/>
            </svg>
          </CloseButton>
        </ChatHeader>
        
        <MessagesContainer>
          {messages.map((msg) => (
            <MessageGroup key={msg.id} isUser={msg.isUser}>
              {msg.text && (
                <MessageBubble isUser={msg.isUser}>{msg.text}</MessageBubble>
              )}
              
              {msg.pendingAction && !msg.isUser && (
                <ActionGateCard>
                  <ActionPrompt>{msg.pendingAction.humanPrompt}</ActionPrompt>
                  <ButtonRow>
                    <ActionButton primary onClick={() => handleConfirmAction(msg.pendingAction!.confirmationToken, msg.pendingAction!.humanPrompt)}>
                      Confirm
                    </ActionButton>
                    <ActionButton onClick={handleRejectAction}>
                      Cancel
                    </ActionButton>
                  </ButtonRow>
                </ActionGateCard>
              )}

              {!msg.isUser && !!msg.citations?.length && (
                <SourcesPanel>
                  <summary>Sources ({msg.citations.length})</summary>
                  {msg.citations.map((c, i) => (
                    <SourceItem key={`${msg.id}-src-${i}`}>
                      <strong>{c.reviewId || 'review'}</strong> ({c.score}): {c.snippet}
                    </SourceItem>
                  ))}
                </SourcesPanel>
              )}

              {!msg.isUser && !!msg.traceId && (
                <TraceIdLabel
                  type="button"
                  title={`Trace ID: ${msg.traceId} (click to copy)`}
                  onClick={() => navigator.clipboard?.writeText(msg.traceId || '')}
                >
                  trace: {msg.traceId.slice(0, 8)}
                </TraceIdLabel>
              )}
            </MessageGroup>
          ))}
          {isLoading && (
            <MessageGroup isUser={false}>
              <LoadingBubble isUser={false}>Thinking</LoadingBubble>
            </MessageGroup>
          )}
          <div ref={messagesEndRef} />
        </MessagesContainer>

        <InputContainer onSubmit={(e) => { e.preventDefault(); sendMessage(inputValue); }}>
          <Input 
            value={inputValue} 
            onChange={e => setInputValue(e.target.value)} 
            placeholder="Ask about products, sizes, or shipping..." 
            disabled={isLoading}
          />
          <SendBtn type="submit" disabled={isLoading || !inputValue.trim()}>
            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path d="M2.01 21L23 12L2.01 3L2 10L17 12L2 14L2.01 21Z"/>
            </svg>
          </SendBtn>
        </InputContainer>
      </ChatContainer>
    </ChatWrapper>
  );
}
