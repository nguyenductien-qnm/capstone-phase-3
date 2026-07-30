// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { ChannelCredentials } from '@grpc/grpc-js';
import {
  AskProductAIAssistantResponse,
  GetAverageProductReviewScoreResponse,
  GetProductReviewsResponse,
  ProductReview,
  ProductReviewServiceClient,
} from '../../protos/demo';
import { GrpcDeadlineMs, unaryWithDeadline } from './GrpcDeadline';

const { PRODUCT_REVIEWS_ADDR = '' } = process.env;

const client = new ProductReviewServiceClient(PRODUCT_REVIEWS_ADDR, ChannelCredentials.createInsecure());

const ProductReviewGateway = () => ({
  getProductReviews(productId: string) {
    return unaryWithDeadline<{ productId: string }, GetProductReviewsResponse>(
      (request, metadata, options, callback) => client.getProductReviews(request, metadata, options, callback),
      { productId },
      GrpcDeadlineMs.productReview
    ).then(response => response.productReviews as ProductReview[]);
  },
  getAverageProductReviewScore(productId: string) {
    return unaryWithDeadline<{ productId: string }, GetAverageProductReviewScoreResponse>(
      (request, metadata, options, callback) =>
        client.getAverageProductReviewScore(request, metadata, options, callback),
      { productId },
      GrpcDeadlineMs.productReview
    ).then(response => response.averageScore);
  },
  askProductAIAssistant(productId: string, question: string) {
    return unaryWithDeadline<{ productId: string; question: string }, AskProductAIAssistantResponse>(
      (request, metadata, options, callback) => client.askProductAiAssistant(request, metadata, options, callback),
      { productId, question },
      GrpcDeadlineMs.productReview
    ).then(response => ({
      text: response.response,
      traceId: response.traceId,
      citations: response.citations,
      traceSteps: response.traceSteps,
    }));
  },
});

export default ProductReviewGateway();
