import assert from 'node:assert/strict';
import test from 'node:test';
import { buildEvidenceBadges, createConversationId, parseTraceMetadata, requestCopilot, safeToolArguments } from './copilotEvidence.ts';

test('confirmation is resent with an isolated conversation id', async () => {
  const calls = [];
  const fetcher = async (_url, init) => {
    calls.push(JSON.parse(String(init.body)));
    return new Response(JSON.stringify({ response: 'Added', actionsTaken: [{ toolName: 'add_to_cart', succeeded: true }] }), { status: 200 });
  };

  const sessionId = createConversationId();
  const result = await requestCopilot({ question: '', userId: 'user-1', sessionId, confirmationToken: 'confirm-1', fetcher });

  assert.equal(calls[0].user_id, 'user-1');
  assert.equal(calls[0].session_id, sessionId);
  assert.equal(calls[0].confirmation_token, 'confirm-1');
  assert.equal(result.actionsTaken[0].toolName, 'add_to_cart');
});

test('bad gateway response becomes an honest degraded fallback', async () => {
  const result = await requestCopilot({
    question: 'hello', userId: 'u', sessionId: 's',
    fetcher: async () => new Response(JSON.stringify({ error: 'private upstream detail' }), { status: 500 }),
  });
  assert.equal(result.degraded, true);
  assert.match(result.response, /temporarily unavailable/i);
  assert.doesNotMatch(result.response, /private upstream detail/i);
});

test('badges and trace metadata are derived only from response evidence', () => {
  assert.deepEqual(buildEvidenceBadges({
    pendingConfirmation: { confirmationToken: 't' }, cacheStatus: 'hit_semantic', degraded: true,
    citations: [{ reviewId: 'r1' }], actionsTaken: [], traceSteps: [{ status: 'blocked' }],
  }), ['Grounded', 'Blocked', 'Confirmation required', 'Semantic cache hit', 'Degraded / fallback']);

  assert.deepEqual(parseTraceMetadata([{ detail: JSON.stringify({ model_id: 'nova', tokens_in: 12, tokens_out: 4, cost_usd: 0.01, outcome: 'ok', timestamp: '2026-07-30T00:00:00Z' }) }]), {
    modelId: 'nova', tokensIn: 12, tokensOut: 4, costUsd: 0.01, outcome: 'ok', timestamp: '2026-07-30T00:00:00Z'
  });
});


test('abstention is derived from an explicit response', () => {
  assert.deepEqual(buildEvidenceBadges({ response: 'There is not enough relevant information to answer.', traceSteps: [] }), ['Abstained']);
});

test('tool cards expose only safe shopping arguments', () => {
  assert.equal(safeToolArguments(JSON.stringify({ product_id: 'p1', quantity: 2, email: 'private@example.com' })), '{\n  "product_id": "p1",\n  "quantity": "2"\n}');
});
