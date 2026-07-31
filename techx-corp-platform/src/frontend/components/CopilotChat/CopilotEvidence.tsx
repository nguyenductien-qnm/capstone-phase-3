import { AlertTriangle, CheckCircle2, ShieldCheck, XCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { TraceCitationPanel } from '../TraceCitationPanel/TraceCitationPanel';
import { anonymizeId, buildEvidenceBadges, type CopilotResponse, parseTraceMetadata, safeToolArguments } from './copilotEvidence';

export function CopilotEvidence({ response, onConfirm, onCancel, compact = false, busy = false }: {
  response: CopilotResponse | null;
  onConfirm?: (token: string) => void;
  onCancel?: () => void;
  compact?: boolean;
  busy?: boolean;
}) {
  if (!response) return null;
  const badges = buildEvidenceBadges(response);
  const metadata = parseTraceMetadata(response.traceSteps);
  const pending = response.pendingConfirmation;
  const pendingArguments = safeToolArguments(pending?.argumentsJson);

  return (
    <div className="space-y-3" aria-live="polite" data-cy="CopilotEvidence">
      {badges.length > 0 && <div className="flex flex-wrap gap-1.5">
        {badges.map(label => <Badge key={label} variant={label.includes('Blocked') || label.includes('Degraded') ? 'destructive' : 'outline'}>{label}</Badge>)}
      </div>}

      {pending?.confirmationToken && (
        <Card className="border-amber-500/50 bg-amber-500/5" data-cy="ConfirmationCard">
          <CardContent className="space-y-3 p-4">
            <div className="flex items-start gap-2"><AlertTriangle className="mt-0.5 size-4 text-amber-600" /><div><p className="font-semibold">Confirm before execution</p><p className="text-sm text-muted-foreground">{pending.humanPrompt || pending.toolName}</p>{pendingArguments && <pre className="mt-2 overflow-auto rounded bg-background/70 p-2 text-xs">{pendingArguments}</pre>}</div></div>
            <div className="flex gap-2">
              <Button size="sm" disabled={busy} onClick={() => onConfirm?.(pending.confirmationToken!)} data-cy="ConfirmAction">{busy ? 'Confirming…' : 'Confirm'}</Button>
              <Button size="sm" variant="outline" disabled={busy} onClick={onCancel} data-cy="CancelAction">Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {response.actionsTaken.length > 0 && <div className="space-y-2">
        {response.actionsTaken.map((action, index) => (
          <div key={`${action.toolName}-${index}`} className="grid grid-cols-[1fr_auto] items-center justify-between rounded-lg border p-3 text-sm">
            <span className="flex items-center gap-2">{action.succeeded ? <CheckCircle2 className="size-4 text-emerald-600" /> : <XCircle className="size-4 text-destructive" />}<strong>{action.toolName || 'Tool action'}</strong></span>
            <span className="text-muted-foreground">{action.durationMs ?? 0}ms</span>
            {safeToolArguments(action.argumentsJson) && <pre className="col-span-2 mt-2 w-full overflow-auto rounded bg-muted/40 p-2 text-xs">{safeToolArguments(action.argumentsJson)}</pre>}
          </div>
        ))}
      </div>}

      {!compact && <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
        <EvidenceValue label="Model" value={metadata.modelId || '—'} />
        <EvidenceValue label="Tokens" value={metadata.tokensIn != null || metadata.tokensOut != null ? `${metadata.tokensIn || 0} in / ${metadata.tokensOut || 0} out` : '—'} />
        <EvidenceValue label="Est. cost" value={metadata.costUsd != null ? `$${metadata.costUsd.toFixed(6)}` : '—'} />
        <EvidenceValue label="Outcome" value={metadata.outcome || (response.degraded ? 'fallback' : 'ok')} />
        <EvidenceValue label="User" value={anonymizeId(response.userId)} />
        <EvidenceValue label="Session" value={anonymizeId(response.sessionId)} />
      </div>}

      <TraceCitationPanel traceId={response.traceId} traceSteps={response.traceSteps} citations={response.citations} defaultOpen={!compact} showSummary={false} />
      {response.sourceFingerprint && <p className="flex items-center gap-1 text-xs text-muted-foreground"><ShieldCheck className="size-3" /> Source {response.sourceFingerprint.slice(0, 12)}…{response.similarity ? ` · similarity ${response.similarity.toFixed(3)}` : ''}</p>}
    </div>
  );
}

function EvidenceValue({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border bg-muted/20 p-2"><div className="text-muted-foreground">{label}</div><div className="mt-1 truncate font-medium" title={value}>{value}</div></div>;
}
