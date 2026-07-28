import { InputHTMLAttributes } from 'react';

interface IProps extends InputHTMLAttributes<HTMLSelectElement> { children: React.ReactNode; }

const Select = ({ children, ...props }: IProps) => (
  <div className="relative">
    <select className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm appearance-none" {...props}>
      {children}
    </select>
    <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground">▾</span>
  </div>
);

export default Select;
