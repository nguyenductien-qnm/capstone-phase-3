import Link from 'next/link';
import { CypressFields } from '../../utils/enums/CypressFields';
import { IProductCartItem } from '../../types/Cart';
import ProductPrice from '../ProductPrice';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Button } from '@/components/ui/button';

interface IProps { isOpen: boolean; onClose(): void; productList: IProductCartItem[]; }

const CartDropdown = ({ productList, isOpen, onClose }: IProps) => (
  <Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
    <SheetContent side="right" className="flex w-full flex-col sm:max-w-md" data-cy={CypressFields.CartDropdown}>
      <SheetHeader>
        <SheetTitle>Shopping Cart</SheetTitle>
      </SheetHeader>
      <Separator />
      <ScrollArea className="flex-1">
        {!productList.length && (
          <p className="py-12 text-center text-muted-foreground">Your shopping cart is empty</p>
        )}
        {productList.map(({ quantity, product: { name, picture, id, priceUsd } }) => (
          <div key={id} className="flex gap-4 py-4" data-cy={CypressFields.CartDropdownItem}>
            <img src={'/images/products/' + picture} alt={name} className="h-16 w-16 rounded-md object-cover" />
            <div className="flex-1">
              <p className="text-sm font-medium">{name}</p>
              <ProductPrice price={priceUsd || { nanos: 0, currencyCode: 'USD', units: 0 }} />
              <p className="text-xs text-muted-foreground">Quantity: {quantity}</p>
            </div>
          </div>
        ))}
      </ScrollArea>
      <Separator />
      <Link href="/cart" onClick={onClose} className="mt-2">
        <Button className="w-full" data-cy={CypressFields.CartGoToShopping}>Go to Shopping Cart</Button>
      </Link>
    </SheetContent>
  </Sheet>
);

export default CartDropdown;
