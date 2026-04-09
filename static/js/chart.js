// TradingView Lightweight Charts integration with ICT overlays

let chartInstance = null;
let candleSeries = null;

function renderChart(chartData, biasResult) {
    const container = document.getElementById('chart-container');
    container.innerHTML = '';

    if (!chartData.candles || chartData.candles.length === 0) {
        container.innerHTML = '<div style="padding:40px;text-align:center;color:#8b949e;">No chart data available</div>';
        return;
    }

    // Create chart
    chartInstance = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: 400,
        layout: {
            background: { color: '#0d1117' },
            textColor: '#8b949e',
        },
        grid: {
            vertLines: { color: '#1c2128' },
            horzLines: { color: '#1c2128' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
        rightPriceScale: {
            borderColor: '#30363d',
        },
        timeScale: {
            borderColor: '#30363d',
            timeVisible: false,
        },
    });

    // Add candlestick series
    candleSeries = chartInstance.addCandlestickSeries({
        upColor: '#3fb950',
        downColor: '#f85149',
        borderUpColor: '#3fb950',
        borderDownColor: '#f85149',
        wickUpColor: '#3fb950',
        wickDownColor: '#f85149',
    });

    candleSeries.setData(chartData.candles);

    // Add PDH/PDL lines
    const kl = chartData.key_levels || {};
    const pricelines = [];

    if (kl.pdh != null) {
        pricelines.push(candleSeries.createPriceLine({
            price: kl.pdh,
            color: '#58a6ff',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: true,
            title: 'PDH',
        }));
    }

    if (kl.pdl != null) {
        pricelines.push(candleSeries.createPriceLine({
            price: kl.pdl,
            color: '#58a6ff',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: true,
            title: 'PDL',
        }));
    }

    // Add DOL target line
    if (kl.dol_target && kl.dol_target.level) {
        candleSeries.createPriceLine({
            price: kl.dol_target.level,
            color: '#d29922',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dotted,
            axisLabelVisible: true,
            title: 'DOL',
        });
    }

    // Add order block zones as price lines (top and bottom)
    if (kl.order_blocks) {
        kl.order_blocks.forEach(ob => {
            const color = ob.type === 'bullish' ? 'rgba(63,185,80,0.4)' : 'rgba(248,81,73,0.4)';
            candleSeries.createPriceLine({
                price: ob.top,
                color: color,
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Solid,
                axisLabelVisible: false,
                title: '',
            });
            candleSeries.createPriceLine({
                price: ob.bottom,
                color: color,
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Solid,
                axisLabelVisible: false,
                title: '',
            });
        });
    }

    // Add FVG zones
    if (kl.fvgs) {
        kl.fvgs.forEach(fvg => {
            const color = fvg.type === 'bullish' ? 'rgba(63,185,80,0.25)' : 'rgba(248,81,73,0.25)';
            candleSeries.createPriceLine({
                price: fvg.top,
                color: color,
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dotted,
                axisLabelVisible: false,
                title: '',
            });
            candleSeries.createPriceLine({
                price: fvg.bottom,
                color: color,
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dotted,
                axisLabelVisible: false,
                title: '',
            });
        });
    }

    // Add swing point markers
    const markers = [];

    if (chartData.swing_highs) {
        chartData.swing_highs.forEach(sh => {
            const ts = parseTimestamp(sh.time);
            if (ts) {
                markers.push({
                    time: ts,
                    position: 'aboveBar',
                    color: '#f85149',
                    shape: 'arrowDown',
                    text: 'SH',
                });
            }
        });
    }

    if (chartData.swing_lows) {
        chartData.swing_lows.forEach(sl => {
            const ts = parseTimestamp(sl.time);
            if (ts) {
                markers.push({
                    time: ts,
                    position: 'belowBar',
                    color: '#3fb950',
                    shape: 'arrowUp',
                    text: 'SL',
                });
            }
        });
    }

    if (markers.length > 0) {
        markers.sort((a, b) => a.time - b.time);
        candleSeries.setMarkers(markers);
    }

    // Fit content
    chartInstance.timeScale().fitContent();

    // Handle resize
    const resizeObserver = new ResizeObserver(() => {
        if (chartInstance) {
            chartInstance.applyOptions({ width: container.clientWidth });
        }
    });
    resizeObserver.observe(container);
}

function parseTimestamp(timeStr) {
    if (!timeStr) return null;
    const d = new Date(timeStr);
    if (isNaN(d.getTime())) return null;
    // Convert to UTC date for daily chart
    return Math.floor(d.getTime() / 1000);
}
