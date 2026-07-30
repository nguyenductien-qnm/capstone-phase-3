// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { CypressFields } from '../../utils/enums/CypressFields';
import { Product } from '../../protos/demo';
import ProductPrice from '../ProductPrice';
import { useState, useEffect } from 'react';
import { useNumberFlagValue } from '@openfeature/react-sdk';
import Link from 'next/link';
import { Card, CardContent, CardFooter } from '../ui/card';
import { ArrowUpRight } from 'lucide-react';

interface IProps {
  product: Product;
}

async function getImageWithHeaders(requestInfo: Request) {
  const res = await fetch(requestInfo);
  return await res.blob();
}

const ProductCard = ({
  product: {
    id,
    picture,
    name,
    priceUsd = {
      currencyCode: 'USD',
      units: 0,
      nanos: 0,
    },
  },
}: IProps) => {
  const imageSlowLoad = useNumberFlagValue('imageSlowLoad', 0);
  const [imageSrc, setImageSrc] = useState<string>('');

  useEffect(() => {
    const headers = new Headers();
    headers.append('x-envoy-fault-delay-request', imageSlowLoad.toString());
    headers.append('Cache-Control', 'no-cache')
    const requestInit = {
      method: "GET",
      headers: headers
    };
    const image_url ='/images/products/' + picture
    const requestInfo = new Request(image_url, requestInit);
    getImageWithHeaders(requestInfo).then(blob => {
      setImageSrc(URL.createObjectURL(blob));
    });
  }, [imageSlowLoad, picture]);

  return (
    <Link href={`/product/${id}`} className="block h-full group">
      <Card className="relative h-full overflow-hidden bg-card border border-border/50 rounded-2xl transition-all duration-300 flex flex-col hover:-translate-y-1 hover:shadow-xl hover:border-border" data-cy={CypressFields.ProductCard}>
        <div className="relative aspect-square overflow-hidden bg-muted/30">
          <div className="absolute inset-0 bg-gradient-to-t from-background/90 to-transparent z-10 opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-end p-4">
            <span className="flex items-center text-sm font-medium text-primary">
              View Details <ArrowUpRight className="ml-1 w-4 h-4" />
            </span>
          </div>
          {imageSrc ? (
            <img 
              src={imageSrc} 
              alt={name} 
              className="object-cover w-full h-full transition-transform duration-700 ease-out group-hover:scale-110" 
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center animate-pulse bg-muted-foreground/10" />
          )}
        </div>
        <CardContent className="p-5 flex-1">
          <h3 className="font-semibold text-lg line-clamp-2 leading-tight text-foreground group-hover:text-primary transition-colors">{name}</h3>
        </CardContent>
        <CardFooter className="p-5 pt-0 mt-auto">
          <div className="w-full flex items-center justify-between">
            <ProductPrice price={priceUsd} />
          </div>
        </CardFooter>
      </Card>
    </Link>
  );
};

export default ProductCard;
