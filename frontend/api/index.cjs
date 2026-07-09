const https = require('https');

const TARGET_HOST = 'zongsechenai-bebcare-buffer.hf.space';
const TIMEOUT_MS = 30000;

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

  let targetPath = req.url;
  if (targetPath.startsWith('/api')) {
    targetPath = targetPath.replace(/^\/api/, '/v1');
  } else if (!targetPath.startsWith('/v1')) {
    targetPath = '/v1' + targetPath;
  }

  console.log(`=== ${req.method} ${targetPath} ===`);

  const headers = {};
  for (const [key, value] of Object.entries(req.headers)) {
    if (key !== 'host' && key !== 'connection') {
      headers[key] = value;
    }
  }
  headers['host'] = TARGET_HOST;

  const options = {
    hostname: TARGET_HOST,
    path: targetPath,
    method: req.method,
    headers: headers,
    timeout: TIMEOUT_MS,
  };

  const proxyReq = https.request(options, (proxyRes) => {
    console.log('HF Space status:', proxyRes.statusCode);
    console.log('HF Space content-type:', proxyRes.headers['content-type']);

    let responseBody = '';
    proxyRes.on('data', (chunk) => {
      responseBody += chunk;
    });
    proxyRes.on('end', () => {
      console.log('HF Space response body:', responseBody.substring(0, 500));

      const responseHeaders = {};
      for (const [key, value] of Object.entries(proxyRes.headers)) {
        responseHeaders[key] = value;
      }
      responseHeaders['access-control-allow-origin'] = '*';
      responseHeaders['access-control-allow-methods'] = 'GET, POST, PUT, DELETE, OPTIONS';
      responseHeaders['access-control-allow-headers'] = 'Content-Type, Authorization';

      res.writeHead(proxyRes.statusCode, responseHeaders);
      res.end(responseBody);
    });
  });

  proxyReq.on('timeout', () => {
    console.error('Proxy request timed out after', TIMEOUT_MS, 'ms');
    proxyReq.destroy();
    res.writeHead(504, {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    });
    res.end(JSON.stringify({ error: 'Gateway Timeout', message: '服务正在启动中，请稍后重试' }));
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
