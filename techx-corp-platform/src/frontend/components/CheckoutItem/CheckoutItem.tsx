// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import Image from 'next/image';
import { useState } from 'react';
import { CypressFields } from '../../utils/enums/CypressFields';
import { Address } from '../../protos/demo';
import { IProductCheckoutItem } from '../../types/Cart';
import ProductPrice from '../ProductPrice';
import { Button } from '../ui/button';

interface IProps {
  checkoutItem: IProductCheckoutItem;
  address: Address;
}

const CheckoutItem = ({
  checkoutItem: {
    item: {
      quantity,
      product: { picture, name },
    },
    cost = { currencyCode: 'USD', units: 0, nanos: 0 },
  },
  address: { streetAddress = '', city = '', state = '', zipCode = '', country = '' },
}: IProps) => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <div 
      className="grid grid-cols-1 lg:grid-cols-[40%_40%_1fr] p-6 rounded-lg border bg-card text-card-foreground shadow-sm"
      data-cy={CypressFields.CheckoutItem}
    >
      <div className="flex gap-6 pb-6 border-b lg:pb-0 lg:pr-6 lg:border-b-0 lg:border-r">
        <div className="relative h-20 w-20 flex-shrink-0 overflow-hidden rounded-md bg-muted">
          <Image
            src={`/images/products/${picture}`}
            alt={name}
            fill
            className="object-cover"
          />
        </div>
        <div className="flex flex-col gap-1 justify-center">
          <h5 className="text-lg font-semibold m-0">{name}</h5>
          <p className="text-muted-foreground m-0">Quantity: {quantity}</p>
          <p className="font-medium m-0">
            Total: <ProductPrice price={cost} />
          </p>
        </div>
      </div>
      
      <div className="flex flex-col gap-1 py-6 border-b lg:py-0 lg:px-6 lg:border-b-0 lg:border-r justify-center">
        <h5 className="text-lg font-semibold m-0 mb-1">Shipping Data</h5>
        <p className="text-muted-foreground m-0 font-light">Street: {streetAddress}</p>
        {!isCollapsed && (
          <Button 
            variant="link"
            size="sm"
            className="p-0 h-auto text-primary justify-start mt-1"
            onClick={() => setIsCollapsed(true)}
          >
            See More
          </Button>
        )}
        {isCollapsed && (
          <>
            <p className="text-muted-foreground m-0 font-light">City: {city}</p>
            <p className="text-muted-foreground m-0 font-light">State: {state}</p>
            <p className="text-muted-foreground m-0 font-light">Zip Code: {zipCode}</p>
            <p className="text-muted-foreground m-0 font-light">Country: {country}</p>
          </>
        )}
      </div>
      
      <div className="flex items-center justify-center pt-6 lg:pt-0 gap-2">
        <div className="h-6 w-6 rounded-full bg-green-100 text-green-600 flex items-center justify-center">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        </div>
        <span className="font-semibold text-green-600">Done</span>
      </div>
    </div>
  );
};

export default CheckoutItem;
