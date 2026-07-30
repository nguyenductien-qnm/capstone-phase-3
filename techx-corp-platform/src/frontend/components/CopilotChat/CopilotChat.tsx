import React, { useState, useEffect, useMemo } from 'react';
import SessionGateway from '../../gateways/Session.gateway';
import { useQueryClient } from '@tanstack/react-query';
import { MandateBadges } from '../MandateExperience/MandateExperience';
import { MessageSquare, Sparkles, X } from 'lucide-react';
import { useLocalRuntime, AssistantRuntimeProvider, type ChatModelAdapter } from "@assistant-ui/react";
import { Thread } from "../assistant-ui/thread";
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Card } from '@/components/ui/card';

export default function CopilotChat() {
  const [isOpen, setIsOpen] = useState(false);
  const [sessionId, setSessionId] = useState('');
  const queryClient = useQueryClient();

  useEffect(() => {
    setSessionId(SessionGateway.getSession().userId);
  }, []);

  const chatAdapter: ChatModelAdapter = useMemo(() => ({
    async *run({ messages, abortSignal }: any) {
      const lastMessage = messages[messages.length - 1];
      if (!lastMessage || lastMessage.role !== "user") return;

      const text = lastMessage.content.map((c: any) => c.text).join(" ");
      
      try {
        const res = await fetch('/api/copilot', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question: text,
            user_id: sessionId,
            session_id: sessionId,
            confirmation_token: ''
          }),
          signal: abortSignal,
        });

        const data = await res.json();
        queryClient.invalidateQueries({ queryKey: ['cart'] });

        if (data.pendingConfirmation) {
          yield {
            content: [
              { type: "text" as const, text: data.response || "Confirmation required." },
              { type: "text" as const, text: `\n\nPending Action: ${data.pendingConfirmation.humanPrompt}` }
            ]
          };
        } else {
          let extra = "";
          if (data.citations && data.citations.length > 0) {
            extra = "\n\n(Citations included in response)";
          }
          yield { content: [{ type: "text" as const, text: (data.response || "I could not process that request.") + extra }] };
        }
      } catch (err) {
        yield { content: [{ type: "text" as const, text: "Connection error. Please try again." }] };
      }
    }
  }), [sessionId, queryClient]);

  const runtime = useLocalRuntime(chatAdapter);

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <div className="fixed bottom-6 right-8 z-[9999] font-sans">
        <PopoverTrigger 
          className="w-16 h-16 rounded-full bg-primary text-primary-foreground shadow-2xl shadow-primary/40 transition-transform duration-300 hover:scale-110 hover:shadow-primary/60 data-[state=open]:scale-0 data-[state=open]:opacity-0 flex items-center justify-center"
          aria-label="Open Shopping Copilot"
        >
          <MessageSquare className="w-7 h-7" />
        </PopoverTrigger>
      </div>
      <PopoverContent 
        side="top" 
        align="end" 
        sideOffset={16}
        className="w-[400px] h-[650px] max-h-[calc(100vh-100px)] p-0 bg-background/80 backdrop-blur-2xl border-border/50 rounded-3xl shadow-2xl flex flex-col overflow-hidden data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2"
      >
        <div className="bg-gradient-to-r from-primary via-primary/80 to-indigo-600 text-primary-foreground p-5 flex flex-row justify-between items-center border-b border-white/10 relative overflow-hidden shrink-0">
          <div className="absolute top-0 right-0 w-32 h-32 bg-white/10 rounded-full blur-2xl -translate-y-1/2 translate-x-1/2" />
          <div className="flex flex-col relative z-10">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-yellow-300" />
              <h3 className="m-0 text-lg font-bold tracking-tight">Shopping Copilot</h3>
            </div>
            <span className="text-xs text-primary-foreground/80 mt-1 flex items-center before:content-[''] before:inline-block before:w-1.5 before:h-1.5 before:rounded-full before:bg-green-400 before:mr-1.5">
              Powered by Assistant-UI
            </span>
            <div className="mt-2">
              <MandateBadges compact />
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsOpen(false)}
            className="bg-black/10 hover:bg-black/20 hover:text-white backdrop-blur-md border border-white/10 w-9 h-9 rounded-full text-white relative z-10"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>
        
        <div className="flex-1 overflow-hidden relative">
          <AssistantRuntimeProvider runtime={runtime}>
            <Thread />
          </AssistantRuntimeProvider>
        </div>
      </PopoverContent>
    </Popover>
  );
}
