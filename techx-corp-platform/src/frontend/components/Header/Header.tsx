// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import Link from 'next/link';
import Image from 'next/image';
import CartIcon from '../CartIcon';
import CurrencySwitcher from '../CurrencySwitcher';
import { Sparkles, Telescope } from 'lucide-react';

const Header = () => {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/80 backdrop-blur-md supports-[backdrop-filter]:bg-background/60 shadow-sm transition-all duration-300">
      <div className="container flex h-16 md:h-20 items-center justify-between px-4 md:px-8 mx-auto max-w-7xl">
        <Link href="/" className="flex items-center gap-3 transition-opacity hover:opacity-90">
          <div className="bg-foreground p-2 rounded-xl">
            <Telescope className="w-6 h-6 text-background" />
          </div>
          <span className="font-bold text-xl md:text-2xl tracking-tight text-foreground">
            TechX Astro
          </span>
        </Link>

        <nav className="hidden md:flex items-center gap-8">

          <Link
            href="/#hot-products"
            className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            Telescopes
          </Link>
          <Link
            href="/#accessories"
            className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            Accessories
          </Link>
        </nav>

        <div className="flex items-center gap-4 md:gap-6">
          <CurrencySwitcher />
          <CartIcon />
        </div>
      </div>
    </header>
  );
};

export default Header;
