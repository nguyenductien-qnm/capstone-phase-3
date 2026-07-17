import { NextApiRequest, NextApiResponse } from 'next';
import * as grpc from '@grpc/grpc-js';

import { ShoppingCopilotServiceClient, ChatWithCopilotRequest, ChatWithCopilotResponse } from '../../protos/shopping_copilot';

const client = new ShoppingCopilotServiceClient(
    process.env.SHOPPING_COPILOT_ADDR || 'shopping-copilot:3552',
    grpc.credentials.createInsecure()
);

export default function handler(req: NextApiRequest, res: NextApiResponse) {
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    const { question, user_id, session_id, confirmation_token } = req.body;

    const request = {
        userId: user_id || 'anonymous',
        question: question || '',
        chatHistory: [],
        sessionId: session_id || 'default-session',
        confirmationToken: confirmation_token || ''
    };

    client.chatWithCopilot(request, (error, response) => {
        if (error) {
            console.error('Copilot gRPC Error:', error);
            return res.status(500).json({ error: error.message });
        }
        res.status(200).json(response);
    });
}
