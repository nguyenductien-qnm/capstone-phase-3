import React, { useState } from 'react';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../ui/collapsible';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { ChevronRight } from 'lucide-react';
import { buildEvidenceBadges, parseTraceMetadata } from '../CopilotChat/copilotEvidence';
import { deriveTraceEvidence, safeCitationId, safeCitationSnippet, safeTraceDetails, safeTraceStepName } from './traceEvidence';

export interface TraceStep {
  stepName?: string;
  latencyMs?: number;
  status?: string;
  detail?: string;
  // in protobuf, snake_case becomes camelCase
  step_name?: string;
  latency_ms?: number;
}

export interface Citation {
  reviewId?: string;
  review_id?: string;
  snippet?: string;
  score?: string;
}

export interface TraceCitationPanelProps {
  traceId?: string;
  traceSteps?: TraceStep[];
  citations?: Citation[];
  defaultOpen?: boolean;
  showSummary?: boolean;
}

export const TraceCitationPanel: React.FC<TraceCitationPanelProps> = ({ 
  traceId, 
  traceSteps = [], 
  citations = [],
  defaultOpen = false,
  showSummary = true
}) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const badges = buildEvidenceBadges({ traceSteps, citations, ...deriveTraceEvidence(traceSteps) });
  const metadata = parseTraceMetadata(traceSteps);
  const totalLatency = traceSteps.reduce((sum, step) => sum + (step.latencyMs ?? step.latency_ms ?? 0), 0);

  if (!traceId && (!traceSteps || traceSteps.length === 0) && (!citations || citations.length === 0)) {
    return null;
  }

  const getStatusVariant = (status: string): "default" | "secondary" | "destructive" | "outline" => {
    if (status === 'blocked' || status === 'error') return 'destructive';
    if (status === 'fallback' || status === 'pending_confirmation') return 'secondary';
    if (status === 'pass' || status === 'ok' || status === 'hit_exact' || status === 'hit_semantic') return 'default';
    return 'outline';
  };

  const getStatusLabel = (status: string) => ({
    pass: 'Passed',
    ok: 'Completed',
    blocked: 'Blocked',
    error: 'Error',
    fallback: 'Fallback',
    pending_confirmation: 'Needs confirmation',
    deduplicated: 'Deduplicated',
    hit_exact: 'Exact cache hit',
    hit_semantic: 'Semantic cache hit',
    miss: 'Cache miss',
    bypass: 'Cache bypass',
    abstained: 'Abstained',
  }[status] || 'Unknown');

  return (
    <Card className="mt-4 overflow-hidden border-border/50 shadow-sm transition-all hover:shadow-md" data-cy="TraceCitationPanel">
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <div className="w-full flex justify-between items-center p-3">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="flex flex-1 items-center justify-start gap-2 h-auto py-2 px-3 font-semibold text-foreground hover:bg-muted">
              <ChevronRight className={`h-4 w-4 shrink-0 transition-transform duration-200 ${isOpen ? 'rotate-90' : ''}`} />
              AI Decision Trace
            </Button>
          </CollapsibleTrigger>
          {traceId && (
            <Button 
              variant="outline" 
              size="sm"
              className="ml-2 font-mono text-xs h-7 text-primary hover:text-primary hover:bg-primary/10"
              onClick={(e) => {
                e.stopPropagation();
                navigator.clipboard?.writeText(traceId);
              }}
              title="Click to copy Trace ID"
              aria-label="Copy trace ID"
            >
              {traceId.slice(0, 8)}...
            </Button>
          )}
        </div>
        
        <CollapsibleContent>
          <CardContent className="px-5 pb-5 pt-0 border-t border-border/50">
            {showSummary && (badges.length > 0 || Object.values(metadata).some(value => value !== undefined)) && (
              <div className="mt-4 flex flex-wrap items-center gap-2">
                {badges.map(label => <Badge key={label} variant={label === 'Blocked' ? 'destructive' : 'outline'}>{label}</Badge>)}
                {metadata.modelId && <Badge variant="secondary">{metadata.modelId}</Badge>}
                {metadata.tokensIn !== undefined && <Badge variant="outline">{metadata.tokensIn} tokens in</Badge>}
                {metadata.tokensOut !== undefined && <Badge variant="outline">{metadata.tokensOut} tokens out</Badge>}
                {metadata.costUsd !== undefined && <Badge variant="outline">${metadata.costUsd.toFixed(8)}</Badge>}
                {metadata.outcome && <Badge variant="outline">Outcome: {metadata.outcome}</Badge>}
                {metadata.timestamp && <span className="text-xs text-muted-foreground">{metadata.timestamp}</span>}
                <span className="text-xs text-muted-foreground">{totalLatency}ms</span>
              </div>
            )}
            {traceSteps && traceSteps.length > 0 && (
              <>
                <div className="mt-4 mb-2">
                  <div className="font-bold text-muted-foreground uppercase text-xs tracking-wider">Decision reasoning</div>
                  <p className="mt-1 text-xs text-muted-foreground">Safe decision summary only; hidden chain-of-thought is never exposed.</p>
                </div>
                <ol className="space-y-0">
                  {traceSteps.map((step, idx) => {
                    const name = safeTraceStepName(step.stepName || step.step_name);
                    const latency = step.latencyMs ?? step.latency_ms ?? 0;
                    const status = (step.status || 'unknown').toLowerCase();
                    const details = safeTraceDetails(step.detail);
                    
                    return (
                      <li key={idx} className="flex gap-3 border-b border-border/30 py-3 last:border-b-0" aria-label={`Step ${idx + 1}: ${name}`}>
                        <span aria-hidden="true" className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold text-muted-foreground">{idx + 1}</span>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                            <span className="text-sm font-medium text-foreground">{name}</span>
                            <div className="flex items-center gap-3">
                              <span className="font-tabular-nums text-xs text-muted-foreground">{latency}ms</span>
                              <Badge variant={getStatusVariant(status)} className="h-5 text-[10px] uppercase">
                                {getStatusLabel(status)}
                              </Badge>
                            </div>
                          </div>
                          {details.length > 0 && (
                            <details className="mt-2 rounded-md border border-border/50 bg-muted/30 px-3 py-2">
                              <summary className="cursor-pointer text-xs font-medium text-muted-foreground">Technical details</summary>
                              <dl className="mt-2 grid gap-1 text-xs sm:grid-cols-2">
                                {details.map(detail => (
                                  <div key={detail.label} className="flex min-w-0 gap-2">
                                    <dt className="shrink-0 text-muted-foreground">{detail.label}:</dt>
                                    <dd className="truncate font-mono text-foreground">{detail.value}</dd>
                                  </div>
                                ))}
                              </dl>
                            </details>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ol>
              </>
            )}

            {citations && citations.length > 0 && (
              <>
                <div className="font-bold text-muted-foreground mt-5 mb-3 uppercase text-xs tracking-wider">Grounded Sources</div>
                <ul className="m-0 pl-5 text-sm text-foreground space-y-2 list-disc marker:text-primary/40">
                  {citations.map((c, i) => (
                    <li key={i} className="leading-relaxed">
                      "{safeCitationSnippet(c.snippet)}" <span className="text-muted-foreground">- <em className="italic">{safeCitationId(c.reviewId || c.review_id)}</em> ({c.score}★)</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
};
