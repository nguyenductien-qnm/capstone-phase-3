// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { ChannelCredentials } from '@grpc/grpc-js';
import {
  CurrencyConversionRequest,
  Empty,
  GetSupportedCurrenciesResponse,
  CurrencyServiceClient,
  Money,
} from '../../protos/demo';
import { GrpcDeadlineMs, unaryWithDeadline } from './GrpcDeadline';

const { CURRENCY_ADDR = '' } = process.env;

const client = new CurrencyServiceClient(CURRENCY_ADDR, ChannelCredentials.createInsecure());

const CurrencyGateway = () => ({
  convert(from: Money, toCode: string) {
    return unaryWithDeadline<CurrencyConversionRequest, Money>(
      (request, metadata, options, callback) => client.convert(request, metadata, options, callback),
      { from, toCode },
      GrpcDeadlineMs.catalog
    );
  },
  getSupportedCurrencies() {
    return unaryWithDeadline<Empty, GetSupportedCurrenciesResponse>(
      (request, metadata, options, callback) =>
        client.getSupportedCurrencies(request, metadata, options, callback),
      {},
      GrpcDeadlineMs.catalog
    );
  },
});

export default CurrencyGateway();
