import React, { useState, useEffect, useRef } from 'react';
import styled from 'styled-components';

const ChatContainer = styled.div<{ isOpen: boolean }>`
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 350px;
  height: 500px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 5px 15px rgba(0,0,0,0.2);
  display: flex;
  flex-direction: column;
  transform: ${props => props.isOpen ? 'translateY(0)' : 'translateY(120%)'};
  transition: transform 0.3s ease-in-out;
  z-index: 1000;
  overflow: hidden;
`;

const ChatHeader = styled.div`
  background: #000;
  color: #fff;
  padding: 15px;
  font-weight: bold;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
`;

const ChatToggleBtn = styled.button`
  position: fixed;
  bottom: 20px;
  right: 20px;
  background: #000;
  color: #fff;
  border: none;
  border-radius: 50%;
  width: 60px;
  height: 60px;
  font-size: 24px;
  cursor: pointer;
  box-shadow: 0 4px 10px rgba(0,0,0,0.3);
  z-index: 999;
`;

const MessagesContainer = styled.div`
  flex: 1;
  padding: 15px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
`;

const MessageBubble = styled.div<{ isUser: boolean }>`
  max-width: 80%;
  padding: 10px 15px;
  border-radius: 15px;
  background: ${props => props.isUser ? '#000' : '#f1f1f1'};
  color: ${props => props.isUser ? '#fff' : '#000'};
  align-self: ${props => props.isUser ? 'flex-end' : 'flex-start'};
  font-size: 14px;
  line-height: 1.4;
`;

const ActionGateCard = styled.div`
  margin-top: 10px;
  padding: 15px;
  border: 1px solid #ddd;
  border-radius: 8px;
  background: #fff;
  color: #000;
`;

const ButtonRow = styled.div`
  display: flex;
  gap: 10px;
  margin-top: 10px;
`;

const ActionButton = styled.button<{ primary?: boolean }>`
  flex: 1;
  padding: 8px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  background: ${props => props.primary ? '#000' : '#ddd'};
  color: ${props => props.primary ? '#fff' : '#000'};
  font-weight: bold;
`;

const InputContainer = styled.form`
  display: flex;
  padding: 10px;
  border-top: 1px solid #eee;
`;

const Input = styled.input`
  flex: 1;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 20px;
  outline: none;
  font-size: 14px;
`;

const SendBtn = styled.button`
  background: #000;
  color: #fff;
  border: none;
  border-radius: 20px;
  padding: 0 15px;
  margin-left: 10px;
  cursor: pointer;
  font-weight: bold;
`;

interface Message {
  id: string;
  text: string;
  isUser: boolean;
  pendingAction?: any;
}

export default function CopilotChat() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { id: '1', text: 'Xin chào! Tôi là trợ lý mua sắm. Tôi có thể giúp gì cho bạn?', isUser: false }
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
  }, [messages]);

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
          user_id: 'user-' + sessionId, // Simplified user ID mapping for demo
          session_id: sessionId,
          confirmation_token: token
        })
      });

      const data = await res.json();
      
      setMessages(prev => [...prev, { 
        id: Date.now().toString(), 
        text: data.response || 'Đã hiểu.', 
        isUser: false,
        pendingAction: data.pendingConfirmation || null
      }]);
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { id: Date.now().toString(), text: 'Lỗi kết nối. Vui lòng thử lại.', isUser: false }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirmAction = (token: string, actionDesc: string) => {
    // Optimistic UI update
    setMessages(prev => [...prev, { id: Date.now().toString(), text: `Đã xác nhận: ${actionDesc}`, isUser: true }]);
    sendMessage('', token);
  };

  const handleRejectAction = () => {
    setMessages(prev => [...prev, { id: Date.now().toString(), text: 'Đã hủy thao tác.', isUser: true }]);
  };

  return (
    <>
      <ChatToggleBtn onClick={() => setIsOpen(!isOpen)}>💬</ChatToggleBtn>
      <ChatContainer isOpen={isOpen}>
        <ChatHeader onClick={() => setIsOpen(false)}>
          Shopping Copilot
          <span>✕</span>
        </ChatHeader>
        
        <MessagesContainer>
          {messages.map((msg) => (
            <div key={msg.id} style={{display: 'flex', flexDirection: 'column'}}>
              <MessageBubble isUser={msg.isUser}>{msg.text}</MessageBubble>
              
              {msg.pendingAction && !msg.isUser && (
                <ActionGateCard>
                  <div style={{fontSize: '13px', marginBottom: '5px'}}><strong>Hành động yêu cầu:</strong></div>
                  <div>{msg.pendingAction.humanPrompt}</div>
                  <ButtonRow>
                    <ActionButton primary onClick={() => handleConfirmAction(msg.pendingAction.confirmationToken, msg.pendingAction.humanPrompt)}>
                      Xác nhận
                    </ActionButton>
                    <ActionButton onClick={handleRejectAction}>
                      Hủy bỏ
                    </ActionButton>
                  </ButtonRow>
                </ActionGateCard>
              )}
            </div>
          ))}
          {isLoading && <MessageBubble isUser={false}>...</MessageBubble>}
          <div ref={messagesEndRef} />
        </MessagesContainer>

        <InputContainer onSubmit={(e) => { e.preventDefault(); sendMessage(inputValue); }}>
          <Input 
            value={inputValue} 
            onChange={e => setInputValue(e.target.value)} 
            placeholder="Nhập yêu cầu của bạn..." 
            disabled={isLoading}
          />
          <SendBtn type="submit" disabled={isLoading || !inputValue.trim()}>Gửi</SendBtn>
        </InputContainer>
      </ChatContainer>
    </>
  );
}
