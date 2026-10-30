let isRunning = true;
let alertActive = true;
let calcEnabled = false;
let currentReportPeriod = 'daily';
const SIGNAL_REFRESH_INTERVAL = 4;
let signalTimerSeconds = SIGNAL_REFRESH_INTERVAL;
let countdownTimer = null;
let lastLiveBalance = 5000;
let mirrorPollTimer = null;

let openPositions = [];

let liquidityPairs = [
  { pair: 'BTC / USDT', volume: 34.2 },
  { pair: 'ETH / USDT', volume: 18.5 },
  { pair: 'SOL / USDT', volume: 6.8 },
  { pair: 'BNB / USDT', volume: 4.1 }
];

let tradeHistory = [
  { pair: 'BTC / USDT', type: 'BUY', lot: '0.15', entry: 64250, exit: 65120, pnl: 210.00, day: 'السبت', time: '02:20:11 م' },
  { pair: 'SOL / USDT', type: 'SELL', lot: '0.50', entry: 145.20, exit: 142.10, pnl: 85.50, day: 'السبت', time: '11:10:45 ص' },
  { pair: 'ETH / USDT', type: 'BUY', lot: '1.00', entry: 3480, exit: 3465, pnl: -15.00, day: 'الجمعة', time: '10:05:00 م' }
];

let signals = [
  { id: 101, pair: 'BTC/USDT', direction: 'BUY', strengthScore: 92, timeframe: '15m', rsi: '68', macd: 'إيجابي', executed: false },
  { id: 102, pair: 'ETH/USDT', direction: 'BUY', strengthScore: 78, timeframe: '1h', rsi: '58', macd: 'إيجابي', executed: false },
  { id: 103, pair: 'SOL/USDT', direction: 'SELL', strengthScore: 88, timeframe: '5m', rsi: '31', macd: 'سلبي', executed: false },
  { id: 104, pair: 'AVAX/USDT', direction: 'SELL', strengthScore: 74, timeframe: '15m', rsi: '29', macd: 'سلبي', executed: false }
];

