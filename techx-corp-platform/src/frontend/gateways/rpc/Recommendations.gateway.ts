// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { ChannelCredentials } from '@grpc/grpc-js';
import {
  ListRecommendationsRequest,
  ListRecommendationsResponse,
  RecommendationServiceClient,
} from '../../protos/demo';
import { GrpcDeadlineMs, unaryWithDeadline } from './GrpcDeadline';

const { RECOMMENDATION_ADDR = '' } = process.env;

const client = new RecommendationServiceClient(RECOMMENDATION_ADDR, ChannelCredentials.createInsecure());

// Tạm thời tắt CircuitBreaker.execute()

const RecommendationsGateway = () => ({
  listRecommendations(userId: string, productIds: string[]) {
    return unaryWithDeadline<ListRecommendationsRequest, ListRecommendationsResponse>(
      (request, metadata, options, callback) => client.listRecommendations(request, metadata, options, callback),
      { userId, productIds },
      GrpcDeadlineMs.recommendation
    );
  },
});

export default RecommendationsGateway();
