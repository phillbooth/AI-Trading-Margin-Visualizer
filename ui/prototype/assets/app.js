const presets = {
  BTCUSDT: { type: 'CRYPTO', entry: 65000, size: 0.18, stop: 62500, leverage: 8, equity: 10000, margin: 7500, maintenance: 0.8, fees: 0.08 },
  ETHUSDT: { type: 'CRYPTO', entry: 3200, size: 4, stop: 3025, leverage: 6, equity: 12000, margin: 8800, maintenance: 0.8, fees: 0.08 },
  AAPL: { type: 'STOCK', entry: 184, size: 120, stop: 176, leverage: 2, equity: 25000, margin: 18000, maintenance: 25, fees: 0.02 },
  XAUUSD: { type: 'COMMODITY', entry: 2325, size: 6, stop: 2280, leverage: 5, equity: 15000, margin: 10000, maintenance: 1.5, fees: 0.04 }
};

const fields = {
  assetPreset: document.getElementById('assetPreset'),
  assetType: document.getElementById('assetType'),
  equity: document.getElementById('equity'),
  availableMargin: document.getElementById('availableMargin'),
  entryPrice: document.getElementById('entryPrice'),
  positionSize: document.getElementById('positionSize'),
  leverage: document.getElementById('leverage'),
  stopPrice: document.getElementById('stopPrice'),
  maintenance: document.getElementById('maintenance'),
  fees: document.getElementById('fees'),
  aiConfidence: document.getElementById('aiConfidence'),
  volatilityShock: document.getElementById('volatilityShock')
};

const output = {
  aiConfidenceValue: document.getElementById('aiConfidenceValue'),
  volatilityShockValue: document.getElementById('volatilityShockValue'),
  healthScore: document.getElementById('healthScore'),
  healthLabel: document.getElementById('healthLabel'),
  liquidationPrice: document.getElementById('liquidationPrice'),
  liqDistance: document.getElementById('liqDistance'),
  initialMargin: document.getElementById('initialMargin'),
  marginUsage: document.getElementById('marginUsage'),
  riskToStop: document.getElementById('riskToStop'),
  riskPercent: document.getElementById('riskPercent'),
  quantMeter: document.getElementById('quantMeter'),
  neuralMeter: document.getElementById('neuralMeter'),
  sentimentMeter: document.getElementById('sentimentMeter'),
  quantValue: document.getElementById('quantValue'),
  neuralValue: document.getElementById('neuralValue'),
  sentimentValue: document.getElementById('sentimentValue'),
  riskBadge: document.getElementById('riskBadge'),
  decisionText: document.getElementById('decisionText'),
  scenarioRows: document.getElementById('scenarioRows'),
  scenarioSummary: document.getElementById('scenarioSummary'),
  snapshotLog: document.getElementById('snapshotLog'),
  saveState: document.getElementById('saveState'),
  mirrorState: document.getElementById('mirrorState'),
  simClock: document.getElementById('simClock'),
  simMode: document.getElementById('simMode'),
  simPrice: document.getElementById('simPrice'),
  simTick: document.getElementById('simTick'),
  simEquity: document.getElementById('simEquity'),
  simDrawdown: document.getElementById('simDrawdown'),
  strategyGen: document.getElementById('strategyGen'),
  strategyState: document.getElementById('strategyState'),
  tapeSummary: document.getElementById('tapeSummary'),
  positionTitle: document.getElementById('positionTitle'),
  positionPnl: document.getElementById('positionPnl'),
  positionFreeMargin: document.getElementById('positionFreeMargin'),
  positionStatus: document.getElementById('positionStatus'),
  decisionSummary: document.getElementById('decisionSummary'),
  decisionLog: document.getElementById('decisionLog'),
  mistakeSummary: document.getElementById('mistakeSummary'),
  mistakeLog: document.getElementById('mistakeLog'),
  brokerSummary: document.getElementById('brokerSummary'),
  brokerLog: document.getElementById('brokerLog'),
  watchlistSummary: document.getElementById('watchlistSummary'),
  watchlistPredictions: document.getElementById('watchlistPredictions'),
  timelineSummary: document.getElementById('timelineSummary'),
  strategyTimeline: document.getElementById('strategyTimeline')
};

const controls = {
  runToggleButton: document.getElementById('runToggleButton'),
  stepButton: document.getElementById('stepButton'),
  resetSimButton: document.getElementById('resetSimButton'),
  speedSelect: document.getElementById('speedSelect'),
  watchlistSymbols: document.getElementById('watchlistSymbols'),
  refreshWatchlistButton: document.getElementById('refreshWatchlistButton')
};

const canvas = document.getElementById('riskCanvas');
const ctx = canvas.getContext('2d');
const equityCanvas = document.getElementById('equityCanvas');
const equityCtx = equityCanvas.getContext('2d');
const storageKey = 'ai-margin-visualizer-snapshots';
let latestState = null;
let replayTimer = null;
const strategyApiBase = window.location.protocol.startsWith('http')
  ? `${window.location.protocol}//${window.location.hostname}:3201`
  : 'http://localhost:3201';
const watchlistRefreshMs = 30000;
const watchlistStaleMs = 90000;

const replay = {
  running: false,
  tick: 0,
  price: 0,
  equity: 0,
  maxEquity: 0,
  pnl: 0,
  freeMargin: 0,
  status: 'Paused',
  decisions: [],
  mistakes: [],
  equitySeries: [],
  generation: 3,
  baseTime: new Date('2024-01-02T09:30:00Z')
};

const strategyFeed = {
  active: null,
  history: [],
  error: '',
  loaded: false
};

const executionFeed = {
  decisions: [],
  mistakes: [],
  brokerEvents: [],
  decisionsSource: 'local',
  mistakesSource: 'local',
  brokerSource: 'local',
  loaded: false,
  error: ''
};

const watchlistFeed = {
  symbols: controls.watchlistSymbols.value,
  source: 'unknown',
  status: 'idle',
  loadedAtMs: 0,
  items: [],
  error: ''
};

