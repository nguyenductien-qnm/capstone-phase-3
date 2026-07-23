// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { NextApiRequest, NextApiResponse } from 'next';
import InstrumentationMiddleware from '../../utils/telemetry/InstrumentationMiddleware';
import CheckoutGateway from '../../gateways/rpc/Checkout.gateway';
import { Empty, PlaceOrderRequest, Product } from '../../protos/demo';
import { IProductCheckoutItem, IProductCheckout } from '../../types/Cart';
import ProductCatalogService from '../../services/ProductCatalog.service';

type TResponse = IProductCheckout | Empty;

const handler = async ({ method, body, query }: NextApiRequest, res: NextApiResponse<TResponse>) => {
  switch (method) {
    case 'POST': {
      const { currencyCode = '' } = query;
      const orderData = body as PlaceOrderRequest;
      const { order: { items = [], ...order } = {} } = await CheckoutGateway.placeOrder(orderData);

      let allProducts: Product[] = [];
      try {
        allProducts = await ProductCatalogService.listProducts(currencyCode as string);
      } catch (error) {
        // The order is already committed. Return a degraded response instead of
        // turning enrichment failure into a retryable checkout failure.
        console.warn('Product catalog enrichment failed after order placement:', error);
      }

      const productList: IProductCheckoutItem[] = items.map(({ item: { productId = '', quantity = 0 } = {}, cost }) => {
        const product = allProducts.find((p: Product) => p.id === productId) || ({} as Product);

        return {
          cost,
          item: {
            productId,
            quantity,
            product,
          },
        };
      });

      return res.status(202).json({ ...order, items: productList });
    }

    default: {
      return res.status(405).send('');
    }
  }
};

export default InstrumentationMiddleware(handler);
