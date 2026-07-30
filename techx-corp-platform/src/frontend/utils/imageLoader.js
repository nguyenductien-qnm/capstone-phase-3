// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
/*
  * We pass down the optimisation request to the image-provider service here, without this, nextJs would try to use internal optimiser which is not working with the external image-provider.
  * Returning a relative path avoids hydration mismatches since the browser will resolve it against the current origin.
  */

export default function imageLoader({ src, width, quality }) {
  // Ensure src doesn't start with a slash if we're combining it, but standard Next.js src often starts with /
  const cleanSrc = src.startsWith('/') ? src.slice(1) : src;
  return `/${cleanSrc}?w=${width}&q=${quality || 75}`;
}
