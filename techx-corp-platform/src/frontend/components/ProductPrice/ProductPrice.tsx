import { useMemo } from 'react';
import getSymbolFromCurrency from 'currency-symbol-map';
import { Money } from '../../protos/demo';
import { useCurrency } from '../../providers/Currency.provider';
import { CypressFields } from '../../utils/enums/CypressFields';

interface IProps { price: Money; }

const ProductPrice = ({ price: { units, currencyCode, nanos } }: IProps) => {
  const { selectedCurrency } = useCurrency();
  const symbol = useMemo(() => getSymbolFromCurrency(currencyCode) || selectedCurrency, [currencyCode, selectedCurrency]);
  return <span data-cy={CypressFields.ProductPrice}>{symbol} {(units + nanos / 1e9).toFixed(2)}</span>;
};

export default ProductPrice;
