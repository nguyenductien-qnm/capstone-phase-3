type TraceStep = { status?: string };

export type SafeTraceDetail = { label: string; value: string };

const SENSITIVE_TEXT = /(?:system prompt|developer message|ignore (?:all )?previous instructions|chain[- ]of[- ]thought)/i;

function redactPublicText(value: string, maxLength: number): string {
  return value
    .slice(0, maxLength)
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '[redacted email]')
    .replace(/(?:\+?\d[\d .()-]{6,}\d)/g, '[redacted phone]');
}

export function safeTraceStepName(name?: string): string {
  if (!name) return 'Unknown step';
  if (SENSITIVE_TEXT.test(name)) return 'Safety check';
  return redactPublicText(name, 120);
}

export function safeCitationSnippet(snippet?: string): string {
  if (!snippet) return 'Source text unavailable.';
  if (SENSITIVE_TEXT.test(snippet)) return 'Source text withheld for safety.';
  return redactPublicText(snippet, 240);
}

export function safeCitationId(id?: string): string {
  if (!id || /[@\d]/.test(id)) return 'source';
  return id.length > 12 ? `${id.slice(0, 6)}…` : id;
}

const SAFE_DETAIL_KEYS = {
  decided_tools: 'Decided tools',
  tool_calls: 'Tool calls',
  stop_reason: 'Stop reason',
  succeeded: 'Succeeded',
  pending_confirmation: 'Confirmation',
  outcome: 'Outcome',
} as const;

const SAFE_ENUMS: Record<string, Set<string>> = {
  stop_reason: new Set(['end_turn', 'tool_use', 'max_tokens', 'guardrail_intervened']),
  outcome: new Set(['ok', 'pass', 'error', 'fallback', 'blocked']),
};

function safeDetailValue(key: string, value: unknown): string | undefined {
  if (Array.isArray(value)) {
    const tools = value.filter(item => typeof item === 'string' && /^[a-zA-Z0-9_.:-]{1,64}$/.test(item));
    return tools.length ? tools.slice(0, 5).join(', ') : undefined;
  }
  if (typeof value === 'boolean') return String(value);
  if (typeof value === 'string' && SAFE_ENUMS[key]?.has(value)) return value;
  return undefined;
}

export function safeTraceDetails(detail?: string): SafeTraceDetail[] {
  if (!detail) return [];
  try {
    const parsed = JSON.parse(detail);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return [];
    return Object.entries(SAFE_DETAIL_KEYS).flatMap(([key, label]) => {
      const value = safeDetailValue(key, (parsed as Record<string, unknown>)[key]);
      return value ? [{ label, value }] : [];
    });
  } catch {
    return [];
  }
}

export function deriveTraceEvidence(traceSteps: TraceStep[]): { cacheStatus?: string; degraded: boolean } {
  const statuses = traceSteps.map(step => String(step.status || '').toLowerCase());
  return {
    cacheStatus: statuses.find(status => status === 'hit_exact' || status === 'hit_semantic'),
    degraded: statuses.includes('fallback'),
  };
}
