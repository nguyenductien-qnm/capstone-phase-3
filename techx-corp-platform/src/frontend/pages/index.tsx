// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { NextPage } from 'next';
import Head from 'next/head';
import Layout from '../components/Layout';
import ProductList from '../components/ProductList';
import { useQuery } from '@tanstack/react-query';
import ApiGateway from '../gateways/Api.gateway';
import Banner from '../components/Banner';
import { CypressFields } from '../utils/enums/CypressFields';
import { useCurrency } from '../providers/Currency.provider';
import { Product } from '../protos/demo';

import { MOCK_PRODUCTS } from '../utils/mockData';

const Home: NextPage = () => {
  const { selectedCurrency } = useCurrency();
  const { data: productList = [] } = useQuery({
    queryKey: ['products', selectedCurrency],
    queryFn: () => ApiGateway.listProducts(selectedCurrency),
  });

  const displayProducts = productList.length > 0 ? productList : MOCK_PRODUCTS;

  return (
    <Layout>
      <Head>
        <title>Otel Demo - Home</title>
      </Head>
      <div data-cy={CypressFields.HomePage}>
        <Banner />
        <div className="w-full px-5 lg:px-24">
          <div className="flex flex-wrap w-full py-32 md:py-48">
            <div className="w-full">
              <ProductList productList={displayProducts} title="Hot Products" subtitle="Discover our most popular picks" />
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default Home;
