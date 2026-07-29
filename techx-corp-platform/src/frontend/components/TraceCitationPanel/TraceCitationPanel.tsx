import { useState } from 'react';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

export interface TraceStep { stepName?: string; latencyMs?: number; status?: string; detail?: string; step_name?: string; latency_ms?: number; }
export interface Citation { reviewId?: string; review_id?: string; snippet?: string; score?: string; }
export interface TraceCitationPanelProps { traceId?: string; traceSteps?: TraceStep[]; citations?: Citation[]; defaultOpen?: boolean; }

export const TraceCitationPanel = ({ traceId, traceSteps = [], citations = [], defaultOpen = false }: TraceCitationPanelProps) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  if (!traceId && !traceSteps.length && !citations.length) return null;

  return (
    <div className="mt-3 rounded-lg border bg-muted/30 p-3 font-mono text-xs" data-cy="TraceCitationPanel">
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <div className="flex items-center justify-between">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="h-auto gap-1 p-0 text-muted-foreground hover:text-foreground">
              ⚡ AI Trace {isOpen ? '▼' : '▶'}
            </Button>
          </CollapsibleTrigger>
          {traceId && (
            <span className="cursor-pointer text-blue-600 hover:underline" onClick={e => { e.stopPropagation(); navigator.clipboard?.writeText(traceId); }}>
              {traceId.slice(0, 8)}...
            </span>
          )}
        </div>
        <CollapsibleContent className="mt-2 space-y-3">
          {traceSteps.length > 0 && (
            <div>
              <h4 className="mb-1 font-bold uppercase tracking-wide">Steps</h4>
              {traceSteps.map((step, idx) => {
                const name = step.stepName || step.step_name || 'Unknown';
                const latency = step.latencyMs ?? step.latency_ms ?? 0;
                const s = step.status || 'unknown';
                return (
                  <div key={idx} className="flex justify-between border-b border-dashed py-1 last:border-0">
                    <div className="flex-1 pr-3"><span>{name}</span>
                      {step.detail && <pre className="mt-1 whitespace-pre-wrap rounded bg-muted p-1 text-[11px] text-muted-foreground">{step.detail}</pre>}
                    </div>
                    <div className="flex gap-3 text-right"><span className="text-muted-foreground">{latency}ms</span>
                      <Badge variant={s === 'blocked' ? 'destructive' : s === 'pass' || s === 'ok' ? 'default' : 'secondary'} className="text-[10px]">{s.toUpperCase()}</Badge></div>
                  </div>
                );
              })}
            </div>
          )}
          {citations.length > 0 && (
            <div><h4 className="mb-1 font-bold uppercase tracking-wide">Sources</h4>
              <ul className="space-y-1 pl-4">{citations.map((c, i) => <li key={i}>"{c.snippet}" — {c.reviewId || c.review_id} ({c.score}★)</li>)}</ul>
            </div>
          )}
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
};
