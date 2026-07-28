import CartIcon from '../CartIcon';
import CurrencySwitcher from '../CurrencySwitcher';

const Header = () => (
  <header className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur">
    <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
      <a href="/" className="flex items-center gap-2 text-xl font-bold">
        <span className="rounded-md bg-blue-600 px-2 py-1 text-sm font-extrabold text-white">TechX</span>
        <span className="hidden sm:inline">Corp</span>
      </a>
      <div className="flex items-center gap-4">
        <CurrencySwitcher />
        <CartIcon />
      </div>
    </div>
  </header>
);

export default Header;
