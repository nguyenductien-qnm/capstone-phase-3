import { CypressFields } from '../../utils/enums/CypressFields';
import { Product } from '../../protos/demo';
import ProductCard from '../ProductCard';

interface IProps {
  productList: Product[];
}

const ProductList = ({ productList }: IProps) => (
  <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3" data-cy={CypressFields.ProductList}>
    {productList.map(product => (
      <ProductCard key={product.id} product={product} />
    ))}
  </div>
);

export default ProductList;
