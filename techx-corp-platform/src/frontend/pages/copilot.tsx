import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import Layout from '../components/Layout';
import { AssistantRuntimeProvider, useLocalRuntime } from "@assistant-ui/react";
import { Thread } from "../components/assistant-ui/thread";
import { useCopilotAdapter } from '../components/CopilotChat/CopilotRuntime';
import { TraceCitationPanel } from '../components/TraceCitationPanel/TraceCitationPanel';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { MessageSquare, Sparkles, Wand2 } from 'lucide-react';

const promptTemplates = [
  "Can you help me find a good telescope for beginners?",
  "What is the best telescope for astrophotography?",
  "Recommend a cheap telescope for my 10 year old son.",
  "Which mount is better: equatorial or altazimuth?",
  "Do you have any solar filters?"
];

export default function CopilotPage() {
  const [traceData, setTraceData] = useState<{
    traceId?: string;
    traceSteps?: any[];
    citations?: any[];
  } | null>(null);

  const handleResponse = React.useCallback((data: any) => {
    setTraceData({
      traceId: data.traceId,
      traceSteps: data.traceSteps,
      citations: data.citations
    });
  }, []);

  const adapter = useCopilotAdapter(handleResponse);

  const runtime = useLocalRuntime(adapter);

  const handlePromptClick = (prompt: string) => {
    runtime.thread.append({
      role: 'user',
      content: [{ type: 'text', text: prompt }]
    });
  };

  return (
    <Layout>
      <Head>
        <title>Shopping Copilot | TechX Corp</title>
      </Head>
      <div className="container mx-auto max-w-7xl px-4 py-8 h-[calc(100vh-80px)] flex flex-col">
        <div className="mb-6 flex items-center gap-3">
          <div className="bg-primary/10 p-2 rounded-xl">
            <Sparkles className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Shopping Copilot</h1>
            <p className="text-muted-foreground text-sm">Your intelligent assistant for astronomy gear</p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 flex-1 min-h-0">
          {/* Left Sidebar: Tracing */}
          <div className="lg:col-span-1 flex flex-col gap-4 overflow-y-auto pr-2 pb-8">
            <Card className="border-primary/20 shadow-sm bg-gradient-to-b from-card to-card/50">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <ActivityIcon className="w-5 h-5 text-primary" />
                  LLM Observability
                </CardTitle>
                <CardDescription>Real-time tracing of AI actions</CardDescription>
              </CardHeader>
              <CardContent>
                {traceData ? (
                  <TraceCitationPanel 
                    traceId={traceData.traceId} 
                    traceSteps={traceData.traceSteps || []}
                    citations={traceData.citations || []}
                  />
                ) : (
                  <div className="text-sm text-muted-foreground bg-muted/30 p-4 rounded-lg border border-border/50 border-dashed text-center">
                    Ask a question to see the AI trace and safety guardrails in action.
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Center: Chat Interface */}
          <div className="lg:col-span-2 flex flex-col rounded-2xl border shadow-sm overflow-hidden bg-card min-h-[500px]">
            <AssistantRuntimeProvider runtime={runtime}>
              <div className="flex-1 overflow-hidden [&_.aui-thread-viewport]:h-full [&_.aui-thread-viewport]:p-4 [&_.aui-root]:h-full">
                <Thread />
              </div>
            </AssistantRuntimeProvider>
          </div>

          {/* Right Sidebar: Prompt Templates */}
          <div className="lg:col-span-1 flex flex-col gap-4 overflow-y-auto pl-2 pb-8">
            <Card className="border-border/50 shadow-none bg-muted/10">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Wand2 className="w-5 h-5 text-indigo-500" />
                  Try Asking
                </CardTitle>
                <CardDescription>Sample prompts to explore</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {promptTemplates.map((prompt, index) => (
                  <Button 
                    key={index}
                    variant="outline"
                    className="justify-start h-auto py-3 px-4 text-left font-normal border-border/60 hover:bg-primary/5 hover:border-primary/30 transition-colors whitespace-normal"
                    onClick={() => handlePromptClick(prompt)}
                  >
                    <MessageSquare className="w-4 h-4 mr-3 flex-shrink-0 text-muted-foreground" />
                    <span className="text-sm">{prompt}</span>
                  </Button>
                ))}
              </CardContent>
            </Card>
          </div>
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
