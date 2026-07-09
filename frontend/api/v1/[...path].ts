export const config = {
  runtime: 'edge',
};

const TARGET_BASE_URL = 'https://zongsechenai-bebcare-buffer.hf.space';

export default async function handler(request: Request) {
  const { pathname, search } = new URL(request.url);
  
  const targetUrl = `${TARGET_BASE_URL}${pathname}${search}`;

  if (request.method === 'OPTIONS') {
    return new Response(null, {
      status: 204,
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        'Access-Control-Max-Age': '86400',
      },
    });
  }

  const requestHeaders = new Headers(request.headers);
  requestHeaders.delete('host');

  const response = await fetch(targetUrl, {
    method: request.method,
    headers: requestHeaders,
    body: request.method !== 'GET' && request.method !== 'HEAD' ? await request.text() : undefined,
    redirect: 'follow',
  });

  const responseHeaders = new Headers(response.headers);
  responseHeaders.set('Access-Control-Allow-Origin', '*');

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders,
  });
}
