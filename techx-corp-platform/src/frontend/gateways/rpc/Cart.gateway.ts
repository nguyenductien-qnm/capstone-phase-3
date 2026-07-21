// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { ChannelCredentials } from '@grpc/grpc-js';
import {
  AddItemRequest,
  Cart,
  CartItem,
  CartServiceClient,
  Empty,
  EmptyCartRequest,
  GetCartRequest,
} from '../../protos/demo';
import { GrpcDeadlineMs, unaryWithDeadline } from './GrpcDeadline';

const { CART_ADDR = '' } = process.env;

const client = new CartServiceClient(CART_ADDR, ChannelCredentials.createInsecure());

const CartGateway = () => ({
  getCart(userId: string) {
    return unaryWithDeadline<GetCartRequest, Cart>(
      (request, metadata, options, callback) => client.getCart(request, metadata, options, callback),
      { userId },
      GrpcDeadlineMs.cart
    );
  },
  addItem(userId: string, item: CartItem) {
    return unaryWithDeadline<AddItemRequest, Empty>(
      (request, metadata, options, callback) => client.addItem(request, metadata, options, callback),
      { userId, item },
      GrpcDeadlineMs.cart
    );
  },
  emptyCart(userId: string) {
    return unaryWithDeadline<EmptyCartRequest, Empty>(
      (request, metadata, options, callback) => client.emptyCart(request, metadata, options, callback),
      { userId },
      GrpcDeadlineMs.cart
    );
  },
});

export default CartGateway();
