// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { NextPage } from 'next';
import Head from 'next/head';
import Image from 'next/image';
import { useRouter } from 'next/router';
import { useCallback, useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import Ad from '../../../components/Ad';
import Layout from '../../../components/Layout';
import ProductPrice from '../../../components/ProductPrice';
import Recommendations from '../../../components/Recommendations';
import ProductReviews from '../../../components/ProductReviews';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../../components/ui/select';
import { CypressFields } from '../../../utils/enums/CypressFields';
import ApiGateway from '../../../gateways/Api.gateway';
import { Product } from '../../../protos/demo';
import AdProvider from '../../../providers/Ad.provider';
import { useCart } from '../../../providers/Cart.provider';
import { useCurrency } from '../../../providers/Currency.provider';
import ProductReviewProvider from '../../../providers/ProductReview.provider';
import ProductAIAssistantProvider from '../../../providers/ProductAIAssistant.provider';
import { Button } from '../../../components/ui/button';
import { MOCK_PRODUCTS } from '../../../utils/mockData';

const quantityOptions = new Array(10).fill(0).map((_, i) => i + 1);

const ProductDetail: NextPage = () => {
  const { push, query } = useRouter();
  const [quantity, setQuantity] = useState(1);
  const {
    addItem,
    cart: { items },
  } = useCart();
  const { selectedCurrency } = useCurrency();
  const productId = query.productId as string;

  useEffect(() => {
    setQuantity(1);
  }, [productId]);

  const {
    data: {
      name,
      picture,
      description,
      priceUsd = { units: 0, currencyCode: 'USD', nanos: 0 },
      categories,
    } = {} as Product,
    isError,
  } = useQuery({
      queryKey: ['product', productId, 'selectedCurrency', selectedCurrency],
      queryFn: () => ApiGateway.getProduct(productId, selectedCurrency),
      enabled: !!productId,
    }
  ) as { data: Product, isError: boolean };

  const mockProduct = MOCK_PRODUCTS.find(p => p.id === productId) || MOCK_PRODUCTS[0];
  const displayProduct = isError || !name ? mockProduct : { name, picture, description, priceUsd, categories };

  const onAddItem = useCallback(async () => {
    await addItem({
      productId,
      quantity,
    });
    push('/cart');
  }, [addItem, productId, quantity, push]);

  return (
    <AdProvider
      productIds={[productId, ...items.map(({ productId }) => productId)]}
      contextKeys={[...new Set(displayProduct.categories || [])]}
    >
      <Head>
        <title>Otel Demo - Product</title>
      </Head>
      <Layout>
        <div className="lg:p-24" data-cy={CypressFields.ProductDetail}>
          <div className="grid grid-cols-1 lg:grid-cols-[40%_60%] gap-7">
            <div 
              className="w-full h-[150px] lg:h-[500px] bg-no-repeat bg-contain bg-center lg:bg-top" 
              style={{ backgroundImage: `url('/images/products/${displayProduct.picture}')` }}
              data-cy={CypressFields.ProductPicture} 
            />
            <div className="flex flex-col gap-4 px-5">
              <h5 className="text-xl lg:text-2xl m-0" data-cy={CypressFields.ProductName}>{displayProduct.name}</h5>
              <p className="m-0 text-gray-500 font-normal lg:text-lg" data-cy={CypressFields.ProductDescription}>{displayProduct.description}</p>
              <div className="font-bold lg:text-2xl m-0">
                <ProductPrice price={displayProduct.priceUsd!} />
              </div>
              <p className="m-0">Quantity</p>
              <Select
                value={quantity.toString()}
                onValueChange={(value) => setQuantity(+value)}
              >
                <SelectTrigger className="w-[100px]" data-cy={CypressFields.ProductQuantity}>
                  <SelectValue placeholder="Quantity" />
                </SelectTrigger>
                <SelectContent>
                  {quantityOptions.map(option => (
                    <SelectItem key={option} value={option.toString()}>
                      {option}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button 
                className="flex items-center gap-2.5 justify-center w-full text-sm font-normal lg:text-base lg:w-[220px]" 
                data-cy={CypressFields.ProductAddToCart} 
                onClick={onAddItem}
              >
                <Image src="/icons/Cart.svg" height="15" width="15" alt="cart" className="invert" /> Add To Cart
              </Button>
            </div>
          </div>
          {productId && (
              <ProductAIAssistantProvider productId={productId}>
                <ProductReviewProvider productId={productId}>
                  <ProductReviews />
                </ProductReviewProvider>
              </ProductAIAssistantProvider>
          )}
          <Recommendations />
        </div>
        <Ad />
      </Layout>
    </AdProvider>
  );
};

export default ProductDetail;
