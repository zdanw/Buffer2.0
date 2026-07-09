const https = require('https');

const TARGET_HOST = 'zongsechenai-bebcare-buffer.hf.space';

module.exports = (req, res) => {
  if (req.method === 'OPTIONS') {
    res.writeHead(200, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    });
    res.end();
    return;
  }

  console.log('=== Proxy Request ===');
  console.log('Method:', req.method);
  console.log('Original URL:', req.url);
  console.log('Headers:', JSON.stringify(req.headers));

  let targetPath = req.url;
  console.log('Target path before processing:', targetPath);

  if (targetPath.startsWith('/api')) {
    targetPath = targetPath.replace(/^\/api/, '/v1');
    console.log('Replaced /api with /v1:', targetPath);
  } else if (!targetPath.startsWith('/v1')) {
    targetPath = '/v1' + targetPath;
    console.log('Added /v1 prefix:', targetPath);
  }

  const headers = {};
  for (const [key, value] of Object.entries(req.headers)) {
    if (key !== 'host' && key !== 'connection') {
      headers[key] = value;
    }
  }
  headers['host'] = TARGET_HOST;

  console.log('Final target:', 'https://' + TARGET_HOST + targetPath);

  const options = {
    hostname: TARGET_HOST,
    path: targetPath,
    method: req.method,
    headers: headers,
  };

  const proxyReq = https.request(options, (proxyRes) => {
    console.log('=== Proxy Response ===');
    console.log('Status:', proxyRes.statusCode);
    console.log('Response headers:', JSON.stringify(proxyRes.headers));

    const responseHeaders = {};
    for (const [key, value] of Object.entries(proxyRes.headers)) {
      responseHeaders[key] = value;
    }
    responseHeaders['access-control-allow-origin'] = '*';
    responseHeaders['access-control-allow-methods'] = 'GET, POST, PUT, DELETE, OPTIONS';
    responseHeaders['access-control-allow-headers'] = 'Content-Type, Authorization';

    res.writeHead(proxyRes.statusCode, responseHeaders);
    proxyRes.pipe(res);
  });

  proxyReq.on('error', (err) => {
    console.error('Proxy error:', err.message);
    res.writeHead(500, {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    });
    res.end(JSON.stringify({ error: 'Proxy error', message: err.message }));
  });

  req.on('data', (chunk) => {
    console.log('Request body chunk:', chunk.toString());
    proxyReq.write(chunk);
  });

  req.on('end', () => {
    proxyReq.end();
  });

  req.on('error', (err) => {
    console.error('Request error:', err.message);
    proxyReq.destroy(err);
  });
};
