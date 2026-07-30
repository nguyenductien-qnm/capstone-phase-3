// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { useState } from 'react';
import { CypressFields } from '../../utils/enums/CypressFields';
import { useCart } from '../../providers/Cart.provider';
import CartDropdown from '../CartDropdown';
import { ShoppingCart } from 'lucide-react';
import { Button } from '../ui/button';

const CartIcon = () => {
  const [isOpen, setIsOpen] = useState(false);
  const {
    cart: { items },
  } = useCart();

  return (
    <>
      <Button 
        variant="ghost" 
        size="icon" 
        className="relative" 
        data-cy={CypressFields.CartIcon} 
        onClick={() => setIsOpen(true)}
      >
        <ShoppingCart className="h-6 w-6" />
        {!!items.length && (
          <span 
            className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground"
            data-cy={CypressFields.CartItemCount}
          >
            {items.length}
          </span>
        )}
      </Button>
      <CartDropdown productList={items} isOpen={isOpen} onClose={() => setIsOpen(false)} />
    </>
  );
};

export default CartIcon;
