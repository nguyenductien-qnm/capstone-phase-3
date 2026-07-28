import Link from 'next/link';
import { useCallback, useState } from 'react';
import { CypressFields } from '../../utils/enums/CypressFields';
import Input from '../Input';
import Button from '../Button';

const currentYear = new Date().getFullYear();
const yearList = Array.from(new Array(20), (v, i) => i + currentYear);

export interface IFormData {
  email: string; streetAddress: string; city: string; state: string; country: string;
  zipCode: string; creditCardNumber: string; creditCardCvv: number;
  creditCardExpirationYear: number; creditCardExpirationMonth: number;
}

interface IProps { onSubmit(formData: IFormData): void; }

const CheckoutForm = ({ onSubmit }: IProps) => {
  const [{ email, streetAddress, city, state, country, zipCode, creditCardCvv, creditCardExpirationMonth, creditCardExpirationYear, creditCardNumber }, setFormData] = useState<IFormData>({
    email: 'someone@example.com', streetAddress: '1600 Amphitheatre Parkway', city: 'Mountain View',
    state: 'CA', country: 'United States', zipCode: '94043', creditCardNumber: '4432-8015-6152-0454',
    creditCardCvv: 672, creditCardExpirationYear: 2030, creditCardExpirationMonth: 1,
  });

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData(fd => ({ ...fd, [e.target.name]: e.target.value }));
  }, []);

  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit({ email, streetAddress, city, state, country, zipCode, creditCardCvv, creditCardExpirationMonth, creditCardExpirationYear, creditCardNumber }); }}
      className="flex flex-col gap-4">
      <h3 className="text-lg font-bold">Shipping Address</h3>
      <Input label="E-mail Address" type="email" id="email" name="email" value={email} required onChange={handleChange} />
      <Input label="Street Address" type="text" name="streetAddress" id="street_address" value={streetAddress} onChange={handleChange} required />
      <Input label="Zip Code" type="text" name="zipCode" id="zip_code" value={zipCode} onChange={handleChange} required />
      <Input label="City" type="text" name="city" id="city" value={city} required onChange={handleChange} />
      <div className="grid grid-cols-2 gap-4">
        <Input label="State" type="text" name="state" id="state" value={state} required onChange={handleChange} />
        <Input label="Country" type="text" id="country" placeholder="Country Name" name="country" value={country} onChange={handleChange} required />
      </div>
      <h3 className="mt-4 text-lg font-bold">Payment Method</h3>
      <Input type="text" label="Credit Card Number" id="credit_card_number" name="creditCardNumber" placeholder="0000-0000-0000-0000" value={creditCardNumber} onChange={handleChange} required pattern="\d{4}-\d{4}-\d{4}-\d{4}" />
      <div className="grid grid-cols-3 gap-4">
        <Input label="Month" name="creditCardExpirationMonth" id="credit_card_expiration_month" value={creditCardExpirationMonth} onChange={handleChange} type="select">
          {['January','February','March','April','May','June','July','August','September','October','November','December'].map((m,i) => <option key={m} value={i+1}>{m}</option>)}
        </Input>
        <Input label="Year" name="creditCardExpirationYear" id="credit_card_expiration_year" value={creditCardExpirationYear} onChange={handleChange} type="select">
          {yearList.map(year => <option value={year} key={year}>{year}</option>)}
        </Input>
        <Input label="CVV" type="password" id="credit_card_cvv" name="creditCardCvv" value={creditCardCvv} required pattern="\d{3}" onChange={handleChange} />
      </div>
      <div className="mt-6 flex justify-between">
        <Link href="/"><Button $type="secondary">Continue Shopping</Button></Link>
        <Button data-cy={CypressFields.CheckoutPlaceOrder} type="submit">Place Order</Button>
      </div>
    </form>
  );
};

export default CheckoutForm;
