// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { NextApiRequest, NextApiResponse } from 'next';
import { status as GrpcStatus, ServiceError } from '@grpc/grpc-js';
import InstrumentationMiddleware from '../../../../utils/telemetry/InstrumentationMiddleware';
import { Empty, Product } from '../../../../protos/demo';
import ProductCatalogService from '../../../../services/ProductCatalog.service';

type TErrorBody = { message: string; productId: string };
type TResponse = Product | Empty | TErrorBody;

function isGrpcNotFound(error: unknown): boolean {
  if (!error || typeof error !== 'object') {
    return false;
  }
  const e = error as Partial<ServiceError>;
  return e.code === GrpcStatus.NOT_FOUND;
}

const handler = async ({ method, query }: NextApiRequest, res: NextApiResponse<TResponse>) => {
  switch (method) {
    case 'GET': {
      const { productId = '', currencyCode = '' } = query;
      try {
        const product = await ProductCatalogService.getProduct(productId as string, currencyCode as string);
        return res.status(200).json(product);
      } catch (error) {
        // Catalog returns gRPC NotFound for missing IDs — map to HTTP 404 (not 500).
        // Avoids treating business miss as Internal Server Error / SLO error noise.
        if (isGrpcNotFound(error)) {
          return res.status(404).json({
            message: 'Product not found',
            productId: productId as string,
          });
        }
        throw error;
      }
    }

    default: {
      return res.status(405).send('');
    }
  }
};

export default InstrumentationMiddleware(handler);
