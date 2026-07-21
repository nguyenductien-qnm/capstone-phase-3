// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import ProductCatalogGateway from '../gateways/rpc/ProductCatalog.gateway';
import CurrencyGateway from '../gateways/rpc/Currency.gateway';
import { Money, Product } from '../protos/demo';

const defaultCurrencyCode = 'USD';

// Singleflight map to coalesce identical concurrent requests
const inFlightPromises = new Map<string, Promise<any>>();

const ProductCatalogService = () => ({
  async getProductPrice(price: Money, currencyCode: string) {
    return !!currencyCode && currencyCode !== defaultCurrencyCode
      ? await CurrencyGateway.convert(price, currencyCode)
      : price;
  },
  async listProducts(currencyCode = 'USD'): Promise<Product[]> {
    const cacheKey = `list:${currencyCode}`;

    if (inFlightPromises.has(cacheKey)) {
      return inFlightPromises.get(cacheKey);
    }

    const promise = (async () => {
      try {
        const { products: productList } = await ProductCatalogGateway.listProducts();

        const results = await Promise.all(
          productList.map(async product => {
            const priceUsd = await this.getProductPrice(product.priceUsd!, currencyCode);
            return {
              ...product,
              priceUsd,
            };
          })
        );
        return results;
      } finally {
        inFlightPromises.delete(cacheKey);
      }
    })();

    inFlightPromises.set(cacheKey, promise);
    return promise;
  },
  async getProduct(id: string, currencyCode = 'USD') {
    const cacheKey = `product:${id}:${currencyCode}`;

    if (inFlightPromises.has(cacheKey)) {
      return inFlightPromises.get(cacheKey);
    }

    const promise = (async () => {
      try {
        const product = await ProductCatalogGateway.getProduct(id);
        const result = {
          ...product,
          priceUsd: await this.getProductPrice(product.priceUsd!, currencyCode),
        };
        return result;
      } finally {
        inFlightPromises.delete(cacheKey);
      }
    })();

    inFlightPromises.set(cacheKey, promise);
    return promise;
  },
});

export default ProductCatalogService();
