// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { useMemo } from 'react';
import getSymbolFromCurrency from 'currency-symbol-map';
import { useCurrency } from '../../providers/Currency.provider';
import { CypressFields } from '../../utils/enums/CypressFields';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';

const CurrencySwitcher = () => {
  const { currencyCodeList, setSelectedCurrency, selectedCurrency } = useCurrency();

  const currencySymbol = useMemo(() => getSymbolFromCurrency(selectedCurrency), [selectedCurrency]);

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm font-medium text-muted-foreground">{currencySymbol}</span>
      <Select 
        value={selectedCurrency} 
        onValueChange={setSelectedCurrency}
      >
        <SelectTrigger className="w-[100px] bg-secondary/50 border-0 focus:ring-0">
          <SelectValue placeholder="Currency" data-cy={CypressFields.CurrencySwitcher} />
        </SelectTrigger>
        <SelectContent>
          {currencyCodeList.map(currencyCode => (
            <SelectItem key={currencyCode} value={currencyCode}>
              {currencyCode}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
};

export default CurrencySwitcher;
