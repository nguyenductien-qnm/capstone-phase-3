// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import Link from 'next/link';
import Image from 'next/image';
import { CypressFields } from '../../utils/enums/CypressFields';
import { IProductCartItem } from '../../types/Cart';
import ProductPrice from '../ProductPrice';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetFooter,
} from '../ui/sheet';
import { Button } from '../ui/button';
import { ScrollArea } from '../ui/scroll-area';

interface IProps {
  isOpen: boolean;
  onClose(open: boolean): void;
  productList: IProductCartItem[];
}

const CartDropdown = ({ productList, isOpen, onClose }: IProps) => {
  return (
    <Sheet open={isOpen} onOpenChange={onClose}>
      <SheetContent data-cy={CypressFields.CartDropdown} className="w-full sm:max-w-md flex flex-col">
        <SheetHeader>
          <SheetTitle className="text-2xl font-bold">Shopping Cart</SheetTitle>
        </SheetHeader>
        
        <ScrollArea className="flex-1 -mx-6 px-6 py-4">
          {!productList.length && (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground mt-10">
              <p className="text-lg">Your shopping cart is empty</p>
            </div>
          )}
          
          <div className="flex flex-col gap-6">
            {productList.map(
              ({ quantity, product: { name, picture, id, priceUsd = { nanos: 0, currencyCode: 'USD', units: 0 } } }) => (
                <div key={id} data-cy={CypressFields.CartDropdownItem} className="flex gap-4 border-b pb-4 last:border-0">
                  <div className="relative h-20 w-20 rounded-md overflow-hidden bg-muted flex-shrink-0">
                    <Image
                      src={`/images/products/${picture}`}
                      alt={name}
                      fill
                      className="object-cover"
                    />
                  </div>
                  <div className="flex flex-col flex-1 justify-between">
                    <div>
                      <h4 className="font-medium text-sm leading-none mb-1">{name}</h4>
                      <p className="text-sm text-muted-foreground">Quantity: {quantity}</p>
                    </div>
                    <div className="font-semibold text-primary">
                      <ProductPrice price={priceUsd} />
                    </div>
                  </div>
                </div>
              )
            )}
          </div>
        </ScrollArea>

        {productList.length > 0 && (
          <SheetFooter className="mt-auto pt-6 pb-2">
            <Link href="/cart" className="w-full" onClick={() => onClose(false)}>
              <Button className="w-full" size="lg" data-cy={CypressFields.CartGoToShopping}>
                Go to Shopping Cart
              </Button>
            </Link>
          </SheetFooter>
        )}
      </SheetContent>
    </Sheet>
  );
};

export default CartDropdown;
