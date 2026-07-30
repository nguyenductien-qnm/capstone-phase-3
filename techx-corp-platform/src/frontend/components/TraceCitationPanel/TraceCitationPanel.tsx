import React, { useState } from 'react';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../ui/collapsible';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { ChevronRight } from 'lucide-react';

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
}

export const TraceCitationPanel: React.FC<TraceCitationPanelProps> = ({ 
  traceId, 
  traceSteps = [], 
  citations = [],
  defaultOpen = false
}) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  if (!traceId && (!traceSteps || traceSteps.length === 0) && (!citations || citations.length === 0)) {
    return null;
  }

  const getStatusVariant = (status: string): "default" | "secondary" | "destructive" | "outline" => {
    if (status === 'blocked' || status === 'error') return 'destructive';
    if (status === 'fallback') return 'secondary';
    if (status === 'pass' || status === 'ok') return 'default';
    return 'outline';
  };

  return (
    <Card className="mt-4 overflow-hidden border-border/50 shadow-sm transition-all hover:shadow-md" data-cy="TraceCitationPanel">
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <div className="w-full flex justify-between items-center p-3">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="flex flex-1 items-center justify-start gap-2 h-auto py-2 px-3 font-semibold text-foreground hover:bg-muted">
              <ChevronRight className={`h-4 w-4 shrink-0 transition-transform duration-200 ${isOpen ? 'rotate-90' : ''}`} />
              AI Evaluation Trace
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
            {traceSteps && traceSteps.length > 0 && (
              <>
                <div className="font-bold text-muted-foreground mt-4 mb-2 uppercase text-xs tracking-wider">Execution Steps</div>
                <div className="space-y-0">
                  {traceSteps.map((step, idx) => {
                    const name = step.stepName || step.step_name || 'Unknown Step';
                    const latency = step.latencyMs ?? step.latency_ms ?? 0;
                    const status = step.status || 'unknown';
                    
                    return (
                      <div key={idx} className="flex flex-col sm:flex-row justify-between py-3 border-b border-border/30 last:border-b-0 gap-2 sm:gap-4">
                        <div className="flex-1 pr-0 sm:pr-4">
                          <span className="text-foreground font-medium text-sm">{name}</span>
                          {step.detail && (
                            <div className="text-xs text-muted-foreground mt-2 bg-muted/50 p-2.5 rounded-md border border-border/50 whitespace-pre-wrap break-all font-mono">
                              {step.detail}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center sm:items-start gap-3 mt-1 sm:mt-0">
                          <span className="text-muted-foreground font-tabular-nums text-xs">{latency}ms</span>
                          <Badge variant={getStatusVariant(status)} className="uppercase text-[10px] h-5">
                            {status}
                          </Badge>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}

            {citations && citations.length > 0 && (
              <>
                <div className="font-bold text-muted-foreground mt-5 mb-3 uppercase text-xs tracking-wider">Grounded Sources</div>
                <ul className="m-0 pl-5 text-sm text-foreground space-y-2 list-disc marker:text-primary/40">
                  {citations.map((c, i) => (
                    <li key={i} className="leading-relaxed">
                      "{c.snippet}" <span className="text-muted-foreground">- <em className="italic">{c.reviewId || c.review_id}</em> ({c.score}★)</span>
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
