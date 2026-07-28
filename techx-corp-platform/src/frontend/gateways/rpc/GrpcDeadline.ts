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
  checkout: 10_000,
  productReview: 25_000,
  productSearch: 5_000,
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
  timeoutMs: number,
  metadata = new Metadata()
): Promise<TResponse> {
  const deadline = new Date(Date.now() + timeoutMs);

  return new Promise<TResponse>((resolve, reject) => {
    invoke(request, metadata, { deadline }, (error, response) => {
      if (error) {
        reject(error);
        return;
      }

      resolve(response);
    });
  });
}

/**
 * Executes a read-only unary RPC, retrying a transient failure once.
 *
 * The catalog deadline is 1s and a cache miss that lands during heavy database
 * work can outlast it even though the upstream is healthy. grpcErrorHttpStatus
 * then turns that into a 504 for the browser, so a blip that a second attempt
 * serves in milliseconds is served as a failed page instead.
 *
 * Only for calls that are safe to repeat. The caller's route timeout still caps
 * the total: two attempts of the catalog deadline stay far inside the 15s Envoy
 * allows /api/products.
 */
export async function unaryWithRetry<TRequest, TResponse>(
  invoke: UnaryRpc<TRequest, TResponse>,
  request: TRequest,
  timeoutMs: number,
  metadata = new Metadata()
): Promise<TResponse> {
  try {
    return await unaryWithDeadline(invoke, request, timeoutMs, metadata);
  } catch (error) {
    if (!isTransientGrpcError(error)) {
      throw error;
    }

    return unaryWithDeadline(invoke, request, timeoutMs, metadata);
  }
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
