// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { useMemo } from 'react';
import getSymbolFromCurrency from 'currency-symbol-map';
import { Money } from '../../protos/demo';
import { useCurrency } from '../../providers/Currency.provider';
import { CypressFields } from '../../utils/enums/CypressFields';
import { Badge } from '../ui/badge';

interface IProps {
  price: Money;
}

const ProductPrice = ({ price: { units, currencyCode, nanos } }: IProps) => {
  const { selectedCurrency } = useCurrency();

  const currencySymbol = useMemo(
    () => getSymbolFromCurrency(currencyCode) || selectedCurrency,
    [currencyCode, selectedCurrency]
  );

  const total = units + nanos / 1000000000;

  return (
    <Badge 
      variant="secondary" 
      className="px-3 py-1 text-base font-bold bg-primary/10 text-primary border-primary/20 hover:bg-primary/20 transition-colors"
      data-cy={CypressFields.ProductPrice}
    >
      {currencySymbol} {total.toFixed(2)}
    </Badge>
  );
};

export default ProductPrice;