function getDirection() {
  return document.querySelector('input[name="direction"]:checked').value;
}

function money(value) {
  const number = Number.isFinite(value) ? value : 0;
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(number);
}

function decimal(value, digits = 2) {
  const number = Number.isFinite(value) ? value : 0;
  return number.toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function percent(value) {
  return `${decimal(Number.isFinite(value) ? value : 0, 1)}%`;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function readModel() {
  const entry = Math.max(0.0001, Number(fields.entryPrice.value));
  const size = Math.max(0.0001, Number(fields.positionSize.value));
  const leverage = clamp(Number(fields.leverage.value), 1, 125);
  const equity = Math.max(0, Number(fields.equity.value));
  const availableMargin = Math.max(0, Number(fields.availableMargin.value));
  const stop = Math.max(0.0001, Number(fields.stopPrice.value));
  const maintenance = clamp(Number(fields.maintenance.value) / 100, 0, 0.5);
  const fees = clamp(Number(fields.fees.value) / 100, 0, 0.1);
  const confidence = clamp(Number(fields.aiConfidence.value), 0, 100);
  const shock = clamp(Number(fields.volatilityShock.value), 1, 30);
  const direction = getDirection();

  const notional = entry * size;
  const initialMargin = notional / leverage;
  const feeCost = notional * fees;
  const priceRisk = Math.abs(entry - stop) * size;
  const riskToStop = priceRisk + feeCost;
  const riskPct = equity > 0 ? (riskToStop / equity) * 100 : 100;
  const freeMargin = availableMargin - initialMargin;
  const marginUsage = availableMargin > 0 ? (initialMargin / availableMargin) * 100 : 100;
  const liqFactor = direction === 'long' ? 1 - (1 / leverage) + maintenance + fees : 1 + (1 / leverage) - maintenance - fees;
  const liquidation = Math.max(0.0001, entry * liqFactor);
  const liqDistancePct = Math.abs(entry - liquidation) / entry * 100;
  const stopBeforeLiq = direction === 'long' ? stop > liquidation : stop < liquidation;
  const volatilityPenalty = Math.max(0, shock - liqDistancePct) * 3.2;
  const riskPenalty = Math.max(0, riskPct - 2) * 5.5;
  const marginPenalty = Math.max(0, marginUsage - 55) * 0.9;
  const stopPenalty = stopBeforeLiq ? 0 : 22;
  const confidenceLift = (confidence - 50) * 0.22;
  const health = clamp(82 + confidenceLift - volatilityPenalty - riskPenalty - marginPenalty - stopPenalty, 0, 100);
  const quant = clamp(100 - riskPct * 8 - marginUsage * 0.25 + (stopBeforeLiq ? 8 : -12), 0, 100);
  const neural = clamp(confidence - shock * 0.7 + liqDistancePct * 1.1, 0, 100);
  const sentiment = clamp(62 + confidence * 0.25 - shock * 0.9 - riskPct * 2, 0, 100);
  const consensus = (quant + neural + sentiment) / 3;

  return {
    asset: fields.assetPreset.value,
    assetType: fields.assetType.value,
    direction,
    entry,
    size,
    leverage,
    equity,
    availableMargin,
    stop,
    maintenance,
    fees,
    confidence,
    shock,
    notional,
    initialMargin,
    feeCost,
    riskToStop,
    riskPct,
    freeMargin,
    marginUsage,
    liquidation,
    liqDistancePct,
    stopBeforeLiq,
    health,
    quant,
    neural,
    sentiment,
    consensus
  };
}

function defensiveRule(model) {
  const signalSpread = Math.max(model.quant, model.neural, model.sentiment) - Math.min(model.quant, model.neural, model.sentiment);
  const reasons = [];

  if (model.consensus >= 42 && model.consensus <= 62) reasons.push('AI consensus is not decisive');
  if (signalSpread >= 32) reasons.push('model signals disagree');
  if (model.riskPct > 3) reasons.push('risk to stop is above the defensive limit');
  if (model.marginUsage > 65) reasons.push('margin usage is elevated');
  if (model.shock > model.liqDistancePct * 0.75) reasons.push('volatility shock is too close to liquidation distance');
  if (!model.stopBeforeLiq) reasons.push('stop is not protecting the position before liquidation');

  return {
    active: reasons.length > 0,
    reasons
  };
}

function classify(model) {
  const defensive = defensiveRule(model);
  if (model.health >= 76 && model.consensus > 62 && model.stopBeforeLiq && !defensive.active) return { label: 'Clear', cls: 'status-ok', defensive };
  if (model.health >= 35 && defensive.active) return { label: 'Defensive', cls: 'status-watch', defensive };
  if (model.health >= 45 && model.consensus >= 42) return { label: 'Caution', cls: 'status-watch', defensive };
  return { label: 'Danger', cls: 'status-danger', defensive };
}

function scenarioPrice(model, movePct) {
  return Math.max(0.0001, model.entry * (1 + movePct / 100));
}

function pnlAt(model, price) {
  const raw = model.direction === 'long' ? (price - model.entry) * model.size : (model.entry - price) * model.size;
  return raw - model.feeCost;
}

function buildScenarios(model) {
  const adverseSign = model.direction === 'long' ? -1 : 1;
  const favorableSign = model.direction === 'long' ? 1 : -1;
  const scenarios = [
    { name: 'Current', price: model.entry },
    { name: 'Favorable 3%', price: scenarioPrice(model, favorableSign * 3) },
    { name: 'Adverse 2%', price: scenarioPrice(model, adverseSign * 2) },
    { name: 'Adverse 5%', price: scenarioPrice(model, adverseSign * 5) },
    { name: `Shock ${model.shock}%`, price: scenarioPrice(model, adverseSign * model.shock) },
    { name: 'Stop', price: model.stop },
    { name: 'Liquidation', price: model.liquidation }
  ];

  return scenarios.map((scenario) => {
    const pnl = pnlAt(model, scenario.price);
    const equityAfter = model.equity + pnl;
    const freeMarginAfter = model.freeMargin + pnl;
    const liquidated = model.direction === 'long' ? scenario.price <= model.liquidation : scenario.price >= model.liquidation;
    const status = liquidated || equityAfter <= 0 ? 'Liquidate' : freeMarginAfter < 0 ? 'Margin Call' : pnl < -model.riskToStop * 0.85 ? 'Watch' : 'OK';
    return { ...scenario, pnl, equityAfter, freeMarginAfter, status };
  });
}

function replayKey(model) {
  return `${model.asset}:${model.direction}`;
}

function formatReplayTime() {
  const time = new Date(replay.baseTime.getTime() + replay.tick * 15 * 60 * 1000);
  return time.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function formatEventTime(value) {
  if (!value) return '--';
  const time = new Date(value);
  if (Number.isNaN(time.getTime())) return value;
  return time.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function projectedPrice(model, tick) {
  const directionBias = model.direction === 'long' ? 1 : -1;
  const signalDrift = directionBias * ((model.consensus - 50) / 50) * tick * 0.08;
  const wave = Math.sin(tick * 0.72) * model.shock * 0.18;
  const chop = Math.cos(tick * 0.31) * model.shock * 0.11;
  const stress = tick > 0 && tick % 11 === 0 ? -model.shock * 0.7 : 0;
  const rebound = tick > 0 && tick % 11 === 1 ? model.shock * 0.32 : 0;
  const movePct = clamp(signalDrift + wave + chop + stress + rebound, -model.shock * 1.4, model.shock * 1.15);
  return scenarioPrice(model, movePct);
}

function replayStatus(model, price, equityAfter, freeMarginAfter, drawdown) {
  const liquidated = model.direction === 'long' ? price <= model.liquidation : price >= model.liquidation;
  const stopped = model.direction === 'long' ? price <= model.stop : price >= model.stop;

  if (liquidated || equityAfter <= 0) return 'Liquidate';
  if (freeMarginAfter < 0) return 'Margin Call';
  if (stopped) return 'Stop Hit';
  if (drawdown >= 6 || Math.abs(price - model.liquidation) / model.entry * 100 < model.shock * 0.45) return 'Watch';
  return 'OK';
}

function decisionFor(model, status, drawdown) {
  const risk = classify(model);

  if (status === 'Liquidate') return { action: 'Emergency Exit', detail: 'Liquidation boundary reached in replay.', cls: 'status-danger' };
  if (status === 'Margin Call' || status === 'Stop Hit') return { action: 'Reduce Risk', detail: 'Protect margin before adding exposure.', cls: 'status-danger' };
  if (risk.label === 'Danger') return { action: 'Hold', detail: 'Risk score blocks new exposure.', cls: 'status-danger' };
  if (risk.label === 'Defensive') return { action: 'Trim Size', detail: 'Defensive rule is active while signals conflict.', cls: 'status-watch' };
  if (model.consensus >= 66 && model.health >= 70 && drawdown < 3) return { action: `Add ${model.direction.toUpperCase()}`, detail: 'Consensus and margin health support measured exposure.', cls: 'status-ok' };
  return { action: 'Hold', detail: 'Signal quality is not strong enough to change exposure.', cls: 'status-watch' };
}

function resetReplayState(model, shouldRender = true) {
  stopReplay();
  replay.tick = 0;
  replay.price = model.entry;
  replay.equity = model.equity;
  replay.maxEquity = model.equity;
  replay.pnl = 0;
  replay.freeMargin = model.freeMargin;
  replay.status = 'Paused';
  replay.decisions = [];
  replay.mistakes = [];
  replay.equitySeries = [{ tick: 0, equity: model.equity, price: model.entry }];
  replay.assetKey = replayKey(model);
  if (shouldRender) render();
}

function ensureReplay(model) {
  if (!replay.equitySeries.length || replay.assetKey !== replayKey(model)) {
    resetReplayState(model, false);
  }
}

function stepReplay() {
  const model = readModel();
  ensureReplay(model);
  replay.tick += 1;
  replay.price = projectedPrice(model, replay.tick);
  replay.pnl = pnlAt(model, replay.price);
  replay.equity = model.equity + replay.pnl;
  replay.freeMargin = model.freeMargin + replay.pnl;
  replay.maxEquity = Math.max(replay.maxEquity, replay.equity);

  const drawdown = replay.maxEquity > 0 ? ((replay.maxEquity - replay.equity) / replay.maxEquity) * 100 : 0;
  replay.status = replayStatus(model, replay.price, replay.equity, replay.freeMargin, drawdown);
  const decision = decisionFor(model, replay.status, drawdown);
  replay.decisions.unshift({
    tick: replay.tick,
    time: formatReplayTime(),
    price: replay.price,
    equity: replay.equity,
    action: decision.action,
    detail: decision.detail,
    cls: decision.cls
  });
  replay.decisions = replay.decisions.slice(0, 8);

  if (replay.status !== 'OK' || drawdown >= 6 || !model.stopBeforeLiq) {
    const lastMistake = replay.mistakes[0];
    const duplicateWindow = lastMistake && lastMistake.status === replay.status && replay.tick - lastMistake.tick < 4;
    if (!duplicateWindow) {
      replay.mistakes.unshift({
        tick: replay.tick,
        time: formatReplayTime(),
        status: replay.status,
        title: replay.status === 'OK' ? 'Drawdown pressure' : replay.status,
        detail: `${model.asset} ${model.direction.toUpperCase()} at ${money(replay.price)} with ${percent(drawdown)} drawdown and ${percent(model.consensus)} consensus.`,
        tags: [percent(model.riskPct), percent(model.marginUsage), percent(model.shock)]
      });
      replay.mistakes = replay.mistakes.slice(0, 6);
    }
  }

  replay.equitySeries.push({ tick: replay.tick, equity: replay.equity, price: replay.price });
  replay.equitySeries = replay.equitySeries.slice(-80);
  renderReplay(model);
}

function startReplay() {
  if (replay.running) return;
  replay.running = true;
  controls.runToggleButton.textContent = 'Pause';
  const delay = Math.max(220, 1100 / Number(controls.speedSelect.value));
  replayTimer = window.setInterval(stepReplay, delay);
  renderReplay(readModel());
}

function stopReplay() {
  replay.running = false;
  controls.runToggleButton.textContent = 'Run';
  if (replayTimer) {
    window.clearInterval(replayTimer);
    replayTimer = null;
  }
}

function drawEquityCurve(model) {
  const width = equityCanvas.width;
  const height = equityCanvas.height;
  const pad = 34;
  const series = replay.equitySeries.length ? replay.equitySeries : [{ tick: 0, equity: model.equity, price: model.entry }];
  const values = series.map((point) => point.equity);
  const min = Math.min(...values, model.equity) * 0.995;
  const max = Math.max(...values, model.equity) * 1.005;
  const range = Math.max(1, max - min);
  const xFor = (index) => pad + (index / Math.max(1, series.length - 1)) * (width - pad * 2);
  const yFor = (value) => height - pad - ((value - min) / range) * (height - pad * 2);

  equityCtx.clearRect(0, 0, width, height);
  equityCtx.fillStyle = '#fbfcfb';
  equityCtx.fillRect(0, 0, width, height);

  equityCtx.strokeStyle = '#d8ded8';
  equityCtx.lineWidth = 1;
  equityCtx.beginPath();
  for (let i = 0; i <= 4; i += 1) {
    const y = pad + i * ((height - pad * 2) / 4);
    equityCtx.moveTo(pad, y);
    equityCtx.lineTo(width - pad, y);
  }
  equityCtx.stroke();

  equityCtx.strokeStyle = '#245c7c';
  equityCtx.lineWidth = 3;
  equityCtx.beginPath();
  series.forEach((point, index) => {
    const x = xFor(index);
    const y = yFor(point.equity);
    if (index === 0) equityCtx.moveTo(x, y);
    else equityCtx.lineTo(x, y);
  });
  equityCtx.stroke();

  const current = series[series.length - 1];
  equityCtx.fillStyle = current.equity >= model.equity ? '#18794e' : '#b42318';
  equityCtx.beginPath();
  equityCtx.arc(xFor(series.length - 1), yFor(current.equity), 5, 0, Math.PI * 2);
  equityCtx.fill();

  equityCtx.fillStyle = '#667267';
  equityCtx.font = '800 12px Inter, sans-serif';
  equityCtx.textAlign = 'left';
  equityCtx.fillText('Paper equity curve', pad, 22);
  equityCtx.textAlign = 'right';
  equityCtx.fillText(money(current.equity), width - pad, 22);
}

function renderEventList() {
  const hasDecisionFeed = executionFeed.decisions.length > 0;
  const hasMistakeFeed = executionFeed.mistakes.length > 0;

  if (hasDecisionFeed) {
    output.decisionSummary.textContent = `${executionFeed.decisions.length} recent (${executionFeed.decisionsSource})`;
    output.decisionLog.innerHTML = executionFeed.decisions.map((item) => {
      const verdict = item.was_correct === true ? 'correct' : item.was_correct === false ? 'wrong' : 'unscored';
      const tags = [item.decision || 'UNKNOWN', verdict];
      if (Number.isFinite(item.actual_return_pct)) tags.push(percent(item.actual_return_pct));
      return `
      <article class="event-item">
        <strong>${item.symbol} ${item.decision || 'HOLD'}</strong>
        <span class="event-meta">${formatEventTime(item.time)} | equity ${money(item.paper_equity ?? 0)}</span>
        <span class="event-meta">${item.reason || 'No decision reason provided.'}</span>
        <div class="event-tags">
          ${tags.map((tag) => `<span class="event-tag">${tag}</span>`).join('')}
        </div>
      </article>
    `;
    }).join('');
  } else if (!replay.decisions.length) {
    output.decisionLog.innerHTML = '<article class="event-item"><strong>No paper decisions yet</strong><span class="event-meta">Run or step the replay to generate events.</span></article>';
    output.decisionSummary.textContent = 'No decisions';
  } else {
    output.decisionSummary.textContent = `${replay.decisions.length} recent (local replay)`;
    output.decisionLog.innerHTML = replay.decisions.map((item) => `
      <article class="event-item">
        <strong>${item.action}</strong>
        <span class="event-meta">${item.time} | ${money(item.price)} | equity ${money(item.equity)}</span>
        <span class="event-meta">${item.detail}</span>
        <div class="event-tags">
          <span class="event-tag ${item.cls}">tick ${item.tick}</span>
        </div>
      </article>
    `).join('');
  }

  if (hasMistakeFeed) {
    output.mistakeSummary.textContent = `${executionFeed.mistakes.length} flagged (${executionFeed.mistakesSource})`;
    output.mistakeLog.innerHTML = executionFeed.mistakes.map((item) => {
      const title = item.title || item.mistake_type || 'Mistake';
      const detail = item.detail || `${item.symbol} ${item.mistake_type || 'issue'} (${item.severity || 'unknown'})`;
      const tags = [item.symbol || 'unknown', item.severity || 'unknown'];
      return `
      <article class="event-item">
        <strong>${title}</strong>
        <span class="event-meta">${formatEventTime(item.time)}</span>
        <span class="event-meta">${detail}</span>
        <div class="event-tags">
          ${tags.map((tag) => `<span class="event-tag">${tag}</span>`).join('')}
        </div>
      </article>
    `;
    }).join('');
  } else if (!replay.mistakes.length) {
    output.mistakeLog.innerHTML = '<article class="event-item"><strong>No replay mistakes</strong><span class="event-meta">Risk breaches and drawdown events appear here.</span></article>';
    output.mistakeSummary.textContent = 'No mistakes';
  } else {
    output.mistakeSummary.textContent = `${replay.mistakes.length} flagged (local replay)`;
    output.mistakeLog.innerHTML = replay.mistakes.map((item) => `
      <article class="event-item">
        <strong>${item.title}</strong>
        <span class="event-meta">${item.time} | tick ${item.tick}</span>
        <span class="event-meta">${item.detail}</span>
        <div class="event-tags">
          ${item.tags.map((tag) => `<span class="event-tag">${tag}</span>`).join('')}
        </div>
      </article>
    `).join('');
  }
}

function renderBrokerEvents() {
  if (!executionFeed.brokerEvents.length) {
    output.brokerSummary.textContent = 'No events';
    output.brokerLog.innerHTML = '<article class="event-item"><strong>No broker events yet</strong><span class="event-meta">Place demo orders or connect Postgres-backed broker events.</span></article>';
    return;
  }

  output.brokerSummary.textContent = `${executionFeed.brokerEvents.length} recent (${executionFeed.brokerSource})`;
  output.brokerLog.innerHTML = executionFeed.brokerEvents.map((item) => {
    const pnlClass = Number(item.realized_pnl || 0) >= 0 ? 'status-ok' : 'status-danger';
    return `
      <article class="event-item">
        <strong>${item.side} ${item.symbol} ${money(item.amount)}</strong>
        <span class="event-meta">${formatEventTime(item.time)} | ${money(item.price)} | units ${decimal(Number(item.units || 0), 6)}</span>
        <span class="event-meta">fee ${money(Number(item.estimated_fee || 0))} | realized ${money(Number(item.realized_pnl || 0))}</span>
        <div class="event-tags">
          <span class="event-tag ${pnlClass}">${item.status || 'accepted'}</span>
          ${item.reason ? `<span class="event-tag">${item.reason}</span>` : ''}
        </div>
      </article>
    `;
  }).join('');
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

async function loadStrategyFeed() {
  try {
    const [active, history] = await Promise.all([
      fetchJson(`${strategyApiBase}/strategy/active`),
      fetchJson(`${strategyApiBase}/strategy/history?limit=8`)
    ]);
    strategyFeed.active = active;
    strategyFeed.history = Array.isArray(history.items) ? history.items : [];
    strategyFeed.error = '';
    strategyFeed.loaded = true;
    if (Number.isFinite(active.generation)) {
      replay.generation = active.generation;
    }
  } catch (error) {
    strategyFeed.error = error.message;
    strategyFeed.loaded = true;
  }
  renderTimeline();
}

async function loadExecutionFeed() {
  try {
    const [decisions, mistakes, brokerEvents] = await Promise.all([
      fetchJson(`${strategyApiBase}/events/decisions?limit=12`),
      fetchJson(`${strategyApiBase}/events/mistakes?limit=12`),
      fetchJson(`${strategyApiBase}/broker/demo/events?limit=12`)
    ]);
    executionFeed.decisions = Array.isArray(decisions.items) ? decisions.items : [];
    executionFeed.mistakes = Array.isArray(mistakes.items) ? mistakes.items : [];
    executionFeed.brokerEvents = Array.isArray(brokerEvents.items) ? brokerEvents.items : [];
    executionFeed.decisionsSource = decisions.source || 'api';
    executionFeed.mistakesSource = mistakes.source || 'api';
    executionFeed.brokerSource = brokerEvents.source || 'api';
    executionFeed.error = '';
    executionFeed.loaded = true;
  } catch (error) {
    executionFeed.error = error.message;
    executionFeed.loaded = true;
  }
  renderEventList();
  renderBrokerEvents();
}

function normalizedWatchlistSymbols(raw) {
  return raw
    .split(',')
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean)
    .join(',');
}

function watchlistAgeSeconds() {
  if (!watchlistFeed.loadedAtMs) return null;
  return Math.max(0, Math.floor((Date.now() - watchlistFeed.loadedAtMs) / 1000));
}

function renderWatchlistFeed() {
  if (watchlistFeed.error) {
    output.watchlistSummary.textContent = `API unavailable (${watchlistFeed.error})`;
    output.watchlistPredictions.innerHTML = '<article class="event-item"><strong>Watchlist unavailable</strong><span class="event-meta">Check Brain API and retry.</span></article>';
    return;
  }

  if (!watchlistFeed.items.length) {
    output.watchlistSummary.textContent = 'No symbols loaded';
    output.watchlistPredictions.innerHTML = '<article class="event-item"><strong>No watchlist data</strong><span class="event-meta">Enter symbols and refresh.</span></article>';
    return;
  }

  const ageSeconds = watchlistAgeSeconds();
  const stale = ageSeconds !== null && ageSeconds > Math.floor(watchlistStaleMs / 1000);
  const staleLabel = stale ? `stale ${ageSeconds}s` : ageSeconds === null ? 'fresh' : `${ageSeconds}s ago`;
  output.watchlistSummary.textContent = `${watchlistFeed.items.length} symbols | ${watchlistFeed.source} | ${staleLabel}`;

  output.watchlistPredictions.innerHTML = watchlistFeed.items.map((item) => {
    const prediction = item.prediction || {};
    const plan = prediction.trade_plan || {};
    const guard = prediction.execution_guardrails || {};
    const cooldown = guard.cooldown || {};
    const blocked = guard.execution_action === 'WAIT_COOLDOWN' || cooldown.can_trade_now === false;
    const decision = prediction.paper_decision || 'HOLD';
    const execAction = guard.execution_action || decision;
    const remainingMs = Number(cooldown.remaining_ms || 0);
    const guardText = blocked
      ? `cooldown ${Math.ceil(remainingMs / 1000)}s`
      : 'tradable now';
    return `
      <article class="event-item">
        <strong>${item.symbol} ${prediction.direction || '--'} (${decimal(Number(prediction.confidence || 0), 0)}%)</strong>
        <span class="event-meta">${formatEventTime(item.latest_candle?.time)} | close ${money(Number(item.latest_candle?.close || 0))}</span>
        <span class="event-meta">paper ${decision} | execution ${execAction} | ${guardText}</span>
        <span class="event-meta">target ${money(Number(plan.target_exit_price || item.latest_candle?.close || 0))} | net ${percent(Number(plan.net_expected_return_pct || 0))}</span>
        <div class="event-tags">
          <span class="event-tag ${blocked ? 'status-watch' : 'status-ok'}">${blocked ? 'WAIT_COOLDOWN' : 'READY'}</span>
          ${plan.fee_assumption_pct !== undefined ? `<span class="event-tag">fee ${percent(Number(plan.fee_assumption_pct || 0))}</span>` : ''}
        </div>
      </article>
    `;
  }).join('');
}

async function loadWatchlistFeed() {
  const symbols = normalizedWatchlistSymbols(controls.watchlistSymbols.value || '');
  if (!symbols) {
    watchlistFeed.items = [];
    watchlistFeed.error = '';
    watchlistFeed.symbols = '';
    renderWatchlistFeed();
    return;
  }

  watchlistFeed.symbols = symbols;
  controls.watchlistSymbols.value = symbols;
  try {
    const payload = await fetchJson(`${strategyApiBase}/watchlist/predictions?symbols=${encodeURIComponent(symbols)}`);
    watchlistFeed.items = Array.isArray(payload.items) ? payload.items : [];
    watchlistFeed.source = payload.source || 'unknown';
    watchlistFeed.status = payload.status || 'ok';
    watchlistFeed.error = '';
    watchlistFeed.loadedAtMs = Date.now();
  } catch (error) {
    watchlistFeed.error = error.message;
  }
  renderWatchlistFeed();
}

function formatTimelineTimestamp(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function renderStrategyFeedTimeline() {
  const testing = replay.mistakes.length > 0;
  const active = strategyFeed.active;
  if (!active) return false;

  output.strategyGen.textContent = `Gen ${active.generation}`;
  if (testing) {
    output.strategyState.textContent = 'Candidate queued';
  } else if (active.selection_source === 'env_override') {
    output.strategyState.textContent = `Pinned by .env (${active.generation_id.toUpperCase()})`;
  } else {
    output.strategyState.textContent = active.validation_status === 'promoted' ? 'Promoted active' : 'Config active';
  }

  const summaryParts = [`${active.generation_id.toUpperCase()} active`];
  if (strategyFeed.history.length) summaryParts.push(`${strategyFeed.history.length} versions`);
  if (active.db_status === 'fallback') summaryParts.push('local fallback');
  output.timelineSummary.textContent = summaryParts.join(' | ');

  const items = strategyFeed.history.map((item) => {
    const metaParts = [];
    if (item.validation_status) metaParts.push(item.validation_status);
    if (item.approval_reason) metaParts.push(item.approval_reason);
    const stamped = formatTimelineTimestamp(item.promoted_at);
    if (stamped) metaParts.push(stamped);
    if (item.strategy_path) metaParts.push(item.strategy_path);
    return {
      title: `Gen ${item.generation} - ${item.name || item.generation_id.toUpperCase()}`,
      meta: metaParts.join(' | ') || 'No promotion metadata recorded yet.',
      cls: item.selected || item.is_active ? 'deployed' : ''
    };
  });

  if (testing) {
    items.unshift({
      title: `Candidate ${active.generation + 1} - queued`,
      meta: `${replay.mistakes.length} mistake signal${replay.mistakes.length === 1 ? '' : 's'} queued for sandbox replay.`,
      cls: 'testing'
    });
  }

  output.strategyTimeline.innerHTML = items.map((item) => `
    <article class="timeline-item ${item.cls}">
      <strong>${item.title}</strong>
      <span>${item.meta}</span>
    </article>
  `).join('');
  return true;
}

function renderTimeline() {
  if (renderStrategyFeedTimeline()) return;

  const testing = replay.mistakes.length > 0;
  output.strategyGen.textContent = `Gen ${replay.generation}`;
  if (strategyFeed.error) {
    output.strategyState.textContent = 'Brain API unavailable';
    output.timelineSummary.textContent = 'Local mock timeline';
  } else {
    output.strategyState.textContent = testing ? 'Candidate queued' : 'Baseline active';
    output.timelineSummary.textContent = testing ? `Candidate ${replay.generation + 1} queued` : `Gen ${replay.generation} active`;
  }

  const items = [
    { title: 'Gen 1 - Baseline ensemble', meta: 'Initial quant, neural, and sentiment blend.', cls: 'deployed' },
    { title: 'Gen 2 - Defensive ambiguity rule', meta: 'Blocks new exposure when model votes disagree.', cls: 'deployed' },
    { title: 'Gen 3 - Margin shock guard', meta: 'Current generation: tests liquidation distance against volatility shock.', cls: 'deployed' }
  ];

  if (testing) {
    items.unshift({
      title: 'Candidate 4 - Volatility filter',
      meta: `${replay.mistakes.length} mistake signal${replay.mistakes.length === 1 ? '' : 's'} queued for sandbox replay.`,
      cls: 'testing'
    });
  }

  output.strategyTimeline.innerHTML = items.map((item) => `
    <article class="timeline-item ${item.cls}">
      <strong>${item.title}</strong>
      <span>${item.meta}</span>
    </article>
  `).join('');
}

function renderReplay(model) {
  ensureReplay(model);
  const drawdown = replay.maxEquity > 0 ? ((replay.maxEquity - replay.equity) / replay.maxEquity) * 100 : 0;
  const pnlClass = replay.pnl >= 0 ? 'profit' : 'loss';
  const statusClass = replay.status === 'OK' || replay.status === 'Paused' ? 'status-ok' : replay.status === 'Watch' ? 'status-watch' : 'status-danger';

  output.mirrorState.textContent = replay.running ? 'Mirror streaming' : 'Mirror paused';
  output.mirrorState.className = replay.running ? 'status-pill' : 'status-pill neutral';
  output.simClock.textContent = formatReplayTime();
  output.simMode.textContent = replay.running ? `Streaming at ${controls.speedSelect.value}x` : 'Replay paused';
  output.simPrice.textContent = money(replay.price);
  output.simTick.textContent = `Tick ${replay.tick}`;
  output.simEquity.textContent = money(replay.equity);
  output.simDrawdown.textContent = `Drawdown ${percent(drawdown)}`;
  const decisionCount = executionFeed.decisions.length || replay.decisions.length;
  const mistakeCount = executionFeed.mistakes.length || replay.mistakes.length;
  output.tapeSummary.textContent = `${replay.status} | ${decisionCount} decisions | ${mistakeCount} mistakes`;
  output.positionTitle.textContent = `${model.asset} ${model.direction.toUpperCase()} x${decimal(model.leverage, 0)}`;
  output.positionPnl.textContent = money(replay.pnl);
  output.positionPnl.className = pnlClass;
  output.positionFreeMargin.textContent = money(replay.freeMargin);
  output.positionStatus.textContent = replay.status;
  output.positionStatus.className = statusClass;

  renderEventList();
  renderBrokerEvents();
  renderWatchlistFeed();
  renderTimeline();
  drawEquityCurve(model);
}

function updateMetrics(model) {
  const risk = classify(model);
  output.aiConfidenceValue.textContent = `${model.confidence}%`;
  output.volatilityShockValue.textContent = `${model.shock}%`;
  output.healthScore.textContent = decimal(model.health, 0);
  output.healthLabel.textContent = risk.label;
  output.liquidationPrice.textContent = money(model.liquidation);
  output.liqDistance.textContent = `${percent(model.liqDistancePct)} from entry`;
  output.initialMargin.textContent = money(model.initialMargin);
  output.marginUsage.textContent = `${percent(model.marginUsage)} of available`;
  output.riskToStop.textContent = money(model.riskToStop);
  output.riskPercent.textContent = `${percent(model.riskPct)} of equity`;

  output.quantMeter.value = model.quant;
  output.neuralMeter.value = model.neural;
  output.sentimentMeter.value = model.sentiment;
  output.quantValue.textContent = decimal(model.quant, 0);
  output.neuralValue.textContent = decimal(model.neural, 0);
  output.sentimentValue.textContent = decimal(model.sentiment, 0);
  output.riskBadge.textContent = risk.label;
  output.riskBadge.className = `signal-badge ${risk.cls}`;

  const stopText = model.stopBeforeLiq ? 'The stop is before estimated liquidation.' : 'The stop is beyond estimated liquidation.';
  const marginText = model.freeMargin >= 0 ? `${money(model.freeMargin)} free margin remains.` : `${money(Math.abs(model.freeMargin))} margin deficit at entry.`;
  const defensiveText = risk.defensive.active
    ? `Defensive rule active: ${risk.defensive.reasons.join(', ')}. Protect capital first: reduce size or leverage, tighten risk, or wait for a clearer setup.`
    : 'Defensive rule clear: risk inputs are aligned enough for normal evaluation.';
  output.decisionText.textContent = `${risk.label}: ${model.asset} ${model.direction.toUpperCase()} has ${percent(model.liqDistancePct)} liquidation distance, ${percent(model.riskPct)} equity risk to stop, and ${percent(model.consensus)} AI consensus. ${stopText} ${marginText} ${defensiveText}`;
}

function updateScenarios(model) {
  const rows = buildScenarios(model);
  const dangerCount = rows.filter((row) => row.status !== 'OK').length;
  output.scenarioSummary.textContent = `${dangerCount} flagged`;
  output.scenarioRows.innerHTML = rows.map((row) => {
    const statusClass = row.status === 'OK' ? 'status-ok' : row.status === 'Watch' ? 'status-watch' : 'status-danger';
    const pnlClass = row.pnl >= 0 ? 'profit' : 'loss';
    return `
      <tr>
        <td>${row.name}</td>
        <td>${money(row.price)}</td>
        <td class="${pnlClass}">${money(row.pnl)}</td>
        <td>${money(row.equityAfter)}</td>
        <td>${money(row.freeMarginAfter)}</td>
        <td><span class="status-cell ${statusClass}">${row.status}</span></td>
      </tr>
    `;
  }).join('');
}

function drawRiskMap(model) {
  const width = canvas.width;
  const height = canvas.height;
  const pad = 48;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = '#fbfcfb';
  ctx.fillRect(0, 0, width, height);

  const levels = [model.entry, model.stop, model.liquidation, scenarioPrice(model, model.direction === 'long' ? -model.shock : model.shock), scenarioPrice(model, model.direction === 'long' ? 4 : -4)];
  const min = Math.min(...levels) * 0.985;
  const max = Math.max(...levels) * 1.015;
  const range = Math.max(0.0001, max - min);
  const xFor = (price) => pad + ((price - min) / range) * (width - pad * 2);
  const yBase = height - pad;
  const yTop = pad;

  const liqX = xFor(model.liquidation);
  const entryX = xFor(model.entry);
  const dangerStart = model.direction === 'long' ? pad : liqX;
  const dangerWidth = model.direction === 'long' ? Math.max(0, liqX - pad) : Math.max(0, width - pad - liqX);

  ctx.fillStyle = 'rgba(180, 35, 24, 0.09)';
  ctx.fillRect(dangerStart, yTop, dangerWidth, yBase - yTop);
  ctx.fillStyle = 'rgba(24, 121, 78, 0.08)';
  const safeStart = model.direction === 'long' ? entryX : pad;
  const safeWidth = model.direction === 'long' ? width - pad - entryX : entryX - pad;
  ctx.fillRect(safeStart, yTop, Math.max(0, safeWidth), yBase - yTop);

  ctx.strokeStyle = '#d8ded8';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pad, yBase);
  ctx.lineTo(width - pad, yBase);
  for (let i = 0; i <= 4; i += 1) {
    const x = pad + i * ((width - pad * 2) / 4);
    ctx.moveTo(x, yTop);
    ctx.lineTo(x, yBase);
  }
  ctx.stroke();

  const pathPrices = model.direction === 'long'
    ? [model.entry, scenarioPrice(model, -1.5), scenarioPrice(model, -model.shock * 0.45), model.stop, scenarioPrice(model, -model.shock)]
    : [model.entry, scenarioPrice(model, 1.5), scenarioPrice(model, model.shock * 0.45), model.stop, scenarioPrice(model, model.shock)];

  ctx.strokeStyle = '#245c7c';
  ctx.lineWidth = 4;
  ctx.beginPath();
  pathPrices.forEach((price, index) => {
    const x = xFor(price);
    const y = yBase - 44 - index * 50 + Math.sin(index) * 8;
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  drawMarker('Entry', model.entry, '#245c7c');
  drawMarker('Stop', model.stop, '#9d6a00');
  drawMarker('Liq', model.liquidation, '#b42318');

  ctx.fillStyle = '#667267';
  ctx.font = '700 13px Inter, sans-serif';
  ctx.textAlign = 'left';
  ctx.fillText(`${model.asset} ${model.direction.toUpperCase()} risk band`, pad, 28);

  function drawMarker(label, price, color) {
    const x = xFor(price);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(x, yTop);
    ctx.lineTo(x, yBase + 8);
    ctx.stroke();

    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, yBase - 22, 6, 0, Math.PI * 2);
    ctx.fill();

    ctx.font = '800 12px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(label, x, yBase + 26);
    ctx.font = '700 12px Inter, sans-serif';
    ctx.fillText(money(price), x, yBase + 42);
  }
}

function loadSnapshots() {
  try {
    return JSON.parse(localStorage.getItem(storageKey)) || [];
  } catch (error) {
    return [];
  }
}

function saveSnapshots(items) {
  localStorage.setItem(storageKey, JSON.stringify(items.slice(0, 8)));
}

function renderSnapshots() {
  const items = loadSnapshots();
  if (!items.length) {
    output.snapshotLog.innerHTML = '<div class="decision-box">No saved snapshots yet.</div>';
    return;
  }

  output.snapshotLog.innerHTML = items.map((item) => `
    <article class="snapshot-item">
      <div>
        <strong>${item.asset} ${item.direction.toUpperCase()} - ${item.label}</strong>
        <span>${item.time} | health ${item.health} | liq ${item.liquidation} | risk ${item.risk}</span>
      </div>
      <span>${item.confidence}</span>
    </article>
  `).join('');
}

function saveSnapshot() {
  if (!latestState) return;
  const risk = classify(latestState);
  const items = loadSnapshots();
  items.unshift({
    asset: latestState.asset,
    direction: latestState.direction,
    label: risk.label,
    health: decimal(latestState.health, 0),
    liquidation: money(latestState.liquidation),
    risk: percent(latestState.riskPct),
    confidence: percent(latestState.confidence),
    time: new Date().toLocaleString()
  });
  saveSnapshots(items);
  renderSnapshots();
  output.saveState.textContent = 'Snapshot saved';
  window.setTimeout(() => { output.saveState.textContent = 'Local snapshot ready'; }, 1800);
}

function applyPreset(name) {
  const preset = presets[name];
  if (!preset) return;
  fields.assetPreset.value = name;
  fields.assetType.value = preset.type;
  fields.entryPrice.value = preset.entry;
  fields.positionSize.value = preset.size;
  fields.stopPrice.value = preset.stop;
  fields.leverage.value = preset.leverage;
  fields.equity.value = preset.equity;
  fields.availableMargin.value = preset.margin;
  fields.maintenance.value = preset.maintenance;
  fields.fees.value = preset.fees;
}

function resetDefaults() {
  applyPreset('BTCUSDT');
  fields.aiConfidence.value = 64;
  fields.volatilityShock.value = 9;
  document.querySelector('input[name="direction"][value="long"]').checked = true;
  resetReplayState(readModel(), false);
  render();
}

function render() {
  latestState = readModel();
  updateMetrics(latestState);
  updateScenarios(latestState);
  drawRiskMap(latestState);
  renderReplay(latestState);
}

Object.entries(fields).forEach(([key, field]) => {
  if (key === 'assetPreset') return;
  field.addEventListener('input', render);
  field.addEventListener('change', render);
});

document.querySelectorAll('input[name="direction"]').forEach((field) => field.addEventListener('change', () => {
  resetReplayState(readModel(), false);
  render();
}));

fields.assetPreset.addEventListener('change', () => {
  applyPreset(fields.assetPreset.value);
  resetReplayState(readModel(), false);
  render();
});

document.getElementById('snapshotButton').addEventListener('click', saveSnapshot);
document.getElementById('resetButton').addEventListener('click', resetDefaults);
controls.runToggleButton.addEventListener('click', () => {
  if (replay.running) {
    stopReplay();
    renderReplay(readModel());
    return;
  }
  startReplay();
});
controls.stepButton.addEventListener('click', () => {
  if (replay.running) stopReplay();
  stepReplay();
});
controls.resetSimButton.addEventListener('click', () => resetReplayState(readModel()));
controls.speedSelect.addEventListener('change', () => {
  if (replay.running) {
    stopReplay();
    startReplay();
    return;
  }
  renderReplay(readModel());
});
controls.refreshWatchlistButton.addEventListener('click', () => {
  loadWatchlistFeed();
});
controls.watchlistSymbols.addEventListener('change', () => {
  loadWatchlistFeed();
});
document.getElementById('clearLogButton').addEventListener('click', () => {
  localStorage.removeItem(storageKey);
  renderSnapshots();
});

renderSnapshots();
render();
loadStrategyFeed();
loadExecutionFeed();
loadWatchlistFeed();
window.setInterval(loadStrategyFeed, 30000);
window.setInterval(loadExecutionFeed, 30000);
window.setInterval(loadWatchlistFeed, watchlistRefreshMs);
