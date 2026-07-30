import { type ChatModelAdapter } from "@assistant-ui/react";
import SessionGateway from "../../gateways/Session.gateway";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { type CopilotResponse, requestCopilot, saveEvidence } from './copilotEvidence';

type Options = { userId?: string; sessionId?: string; surface?: string };

export const useCopilotAdapter = (onResponse?: (data: CopilotResponse) => void, options: Options = {}) => {
  const confirmationToken = useRef('');
  const identity = useRef({ userId: options.userId, sessionId: options.sessionId });
  identity.current = { userId: options.userId, sessionId: options.sessionId };
  const [latestResponse, setLatestResponse] = useState<CopilotResponse | null>(null);
  const [isConfirming, setIsConfirming] = useState(false);

  useEffect(() => {
    confirmationToken.current = '';
    setLatestResponse(null);
    setIsConfirming(false);
  }, [options.userId, options.sessionId]);

  const recordResponse = useCallback((data: CopilotResponse, userId: string, sessionId: string) => {
    if (identity.current.userId !== userId || identity.current.sessionId !== sessionId) return;
    const recorded = { ...data, userId, sessionId, surface: options.surface, recordedAt: new Date().toISOString() };
    setLatestResponse(recorded);
    onResponse?.(recorded);
    saveEvidence(recorded);
  }, [onResponse, options.surface]);

  const adapter: ChatModelAdapter = useMemo(() => ({
    async *run({ messages, abortSignal }: any) {
      const lastMessage = messages[messages.length - 1];
      if (!lastMessage || lastMessage.role !== "user") return;

      const userId = options.userId || SessionGateway.getSession().userId || 'anonymous';
      const sessionId = options.sessionId || userId;
      const token = confirmationToken.current;
      confirmationToken.current = '';
      const question = token ? '' : lastMessage.content.map((part: any) => part.text || '').join(' ').trim();
      const data = await requestCopilot({ question, userId, sessionId, confirmationToken: token, signal: abortSignal });
      recordResponse(data, userId, sessionId);
      setIsConfirming(false);
      yield { content: [{ type: "text" as const, text: data.response }] };
    }
  }), [options.userId, options.sessionId, recordResponse]);

  return {
    adapter,
    latestResponse,
    isConfirming,
    confirm: (token: string) => { confirmationToken.current = token; setIsConfirming(true); },
    cancelConfirmation: () => { confirmationToken.current = ''; setIsConfirming(false); setLatestResponse(current => current ? { ...current, pendingConfirmation: undefined } : current); },
  };
};
