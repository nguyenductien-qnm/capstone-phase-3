// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { CypressFields } from '../../utils/enums/CypressFields';
import { Product } from '../../protos/demo';
import ProductCard from '../ProductCard';
import { Button } from '../ui/button';
import { ArrowRight } from 'lucide-react';
import Link from 'next/link';

interface IProps {
  productList: Product[];
  title?: string;
  subtitle?: string;
  viewAllLink?: string;
}

const ProductList = ({ productList, title = "Hot Products", subtitle = "Discover our most popular picks", viewAllLink = "#" }: IProps) => {
  return (
    <section className="w-full py-12" data-cy={CypressFields.ProductList}>
      <div className="flex flex-col sm:flex-row items-start sm:items-end justify-between mb-10 gap-4">
        <div className="space-y-2">
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">{title}</h2>
          <p className="text-lg text-muted-foreground">{subtitle}</p>
        </div>
        <Link href={viewAllLink}>
          <Button variant="outline" className="group rounded-full px-6 border-border/60 hover:bg-muted">
            View all products
            <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
          </Button>
        </Link>
      </div>
      
      <div className="grid grid-flow-dense grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6 lg:gap-8">
        {productList.map(product => (
          <ProductCard key={product.id} product={product} />
        ))}
      </div>
    </section>
  );
};

export default ProductList;
