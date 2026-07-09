const http = require('http');
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

  const path = req.url.replace(/^\/api/, '/v1');
  
  const options = {
    hostname: TARGET_HOST,
    path: path,
    method: req.method,
    headers: {
      ...req.headers,
      'Host': TARGET_HOST,
    },
  };

  const protocol = TARGET_HOST.startsWith('https') ? https : http;

  const proxyReq = protocol.request(options, (proxyRes) => {
    const headers = {
      ...proxyRes.headers,
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    };

    res.writeHead(proxyRes.statusCode, headers);
    proxyRes.pipe(res);
  });

  proxyReq.on('error', (err) => {
    res.writeHead(500, {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    });
    res.end(JSON.stringify({ error: 'Proxy error', message: err.message }));
  });

  req.pipe(proxyReq);
};