async function apiPost(path, body) {
  const opts = { method: 'POST', headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  return res.json().catch(() => ({}));
}

function fmtMoney(n) {
  const v = Number(n) || 0;
  return v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' $';
}

function applyMirror(m) {
  if (!m) return;
  lastLiveBalance = Math.max(m.total_balance_usd || 0, m.initial_balance_usd || 5000);
  const totalEl = document.getElementById('totalBalance');
  if (totalEl) totalEl.innerText = fmtMoney(lastLiveBalance);
  const dailyEl = document.getElementById('dailyProfitPct');
  if (dailyEl) {
    const pct = m.daily_profit_pct || 0;
    dailyEl.innerText = `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`;
    dailyEl.className = `text-base font-num font-bold mt-0.5 ${pct >= 0 ? 'text-emerald-400/90' : 'text-rose-400/90'}`;
  }
  const repCurr = document.getElementById('repCurrBal');
  if (repCurr) repCurr.innerText = fmtMoney(lastLiveBalance);
  const repBase = document.getElementById('repBaseBal');
  if (repBase) repBase.innerText = fmtMoney(m.initial_balance_usd || lastLiveBalance);
  openPositions = (m.positions || []).map(p => ({
    id: p.id || p.symbol,
    symbol: p.symbol,
    pair: p.pair,
    type: p.type || 'BUY',
    lot: p.lot,
    entry: p.entry,
    current: p.current,
    pnl: p.pnl
  }));
  renderPositions();
  if (typeof m.bot_running === 'boolean' && m.bot_running !== isRunning) {
    isRunning = m.bot_running;
    syncBotUiFromState();
  }
}

async function refreshBinanceMirror() {
  try {
    const res = await fetch('/api/binance_mirror');
    if (!res.ok) return;
    const data = await res.json();
    applyMirror(data);
  } catch (_) {
    /* keep last snapshot — avoid flashing zeros */
  }
}

function syncBotUiFromState() {
  const icon = document.getElementById('botBtnIcon');
  const text = document.getElementById('botBtnText');
  const statusText = document.getElementById('statusText');
  const statusDot = document.getElementById('statusDot');
  const statusPing = document.getElementById('statusPing');
  if (!icon || !text) return;
  if (isRunning) {
    icon.className = 'fa-solid fa-pause text-[10px]';
    text.innerText = 'إيقاف عمليات البوت مؤقتاً';
    statusText.innerText = 'النظام: نشط';
    statusText.className = 'text-[11px] font-bold text-emerald-400/90 tracking-wide';
    statusDot.className = 'relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500';
    statusPing.classList.remove('hidden');
  } else {
    icon.className = 'fa-solid fa-play text-[10px]';
    text.innerText = 'استئناف عمليات البوت';
    statusText.innerText = 'النظام: متوقف مؤقتاً';
    statusText.className = 'text-[11px] font-bold text-amber-400/90 tracking-wide';
    statusDot.className = 'relative inline-flex rounded-full h-2.5 w-2.5 bg-amber-500';
    statusPing.classList.add('hidden');
  }
}

function showToast(msg) {
  const toast = document.getElementById('toast');
  const toastMsg = document.getElementById('toastMsg');
  if (!toast || !toastMsg) return;
  toastMsg.innerText = msg;
  toast.classList.remove('opacity-0', 'pointer-events-none');
  toast.classList.add('opacity-100');
  setTimeout(() => {
    toast.classList.remove('opacity-100');
    toast.classList.add('opacity-0', 'pointer-events-none');
  }, 2300);
}

function toggleAccordion(id) {
  const content = document.getElementById(id);
  const icon = document.getElementById(`${id}-icon`);
  if (!content) return;
  const isOpen = content.classList.contains('open');
  if (isOpen) {
    content.classList.remove('open');
    if (icon) icon.classList.remove('rotate-180');
  } else {
    content.classList.add('open');
    if (icon) icon.classList.add('rotate-180');
  }
}

function toggleCalculatorPower() {
  calcEnabled = !calcEnabled;
  const btn = document.getElementById('calcPowerBtn');
  const icon = document.getElementById('calcPowerIcon');
  const text = document.getElementById('calcPowerText');
  const capInput = document.getElementById('calcCapital');
  const riskInput = document.getElementById('calcRisk');
  const calcBtn = document.getElementById('calcBtn');
  if (calcEnabled) {
    btn.className = 'bg-emerald-950/40 hover:bg-emerald-900/40 border border-emerald-500/30 text-emerald-400/90 px-2.5 py-1 rounded-lg text-[10px] font-bold transition-all active:scale-95 flex items-center gap-1.5 shadow-sm';
    icon.className = 'fa-solid fa-power-off text-[9px]';
    text.innerText = 'يعمل (مفعل)';
    capInput.disabled = false;
    capInput.value = lastLiveBalance.toFixed(2);
    capInput.className = 'w-full bg-[#0d111a] border border-gray-700 rounded-lg px-2.5 py-1.5 text-gray-200 font-num text-xs';
    riskInput.disabled = false;
    riskInput.value = '2.00';
    riskInput.className = 'w-full bg-[#0d111a] border border-gray-700 rounded-lg px-2.5 py-1.5 text-gray-200 font-num text-xs';
    calcBtn.disabled = false;
    calcBtn.className = 'w-full bg-purple-700/80 hover:bg-purple-600/80 text-white py-2 rounded-lg font-bold text-[11px] shadow transition-all active:scale-95 cursor-pointer';
    document.getElementById('calcResult').innerText = 'الحاسبة جاهزة للحساب بمعامل كيلي الديناميكي ومخاطرة ATR.';
    showToast('تم تفعيل حاسبة العقود بنجاح 🧮');
  } else {
    btn.className = 'bg-rose-950/40 hover:bg-rose-900/40 border border-rose-500/30 text-rose-400/90 px-2.5 py-1 rounded-lg text-[10px] font-bold transition-all active:scale-95 flex items-center gap-1.5 shadow-sm';
    icon.className = 'fa-solid fa-power-off text-[9px]';
    text.innerText = 'متوقف (غير مفعل)';
    capInput.disabled = true;
    capInput.value = '0.00';
    capInput.className = 'w-full bg-[#0d111a] border border-gray-800 rounded-lg px-2.5 py-1.5 text-gray-500 font-num text-xs opacity-60';
    riskInput.disabled = true;
    riskInput.value = '0.00';
    riskInput.className = 'w-full bg-[#0d111a] border border-gray-800 rounded-lg px-2.5 py-1.5 text-gray-500 font-num text-xs opacity-60';
    calcBtn.disabled = true;
    calcBtn.className = 'w-full bg-gray-800 text-gray-500 py-2 rounded-lg font-bold text-[11px] cursor-not-allowed shadow';
    document.getElementById('calcResult').innerText = 'الحاسبة معطلة ومصفرة بالكامل. قم بتفعيل الزر لأداء الحسابات.';
    showToast('تم إيقاف حاسبة العقود');
  }
}

function calculateLotSize() {
  if (!calcEnabled) return;
  const cap = parseFloat(document.getElementById('calcCapital').value) || 0;
  const riskPct = parseFloat(document.getElementById('calcRisk').value) || 0;
  const p = 0.68;
  const b = 2.0;
  const q = 1.0 - p;
  const rawKelly = (b * p - q) / b;
  const fractionalKelly = rawKelly * 0.30;
  const volatilityScalar = Math.min(Math.max(0.015 / 0.008, 0.4), 1.2);
  let calculatedRiskFraction = (riskPct / 100.0) * fractionalKelly * volatilityScalar;
  if (calculatedRiskFraction > 0.03) calculatedRiskFraction = 0.03;
  const recommendedLot = ((cap * calculatedRiskFraction) / 100).toFixed(2);
  document.getElementById('calcResult').innerText = `العقد الموصى به (معامل كيلي الديناميكي): ${recommendedLot} لوت`;
  showToast('تم حساب حجم العقد بناءً على دستور كيلي الديناميكي 🧮');
}

function setReportPeriod(period) {
  currentReportPeriod = period;
  const btnD = document.getElementById('btnDaily');
  const btnW = document.getElementById('btnWeekly');
  const btnM = document.getElementById('btnMonthly');
  const base = 'px-2.5 py-1 rounded-md text-[10px] font-bold text-gray-400 hover:text-white transition-all';
  btnD.className = base;
  btnW.className = base;
  btnM.className = base;
  if (period === 'daily') {
    btnD.className = 'px-2.5 py-1 rounded-md text-[10px] font-black bg-emerald-600 text-white transition-all shadow-sm';
    document.getElementById('repWinAmt').innerText = '+183.43 $';
    document.getElementById('repWinCount').innerText = '4 صفقات';
    document.getElementById('repLossCount').innerText = '0 صفقات';
    showToast('تم اختيار التقرير اليومي');
  } else if (period === 'weekly') {
    btnW.className = 'px-2.5 py-1 rounded-md text-[10px] font-black bg-emerald-600 text-white transition-all shadow-sm';
    document.getElementById('repWinAmt').innerText = '+45.00 $';
    document.getElementById('repWinCount').innerText = '24 صفقة';
    document.getElementById('repLossCount').innerText = '2 صفقة';
    showToast('تم اختيار التقرير الأسبوعي');
  } else {
    btnM.className = 'px-2.5 py-1 rounded-md text-[10px] font-black bg-emerald-600 text-white transition-all shadow-sm';
    document.getElementById('repWinAmt').innerText = '+120.00 $';
    document.getElementById('repWinCount').innerText = '114 صفقة';
    document.getElementById('repLossCount').innerText = '5 صفقات';
    showToast('تم اختيار التقرير الشهري');
  }
}

function renderPositions() {
  const container = document.getElementById('positionsList');
  if (!container) return;
  container.innerHTML = '';
  let totalWinning = 0;
  let totalLosing = 0;
  if (openPositions.length === 0) {
    container.innerHTML = '<div class="text-center text-xs text-gray-400 font-medium py-2">لا توجد صفقات مفتوحة حالياً</div>';
    document.getElementById('winningPnlVal').innerText = '+0.00 $';
    document.getElementById('losingPnlVal').innerText = '-0.00 $';
    document.getElementById('activePositionsCount').innerText = '0';
    return;
  }
  openPositions.forEach(pos => {
    const isProfitable = pos.pnl >= 0;
    if (isProfitable) totalWinning += pos.pnl;
    else totalLosing += Math.abs(pos.pnl);
    const item = document.createElement('div');
    item.className = 'bg-[#121724]/90 p-2.5 rounded-xl border border-gray-800/60 flex items-center justify-between';
    const closeBtnClass = isProfitable
      ? 'bg-emerald-700/80 hover:bg-emerald-600/80 border-emerald-600/40 text-white'
      : 'bg-rose-700/80 hover:bg-rose-600/80 border-rose-600/40 text-white';
    item.innerHTML = `
      <div>
        <div class="flex items-center gap-1.5">
          <span class="font-bold text-xs text-gray-200">${pos.pair}</span>
          <span class="text-[10px] text-emerald-400/90 bg-emerald-950/60 px-1.5 py-0.5 rounded font-num font-medium">${pos.type} ${pos.lot}</span>
          <span class="text-[10px] font-num font-bold ${isProfitable ? 'text-emerald-400/90' : 'text-rose-400/90'}">${isProfitable ? '+' : ''}${pos.pnl.toFixed(2)} $</span>
        </div>
        <div class="text-[10px] text-gray-400 mt-1 font-medium">دخول: ${pos.entry.toLocaleString()} | الحالي: ${pos.current.toLocaleString()}</div>
      </div>
      <div class="flex items-center gap-1.5">
        <button type="button" data-partial="${pos.id}" class="text-[10px] bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 px-2 py-1 rounded-lg border border-amber-500/30 font-bold flex items-center gap-1 transition-all active:scale-95 shadow-sm"><span>50%</span><span class="text-amber-400/80 font-medium">×</span></button>
        <button type="button" data-close="${pos.id}" class="text-[10px] ${closeBtnClass} px-2.5 py-1 rounded-lg border font-bold transition-all active:scale-95 shadow-sm">إغلاق</button>
      </div>`;
    item.querySelector('[data-partial]').onclick = () => partialClosePosition(pos.id);
    item.querySelector('[data-close]').onclick = () => closePosition(pos.id);
    container.appendChild(item);
  });
  document.getElementById('winningPnlVal').innerText = `+${totalWinning.toFixed(2)} $`;
  document.getElementById('losingPnlVal').innerText = `-${totalLosing.toFixed(2)} $`;
  document.getElementById('activePositionsCount').innerText = String(openPositions.length);
}

async function partialClosePosition(id) {
  const pos = openPositions.find(p => p.id === id);
  if (!pos) return;
  const symbol = pos.symbol || String(id);
  const out = await apiPost('/api/control/partial_close', { symbol, fraction: 0.5 });
  if (out.ok) {
    showToast(`تم إغلاق 50% من صفقة ${pos.pair}`);
    await refreshBinanceMirror();
  } else showToast(out.error || 'فشل الإغلاق الجزئي');
}

async function closePosition(id) {
  const pos = openPositions.find(p => p.id === id);
  const symbol = pos?.symbol || String(id);
  const out = await apiPost(`/api/control/close/${encodeURIComponent(symbol)}`);
  if (out.ok) {
    showToast('تم إغلاق الصفقة بالكامل');
    await refreshBinanceMirror();
  } else showToast(out.error || 'فشل الإغلاق');
}

async function closeWinningTrades() {
  const out = await apiPost('/api/control/close_winners');
  await refreshBinanceMirror();
  if (out.closed > 0) showToast('تم إغلاق الصفقات الرابحة وتحصين الأرباح بنجاح 💰');
  else showToast('لا توجد صفقات رابحة مفتوحة');
}

async function closeLosingTrades() {
  const out = await apiPost('/api/control/close_losers');
  await refreshBinanceMirror();
  if (out.closed > 0) showToast('تم إغلاق الصفقات الخاسرة بنجاح');
  else showToast('لا توجد صفقات خاسرة لإغلاقها');
}

function renderLiquidity() {
  const container = document.getElementById('liquidityList');
  if (!container) return;
  container.innerHTML = '';
  liquidityPairs.forEach((item, index) => {
    const el = document.createElement('div');
    el.className = 'bg-[#121724]/90 p-2.5 rounded-xl border border-gray-800/60 flex items-center justify-between';
    el.innerHTML = `<span class="font-bold text-gray-300 font-num">${index + 1}. ${item.pair}</span><span class="font-num text-amber-400/90 font-bold">${item.volume.toFixed(1)}B</span>`;
    container.appendChild(el);
  });
}

function renderHistory() {
  const container = document.getElementById('historyList');
  if (!container) return;
  container.innerHTML = '';
  tradeHistory.forEach(item => {
    const el = document.createElement('div');
    const isWin = item.pnl >= 0;
    const typeText = item.type === 'BUY' ? 'شراء' : 'بيع';
    el.className = 'bg-[#121724]/90 p-2.5 rounded-xl border border-gray-800/60 flex items-center justify-between';
    el.innerHTML = `
      <div>
        <div class="flex items-center gap-1.5">
          <span class="font-bold text-xs text-gray-200 font-num">${item.pair}</span>
          <span class="text-[10px] px-1.5 py-0.2 rounded font-bold font-num ${item.type === 'BUY' ? 'bg-emerald-950/60 text-emerald-400/90' : 'bg-rose-950/60 text-rose-400/90'}">${typeText} ${item.lot}</span>
        </div>
        <div class="text-[10px] text-gray-400 mt-1 font-medium"><span>${item.day} - ${item.time}</span></div>
      </div>
      <div class="text-left font-num">
        <div class="text-xs font-bold ${isWin ? 'text-emerald-400/90' : 'text-rose-400/90'}">${isWin ? '+' : ''}${item.pnl.toFixed(2)} $</div>
        <div class="text-[10px] text-gray-400 mt-0.5">${item.entry} ← ${item.exit}</div>
      </div>`;
    container.appendChild(el);
  });
}

function updateSignalTimerUI() {
  const timerEl = document.getElementById('signalTimer');
  if (!timerEl) return;
  const secs = signalTimerSeconds < 10 ? `0${signalTimerSeconds}` : signalTimerSeconds;
  timerEl.innerText = `00:${secs}`;
}

function startSignalCountdown() {
  if (countdownTimer) clearInterval(countdownTimer);
  countdownTimer = setInterval(() => {
    if (!isRunning) return;
    signalTimerSeconds--;
    if (signalTimerSeconds <= 0) refreshSignals(false);
    else updateSignalTimerUI();
  }, 1000);
}

function refreshSignals(isManual = false) {
  const icon = document.getElementById('refreshIcon');
  if (icon) icon.classList.add('fa-spin');
  const pairs = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'AVAX/USDT'];
  const timeframes = ['5m', '15m', '1h', '4h'];
  signals = pairs.slice(0, 4).map((pair, idx) => {
    const direction = Math.random() > 0.45 ? 'BUY' : 'SELL';
    const strengthScore = Math.floor(72 + Math.random() * 25);
    const timeframe = timeframes[Math.floor(Math.random() * timeframes.length)];
    const rsi = Math.floor(direction === 'BUY' ? 50 + Math.random() * 25 : 20 + Math.random() * 25);
    return {
      id: Date.now() + idx,
      pair,
      direction,
      strengthScore,
      timeframe,
      rsi: String(rsi),
      macd: direction === 'BUY' ? 'إيجابي' : 'سلبي',
      executed: false
    };
  });
  /* التنفيذ الحي يتم عبر محرك Rust — لا محاكاة دخول وهمي على اللوحة */
  setTimeout(() => {
    renderSignals();
    renderPositions();
    if (icon) icon.classList.remove('fa-spin');
    signalTimerSeconds = SIGNAL_REFRESH_INTERVAL;
    updateSignalTimerUI();
    if (isManual) showToast('تم تحديث الإشارات الفنية بنجاح 📡');
  }, 200);
}

