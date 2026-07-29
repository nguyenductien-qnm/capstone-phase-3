import { CypressFields } from '../../utils/enums/CypressFields';
import { useAd } from '../../providers/Ad.provider';
import ProductCard from '../ProductCard';

const Recommendations = () => {
  const { recommendedProductList } = useAd();
  if (!recommendedProductList?.length) return null;
  return (
    <section data-cy={CypressFields.RecommendationList} className="mt-8">
      <h3 className="mb-4 text-xl font-bold">You May Also Like</h3>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {recommendedProductList.map(product => (
          <ProductCard key={product.id} product={product} />
        ))}
      </div>
    </section>
  );
};

export default Recommendations;
