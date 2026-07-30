export type PendingConfirmation = {
  toolName?: string;
  argumentsJson?: string;
  humanPrompt?: string;
  confirmationToken?: string;
  expiresAtUnix?: number;
};

export type ToolAction = {
  toolName?: string;
  argumentsJson?: string;
  succeeded?: boolean;
  startedAtUnix?: number;
  durationMs?: number;
};

export type CopilotResponse = {
  response: string;
  pendingConfirmation?: PendingConfirmation;
  actionsTaken: ToolAction[];
  degraded: boolean;
  traceId?: string;
  citations: Array<{ reviewId?: string; review_id?: string; snippet?: string; score?: string }>;
  traceSteps: Array<{ stepName?: string; step_name?: string; latencyMs?: number; latency_ms?: number; status?: string; detail?: string }>;
  cacheStatus?: string;
  similarity?: number;
  sourceFingerprint?: string;
  recordedAt?: string;
  userId?: string;
  sessionId?: string;
  surface?: string;
};

type CopilotRequest = {
  question: string;
  userId: string;
  sessionId: string;
  confirmationToken?: string;
  signal?: AbortSignal;
  fetcher?: typeof fetch;
};

const fallbackResponse = (): CopilotResponse => ({
  response: 'The AI service is temporarily unavailable. No action was taken. Please try again shortly.',
  actionsTaken: [],
  citations: [],
  traceSteps: [],
  degraded: true,
  cacheStatus: 'bypass',
});

export const createConversationId = () =>
  globalThis.crypto?.randomUUID?.() ?? `session-${Date.now()}-${Math.random().toString(36).slice(2)}`;

export async function requestCopilot({ question, userId, sessionId, confirmationToken = '', signal, fetcher = fetch }: CopilotRequest): Promise<CopilotResponse> {
  try {
    const response = await fetcher('/api/copilot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, user_id: userId, session_id: sessionId, confirmation_token: confirmationToken }),
      signal,
    });
    if (!response.ok) return fallbackResponse();
    const data = await response.json();
    return {
      response: data.response || 'I could not process that request.',
      pendingConfirmation: data.pendingConfirmation,
      actionsTaken: Array.isArray(data.actionsTaken) ? data.actionsTaken : [],
      degraded: Boolean(data.degraded),
      traceId: data.traceId,
      citations: Array.isArray(data.citations) ? data.citations : [],
      traceSteps: Array.isArray(data.traceSteps) ? data.traceSteps : [],
      cacheStatus: data.cacheStatus,
      similarity: data.similarity,
      sourceFingerprint: data.sourceFingerprint,
    };
  } catch {
    return fallbackResponse();
  }
}

const statusLabels: Record<string, string> = {
  hit_exact: 'Exact cache hit',
  hit_semantic: 'Semantic cache hit',
  miss: 'Cache miss',
  bypass: 'Cache bypass',
};

export function buildEvidenceBadges(data: Partial<CopilotResponse>): string[] {
  const statuses = (data.traceSteps || []).map(step => String(step.status || '').toLowerCase());
  const abstained = statuses.includes('abstained') || statuses.includes('abstain') || /(?:no|not enough|insufficient) (?:relevant )?(?:information|evidence)/i.test(data.response || '');
  return [
    data.citations?.length ? 'Grounded' : '',
    statuses.includes('blocked') ? 'Blocked' : '',
    abstained ? 'Abstained' : '',
    data.pendingConfirmation?.confirmationToken ? 'Confirmation required' : '',
    data.actionsTaken?.some(action => action.succeeded) ? 'Executed' : '',
    data.cacheStatus ? statusLabels[data.cacheStatus] || data.cacheStatus : '',
    data.degraded ? 'Degraded / fallback' : '',
  ].filter(Boolean);
}

export type TraceMetadata = {
  modelId?: string;
  tokensIn?: number;
  tokensOut?: number;
  costUsd?: number;
  outcome?: string;
  timestamp?: string;
};

