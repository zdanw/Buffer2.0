const https = require('https');

/** 仅 hostname；若误填带协议的 URL 会剥掉，避免代理走错。 */
function resolveTargetHost() {
  const raw = (process.env.HF_SPACE_HOST || 'zongsechenai-bebcare-buffer.hf.space').trim();
  return raw.replace(/^https?:\/\//i, '').split('/')[0];
}

const TARGET_HOST = resolveTargetHost();
// Align with frontend axios timeout (60s); long generate jobs use async poll.
const TIMEOUT_MS = 60000;

function resolveAllowedOrigin(req) {
  const configured = (process.env.ALLOWED_ORIGINS || '')
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s && s !== '*');
  const requestOrigin = req.headers.origin;
  if (requestOrigin && configured.includes(requestOrigin)) {
    return requestOrigin;
  }
  // Same-origin browser calls often omit Origin; fall back to first configured origin for ACAO.
  return configured[0] || '';
}

function corsHeaders(req) {
  const origin = resolveAllowedOrigin(req);
  const headers = {
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  };
  if (origin) {
    headers['Access-Control-Allow-Origin'] = origin;
    headers['Access-Control-Allow-Credentials'] = 'true';
    headers['Vary'] = 'Origin';
  }
  return headers;
}

module.exports = (req, res) => {
  if (req.method === 'OPTIONS') {
    res.writeHead(200, corsHeaders(req));
    res.end();
    return;
  }

  let targetPath = req.url;
  // Stripe Dashboard endpoint alias → backend billing webhook
  const pathOnly = (targetPath || '').split('?')[0];
  if (pathOnly === '/payments/webhook' || pathOnly === '/api/payments/webhook') {
    targetPath = '/v1/billing/webhook';
  } else if (targetPath.startsWith('/api')) {
    // /api/v1/... must become /v1/... (not /v1/v1/...)
    targetPath = targetPath.replace(/^\/api/, '');
    if (!targetPath.startsWith('/v1')) {
      targetPath = '/v1' + (targetPath.startsWith('/') ? targetPath : `/${targetPath}`);
    }
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

    const chunks = [];
    proxyRes.on('data', (chunk) => {
      chunks.push(chunk);
    });
    proxyRes.on('end', () => {
      const responseBody = Buffer.concat(chunks).toString('utf8');
      console.log('HF Space response body:', responseBody.substring(0, 500));

      const responseHeaders = {};
      for (const [key, value] of Object.entries(proxyRes.headers)) {
        const lower = key.toLowerCase();
        if (lower.startsWith('access-control-')) {
          continue;
        }
        responseHeaders[key] = value;
      }
      Object.assign(responseHeaders, corsHeaders(req));

      if (!responseHeaders['content-type']) {
        responseHeaders['content-type'] = 'application/json; charset=utf-8';
      }

      res.writeHead(proxyRes.statusCode, responseHeaders);
      res.end(responseBody);
    });
  });

  proxyReq.on('timeout', () => {
    console.error('Proxy request timed out after', TIMEOUT_MS, 'ms');
    proxyReq.destroy();
    res.writeHead(504, {
      'Content-Type': 'application/json',
      ...corsHeaders(req),
    });
    res.end(JSON.stringify({ error: 'Gateway Timeout', message: '服务正在启动中，请稍后重试' }));
  });

  proxyReq.on('error', (err) => {
    console.error('Proxy error:', err.message);
    res.writeHead(500, {
      'Content-Type': 'application/json',
      ...corsHeaders(req),
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
