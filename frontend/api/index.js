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

  try {
    let targetPath = req.url;
    if (targetPath.startsWith('/api')) {
      targetPath = targetPath.replace(/^\/api/, '/v1');
    } else if (targetPath.startsWith('/v1')) {
      targetPath = targetPath;
    } else {
      targetPath = '/v1' + targetPath;
    }

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
    };

    const proxyReq = https.request(options, (proxyRes) => {
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
      proxyReq.write(chunk);
    });

    req.on('end', () => {
      proxyReq.end();
    });

    req.on('error', (err) => {
      console.error('Request error:', err.message);
      proxyReq.destroy(err);
    });

  } catch (err) {
    console.error('Function error:', err.message);
    res.writeHead(500, {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    });
    res.end(JSON.stringify({ error: 'Internal error', message: err.message }));
  }
};
