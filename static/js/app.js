// ICT Daily Bias Dashboard — Main Application Logic

let biasData = null;
let activeSymbol = null;

async function fetchBias() {
    try {
        const resp = await fetch('/api/bias');
        const data = await resp.json();
        biasData = data;
        renderCards(data);
        document.getElementById('last-refresh').textContent = `Last: ${data.timestamp}`;
    } catch (e) {
        console.error('Failed to fetch bias data:', e);
    }
}

function renderCards(data) {
    const grid = document.getElementById('cards-grid');
    if (!data.instruments || data.instruments.length === 0) {
        grid.innerHTML = '<div class="loading">No data available. Waiting for market data...</div>';
        return;
    }

    grid.innerHTML = data.instruments.map(inst => {
        const biasClass = `bias-${inst.bias.toLowerCase()}`;
        const confColor = inst.bias === 'Bullish' ? '#3fb950' :
                          inst.bias === 'Bearish' ? '#f85149' : '#8b949e';
        const isActive = activeSymbol === inst.symbol ? ' active' : '';

        const factorRows = Object.entries(inst.factors || {}).map(([name, f]) => {
            const icon = f.signal === 'bullish' ? '&#9650;' :
                         f.signal === 'bearish' ? '&#9660;' : '&#8212;';
            const label = name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
            return `<div class="factor-row">
                <span class="factor-icon ${f.signal}">${icon}</span>
                <span>${label}</span>
            </div>`;
        }).join('');

        return `<div class="card${isActive}" onclick="openDetail('${inst.symbol}')">
            <div class="card-header">
                <span class="card-symbol">${inst.symbol}</span>
                <span class="bias-badge ${biasClass}">${inst.bias}</span>
            </div>
            <div class="card-confidence">
                <span class="confidence-label">Confidence: ${inst.confidence}%</span>
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width:${inst.confidence}%;background:${confColor}"></div>
                </div>
            </div>
            <div class="card-factors">${factorRows}</div>
        </div>`;
    }).join('');
}

async function openDetail(symbol) {
    activeSymbol = symbol;
    const panel = document.getElementById('detail-panel');
    panel.classList.remove('hidden');

    // Update header
    const inst = biasData.instruments.find(i => i.symbol === symbol);
    if (!inst) return;

    document.getElementById('detail-symbol').textContent = symbol;
    const badge = document.getElementById('detail-bias-badge');
    badge.textContent = `${inst.bias} ${inst.confidence}%`;
    badge.className = `bias-badge bias-${inst.bias.toLowerCase()}`;

    // Render factors table
    renderFactors(inst);
    renderKeyLevels(inst);

    // Re-render cards to update active state
    renderCards(biasData);

    // Load chart
    try {
        const resp = await fetch(`/api/chart/${encodeURIComponent(symbol)}`);
        const chartData = await resp.json();
        renderChart(chartData, inst);
    } catch (e) {
        console.error('Failed to load chart:', e);
    }

    // Scroll to detail panel
    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderFactors(inst) {
    const container = document.getElementById('factors-table');
    const rows = Object.entries(inst.factors || {}).map(([name, f]) => {
        const signalClass = f.signal === 'bullish' ? 'color:#3fb950' :
                            f.signal === 'bearish' ? 'color:#f85149' : 'color:#8b949e';
        const label = name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        const weight = (f.weight * 100).toFixed(0);
        return `<div class="factor-detail-row">
            <div>
                <div class="factor-name">${label} (${weight}%)</div>
                <div class="factor-detail">${f.detail || ''}</div>
            </div>
            <span class="factor-signal" style="${signalClass}">
                ${f.signal.toUpperCase()} (${(f.score * 100).toFixed(1)}%)
            </span>
        </div>`;
    }).join('');

    container.innerHTML = `<h3>Factor Breakdown</h3>
        <div>
            <div class="factor-detail-row" style="font-weight:600;">
                <span>Total Score</span>
                <span style="color:${inst.bias === 'Bullish' ? '#3fb950' : inst.bias === 'Bearish' ? '#f85149' : '#8b949e'}">
                    ${(inst.score * 100).toFixed(1)}%
                </span>
            </div>
            <div class="factor-detail-row">
                <span class="factor-name">Structure</span>
                <span>${inst.structure || 'N/A'}</span>
            </div>
            <div class="factor-detail-row">
                <span class="factor-name">Structure Break</span>
                <span>${inst.structure_break?.detail || 'None'}</span>
            </div>
            ${rows}
        </div>`;
}

function renderKeyLevels(inst) {
    const container = document.getElementById('key-levels');
    const kl = inst.key_levels || {};
    const fmt = (v) => v != null ? Number(v).toFixed(5) : 'N/A';

    let levelsHtml = `
        <div class="level-row"><span class="level-label">Current Price</span><span class="level-value">${fmt(kl.current_price)}</span></div>
        <div class="level-row"><span class="level-label">Prev Day High</span><span class="level-value">${fmt(kl.pdh)}</span></div>
        <div class="level-row"><span class="level-label">Prev Day Low</span><span class="level-value">${fmt(kl.pdl)}</span></div>
    `;

    if (kl.dol_target) {
        levelsHtml += `<div class="level-row">
            <span class="level-label">DOL Target (${kl.dol_target.label || ''})</span>
            <span class="level-value">${fmt(kl.dol_target.level)}</span>
        </div>`;
    }

    // Order blocks
    if (kl.order_blocks && kl.order_blocks.length > 0) {
        levelsHtml += '<div style="margin-top:10px;font-size:12px;color:#8b949e;font-weight:600;">Order Blocks</div>';
        kl.order_blocks.forEach(ob => {
            const color = ob.type === 'bullish' ? '#3fb950' : '#f85149';
            levelsHtml += `<div class="level-row">
                <span class="level-label" style="color:${color}">${ob.type.toUpperCase()} OB</span>
                <span class="level-value">${fmt(ob.top)} - ${fmt(ob.bottom)}</span>
            </div>`;
        });
    }

    // FVGs
    if (kl.fvgs && kl.fvgs.length > 0) {
        levelsHtml += '<div style="margin-top:10px;font-size:12px;color:#8b949e;font-weight:600;">Fair Value Gaps</div>';
        kl.fvgs.forEach(fvg => {
            const color = fvg.type === 'bullish' ? '#3fb950' : '#f85149';
            levelsHtml += `<div class="level-row">
                <span class="level-label" style="color:${color}">${fvg.type.toUpperCase()} FVG</span>
                <span class="level-value">${fmt(fvg.top)} - ${fmt(fvg.bottom)}</span>
            </div>`;
        });
    }

    container.innerHTML = `<h3>Key Levels</h3><div>${levelsHtml}</div>`;
}

function closeDetail() {
    activeSymbol = null;
    document.getElementById('detail-panel').classList.add('hidden');
    renderCards(biasData);
}

async function forceRefresh() {
    const btn = document.getElementById('refresh-btn');
    btn.classList.add('loading');
    btn.textContent = 'Refreshing...';
    try {
        await fetch('/api/refresh');
        await fetchBias();
        if (activeSymbol) {
            await openDetail(activeSymbol);
        }
    } catch (e) {
        console.error('Refresh failed:', e);
    } finally {
        btn.classList.remove('loading');
        btn.textContent = 'Refresh';
    }
}

// Initial load
fetchBias();

// Auto-refresh every 5 minutes
setInterval(fetchBias, 5 * 60 * 1000);
