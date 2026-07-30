// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import Link from 'next/link';
import { useCallback, useState } from 'react';
import { CypressFields } from '../../utils/enums/CypressFields';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { CreditCard, MapPin, CheckCircle2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';

const currentYear = new Date().getFullYear();
const yearList = Array.from(new Array(20), (v, i) => i + currentYear);

export interface IFormData {
  email: string;
  streetAddress: string;
  city: string;
  state: string;
  country: string;
  zipCode: string;
  creditCardNumber: string;
  creditCardCvv: number;
  creditCardExpirationYear: number;
  creditCardExpirationMonth: number;
}

interface IProps {
  onSubmit(formData: IFormData): void;
}

const CheckoutForm = ({ onSubmit }: IProps) => {
  const [formData, setFormData] = useState<IFormData>({
    email: 'someone@example.com',
    streetAddress: '1600 Amphitheatre Parkway',
    city: 'Mountain View',
    state: 'CA',
    country: 'United States',
    zipCode: "94043",
    creditCardNumber: '4432-8015-6152-0454',
    creditCardCvv: 672,
    creditCardExpirationYear: 2030,
    creditCardExpirationMonth: 1,
  });

  const {
    email,
    streetAddress,
    city,
    state,
    country,
    zipCode,
    creditCardCvv,
    creditCardExpirationMonth,
    creditCardExpirationYear,
    creditCardNumber,
  } = formData;

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData(prev => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  }, []);

  return (
    <Card className="w-full border-border/50 shadow-xl bg-card/50 backdrop-blur-sm overflow-hidden">
      <div className="h-2 bg-gradient-to-r from-primary to-indigo-500 w-full" />
      <CardHeader className="space-y-1 bg-muted/20 border-b border-border/30 pb-6">
        <CardTitle className="text-2xl font-bold">Checkout</CardTitle>
        <CardDescription>
          Complete your order securely below.
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-6">
        <form
          onSubmit={(event: { preventDefault: () => void; }) => {
            event.preventDefault();
            onSubmit(formData);
          }}
          className="w-full space-y-8"
        >
          {/* Shipping Section */}
          <div className="space-y-4">
            <div className="flex items-center gap-2 pb-2 border-b border-border/50">
              <MapPin className="w-5 h-5 text-primary" />
              <h3 className="text-lg font-semibold tracking-tight">Shipping Address</h3>
            </div>
            <div className="grid gap-4 mt-4">
              <div className="space-y-2">
                <Label htmlFor="email">E-mail Address</Label>
                <Input
                  type="email"
                  id="email"
                  name="email"
                  value={email}
                  required
                  onChange={handleChange}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="street_address">Street Address</Label>
                <Input
                  type="text"
                  name="streetAddress"
                  id="street_address"
                  value={streetAddress}
                  onChange={handleChange}
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="city">City</Label>
                  <Input type="text" name="city" id="city" value={city} required onChange={handleChange} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="zip_code">Zip Code</Label>
                  <Input
                    type="text"
                    name="zipCode"
                    id="zip_code"
                    value={zipCode}
                    onChange={handleChange}
                    required
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="state">State</Label>
                  <Input type="text" name="state" id="state" value={state} required onChange={handleChange} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="country">Country</Label>
                  <Input
                    type="text"
                    id="country"
                    placeholder="Country Name"
                    name="country"
                    value={country}
                    onChange={handleChange}
                    required
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Payment Section */}
          <div className="space-y-4 pt-4">
            <div className="flex items-center gap-2 pb-2 border-b border-border/50">
              <CreditCard className="w-5 h-5 text-primary" />
              <h3 className="text-lg font-semibold tracking-tight">Payment Method</h3>
            </div>
            <div className="grid gap-4 mt-4">
              <div className="space-y-2">
                <Label htmlFor="credit_card_number">Credit Card Number</Label>
                <Input
                  type="text"
                  id="credit_card_number"
                  name="creditCardNumber"
                  placeholder="0000-0000-0000-0000"
                  value={creditCardNumber}
                  onChange={handleChange}
                  required
                  pattern="\d{4}-\d{4}-\d{4}-\d{4}"
                />
              </div>

              <div className="grid grid-cols-[1fr_1fr_100px] gap-4">
                <div className="space-y-2">
                  <Label htmlFor="credit_card_expiration_month">Month</Label>
                  <Select
                    value={creditCardExpirationMonth.toString()}
                    onValueChange={(val) => setFormData(prev => ({ ...prev, creditCardExpirationMonth: +val }))}
                  >
                    <SelectTrigger id="credit_card_expiration_month">
                      <SelectValue placeholder="Month" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">January</SelectItem>
                      <SelectItem value="2">February</SelectItem>
                      <SelectItem value="3">March</SelectItem>
                      <SelectItem value="4">April</SelectItem>
                      <SelectItem value="5">May</SelectItem>
                      <SelectItem value="6">June</SelectItem>
                      <SelectItem value="7">July</SelectItem>
                      <SelectItem value="8">August</SelectItem>
                      <SelectItem value="9">September</SelectItem>
                      <SelectItem value="10">October</SelectItem>
                      <SelectItem value="11">November</SelectItem>
                      <SelectItem value="12">December</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="credit_card_expiration_year">Year</Label>
                  <Select
                    value={creditCardExpirationYear.toString()}
                    onValueChange={(val) => setFormData(prev => ({ ...prev, creditCardExpirationYear: +val }))}
                  >
                    <SelectTrigger id="credit_card_expiration_year">
                      <SelectValue placeholder="Year" />
                    </SelectTrigger>
                    <SelectContent>
                      {yearList.map(year => (
                        <SelectItem value={year.toString()} key={year}>
                          {year}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="credit_card_cvv">CVV</Label>
                  <Input
                    type="password"
                    id="credit_card_cvv"
                    name="creditCardCvv"
                    value={creditCardCvv}
                    required
                    pattern="\d{3}"
                    onChange={handleChange}
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="flex flex-col-reverse justify-center items-center gap-4 pt-6 mt-4 border-t border-border/50 sm:flex-row sm:justify-end">
            <Link href="/" className="w-full sm:w-auto">
              <Button variant="outline" size="lg" className="w-full h-12 px-8 text-base font-medium">Continue Shopping</Button>
            </Link>
            <Button data-cy={CypressFields.CheckoutPlaceOrder} type="submit" size="lg" className="w-full sm:w-auto h-12 px-8 text-base font-medium gap-2 shadow-lg shadow-primary/25">
              Place Order <CheckCircle2 className="w-5 h-5" />
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
};

export default CheckoutForm;
