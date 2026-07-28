import { useState } from 'react';
import { CypressFields } from '../../utils/enums/CypressFields';
import { useCart } from '../../providers/Cart.provider';
import CartDropdown from '../CartDropdown';

const CartIcon = () => {
  const [isOpen, setIsOpen] = useState(false);
  const { cart: { items } } = useCart();

  return (
    <>
      <button onClick={() => setIsOpen(true)} data-cy={CypressFields.CartIcon}
        className="relative rounded-md p-2 transition hover:bg-muted">
        <img src="/icons/CartIcon.svg" alt="Cart" title="Cart" className="h-6 w-6" />
        {!!items.length && (
          <span data-cy={CypressFields.CartItemCount}
            className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs font-bold text-white">
            {items.length}
          </span>
        )}
      </button>
      <CartDropdown productList={items} isOpen={isOpen} onClose={() => setIsOpen(false)} />
    </>
  );
};

export default CartIcon;
