// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import Link from 'next/link';
import Image from 'next/image';
import { Button } from '../ui/button';
import { ArrowRight, Star } from 'lucide-react';
import { HeroVideoDialog } from "../ui/hero-video-dialog";

const Banner = () => {
  return (
    <section className="relative w-full overflow-hidden border-b border-border/40">
      <div className="absolute inset-0 bg-background" />

      <div className="container relative z-10 mx-auto px-4 py-32 md:px-8 lg:py-48 max-w-7xl">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          
          <div className="flex flex-col items-center text-center lg:items-start lg:text-left space-y-8 max-w-2xl mx-auto lg:mx-0">
            <div className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              <span>TechX Corporation</span>
            </div>
            
            <h1 className="text-5xl md:text-6xl lg:text-[5.5rem] font-medium tracking-tight text-foreground leading-[1.05]">
              The best telescopes to see the world closer.
            </h1>
            
            <p className="text-lg sm:text-xl text-muted-foreground max-w-xl">
              Discover a whole new universe from your backyard. Let's make stargazing easier and much more enjoyable.
            </p>
            
            <div className="flex flex-col sm:flex-row items-center gap-4 w-full sm:w-auto pt-4">
              <Link href="#hot-products" className="w-full sm:w-auto">
                <Button size="lg" className="w-full sm:w-auto text-base rounded-full px-8 h-12 bg-foreground text-background hover:bg-foreground/90 transition-colors border-none">
                  Go Shopping
                </Button>
              </Link>

            </div>
          </div>

          <div className="relative w-full flex items-center justify-center p-4 lg:p-8">
            <HeroVideoDialog
              animationStyle="from-center"
              videoSrc="https://www.youtube.com/embed/qh3NGpYRG3I?si=4rb-zSdDkVK9qxxb"
              thumbnailSrc="/images/Banner.png"
              thumbnailAlt="Telescope Banner"
              className="w-full h-full max-w-2xl mx-auto"
            />
          </div>

        </div>
      </div>
    </section>
  );
};

export default Banner;
