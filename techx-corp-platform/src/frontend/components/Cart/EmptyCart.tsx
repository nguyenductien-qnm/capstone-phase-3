// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import Link from 'next/link';
import { Button } from '../ui/button';

const EmptyCart = () => {
  return (
    <div className="flex flex-col items-center justify-center py-20 px-4 text-center">
      <div className="rounded-full bg-muted p-6 mb-6">
        <svg 
          xmlns="http://www.w3.org/2000/svg" 
          width="48" 
          height="48" 
          viewBox="0 0 24 24" 
          fill="none" 
          stroke="currentColor" 
          strokeWidth="2" 
          strokeLinecap="round" 
          strokeLinejoin="round" 
          className="text-muted-foreground"
        >
          <circle cx="8" cy="21" r="1" />
          <circle cx="19" cy="21" r="1" />
          <path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12" />
        </svg>
      </div>
      <h2 className="text-3xl font-bold tracking-tight mb-3">Your shopping cart is empty!</h2>
      <p className="text-lg text-muted-foreground mb-8 max-w-[500px]">
        Items you add to your shopping cart will appear here. Start shopping to add items to your cart.
      </p>

      <Link href="/">
        <Button size="lg" className="px-8 text-base">Continue Shopping</Button>
      </Link>
    </div>
  );
};

export default EmptyCart;
