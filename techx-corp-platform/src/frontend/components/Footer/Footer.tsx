// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useState } from 'react';
import SessionGateway from '../../gateways/Session.gateway';
import { CypressFields } from '../../utils/enums/CypressFields';
import PlatformFlag from '../PlatformFlag';
import Link from 'next/link';
import { Telescope } from 'lucide-react';

const currentYear = new Date().getFullYear();

const { userId } = SessionGateway.getSession();

const Footer = () => {
  const [sessionId, setSessionId] = useState('');

  useEffect(() => {
    setSessionId(userId);
  }, []);

  return (
    <footer className="w-full border-t border-border bg-card text-card-foreground">
      <div className="container mx-auto px-4 md:px-8 max-w-7xl pt-16 pb-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-12 md:gap-8 mb-16">
          <div className="flex flex-col gap-4 md:col-span-2">
            <Link href="/" className="flex items-center gap-3 w-fit">
              <div className="bg-primary/10 p-2 rounded-xl">
                <Telescope className="w-6 h-6 text-primary" />
              </div>
              <span className="font-bold text-xl tracking-tight">TechX Astro</span>
            </Link>
            <p className="text-muted-foreground max-w-sm">
              This website is hosted for demo purposes only. It is not an actual shop.
              Explore the stars with our premium telescope collection.
            </p>
          </div>
          
          <div className="flex flex-col gap-4">
            <h3 className="font-semibold text-foreground">Categories</h3>
            <Link href="#" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Telescopes</Link>
            <Link href="#" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Binoculars</Link>
            <Link href="#" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Accessories</Link>
            <Link href="#" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Mounts & Tripods</Link>
          </div>
          
          <div className="flex flex-col gap-4">
            <h3 className="font-semibold text-foreground">Legal & Info</h3>
            <Link href="#" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Privacy Policy</Link>
            <Link href="#" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Terms of Service</Link>
            <Link href="#" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Shipping & Returns</Link>
            <span className="text-sm text-muted-foreground flex flex-col gap-1 mt-2">
              <span className="font-medium text-foreground">Session ID:</span>
              <span className="font-mono text-xs truncate bg-muted/50 p-1.5 rounded-md" data-cy={CypressFields.SessionId}>{sessionId}</span>
            </span>
          </div>
        </div>
        
        <div className="pt-8 border-t border-border flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-sm text-muted-foreground font-medium">
            &copy; {currentYear} TechX Corp. All rights reserved.
          </p>
          <div className="flex justify-center">
            <PlatformFlag />
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
