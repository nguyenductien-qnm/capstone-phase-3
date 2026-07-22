// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { NextApiRequest, NextApiResponse } from 'next';
import InstrumentationMiddleware from '../../../../utils/telemetry/InstrumentationMiddleware';
import { Empty } from '../../../../protos/demo';
import ProductReviewService from '../../../../services/ProductReview.service';

type TResponse = {
    text: string;
    traceId: string;
    citations: unknown[];
} | Empty;

const AI_UNAVAILABLE_RESPONSE = {
    text: 'Xin lỗi, AI Assistant hiện không khả dụng do hệ thống đang bảo trì. Vui lòng thử lại sau.',
    traceId: '',
    citations: [],
};

const handler = async ({ method, body, query }: NextApiRequest, res: NextApiResponse<TResponse>) => {

    switch (method) {
        case 'POST': {
            const { productId = '' } = query;
            const { question } = body ;

            try {
                const response = await ProductReviewService.askProductAIAssistant(
                    productId as string,
                    question as string,
                );

                return res.status(200).json(response);
            } catch (error) {
                // Product-reviews is optional for the product page. Keep this
                // endpoint successful when that dependency is unavailable so
                // frontend-proxy does not report a user-visible 500.
                console.warn('Product AI assistant unavailable; returning fallback response:', error);
                return res.status(200).json(AI_UNAVAILABLE_RESPONSE);
            }
        }

        default: {
            return res.status(405).send('');
        }
    }
};

export default InstrumentationMiddleware(handler);
