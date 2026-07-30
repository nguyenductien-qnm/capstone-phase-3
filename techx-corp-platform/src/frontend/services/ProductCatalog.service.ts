import { LRUCache } from 'lru-cache';
import ProductCatalogGateway from '../gateways/rpc/ProductCatalog.gateway';
import CurrencyGateway from '../gateways/rpc/Currency.gateway';
import { Money, Product } from '../protos/demo';

const DEFAULT_CURRENCY_CODE = 'USD';
const CACHE_TTL_MS = 10_000;
const CURRENCY_CONCURRENCY = 16;

/**
 * Các request đồng thời cùng key sẽ dùng chung một Promise.
 */
const inFlightPromises = new Map<string, Promise<unknown>>();

/**
 * Cache dữ liệu gốc từ Product Catalog.
 *
 * Dữ liệu này không phụ thuộc currency, vì vậy phải tách khỏi cache
 * dữ liệu đã quy đổi.
 */
const baseProductListCache = new LRUCache<string, Product[]>({
  max: 1,
  ttl: CACHE_TTL_MS,
});

const baseProductCache = new LRUCache<string, Product>({
  max: 500,
  ttl: CACHE_TTL_MS,
});

/**
 * Cache dữ liệu sau khi đã quy đổi tiền tệ.
 */
const convertedProductListCache = new LRUCache<string, Product[]>({
  max: 32,
  ttl: CACHE_TTL_MS,
});

const convertedProductCache = new LRUCache<string, Product>({
  max: 1_000,
  ttl: CACHE_TTL_MS,
});

function normalizeCurrencyCode(currencyCode?: string): string {
  return currencyCode?.trim().toUpperCase() || DEFAULT_CURRENCY_CODE;
}

/**
 * Coalesce các request đồng thời có cùng key.
 *
 * Promise lỗi không được cache và entry luôn được dọn sau khi hoàn thành.
 */
function singleFlight<T>(key: string, loader: () => Promise<T>): Promise<T> {
  const existingPromise = inFlightPromises.get(key) as Promise<T> | undefined;

  if (existingPromise) {
    return existingPromise;
  }

  // Promise.resolve().then() giúp bắt cả lỗi synchronous từ loader.
  const promise = Promise.resolve().then(loader);

  inFlightPromises.set(key, promise);

  const cleanup = () => {
    // Tránh xóa nhầm Promise mới nếu key đã được tái sử dụng.
    if (inFlightPromises.get(key) === promise) {
      inFlightPromises.delete(key);
    }
  };

  promise.then(cleanup, cleanup);

  return promise;
}

/**
 * Kết hợp cache-aside và singleflight.
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
     * trước khi loader này chạy.
     */
    const refreshedCachedValue = cache.get(cacheKey);

    if (refreshedCachedValue !== undefined) {
      return refreshedCachedValue;
    }

    const value = await loader();

    cache.set(cacheKey, value);

    return value;
  });
}

/**
 * Giới hạn số RPC currency chạy đồng thời.
 *
 * Promise.all() không giới hạn có thể gửi hàng trăm RPC cùng lúc,
 * làm tăng latency và gây quá tải Currency Service.
 */
async function mapWithConcurrency<T, R>(
  items: readonly T[],
  concurrency: number,
  mapper: (item: T, index: number) => Promise<R>
): Promise<R[]> {
  if (items.length === 0) {
    return [];
  }

  const results = new Array<R>(items.length);
  const workerCount = Math.min(concurrency, items.length);

  let currentIndex = 0;

  async function worker(): Promise<void> {
    while (currentIndex < items.length) {
      const index = currentIndex++;

      results[index] = await mapper(items[index], index);
    }
  }

  await Promise.all(Array.from({ length: workerCount }, () => worker()));

  return results;
}

async function getBaseProductList(): Promise<Product[]> {
  return getOrLoad(baseProductListCache, 'all', 'catalog:list', async () => {
    const { products = [] } = await ProductCatalogGateway.listProducts();

    /*
     * Prime item cache để getProduct() không phải gọi lại
     * Product Catalog sau khi listProducts() vừa chạy.
     */
    for (const product of products) {
      if (product.id) {
        baseProductCache.set(product.id, product);
      }
    }

    return products;
  });
}

async function getBaseProduct(id: string): Promise<Product> {
  return getOrLoad(baseProductCache, id, `catalog:product:${id}`, () => ProductCatalogGateway.getProduct(id));
}

async function convertProductPrice(price: Money, currencyCode: string): Promise<Money> {
  if (currencyCode === DEFAULT_CURRENCY_CODE) {
    return price;
  }

  return CurrencyGateway.convert(price, currencyCode);
}

async function convertProduct(product: Product, currencyCode: string): Promise<Product> {
  if (currencyCode === DEFAULT_CURRENCY_CODE) {
    return product;
  }

  if (!product.priceUsd) {
    throw new Error(`Product "${product.id}" does not have priceUsd`);
  }

  return {
    ...product,
    priceUsd: await convertProductPrice(product.priceUsd, currencyCode),
  };
}

const ProductCatalogService = {
  async getProductPrice(price: Money, currencyCode = DEFAULT_CURRENCY_CODE): Promise<Money> {
    return convertProductPrice(price, normalizeCurrencyCode(currencyCode));
  },

  async listProducts(currencyCode = DEFAULT_CURRENCY_CODE): Promise<Product[]> {
    const normalizedCurrency = normalizeCurrencyCode(currencyCode);

    /*
     * USD trả thẳng dữ liệu gốc:
     * - Không tạo object mới
     * - Không sử dụng thêm converted cache
     * - Không gọi Currency Service
     */
    if (normalizedCurrency === DEFAULT_CURRENCY_CODE) {
      return getBaseProductList();
    }

    return getOrLoad(
      convertedProductListCache,
      normalizedCurrency,
      `converted:list:${normalizedCurrency}`,
      async () => {
        const productList = await getBaseProductList();

        const convertedProducts = await mapWithConcurrency(productList, CURRENCY_CONCURRENCY, product =>
          convertProduct(product, normalizedCurrency)
        );

        /*
         * Prime converted item cache để getProduct(id, currency)
         * có thể dùng lại kết quả từ listProducts().
         */
        for (const product of convertedProducts) {
          if (product.id) {
            convertedProductCache.set(`${product.id}:${normalizedCurrency}`, product);
          }
        }

        return convertedProducts;
      }
    );
  },

  async getProduct(id: string, currencyCode = DEFAULT_CURRENCY_CODE): Promise<Product> {
    const normalizedCurrency = normalizeCurrencyCode(currencyCode);

    if (normalizedCurrency === DEFAULT_CURRENCY_CODE) {
      return getBaseProduct(id);
    }

    const cacheKey = `${id}:${normalizedCurrency}`;

    return getOrLoad(convertedProductCache, cacheKey, `converted:product:${cacheKey}`, async () => {
      const product = await getBaseProduct(id);

      return convertProduct(product, normalizedCurrency);
    });
  },
};

export default ProductCatalogService;
