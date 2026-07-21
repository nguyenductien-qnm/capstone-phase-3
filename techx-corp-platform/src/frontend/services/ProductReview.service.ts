// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { LRUCache } from 'lru-cache';
import ProductReviewGateway from '../gateways/rpc/ProductReview.gateway';

const CACHE_TTL_MS = 15_000;

type ProductReviews = Awaited<ReturnType<typeof ProductReviewGateway.getProductReviews>>;

type AverageProductReviewScore = Awaited<ReturnType<typeof ProductReviewGateway.getAverageProductReviewScore>>;

const inFlightPromises = new Map<string, Promise<unknown>>();

const productReviewsCache = new LRUCache<string, ProductReviews>({
  max: 500,
  ttl: CACHE_TTL_MS,
});

const averageScoreCache = new LRUCache<string, AverageProductReviewScore>({
  max: 500,
  ttl: CACHE_TTL_MS,
});

/**
 * Gộp các request đồng thời có cùng key thành một request duy nhất.
 */
function singleFlight<T>(key: string, loader: () => Promise<T>): Promise<T> {
  const existingPromise = inFlightPromises.get(key) as Promise<T> | undefined;

  if (existingPromise) {
    return existingPromise;
  }

  /*
   * Promise.resolve().then(loader) cũng bắt được lỗi synchronous
   * xảy ra trước khi loader trả về Promise.
   */
  const promise = Promise.resolve().then(loader);

  inFlightPromises.set(key, promise);

  const cleanup = () => {
    /*
     * Chỉ xóa nếu entry hiện tại vẫn trỏ tới Promise này.
     * Tránh xóa nhầm một request mới có cùng key.
     */
    if (inFlightPromises.get(key) === promise) {
      inFlightPromises.delete(key);
    }
  };

  promise.then(cleanup, cleanup);

  return promise;
}

/**
 * Cache-aside kết hợp singleflight.
 */
async function getOrLoad<T extends {}>(
  cache: LRUCache<string, T>,
  cacheKey: string,
  flightKey: string,
  loader: () => Promise<T>
): Promise<T> {
  const cachedValue = cache.get(cacheKey);

  if (cachedValue !== undefined) {
    return cachedValue;
  }

  return singleFlight(flightKey, async () => {
    /*
     * Double-check cache vì một request khác có thể vừa hoàn thành
     * trước khi loader này thực sự chạy.
     */
    const refreshedValue = cache.get(cacheKey);

    if (refreshedValue !== undefined) {
      return refreshedValue;
    }

    const value = await loader();

    cache.set(cacheKey, value);

    return value;
  });
}

function normalizeProductId(id: string): string {
  const normalizedId = id.trim();

  if (!normalizedId) {
    throw new Error('Product ID is required');
  }

  return normalizedId;
}

const ProductReviewService = {
  async getProductReviews(id: string): Promise<ProductReviews> {
    const productId = normalizeProductId(id);

    return getOrLoad(productReviewsCache, productId, `reviews:${productId}`, async () => {
      try {
        return await ProductReviewGateway.getProductReviews(productId);
      } catch (error) {
        console.warn(`Failed to fetch product reviews for ${productId}, using fallback:`, error);
        return [];
      }
    });
  },

  async getAverageProductReviewScore(id: string): Promise<AverageProductReviewScore> {
    const productId = normalizeProductId(id);

    return getOrLoad(averageScoreCache, productId, `average-score:${productId}`, async () => {
      try {
        return await ProductReviewGateway.getAverageProductReviewScore(productId);
      } catch (error) {
        console.warn(`Failed to fetch average score for ${productId}, using fallback:`, error);
        return "0.0";
      }
    });
  },

  async askProductAIAssistant(
    id: string,
    question: string
  ): ReturnType<typeof ProductReviewGateway.askProductAIAssistant> {
    const productId = normalizeProductId(id);
    const normalizedQuestion = question.trim();

    if (!normalizedQuestion) {
      throw new Error('Question is required');
    }

    /*
     * Không cache AI response vì:
     * - Kết quả có thể không deterministic.
     * - Có thể phụ thuộc user/session/context.
     * - Cache key có thể chứa dữ liệu nhạy cảm.
     */
    try {
      return await ProductReviewGateway.askProductAIAssistant(productId, normalizedQuestion);
    } catch (error) {
      console.warn(`Failed to ask AI Assistant for ${productId}, using fallback:`, error);
      return { 
        text: "Xin lỗi, AI Assistant hiện không khả dụng do hệ thống đang bảo trì. Vui lòng thử lại sau.", 
        traceId: "", 
        citations: [] 
      };
    }
  },

  /**
   * Gọi sau khi thêm, sửa hoặc xóa review.
   */
  invalidateProductReviews(id: string): void {
    const productId = normalizeProductId(id);

    productReviewsCache.delete(productId);
    averageScoreCache.delete(productId);
  },
};

export default ProductReviewService;
