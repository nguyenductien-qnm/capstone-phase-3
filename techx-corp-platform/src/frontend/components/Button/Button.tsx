import { Button as ShadcnButton } from '@/components/ui/button';

interface ButtonProps {
  $type?: 'primary' | 'secondary' | 'link';
  children: React.ReactNode;
  onClick?: () => void;
  type?: 'button' | 'submit';
  className?: string;
  disabled?: boolean;
  'data-cy'?: string;
}

const variantMap: Record<string, 'default' | 'secondary' | 'link'> = {
  primary: 'default',
  secondary: 'secondary',
  link: 'link',
};

const Button = ({ $type = 'primary', children, ...props }: ButtonProps) => (
  <ShadcnButton variant={variantMap[$type] || 'default'} size="lg" {...props}>
    {children}
  </ShadcnButton>
);

export default Button;
