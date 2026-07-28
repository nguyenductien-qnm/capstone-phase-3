// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { ChannelCredentials } from '@grpc/grpc-js';
import {
  Empty,
  GetProductRequest,
  ListProductsResponse,
  Product,
  ProductCatalogServiceClient,
} from '../../protos/demo';
import { GrpcDeadlineMs, unaryWithRetry } from './GrpcDeadline';

const { PRODUCT_CATALOG_ADDR = '' } = process.env;

const client = new ProductCatalogServiceClient(PRODUCT_CATALOG_ADDR, ChannelCredentials.createInsecure());

const ProductCatalogGateway = () => ({
  listProducts() {
    return unaryWithRetry<Empty, ListProductsResponse>(
      (request, metadata, options, callback) => client.listProducts(request, metadata, options, callback),
      {},
      GrpcDeadlineMs.catalog
    );
  },
  getProduct(id: string) {
    return unaryWithRetry<GetProductRequest, Product>(
      (request, metadata, options, callback) => client.getProduct(request, metadata, options, callback),
      { id },
      GrpcDeadlineMs.catalog
    );
  },
});

export default ProductCatalogGateway();
