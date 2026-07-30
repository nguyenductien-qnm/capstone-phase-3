// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { useRouter } from 'next/router';
import { useCallback, useRef } from 'react';
import CartItems from '../CartItems';
import CheckoutForm from '../CheckoutForm';
import { IFormData } from '../CheckoutForm/CheckoutForm';
import SessionGateway from '../../gateways/Session.gateway';
import { useCart } from '../../providers/Cart.provider';
import { useCurrency } from '../../providers/Currency.provider';
import { Button } from '../ui/button';

const { userId } = SessionGateway.getSession();

const CartDetail = () => {
  const {
    cart: { items },
    emptyCart,
    placeOrder,
  } = useCart();
  const { selectedCurrency } = useCurrency();
  const { push } = useRouter();
  const checkoutIdempotencyKey = useRef<string | null>(null);

  const onPlaceOrder = useCallback(
    async ({
      email,
      state,
      streetAddress,
      country,
      city,
      zipCode,
      creditCardCvv,
      creditCardExpirationMonth,
      creditCardExpirationYear,
      creditCardNumber,
    }: IFormData) => {
      const idempotencyKey = checkoutIdempotencyKey.current ?? crypto.randomUUID();
      checkoutIdempotencyKey.current = idempotencyKey;
      const order = await placeOrder(
        {
          userId,
          email,
          address: {
            streetAddress,
            state,
            country,
            city,
            zipCode,
          },
          userCurrency: selectedCurrency,
          creditCard: {
            creditCardCvv,
            creditCardExpirationMonth,
            creditCardExpirationYear,
            creditCardNumber,
          },
        },
        idempotencyKey
      );
      checkoutIdempotencyKey.current = null;

      push({
        pathname: `/cart/checkout/${order.orderId}`,
        query: { order: JSON.stringify(order) },
      });
    },
    [placeOrder, push, selectedCurrency]
  );

  return (
    <div className="flex flex-col gap-12 lg:grid lg:grid-cols-2 lg:gap-16">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b pb-4">
          <h1 className="text-3xl font-bold tracking-tight">Shopping Cart</h1>
          <Button 
            variant="destructive"
            size="sm"
            onClick={emptyCart} 
          >
            Empty Cart
          </Button>
        </div>
        <CartItems productList={items} />
      </div>
      <div>
        <CheckoutForm onSubmit={onPlaceOrder} />
      </div>
    </div>
  );
};

export default CartDetail;
