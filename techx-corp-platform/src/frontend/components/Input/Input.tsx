import { HTMLInputTypeAttribute, InputHTMLAttributes } from 'react';
import { Input as ShadcnInput } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

interface IProps extends InputHTMLAttributes<HTMLSelectElement | HTMLInputElement> {
  type: HTMLInputTypeAttribute | 'select';
  children?: React.ReactNode;
  label: string;
}

const Input = ({ type, id = '', children, label, ...props }: IProps) => (
  <div className="flex flex-col gap-2">
    <Label htmlFor={id}>{label}</Label>
    {type === 'select' ? (
      <select
        id={id}
        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
        {...props}
      >
        {children}
      </select>
    ) : (
      <ShadcnInput id={id} type={type} {...props} />
    )}
  </div>
);

export default Input;
