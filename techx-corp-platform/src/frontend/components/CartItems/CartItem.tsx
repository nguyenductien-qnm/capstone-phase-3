import Link from 'next/link';
import { Product } from '../../protos/demo';
import ProductPrice from '../ProductPrice';
import { TableCell, TableRow } from '@/components/ui/table';

interface IProps { product: Product; quantity: number; }

const CartItem = ({ product: { id, name, picture, priceUsd }, quantity }: IProps) => (
  <TableRow>
    <TableCell>
      <Link href={`/product/${id}`} className="flex items-center gap-3">
        <img alt={name} src={'/images/products/' + picture} className="h-12 w-12 rounded-md object-cover" />
        <span>{name}</span>
      </Link>
    </TableCell>
    <TableCell>{quantity}</TableCell>
    <TableCell className="text-right"><ProductPrice price={priceUsd || { units: 0, nanos: 0, currencyCode: 'USD' }} /></TableCell>
  </TableRow>
);

export default CartItem;