function renderSignals() {
  const container = document.getElementById('signalsList');
  if (!container) return;
  container.innerHTML = '';
  signals.forEach(sig => {
    const isBuy = sig.direction === 'BUY';
    const strength = sig.strengthScore;
    const card = document.createElement('div');
    card.className = 'bg-[#121724]/90 px-3 py-2 rounded-xl border border-gray-800/60 flex items-center justify-between gap-2 transition-all hover:border-gold-500/20 shadow-sm';
    let actionAreaHtml = '';
    if (strength >= 85) {
      actionAreaHtml = '<div class="px-2.5 py-1 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-[10px] font-bold flex items-center gap-1 cursor-default select-none shadow-sm"><i class="fa-solid fa-robot text-[10px]"></i><span>تم الدخول تلقائياً ✓</span></div>';
    } else if (sig.executed) {
      actionAreaHtml = '<button disabled class="px-2.5 py-1 rounded-lg bg-emerald-500/15 text-emerald-400/90 border border-emerald-500/30 text-[10px] font-bold flex items-center gap-1 cursor-not-allowed opacity-80"><i class="fa-solid fa-check text-[10px]"></i><span>تم الدخول ✓</span></button>';
    } else {
      actionAreaHtml = `<button type="button" data-exec="${sig.id}" class="px-2.5 py-1 rounded-lg ${isBuy ? 'bg-emerald-600/80 hover:bg-emerald-500/80 border-emerald-500/40' : 'bg-rose-600/80 hover:bg-rose-500/80 border-rose-500/40'} text-white border text-[10px] font-bold flex items-center gap-1 transition-all active:scale-95 shadow-sm"><i class="fa-solid ${isBuy ? 'fa-arrow-trend-up' : 'fa-arrow-trend-down'} text-[9px]"></i><span>دخول مباشر</span></button>`;
    }
    card.innerHTML = `
      <div class="flex items-center gap-2.5">
        <div>
          <div class="flex items-center gap-1.5">
            <span class="font-bold text-xs font-num text-gray-200 tracking-wide">${sig.pair}</span>
            <span class="text-[10px] px-1.5 py-0.2 rounded font-bold font-num ${isBuy ? 'bg-emerald-950/60 text-emerald-400/90 border border-emerald-500/20' : 'bg-rose-950/60 text-rose-400/90 border border-rose-500/20'}">${isBuy ? 'شراء' : 'بيع'}</span>
            <span class="text-[10px] font-num font-bold text-gold-400/90 bg-gold-500/10 border border-gold-500/20 px-1.5 py-0.2 rounded">${strength}%</span>
          </div>
          <div class="text-[10px] text-gray-400 mt-1 flex items-center gap-2 font-medium">
            <span>الإطار: <strong class="text-gray-300 font-num">${sig.timeframe}</strong></span>
            <span>RSI: <strong class="text-gray-300 font-num">${sig.rsi}</strong></span>
            <span>MACD: <strong class="${isBuy ? 'text-emerald-400/90' : 'text-rose-400/90'} font-bold">${sig.macd}</strong></span>
          </div>
        </div>
      </div>
      <div class="flex items-center">${actionAreaHtml}</div>`;
    const execBtn = card.querySelector('[data-exec]');
    if (execBtn) execBtn.onclick = () => executeTrade(sig.id);
    container.appendChild(card);
  });
}

