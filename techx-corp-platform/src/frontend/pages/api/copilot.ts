import { NextApiRequest, NextApiResponse } from 'next';
import * as grpc from '@grpc/grpc-js';

import InstrumentationMiddleware from '../../utils/telemetry/InstrumentationMiddleware';
import { ShoppingCopilotServiceClient, ChatWithCopilotResponse } from '../../protos/shopping_copilot';

const client = new ShoppingCopilotServiceClient(
  process.env.SHOPPING_COPILOT_ADDR || 'shopping-copilot:3552',
  grpc.credentials.createInsecure(),
);
const safeString = (value: unknown, max: number) => typeof value === 'string' ? value.trim().slice(0, max) : '';

async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const question = safeString(req.body?.question, 4000);
  const confirmationToken = safeString(req.body?.confirmation_token, 512);
  const request = {
    userId: safeString(req.body?.user_id, 256) || 'anonymous',
    question,
    chatHistory: [],
    sessionId: safeString(req.body?.session_id, 256) || 'default-session',
    confirmationToken,
  };
  if (!question && !confirmationToken) return res.status(400).json({ error: 'Question or confirmation token is required' });

  try {
    const response = await new Promise<ChatWithCopilotResponse>((resolve, reject) => {
      client.chatWithCopilot(request, new grpc.Metadata(), { deadline: Date.now() + 10_000 }, (error, value) => error ? reject(error) : resolve(value as ChatWithCopilotResponse));
    });
    return res.status(200).json(response);
  } catch (error) {
    console.error('Copilot gRPC request failed', error);
    return res.status(503).json({
      response: 'The AI service is temporarily unavailable. No action was taken. Please try again shortly.',
      pendingConfirmation: undefined,
      actionsTaken: [],
      degraded: true,
      traceId: '',
      citations: [],
      traceSteps: [],
      cacheStatus: 'bypass',
      similarity: 0,
      sourceFingerprint: '',
    });
  }
}

export default InstrumentationMiddleware(handler);
