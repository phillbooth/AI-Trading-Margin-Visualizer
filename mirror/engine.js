const fs = require('node:fs');
const path = require('node:path');

function parseCsvLine(line) {
  return line.split(',').map((value) => value.trim());
}

function loadCandles(filePath) {
  const source = fs.readFileSync(filePath, 'utf8').trim();
  const [headerLine, ...lines] = source.split(/\r?\n/);
  const headers = parseCsvLine(headerLine);

  return lines.map((line) => {
    const values = parseCsvLine(line);
    const row = Object.fromEntries(headers.map((header, index) => [header, values[index]]));
    return {
      time: row.time,
      symbol: row.symbol,
      open: Number(row.open),
      high: Number(row.high),
      low: Number(row.low),
      close: Number(row.close),
      volume: Number(row.volume)
    };
  });
}

class ReplayEngine {
  constructor(options = {}) {
    this.filePath = options.filePath || path.resolve('data/sample_stock_ohlcv.csv');
    this.candles = loadCandles(this.filePath);
    this.index = 0;
    this.paused = true;
    this.startedAt = new Date().toISOString();
  }

  current() {
    return this.candles[this.index] || null;
  }

  status() {
    return {
      paused: this.paused,
      index: this.index,
      total: this.candles.length,
      startedAt: this.startedAt,
      current: this.current()
    };
  }

  step(count = 1) {
    this.index = Math.min(this.candles.length - 1, this.index + count);
    return this.status();
  }

  reset() {
    this.index = 0;
    this.paused = true;
    this.startedAt = new Date().toISOString();
    return this.status();
  }

  pause() {
    this.paused = true;
    return this.status();
  }

  resume() {
    this.paused = false;
    return this.status();
  }
}

module.exports = {
  ReplayEngine,
  loadCandles
};
