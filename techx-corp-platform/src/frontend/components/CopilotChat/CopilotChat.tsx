import React, { useEffect, useState } from 'react';
import SessionGateway from '../../gateways/Session.gateway';
import { useQueryClient } from '@tanstack/react-query';
import { MandateBadges } from '../MandateExperience/MandateExperience';
import { MessageSquare, Sparkles, X } from 'lucide-react';
import { useLocalRuntime, AssistantRuntimeProvider } from "@assistant-ui/react";
import { Thread } from "../assistant-ui/thread";
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { useCopilotAdapter } from './CopilotRuntime';
import { CopilotEvidence } from './CopilotEvidence';
import { createConversationId } from './copilotEvidence';

export default function CopilotChat() {
  const [isOpen, setIsOpen] = useState(false);
  const [userId, setUserId] = useState('anonymous');
  const [sessionId] = useState(createConversationId);
  const queryClient = useQueryClient();

  useEffect(() => setUserId(SessionGateway.getSession().userId || 'anonymous'), []);
  const { adapter, latestResponse, isConfirming, confirm, cancelConfirmation } = useCopilotAdapter(
    () => queryClient.invalidateQueries({ queryKey: ['cart'] }),
    { userId, sessionId, surface: 'Floating Copilot' },
  );
  const runtime = useLocalRuntime(adapter);
  const confirmAction = (token: string) => {
    confirm(token);
    runtime.thread.append({ role: 'user', content: [{ type: 'text', text: 'Confirm this action' }] });
  };

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <div className="fixed bottom-6 right-8 z-[9999] font-sans">
        <PopoverTrigger className="flex h-16 w-16 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-2xl shadow-primary/40 transition-transform duration-300 hover:scale-110 data-[state=open]:scale-0 data-[state=open]:opacity-0" aria-label="Open Shopping Copilot"><MessageSquare className="h-7 w-7" /></PopoverTrigger>
      </div>
      <PopoverContent side="top" align="end" sideOffset={16} className="flex h-[650px] max-h-[calc(100vh-100px)] w-[400px] flex-col overflow-hidden rounded-3xl border-border/50 bg-background/80 p-0 shadow-2xl backdrop-blur-2xl">
        <div className="relative flex shrink-0 items-center justify-between overflow-hidden border-b border-white/10 bg-gradient-to-r from-primary via-primary/80 to-indigo-600 p-5 text-primary-foreground">
          <div className="relative z-10 flex flex-col">
            <div className="flex items-center gap-2"><Sparkles className="h-5 w-5 text-yellow-300" /><h3 className="text-lg font-bold tracking-tight">Shopping Copilot</h3></div>
            <span className="mt-1 text-xs text-primary-foreground/80">Grounded · observable · confirmation-gated</span>
            <div className="mt-2"><MandateBadges compact inverse /></div>
          </div>
          <Button variant="ghost" size="icon" onClick={() => setIsOpen(false)} className="relative z-10 h-9 w-9 rounded-full border border-white/10 bg-black/10 text-white hover:bg-black/20 hover:text-white"><X className="h-4 w-4" /><span className="sr-only">Close Copilot</span></Button>
        </div>
        {latestResponse && <div className="max-h-52 shrink-0 overflow-auto border-b bg-background/90 p-3"><CopilotEvidence compact response={latestResponse} busy={isConfirming} onConfirm={confirmAction} onCancel={cancelConfirmation} /></div>}
        <div className="relative flex-1 overflow-hidden"><AssistantRuntimeProvider runtime={runtime}><Thread /></AssistantRuntimeProvider></div>
      </PopoverContent>
    </Popover>
  );
}
