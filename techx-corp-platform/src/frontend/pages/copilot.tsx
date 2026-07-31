import React, { useEffect, useState } from 'react';
import Head from 'next/head';
import Layout from '../components/Layout';
import { AssistantRuntimeProvider, useLocalRuntime } from "@assistant-ui/react";
import { Thread } from "../components/assistant-ui/thread";
import { useCopilotAdapter } from '../components/CopilotChat/CopilotRuntime';
import { CopilotEvidence } from '../components/CopilotChat/CopilotEvidence';
import { COPILOT_DEMO_CASES, createConversationId } from '../components/CopilotChat/copilotEvidence';
import SessionGateway from '../gateways/Session.gateway';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { MessageSquare, RefreshCw, Sparkles, UserRoundCog, Wand2 } from 'lucide-react';



export default function CopilotPage() {
  const [userId, setUserId] = useState('anonymous');
  const [sessionId, setSessionId] = useState(createConversationId);

  useEffect(() => setUserId(SessionGateway.getSession().userId || 'anonymous'), []);

  const { adapter, latestResponse, isConfirming, confirm, cancelConfirmation } = useCopilotAdapter(undefined, { userId, sessionId, surface: 'Shopping Copilot' });
  const runtime = useLocalRuntime(adapter);
  const evidence = latestResponse?.userId === userId && latestResponse?.sessionId === sessionId ? latestResponse : null;

  const appendPrompt = (prompt: string) => runtime.thread.append({ role: 'user', content: [{ type: 'text', text: prompt }] });
  const resetView = () => runtime.thread.reset();
  const startSession = (nextUserId = userId) => {
    setUserId(nextUserId);
    setSessionId(createConversationId());
    resetView();
  };
  const confirmAction = (token: string) => {
    confirm(token);
    appendPrompt('Confirm this action');
  };

  return (
    <Layout>
      <Head><title>Shopping Copilot | TechX Corp</title></Head>
      <div className="container mx-auto flex min-h-[calc(100vh-80px)] max-w-[1440px] flex-col px-4 py-6 lg:h-[calc(100vh-5rem)] lg:min-h-[680px] lg:py-6">
        <div className="mb-6 flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-primary/10 p-2"><Sparkles className="h-6 w-6 text-primary" /></div>
            <div><h1 className="text-2xl font-bold tracking-tight">Shopping Copilot</h1><p className="text-sm text-muted-foreground">Grounded answers, confirmation-gated actions and live evidence</p></div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={() => startSession()}><RefreshCw className="mr-2 size-4" />New conversation</Button>
            <Button size="sm" variant="outline" onClick={() => startSession()}><RefreshCw className="mr-2 size-4" />Same user / new session</Button>
            <Button size="sm" variant="outline" onClick={() => startSession(`demo-${createConversationId()}`)}><UserRoundCog className="mr-2 size-4" />Different user</Button>
          </div>
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(340px,420px)]">
          <div className="order-1 flex min-h-[560px] min-w-0 flex-col overflow-hidden rounded-2xl border bg-card shadow-sm lg:min-h-0">
            <AssistantRuntimeProvider runtime={runtime}><div className="flex-1 overflow-hidden [&_.aui-root]:h-full [&_.aui-thread-viewport]:h-full [&_.aui-thread-viewport]:p-4"><Thread /></div></AssistantRuntimeProvider>
          </div>

          <aside className="order-2 grid min-h-0 gap-4 lg:grid-rows-[minmax(0,1fr)_minmax(0,1fr)]">
            <Card className="flex min-h-0 flex-col overflow-hidden border-primary/20">
              <CardHeader className="pb-3"><CardTitle className="flex items-center gap-2 text-lg"><ActivityIcon className="h-5 w-5 text-primary" />AI Evidence</CardTitle><CardDescription>Request-derived proof, never fixed readiness badges</CardDescription></CardHeader>
              <Separator />
              <ScrollArea className="min-h-0 flex-1"><CardContent className="pt-4">
                {evidence ? <CopilotEvidence response={evidence} busy={isConfirming} onConfirm={confirmAction} onCancel={cancelConfirmation} /> : <div className="rounded-lg border border-dashed bg-muted/30 p-4 text-center text-sm text-muted-foreground">Ask a question to populate trace, cache, grounding and tool evidence.</div>}
              </CardContent></ScrollArea>
            </Card>

            <Card className="flex min-h-0 flex-col overflow-hidden border-border/50 bg-muted/10 shadow-none">
              <CardHeader className="pb-3"><CardTitle className="flex items-center gap-2 text-lg"><Wand2 className="h-5 w-5 text-indigo-500" />AIE demo cases</CardTitle><CardDescription>Core, top-race, safety, cache and memory prompts</CardDescription></CardHeader>
              <Separator />
              <ScrollArea className="min-h-0 flex-1"><CardContent className="space-y-5 pt-4">
                {COPILOT_DEMO_CASES.map(group => (
                  <section key={group.title} aria-label={group.title}>
                    <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{group.title}</h2>
                    <div className="flex flex-col gap-2">
                      {group.cases.map(item => (
                        <div key={`${group.title}-${item.label}`} className="rounded-lg border bg-background/50 p-2">
                          <div className="px-1 pb-1 text-xs font-medium text-foreground">{item.label}</div>
                          <div className="flex flex-col gap-1">
                            {item.prompts.map((prompt, index) => (
                              <Button key={prompt} variant="ghost" className="h-auto justify-start whitespace-normal px-2 py-2 text-left font-normal" onClick={() => appendPrompt(prompt)}>
                                <MessageSquare className="mr-2 size-4 shrink-0 text-muted-foreground" />
                                <span className="text-xs text-muted-foreground">{item.prompts.length > 1 ? `${index + 1}. ` : ''}{prompt}</span>
                              </Button>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>
                ))}
                <p className="text-xs text-muted-foreground">For multi-turn cases, click prompts 1 then 2 in the same session. Repeat any single-turn prompt to show an exact cache hit; use session controls to show isolation.</p>
              </CardContent></ScrollArea>
            </Card>
          </aside>
        </div>
      </div>
    </Layout>
  );
}

function ActivityIcon(props: any) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </svg>
  )
}
