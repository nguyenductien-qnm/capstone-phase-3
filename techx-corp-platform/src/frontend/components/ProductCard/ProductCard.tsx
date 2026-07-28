import { CypressFields } from '../../utils/enums/CypressFields';
import { Product } from '../../protos/demo';
import ProductPrice from '../ProductPrice';
import { useState, useEffect } from 'react';
import { useNumberFlagValue } from '@openfeature/react-sdk';

interface IProps {
  product: Product;
}

async function getImageWithHeaders(requestInfo: Request) {
  const res = await fetch(requestInfo);
  return await res.blob();
}

const ProductCard = ({ product: { id, picture, name, priceUsd } }: IProps) => {
  const imageSlowLoad = useNumberFlagValue('imageSlowLoad', 0);
  const [imageSrc, setImageSrc] = useState<string>('');

  useEffect(() => {
    const headers = new Headers();
    headers.append('x-envoy-fault-delay-request', imageSlowLoad.toString());
    headers.append('Cache-Control', 'no-cache');
    getImageWithHeaders(new Request('/images/products/' + picture, { method: 'GET', headers })).then(blob =>
      setImageSrc(URL.createObjectURL(blob))
    );
  }, [imageSlowLoad, picture]);

  return (
    <a
      href={`/product/${id}`}
      data-cy={CypressFields.ProductCard}
      className="group block overflow-hidden rounded-lg border border-border bg-card transition-shadow hover:shadow-md"
    >
      <div className="aspect-square overflow-hidden bg-muted">
        {imageSrc ? (
          <img
            src={imageSrc}
            alt={name}
            className="h-full w-full object-cover transition-transform group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-muted-foreground text-sm">Loading...</div>
        )}
      </div>
      <div className="p-4">
        <h3 className="text-sm font-medium line-clamp-2">{name}</h3>
        <p className="mt-2 text-lg font-bold">
          <ProductPrice price={priceUsd || { currencyCode: 'USD', units: 0, nanos: 0 }} />
        </p>
      </div>
    </a>
  );
};

export default ProductCard;
