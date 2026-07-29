import { useRouter } from 'next/router';
import { useCallback, useRef } from 'react';
import CartItems from '../CartItems';
import CheckoutForm from '../CheckoutForm';
import { IFormData } from '../CheckoutForm/CheckoutForm';
import SessionGateway from '../../gateways/Session.gateway';
import { useCart } from '../../providers/Cart.provider';
import { useCurrency } from '../../providers/Currency.provider';
import Button from '../Button';

const { userId } = SessionGateway.getSession();

const CartDetail = () => {
  const { cart: { items }, emptyCart, placeOrder } = useCart();
  const { selectedCurrency } = useCurrency();
  const { push } = useRouter();
  const checkoutIdempotencyKey = useRef<string | null>(null);

  const onPlaceOrder = useCallback(async ({ email, state, streetAddress, country, city, zipCode, creditCardCvv, creditCardExpirationMonth, creditCardExpirationYear, creditCardNumber }: IFormData) => {
    const idempotencyKey = checkoutIdempotencyKey.current ?? crypto.randomUUID();
    checkoutIdempotencyKey.current = idempotencyKey;
    const order = await placeOrder({ userId, email, address: { streetAddress, state, country, city, zipCode }, userCurrency: selectedCurrency, creditCard: { creditCardCvv, creditCardExpirationMonth, creditCardExpirationYear, creditCardNumber } }, idempotencyKey);
    checkoutIdempotencyKey.current = null;
    push({ pathname: `/cart/checkout/${order.orderId}`, query: { order: JSON.stringify(order) } });
  }, [placeOrder, push, selectedCurrency]);

  return (
    <div className="mx-auto grid max-w-7xl gap-8 px-4 py-8 lg:grid-cols-[1fr_400px]">
      <div>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-2xl font-bold">Shopping Cart</h2>
          <Button $type="link" onClick={emptyCart}>Empty Cart</Button>
        </div>
        <CartItems productList={items} />
      </div>
      <CheckoutForm onSubmit={onPlaceOrder} />
    </div>
  );
};

export default CartDetail;
