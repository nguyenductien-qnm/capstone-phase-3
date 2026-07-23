// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import {
  CallOptions,
  ClientUnaryCall,
  Metadata,
  ServiceError,
  status,
} from '@grpc/grpc-js';

export const GrpcDeadlineMs = {
  cart: 750,
  catalog: 1_000,
  recommendation: 1_000,
  checkout: 2_000,
  productReview: 10_000,
} as const;

type UnaryRpc<TRequest, TResponse> = (
  request: TRequest,
  metadata: Metadata,
  options: Partial<CallOptions>,
  callback: (error: ServiceError | null, response: TResponse) => void
) => ClientUnaryCall;

/**
 * Executes a unary RPC with a real grpc-js deadline. grpc-js cancels the
 * underlying call when the deadline expires; this is deliberately not a
 * Promise.race wrapper, which would leave the RPC running in the background.
 */
export function unaryWithDeadline<TRequest, TResponse>(
  invoke: UnaryRpc<TRequest, TResponse>,
  request: TRequest,
  timeoutMs: number
): Promise<TResponse> {
  const deadline = new Date(Date.now() + timeoutMs);

  return new Promise<TResponse>((resolve, reject) => {
    invoke(request, new Metadata(), { deadline }, (error, response) => {
      if (error) {
        reject(error);
        return;
      }

      resolve(response);
    });
  });
}

export function isTransientGrpcError(error: unknown): error is ServiceError {
  if (!isGrpcError(error)) {
    return false;
  }

  return [
    status.CANCELLED,
    status.DEADLINE_EXCEEDED,
    status.RESOURCE_EXHAUSTED,
    status.UNAVAILABLE,
  ].includes(error.code);
}

export function grpcErrorHttpStatus(error: unknown): 503 | 504 | undefined {
  if (!isGrpcError(error)) {
    return undefined;
  }

  if (error.code === status.DEADLINE_EXCEEDED) {
    return 504;
  }

  if ([status.CANCELLED, status.RESOURCE_EXHAUSTED, status.UNAVAILABLE].includes(error.code)) {
    return 503;
  }

  return undefined;
}

function isGrpcError(error: unknown): error is ServiceError {
  return error instanceof Error && typeof (error as Partial<ServiceError>).code === 'number';
}
