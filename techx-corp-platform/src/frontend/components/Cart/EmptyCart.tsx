import Link from 'next/link';
import Button from '../Button';

const EmptyCart = () => (
  <div className="flex min-h-[400px] flex-col items-center justify-center gap-4 text-center">
    <h2 className="text-2xl font-bold">Your shopping cart is empty!</h2>
    <p className="text-muted-foreground">Items you add to your shopping cart will appear here.</p>
    <Link href="/"><Button $type="primary">Continue Shopping</Button></Link>
  </div>
);

export default EmptyCart;
