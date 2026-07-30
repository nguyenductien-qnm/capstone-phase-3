// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { NextApiHandler } from 'next';
import CartGateway from '../../gateways/rpc/Cart.gateway';
import { AddItemRequest, Empty, Product } from '../../protos/demo';
import ProductCatalogService from '../../services/ProductCatalog.service';
import { IProductCart, IProductCartItem } from '../../types/Cart';
import InstrumentationMiddleware from '../../utils/telemetry/InstrumentationMiddleware';
import { isTransientGrpcError } from '../../gateways/rpc/GrpcDeadline';

type TResponse = IProductCart | Empty;

const handler: NextApiHandler<TResponse> = async ({ method, body, query }, res) => {
  switch (method) {
    case 'GET': {
      const { sessionId = '', currencyCode = '' } = query;
      const cartPromise = CartGateway.getCart(sessionId as string);
      const productsPromise = ProductCatalogService.listProducts(currencyCode as string).catch(error => {
        if (isTransientGrpcError(error)) {
          return [];
        }

        throw error;
      });
      const [{ userId, items }, allProducts] = await Promise.all([cartPromise, productsPromise]);

      const productList: IProductCartItem[] = items.map(({ productId, quantity }) => {
        const product = allProducts.find((p: Product) => p.id === productId) || ({} as Product);

        return {
          productId,
          quantity,
          product,
        };
      });

      return res.status(200).json({ userId, items: productList });
    }

    case 'POST': {
      const { userId, item } = body as AddItemRequest;

      const cart = await CartGateway.addItemAndGetCart(userId, item!);
      return res.status(200).json(cart);
    }

    case 'DELETE': {
      const { userId } = body as AddItemRequest;
      await CartGateway.emptyCart(userId);

      return res.status(204).send('');
    }

    default: {
      return res.status(405);
    }
  }
};

export default InstrumentationMiddleware(handler);