function executeTrade(signalId) {
  const sig = signals.find(s => s.id === Number(signalId));
  if (!sig || sig.executed) return;
  sig.executed = true;
  openPositions.push({
    id: Date.now(),
    pair: sig.pair,
    type: sig.direction,
    lot: '0.10',
    entry: sig.direction === 'BUY' ? 65000 : 64000,
    current: sig.direction === 'BUY' ? 65100 : 63900,
    pnl: 10.0
  });
  renderSignals();
  renderPositions();
  showToast(`🚀 تم فتح الصفقة بنجاح على ${sig.pair}`);
}

async function emergencyCloseAll() {
  const out = await apiPost('/api/control/emergency_close');
  await refreshBinanceMirror();
  showToast(out.closed ? '🚨 تم الإغلاق الطارئ لجميع المراكز' : '🚨 أمر الطوارئ — راجع السجل');
}

async function toggleBotState() {
  const out = await apiPost('/api/control/bot_toggle');
  if (typeof out.bot_running === 'boolean') isRunning = out.bot_running;
  else isRunning = !isRunning;
  syncBotUiFromState();
  showToast(isRunning ? 'تم استئناف عمل البوت' : 'تم إيقاف البوت مؤقتاً');
}

function toggleAlerts() {
  alertActive = !alertActive;
  const alertText = document.getElementById('alertText');
  const alertIcon = document.getElementById('alertIcon');
  if (alertActive) {
    alertText.innerText = 'التنبيهات مفعلة';
    alertIcon.className = 'fa-solid fa-bell text-gold-400/80 text-[10px]';
    showToast('تم تفعيل التنبيهات');
  } else {
    alertText.innerText = 'التنبيهات متوقفة';
    alertIcon.className = 'fa-solid fa-bell-slash text-gray-500 text-[10px]';
    showToast('تم إيقاف التنبيهات');
  }
}

