// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { NextApiRequest, NextApiResponse } from 'next';
import InstrumentationMiddleware from '../../utils/telemetry/InstrumentationMiddleware';
import RecommendationsGateway from '../../gateways/rpc/Recommendations.gateway';
import { Empty, Product } from '../../protos/demo';
import ProductCatalogService from '../../services/ProductCatalog.service';
import { isTransientGrpcError } from '../../gateways/rpc/GrpcDeadline';

type TResponse = Product[] | Empty;

const handler = async ({ method, query }: NextApiRequest, res: NextApiResponse<TResponse>) => {
  switch (method) {
    case 'GET': {
      const { productIds = [], sessionId = '', currencyCode = '' } = query;
      try {
        const recommendationsPromise = RecommendationsGateway.listRecommendations(
          sessionId as string,
          productIds as string[]
        );
        const productsPromise = ProductCatalogService.listProducts(currencyCode as string);
        const [{ productIds: productList }, allProducts] = await Promise.all([
          recommendationsPromise,
          productsPromise,
        ]);
        const recommendedProductList = productList
          .slice(0, 4)
          .map(id => allProducts.find((p: Product) => p.id === id))
          .filter((product): product is Product => Boolean(product));

        return res.status(200).json(recommendedProductList);
      } catch (error) {
        if (isTransientGrpcError(error)) {
          return res.status(200).json([]);
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
