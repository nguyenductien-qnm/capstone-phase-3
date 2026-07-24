// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { ChannelCredentials } from '@grpc/grpc-js';
import { CheckoutServiceClient, PlaceOrderRequest, PlaceOrderResponse } from '../../protos/demo';
import { GrpcDeadlineMs, unaryWithDeadline } from './GrpcDeadline';

const { CHECKOUT_ADDR = '' } = process.env;

const client = new CheckoutServiceClient(CHECKOUT_ADDR, ChannelCredentials.createInsecure());

const CheckoutGateway = () => ({
  placeOrder(order: PlaceOrderRequest) {
    return unaryWithDeadline<PlaceOrderRequest, PlaceOrderResponse>(
      (request, metadata, options, callback) => client.placeOrder(request, metadata, options, callback),
      order,
      GrpcDeadlineMs.checkout
    );
  },
});

export default CheckoutGateway();
