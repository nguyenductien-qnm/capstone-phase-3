// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

interface IRequestParams {
  url: string;
  body?: object;
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  queryParams?: Record<string, any>;
  headers?: Record<string, string>;
}

const request = async <T>({
  url = '',
  method = 'GET',
  body,
  queryParams = {},
  headers = {
    'content-type': 'application/json',
  },
}: IRequestParams): Promise<T> => {
  const response = await fetch(`${url}?${new URLSearchParams(queryParams).toString()}`, {
    method,
    body: body ? JSON.stringify(body) : undefined,
    headers,
  });

  const responseText = await response.text();

  if (!response.ok) {
    throw new Error(responseText || `HTTP error: ${response.status} ${response.statusText}`);
  }

  if (!!responseText) {
    try {
      return JSON.parse(responseText);
    } catch (e) {
      console.error('JSON parse error in Request.ts:', e);
      return responseText as unknown as T;
    }
  }

  return undefined as unknown as T;
};

export default request;
