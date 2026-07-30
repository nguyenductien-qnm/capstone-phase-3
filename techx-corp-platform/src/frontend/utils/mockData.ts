// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { Product } from '../protos/demo';

export const MOCK_PRODUCTS: Product[] = [
  {
    id: 'mock-1',
    name: 'Astronomy Telescope 100mm',
    description: 'Perfect for beginners looking to explore the moon and planets.',
    picture: 'telescope.jpg',
    priceUsd: { currencyCode: 'USD', units: 199, nanos: 990000000 },
    categories: ['telescopes']
  },
  {
    id: 'mock-2',
    name: 'Deep Sky Explorer 8"',
    description: 'A powerful Dobsonian telescope for viewing distant galaxies.',
    picture: 'dobsonian.jpg',
    priceUsd: { currencyCode: 'USD', units: 549, nanos: 0 },
    categories: ['telescopes', 'advanced']
  },
  {
    id: 'mock-3',
    name: 'Roof Binoculars 10x42',
    description: 'Compact and durable binoculars for bird watching and hiking.',
    picture: 'binoculars.jpg',
    priceUsd: { currencyCode: 'USD', units: 129, nanos: 500000000 },
    categories: ['binoculars', 'accessories']
  }
];