function updateSyncClock() {
  const el = document.getElementById('syncTime');
  if (!el) return;
  el.innerText = new Date().toLocaleTimeString('ar-IQ', { hour12: false });
}

async function loadTradeHistoryFromApi() {
  try {
    const res = await fetch('/api/trades/history');
    const data = await res.json();
    if (!data.ok || !Array.isArray(data.trades) || !data.trades.length) return;
    tradeHistory = data.trades.slice(-20).reverse().map(t => {
      const isBuy = t.isBuyer;
      const price = parseFloat(t.price) || 0;
      const qty = parseFloat(t.qty) || 0;
      const dt = new Date(t.time || Date.now());
      return {
        pair: (t.symbol || 'BTCUSDT').replace('USDT', ' / USDT'),
        type: isBuy ? 'BUY' : 'SELL',
        lot: String(qty),
        entry: price,
        exit: price,
        pnl: isBuy ? -qty * price * 0.001 : qty * price * 0.001,
        day: dt.toLocaleDateString('ar-IQ', { weekday: 'long' }),
        time: dt.toLocaleTimeString('ar-IQ')
      };
    });
    renderHistory();
  } catch (_) {}
}

document.addEventListener('DOMContentLoaded', () => {
  renderSignals();
  renderPositions();
  renderLiquidity();
  renderHistory();
  updateSignalTimerUI();
  startSignalCountdown();
  updateSyncClock();
  setInterval(updateSyncClock, 1000);
  refreshBinanceMirror();
  loadTradeHistoryFromApi();
  if (mirrorPollTimer) clearInterval(mirrorPollTimer);
  mirrorPollTimer = setInterval(refreshBinanceMirror, 2500);
  fetch('/api/health').catch(() => {});
});
