// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { CypressFields } from '../../utils/enums/CypressFields';
import { useAd } from '../../providers/Ad.provider';
import ProductCard from '../ProductCard';
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from '../ui/carousel';

const Recommendations = () => {
  const { recommendedProductList } = useAd();

  if (!recommendedProductList || recommendedProductList.length === 0) {
    return null;
  }

  return (
    <section data-cy={CypressFields.RecommendationList} className="mt-16 w-full py-8">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary">
              AI recommendations
            </span>
            <span className="text-xs text-muted-foreground">Semantic similarity with safe fallback</span>
          </div>
          <h2 className="text-3xl font-bold tracking-tight text-foreground">You May Also Like</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Related products ranked from the item you are viewing.
          </p>
        </div>
      </div>
      
      <div className="px-12 relative w-full">
        <Carousel
          opts={{
            align: "start",
            loop: true,
          }}
          className="w-full"
        >
          <CarouselContent className="-ml-2 md:-ml-4">
            {recommendedProductList.map(product => (
              <CarouselItem key={product.id} className="pl-2 md:pl-4 sm:basis-1/2 md:basis-1/3 lg:basis-1/4">
                <ProductCard product={product} />
              </CarouselItem>
            ))}
          </CarouselContent>
          <CarouselPrevious className="absolute -left-4 top-1/2 -translate-y-1/2 border-border bg-background shadow-md hover:bg-muted" />
          <CarouselNext className="absolute -right-4 top-1/2 -translate-y-1/2 border-border bg-background shadow-md hover:bg-muted" />
        </Carousel>
      </div>
    </section>
  );
};

export default Recommendations;
