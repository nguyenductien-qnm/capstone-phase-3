import { useMemo } from 'react';
import { useQuery, UseQueryOptions } from '@tanstack/react-query';
import ApiGateway from '../../gateways/Api.gateway';
import { Address, Money } from '../../protos/demo';
import { useCurrency } from '../../providers/Currency.provider';
import { IProductCartItem } from '../../types/Cart';
import ProductPrice from '../ProductPrice';
import CartItem from './CartItem';
import { Table, TableBody, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Separator } from '@/components/ui/separator';

interface IProps {
  productList: IProductCartItem[];
  shouldShowPrice?: boolean;
}

const CartItems = ({ productList, shouldShowPrice = true }: IProps) => {
  const { selectedCurrency } = useCurrency();
  const address: Address = {
    streetAddress: '1600 Amphitheatre Parkway',
    city: 'Mountain View',
    state: 'CA',
    country: 'United States',
    zipCode: '94043',
  };
  const { data: shippingConst = { units: 0, currencyCode: 'USD', nanos: 0 } } = useQuery({
    queryKey: ['shipping', productList, selectedCurrency, address],
    queryFn: () => ApiGateway.getShippingCost(productList, selectedCurrency, address),
  } as UseQueryOptions<Money, Error>);
  const total = useMemo<Money>(() => {
    const nanoSum =
      productList.reduce(
        (acc, { product: { priceUsd: { nanos = 0 } = {} }, quantity }) => acc + Number(nanos) * quantity,
        0
      ) + (shippingConst?.nanos || 0);
    const unitSum =
      productList.reduce(
        (acc, { product: { priceUsd: { units = 0 } = {} }, quantity }) => acc + Number(units) * quantity,
        0
      ) +
      (shippingConst?.units || 0) +
      Math.floor(nanoSum / 1e9);
    return { units: unitSum, currencyCode: selectedCurrency, nanos: nanoSum % 1e9 };
  }, [shippingConst, productList, selectedCurrency]);

  return (
    <div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Product</TableHead>
            <TableHead>Quantity</TableHead>
            <TableHead className="text-right">Price</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {productList.map(({ productId, product, quantity }) => (
            <CartItem key={productId} product={product} quantity={quantity} />
          ))}
        </TableBody>
      </Table>
      {shouldShowPrice && (
        <>
          <Separator className="my-4" />
          <div className="flex justify-between text-sm">
            <span>Shipping</span>
            <ProductPrice price={shippingConst} />
          </div>
          <div className="mt-2 flex justify-between text-lg font-bold">
            <span>Total</span>
            <ProductPrice price={total} />
          </div>
        </>
      )}
    </div>
  );
};

export default CartItems;
