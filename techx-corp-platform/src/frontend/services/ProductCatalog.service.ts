// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import ProductCatalogGateway from '../gateways/rpc/ProductCatalog.gateway';
import CurrencyGateway from '../gateways/rpc/Currency.gateway';
import { Money, Product } from '../protos/demo';
import Redis from 'ioredis';

const defaultCurrencyCode = 'USD';

const redisUrl = process.env.VALKEY_ADDR ? `redis://${process.env.VALKEY_ADDR}` : 'redis://localhost:6379';
const redis = new Redis(redisUrl, {
  maxRetriesPerRequest: 1,
  connectTimeout: 2000,
  commandTimeout: 1000,
  retryStrategy: times => Math.min(times * 50, 2000),
});

redis.on('error', err => {
  console.warn('Redis/Valkey connection error:', err.message);
});

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

    try {
      const cached = await redis.get(cacheKey);
      if (cached) return JSON.parse(cached);
    } catch (err: any) {
      console.warn('Redis get failed for listProducts, falling back to gRPC:', err.message);
    }

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
        try {
          await redis.set(cacheKey, JSON.stringify(results), 'EX', 60);
        } catch (err: any) {
          console.warn('Redis set failed for listProducts:', err.message);
        }
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

    try {
      const cached = await redis.get(cacheKey);
      if (cached) return JSON.parse(cached);
    } catch (err: any) {
      console.warn('Redis get failed for getProduct, falling back to gRPC:', err.message);
    }

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
        try {
          await redis.set(cacheKey, JSON.stringify(result), 'EX', 30);
        } catch (err: any) {
          console.warn('Redis set failed for getProduct:', err.message);
        }
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
