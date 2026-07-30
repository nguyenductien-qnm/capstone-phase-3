// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { useMemo } from 'react';
import { useQuery, UseQueryOptions } from '@tanstack/react-query';
import Link from 'next/link';
import Image from 'next/image';
import ApiGateway from '../../gateways/Api.gateway';
import { Address, Money } from '../../protos/demo';
import { useCurrency } from '../../providers/Currency.provider';
import { IProductCartItem } from '../../types/Cart';
import ProductPrice from '../ProductPrice';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableFooter,
} from '../ui/table';

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

  const queryKey = ['shipping', productList, selectedCurrency, address];
  const queryFn = () => ApiGateway.getShippingCost(productList, selectedCurrency, address);
  const queryOptions: UseQueryOptions<Money, Error> = {
    queryKey,
    queryFn,
  };
  const { data: shippingConst = { units: 0, currencyCode: 'USD', nanos: 0 } } = useQuery(queryOptions);

  const total = useMemo<Money>(() => {
    const nanoSum =
      productList.reduce((acc, { product: { priceUsd: { nanos = 0 } = {} }, quantity }) => acc + Number(nanos) * quantity, 0) +
        shippingConst?.nanos || 0;
    const nanoExceed = Math.floor(nanoSum / 1000000000);

    const unitSum =
      productList.reduce((acc, { product: { priceUsd: { units = 0 } = {} }, quantity }) => acc + Number(units) * quantity, 0) +
        (shippingConst?.units || 0) + nanoExceed;

    return {
      units: unitSum,
      currencyCode: selectedCurrency,
      nanos: nanoSum % 1000000000,
    };
  }, [shippingConst?.units, shippingConst?.nanos, productList, selectedCurrency]);

  return (
    <div className="w-full overflow-hidden rounded-lg border bg-card text-card-foreground shadow-sm">
      <Table>
        <TableHeader className="bg-muted/50">
          <TableRow>
            <TableHead className="w-[50%]">Product</TableHead>
            <TableHead className="text-center">Quantity</TableHead>
            <TableHead className="text-right">Price</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {productList.map(({ productId, product: { id, name, picture, priceUsd = { units: 0, nanos: 0, currencyCode: 'USD' } }, quantity }) => (
            <TableRow key={productId}>
              <TableCell>
                <Link href={`/product/${id}`} className="flex items-center gap-4 hover:underline">
                  <div className="relative h-16 w-16 md:h-24 md:w-24 flex-shrink-0 overflow-hidden rounded-md border bg-muted">
                    <Image
                      src={`/images/products/${picture}`}
                      alt={name}
                      fill
                      className="object-cover"
                    />
                  </div>
                  <span className="font-medium">{name}</span>
                </Link>
              </TableCell>
              <TableCell className="text-center font-medium">{quantity}</TableCell>
              <TableCell className="text-right font-medium">
                <ProductPrice price={priceUsd} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
        {shouldShowPrice && (
          <TableFooter className="bg-muted/50">
            <TableRow>
              <TableCell colSpan={2} className="text-right font-medium text-muted-foreground">Shipping</TableCell>
              <TableCell className="text-right font-medium">
                <ProductPrice price={shippingConst} />
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell colSpan={2} className="text-right text-lg font-bold">Total</TableCell>
              <TableCell className="text-right text-lg font-bold text-primary">
                <ProductPrice price={total} />
              </TableCell>
            </TableRow>
          </TableFooter>
        )}
      </Table>
    </div>
  );
};

export default CartItems;
