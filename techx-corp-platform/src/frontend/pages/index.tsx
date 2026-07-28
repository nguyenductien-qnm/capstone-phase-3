import { NextPage } from 'next';
import Head from 'next/head';
import Layout from '../components/Layout';
import ProductList from '../components/ProductList';
import { useQuery } from '@tanstack/react-query';
import ApiGateway from '../gateways/Api.gateway';
import Banner from '../components/Banner';
import { CypressFields } from '../utils/enums/CypressFields';
import { useCurrency } from '../providers/Currency.provider';

const Home: NextPage = () => {
  const { selectedCurrency } = useCurrency();
  const { data: productList = [] } = useQuery({
    queryKey: ['products', selectedCurrency],
    queryFn: () => ApiGateway.listProducts(selectedCurrency),
  });

  return (
    <Layout>
      <Head>
        <title>TechX Corp — Store</title>
      </Head>
      <div data-cy={CypressFields.HomePage}>
        <Banner />
        <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          <h2 className="mb-8 text-2xl font-bold tracking-tight" data-cy={CypressFields.HotProducts} id="hot-products">
            Hot Products
          </h2>
          <ProductList productList={productList} />
        </div>
      </div>
    </Layout>
  );
};

export default Home;
