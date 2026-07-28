import { useMemo } from 'react';
import getSymbolFromCurrency from 'currency-symbol-map';
import { useCurrency } from '../../providers/Currency.provider';
import { CypressFields } from '../../utils/enums/CypressFields';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const CurrencySwitcher = () => {
  const { currencyCodeList, setSelectedCurrency, selectedCurrency } = useCurrency();
  const symbol = useMemo(() => getSymbolFromCurrency(selectedCurrency), [selectedCurrency]);

  return (
    <Select value={selectedCurrency} onValueChange={setSelectedCurrency}>
      <SelectTrigger className="w-[100px]" data-cy={CypressFields.CurrencySwitcher}>
        <SelectValue placeholder={symbol} />
      </SelectTrigger>
      <SelectContent>
        {currencyCodeList.map(code => (
          <SelectItem key={code} value={code}>{code}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
};

export default CurrencySwitcher;
