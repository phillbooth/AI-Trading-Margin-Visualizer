const http = require('node:http');
const path = require('node:path');
const { ReplayEngine } = require('./engine');

const port = Number(process.env.PORT || 3101);
const dataPath = process.env.HISTORICAL_DATA_PATH || path.resolve(__dirname, '../data/fixtures/sample_stock_ohlcv.csv');
const engine = new ReplayEngine({ filePath: dataPath });

function sendJson(response, statusCode, payload) {
  response.writeHead(statusCode, {
    'content-type': 'application/json',
    'access-control-allow-origin': '*'
  });
  response.end(JSON.stringify(payload, null, 2));
}

function route(request, response) {
  const url = new URL(request.url, `http://${request.headers.host}`);

  if (url.pathname === '/health') {
    sendJson(response, 200, { ok: true, service: 'mirror' });
    return;
  }

  if (url.pathname === '/status') {
    sendJson(response, 200, engine.status());
    return;
  }

  if (url.pathname === '/candles') {
    sendJson(response, 200, { candles: engine.candles });
    return;
  }

  if (url.pathname === '/step') {
    const count = Number(url.searchParams.get('count') || 1);
    sendJson(response, 200, engine.step(Number.isFinite(count) ? count : 1));
    return;
  }

  if (url.pathname === '/pause') {
    sendJson(response, 200, engine.pause());
    return;
  }

  if (url.pathname === '/resume') {
    sendJson(response, 200, engine.resume());
    return;
  }

  if (url.pathname === '/reset') {
    sendJson(response, 200, engine.reset());
    return;
  }

  sendJson(response, 404, { error: 'Unknown Mirror endpoint.' });
}

const server = http.createServer(route);

server.listen(port, () => {
  console.log(`Mirror replay API listening on http://localhost:${port}`);
});

process.on('SIGINT', () => {
  server.close(() => process.exit(0));
});

process.on('SIGTERM', () => {
  server.close(() => process.exit(0));
});
