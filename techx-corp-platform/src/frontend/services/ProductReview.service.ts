// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import ProductReviewGateway from '../gateways/rpc/ProductReview.gateway';

// Singleflight map to coalesce identical concurrent requests
const inFlightPromises = new Map<string, Promise<any>>();

const ProductReviewService = () => ({
    async getProductReviews(id: string) {
        const cacheKey = `reviews:${id}`;

        if (inFlightPromises.has(cacheKey)) {
            return inFlightPromises.get(cacheKey);
        }

        const promise = (async () => {
            try {
                const productReviews = await ProductReviewGateway.getProductReviews(id);
                return productReviews;
            } finally {
                inFlightPromises.delete(cacheKey);
            }
        })();

        inFlightPromises.set(cacheKey, promise);
        return promise;
    },
    async getAverageProductReviewScore(id: string) {
        const cacheKey = `avg-score:${id}`;

        if (inFlightPromises.has(cacheKey)) {
            return inFlightPromises.get(cacheKey);
        }

        const promise = (async () => {
            try {
                const averageScore = await ProductReviewGateway.getAverageProductReviewScore(id);
                return averageScore;
            } finally {
                inFlightPromises.delete(cacheKey);
            }
        })();

        inFlightPromises.set(cacheKey, promise);
        return promise;
    },
    async askProductAIAssistant(id: string, question: string) {
        // No singleflight — different questions produce different results
        const response = await ProductReviewGateway.askProductAIAssistant(id, question);
        return response;
    },
});

export default ProductReviewService();
