// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { LRUCache } from 'lru-cache';
import ProductCatalogGateway from '../gateways/rpc/ProductCatalog.gateway';
import CurrencyGateway from '../gateways/rpc/Currency.gateway';
import { Money, Product } from '../protos/demo';

const defaultCurrencyCode = 'USD';

// Product cache: productId:currencyCode → Product (with converted price)
const productCache = new LRUCache<string, Product>({
  max: 500,
  ttl: 60_000, // 60 seconds
});

// List cache: list:currencyCode → Product[]
const listCache = new LRUCache<string, Product[]>({
  max: 10,
  ttl: 60_000, // 60 seconds
});

const ProductCatalogService = () => ({
  async getProductPrice(price: Money, currencyCode: string) {
    return !!currencyCode && currencyCode !== defaultCurrencyCode
      ? await CurrencyGateway.convert(price, currencyCode)
      : price;
  },
  async listProducts(currencyCode = 'USD') {
    const cacheKey = `list:${currencyCode}`;
    const cached = listCache.get(cacheKey);
    if (cached) return cached;

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

    listCache.set(cacheKey, results);
    return results;
  },
  async getProduct(id: string, currencyCode = 'USD') {
    const cacheKey = `${id}:${currencyCode}`;
    const cached = productCache.get(cacheKey);
    if (cached) return cached;

    const product = await ProductCatalogGateway.getProduct(id);
    const result = {
      ...product,
      priceUsd: await this.getProductPrice(product.priceUsd!, currencyCode),
    };

    productCache.set(cacheKey, result);
    return result;
  },
});

export default ProductCatalogService();