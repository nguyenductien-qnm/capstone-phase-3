// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { ChannelCredentials, Metadata } from '@grpc/grpc-js';
import { ListRecommendationsResponse, RecommendationServiceClient } from '../../protos/demo';
import { CircuitBreaker } from '../../utils/resilience/CircuitBreaker';

const { RECOMMENDATION_ADDR = '', RECOMMENDATION_TIMEOUT_MS = '2000' } = process.env;

const client = new RecommendationServiceClient(RECOMMENDATION_ADDR, ChannelCredentials.createInsecure());

// CDO-218 (M17-R1): recommendation không-thiết-yếu → bọc circuit breaker + deadline.
// Lỗi/chậm/mở mạch => trả productIds rỗng, trang vẫn hiển thị (không có gợi ý).
const timeoutMs = Number(RECOMMENDATION_TIMEOUT_MS);
const breaker = new CircuitBreaker({ name: 'recommendation', timeoutMs });

const RecommendationsGateway = () => ({
  listRecommendations(userId: string, productIds: string[]) {
    return breaker.execute<ListRecommendationsResponse>(
      () =>
        new Promise<ListRecommendationsResponse>((resolve, reject) =>
          // Chữ ký: listRecommendations(request, metadata, options, callback). Deadline là
          // CallOption -> đặt ở options (thứ 3), metadata rỗng ở thứ 2.
          client.listRecommendations(
            { userId, productIds },
            new Metadata(),
            { deadline: new Date(Date.now() + timeoutMs) },
            (error, response) => (error ? reject(error) : resolve(response))
          )
        ),
      // Fallback tạo mới mỗi lần để tránh chia sẻ state nếu caller mutate.
      { productIds: [] }
    );
  },
});

export default RecommendationsGateway();
