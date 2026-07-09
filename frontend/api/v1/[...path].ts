export const config = {
  runtime: 'edge',
};

const TARGET_URL = 'https://zongsechenai-bebcare-buffer.hf.space/v1';

export default async function handler(request: Request): Promise<Response> {
  const { pathname, search } = new URL(request.url);
  const path = pathname.replace(/^\/api\/v1\//, '') || '';
  
  const targetUrl = `${TARGET_URL}/${path}${search}`;

  const body = await request.text();
  
  const headers = new Headers(request.headers);
  headers.set('Host', new URL(TARGET_URL).hostname);

  const response = await fetch(targetUrl, {
    method: request.method,
    headers,
    body: body || undefined,
  });

  const responseHeaders = new Headers(response.headers);
  responseHeaders.set('Access-Control-Allow-Origin', '*');
  responseHeaders.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  responseHeaders.set('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  return new Response(response.body, {
    status: response.status,
    headers: responseHeaders,
  });
}