export function parseTraceMetadata(steps: CopilotResponse['traceSteps'] = []): TraceMetadata {
  return steps.reduce<TraceMetadata>((metadata, step) => {
    try {
      const detail = JSON.parse(step.detail || '{}');
      return {
        modelId: metadata.modelId ?? detail.model_id ?? detail.modelId ?? detail.routed_model,
        tokensIn: metadata.tokensIn ?? detail.tokens_in ?? detail.tokensIn ?? detail.input_tokens,
        tokensOut: metadata.tokensOut ?? detail.tokens_out ?? detail.tokensOut ?? detail.output_tokens,
        costUsd: metadata.costUsd ?? detail.cost_usd ?? detail.costUsd ?? detail.estimated_cost_usd,
        outcome: metadata.outcome ?? detail.outcome,
        timestamp: metadata.timestamp ?? detail.timestamp ?? detail.timestamp_utc,
      };
    } catch {
      return metadata;
    }
  }, {});
}

export const anonymizeId = (value?: string) => value ? `${value.slice(0, 4)}…${value.slice(-4)}` : '—';

export function safeToolArguments(value?: string): string {
  if (!value) return '';
  try {
    const parsed = JSON.parse(value);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return '';
    const allowed = ['product_id', 'quantity', 'query', 'category'];
    const safe = Object.fromEntries(allowed.filter(key => key in parsed).map(key => [key, String(parsed[key]).slice(0, 120)]));
    return Object.keys(safe).length ? JSON.stringify(safe, null, 2) : '';
  } catch {
    return '';
  }
}

const EVIDENCE_KEY = 'aie-evidence-v1';
export type EvidenceRecord = CopilotResponse & { recordedAt: string; userId: string; sessionId: string; surface?: string };

export function saveEvidence(record: EvidenceRecord) {
  if (typeof window === 'undefined') return;
  const metadata = parseTraceMetadata(record.traceSteps);
  const sanitized: EvidenceRecord = {
    ...record,
    response: '',
    pendingConfirmation: undefined,
    citations: record.citations.map(citation => ({ reviewId: citation.reviewId || citation.review_id })),
    actionsTaken: record.actionsTaken.map(action => ({ toolName: action.toolName, succeeded: action.succeeded, durationMs: action.durationMs })),
    traceSteps: record.traceSteps.map((step, index) => ({ ...step, detail: index === 0 ? JSON.stringify(metadata) : '' })),
  };
  const records = loadEvidence();
  try { window.sessionStorage.setItem(EVIDENCE_KEY, JSON.stringify([...records.slice(-99), sanitized])); } catch { /* evidence is best-effort */ }
}

export function loadEvidence(): EvidenceRecord[] {
  if (typeof window === 'undefined') return [];
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(EVIDENCE_KEY) || '[]');
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(item => item && typeof item === 'object').map(item => ({
      ...item,
      response: typeof item.response === 'string' ? item.response : '',
      actionsTaken: Array.isArray(item.actionsTaken) ? item.actionsTaken : [],
      citations: Array.isArray(item.citations) ? item.citations : [],
      traceSteps: Array.isArray(item.traceSteps) ? item.traceSteps : [],
      degraded: Boolean(item.degraded),
      recordedAt: typeof item.recordedAt === 'string' ? item.recordedAt : new Date(0).toISOString(),
      userId: typeof item.userId === 'string' ? item.userId : 'unknown',
      sessionId: typeof item.sessionId === 'string' ? item.sessionId : 'unknown',
    }));
  } catch {
    return [];
  }
}

export function aggregateEvidence(records: EvidenceRecord[]) {
  const latencies = records.map(record => record.traceSteps.reduce((sum, step) => sum + (step.latencyMs ?? step.latency_ms ?? 0), 0)).filter(Boolean).sort((a, b) => a - b);
  const percentile = (p: number) => latencies.length ? latencies[Math.min(latencies.length - 1, Math.ceil(latencies.length * p) - 1)] : 0;
  const metadata = records.map(record => parseTraceMetadata(record.traceSteps));
  const modelCalls = metadata.filter(item => item.modelId);
  const totalCost = metadata.reduce((sum, item) => sum + (item.costUsd || 0), 0);
  const cacheable = records.filter(record => record.cacheStatus);
  const totalTokens = metadata.reduce((sum, item) => sum + (item.tokensIn || 0) + (item.tokensOut || 0), 0);
  return {
    requests: records.length,
    p50LatencyMs: percentile(0.5),
    p95LatencyMs: percentile(0.95),
    costPerRequest: modelCalls.length ? totalCost / modelCalls.length : 0,
    totalTokens,
    cacheHitRate: cacheable.length ? cacheable.filter(record => record.cacheStatus?.startsWith('hit_')).length / cacheable.length : 0,
    fallbackRate: records.length ? records.filter(record => record.degraded).length / records.length : 0,
  };
}
