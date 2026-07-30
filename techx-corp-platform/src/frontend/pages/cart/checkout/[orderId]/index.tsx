// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { NextPage } from 'next';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useMemo } from 'react';
import Ad from '../../../../components/Ad';
import { Button } from '../../../../components/ui/button';
import Layout from '../../../../components/Layout';
import ProductPrice from '../../../../components/ProductPrice';
import Recommendations from '../../../../components/Recommendations';
import AdProvider from '../../../../providers/Ad.provider';
import { Money } from '../../../../protos/demo';
import { IProductCheckout } from '../../../../types/Cart';

const Checkout: NextPage = () => {
  const { query } = useRouter();
  const { orderId, items = [], shippingAddress, shippingCost = { units: 0, currencyCode: 'USD', nanos: 0 } } = JSON.parse((query.order || '{}') as string) as IProductCheckout;

  const orderTotal = useMemo<Money>(() => {
    const itemsTotal = items.reduce((acc, { item, cost = { units: 0, nanos: 0, currencyCode: 'USD' } }) => {
      return {
        units: acc.units + (cost.units || 0) * item.quantity,
        nanos: acc.nanos + (cost.nanos || 0) * item.quantity,
        currencyCode: cost.currencyCode || 'USD',
      };
    }, { units: 0, nanos: 0, currencyCode: 'USD' });

    const totalNanos = itemsTotal.nanos + (shippingCost.nanos || 0);
    const nanoExceed = Math.floor(totalNanos / 1000000000);

    return {
      units: itemsTotal.units + (shippingCost.units || 0) + nanoExceed,
      nanos: totalNanos % 1000000000,
      currencyCode: shippingCost.currencyCode || 'USD',
    };
  }, [items, shippingCost]);

  return (
    <AdProvider
      productIds={items.map(({ item }) => item?.productId || '')}
      contextKeys={[...new Set(items.flatMap(({ item }) => item.product.categories))]}
    >
      <Head>
        <title>Otel Demo - Checkout</title>
      </Head>
      <Layout>
        <div className="m-5 lg:m-24">
          <div className="flex flex-col gap-7 mb-30 lg:grid lg:grid-cols-2 lg:gap-10 lg:grid-areas-checkout">
            <div className="flex flex-col gap-4 lg:col-start-1 lg:col-end-2">
              <h1 className="text-center m-0 text-xl lg:text-left lg:text-3xl font-bold">Your order is complete!</h1>
              <h3 className="text-center m-0 text-base text-gray-400 font-medium lg:text-left lg:text-lg">We&apos;ve sent you a confirmation email.</h3>
              <div className="flex gap-2 justify-center mt-2 lg:justify-start">
                <span className="font-bold text-gray-700">Order ID:</span>
                <span className="text-gray-700">{orderId}</span>
              </div>
            </div>

            <div className="flex flex-col gap-2 p-5 bg-gray-50 rounded-lg lg:col-start-2 lg:col-end-3 text-right">
              <h4 className="m-0 mb-3 text-xl text-gray-700 font-bold">Shipping Address</h4>
              <p className="m-0 my-1 text-base text-gray-700">{shippingAddress.streetAddress}</p>
              <p className="m-0 my-1 text-base text-gray-700">{shippingAddress.city}, {shippingAddress.state} {shippingAddress.zipCode}</p>
              <p className="m-0 my-1 text-base text-gray-700">{shippingAddress.country}</p>
            </div>

            <div className="flex flex-col gap-6 lg:col-span-2">
              <h4 className="m-0 mb-3 text-xl text-gray-700 font-bold">Order Items</h4>
              <div className="flex flex-col gap-4">
                {items.map(({ item, cost = { units: 0, currencyCode: 'USD', nanos: 0 } }) => {
                  const itemTotal: Money = {
                    units: (cost.units || 0) * item.quantity,
                    nanos: (cost.nanos || 0) * item.quantity,
                    currencyCode: cost.currencyCode || 'USD',
                  };
                  // Handle nanos overflow
                  const nanoExceed = Math.floor(itemTotal.nanos / 1000000000);
                  itemTotal.units += nanoExceed;
                  itemTotal.nanos = itemTotal.nanos % 1000000000;

                  return (
                    <div key={item.productId} className="flex gap-4 items-center p-4 bg-white border border-gray-200 rounded-lg">
                      <img className="w-20 h-20 object-contain rounded-sm shrink-0" src={"/images/products/" + item.product.picture} alt={item.product.name}/>
                      <div className="flex flex-col gap-1 flex-1">
                        <h5 className="m-0 text-lg font-normal">{item.product.name}</h5>
                        <p className="m-0 text-base text-gray-400">Quantity: {item.quantity}</p>
                      </div>
                      <div className="text-lg font-bold text-gray-700 text-right whitespace-nowrap">
                        <ProductPrice price={itemTotal} />
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="flex flex-col gap-3 p-6 bg-gray-50 rounded-lg mt-4">
                <div className="flex justify-between items-center text-base text-gray-700">
                  <span>Shipping:</span>
                  <ProductPrice price={shippingCost} />
                </div>
                <div className="flex justify-between items-center pt-3 border-t-2 border-gray-200 mt-2">
                  <span className="text-xl font-bold text-gray-700">Total:</span>
                  <span className="text-xl font-bold text-gray-700">
                    <ProductPrice price={orderTotal} />
                  </span>
                </div>
              </div>
            </div>

            <div className="flex justify-center items-center lg:col-span-2">
              <Link href="/">
                <Button type="button">Continue Shopping</Button>
              </Link>
            </div>
          </div>
          <Recommendations />
        </div>
        <Ad />
      </Layout>
    </AdProvider>
  );
};

export default Checkout;
