import Image from 'next/image';
import { useState } from 'react';
import { CypressFields } from '../../utils/enums/CypressFields';
import { Address } from '../../protos/demo';
import { IProductCheckoutItem } from '../../types/Cart';
import ProductPrice from '../ProductPrice';
import { Separator } from '@/components/ui/separator';

interface IProps { checkoutItem: IProductCheckoutItem; address: Address; }

const CheckoutItem = ({ checkoutItem: { item: { quantity, product: { picture, name } }, cost }, address: { streetAddress, city, state, zipCode, country } }: IProps) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  return (
    <div data-cy={CypressFields.CheckoutItem} className="rounded-lg border p-4">
      <div className="flex items-center gap-4">
        <img src={'/images/products/' + picture} alt={name} className="h-16 w-16 rounded-md object-cover" />
        <div className="flex-1">
          <p className="font-medium">{name}</p>
          <p className="text-sm text-muted-foreground">Quantity: {quantity}</p>
          <p className="text-sm">Total: <ProductPrice price={cost || { currencyCode: 'USD', units: 0, nanos: 0 }} /></p>
        </div>
      </div>
      <Separator className="my-3" />
      <div className="text-sm">
        <p className="font-medium">Shipping Data</p>
        <p className="text-muted-foreground">Street: {streetAddress || ''}</p>
        {!isCollapsed && <button onClick={() => setIsCollapsed(true)} className="text-blue-600 hover:underline">See More</button>}
        {isCollapsed && <><p className="text-muted-foreground">City: {city || ''}</p><p className="text-muted-foreground">State: {state || ''}</p><p className="text-muted-foreground">Zip: {zipCode || ''}</p><p className="text-muted-foreground">Country: {country || ''}</p></>}
      </div>
      <div className="mt-2 flex items-center gap-1 text-green-600"><Image src="/icons/Check.svg" alt="check" height="14" width="16" /><span>Done</span></div>
    </div>
  );
};

export default CheckoutItem;
