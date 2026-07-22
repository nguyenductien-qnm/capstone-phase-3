// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { ChannelCredentials, Metadata } from '@grpc/grpc-js';
import { AdResponse, AdServiceClient } from '../../protos/demo';
import { CircuitBreaker } from '../../utils/resilience/CircuitBreaker';

const { AD_ADDR = '', AD_TIMEOUT_MS = '2000' } = process.env;

const client = new AdServiceClient(AD_ADDR, ChannelCredentials.createInsecure());

// CDO-218 (M17-R1): ads là nội dung không-thiết-yếu → bọc circuit breaker + deadline.
// Lỗi/chậm/mở mạch => trả danh sách rỗng, KHÔNG làm hỏng trang.
const timeoutMs = Number(AD_TIMEOUT_MS);
const breaker = new CircuitBreaker({ name: 'ad', timeoutMs });

const AdGateway = () => ({
  listAds(contextKeys: string[]) {
    return breaker.execute<AdResponse>(
      () =>
        new Promise<AdResponse>((resolve, reject) =>
          // Chữ ký: getAds(request, metadata, options, callback). Deadline là CallOption
          // nên PHẢI đặt ở tham số options (thứ 3), metadata rỗng ở thứ 2.
          client.getAds(
            { contextKeys: contextKeys },
            new Metadata(),
            { deadline: new Date(Date.now() + timeoutMs) },
            (error, response) => (error ? reject(error) : resolve(response))
          )
        ),
      // Fallback tạo mới mỗi lần để tránh chia sẻ state nếu caller mutate.
      { ads: [] }
    );
  },
});

export default AdGateway();
