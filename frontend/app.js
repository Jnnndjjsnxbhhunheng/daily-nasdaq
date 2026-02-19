const strategyNames = {
  ma250_drawdown: "MA250 回撤定投",
  ma200_drawdown: "MA200 回撤定投",
  ma150_drawdown: "MA150 回撤定投",
  ma_cross_sell: "MA200 金叉死叉",
  macd_weekly: "周线 MACD 趋势",
  discount_dca: "折扣 DCA",
  market_breadth_dca: "市场宽度 DCA",
  rsi_reversion: "RSI 均值回归",
  plain_dca: "普通定投",
  etf_dca_dip_buy: "双 ETF 跌买",
};

const palette = [
  "#38bdf8",
  "#f97316",
  "#22c55e",
  "#a78bfa",
  "#facc15",
  "#14b8a6",
  "#ef4444",
  "#2dd4bf",
  "#fb7185",
  "#60a5fa",
];

const state = {
  payload: null,
  selected: null,
  source: "",
  charts: {
    yearly: null,
    totalReturn: null,
    trailingXirr: null,
  },
  visibleStrategies: new Set(),
  colorMap: new Map(),
};

const els = {
  strategyList: document.getElementById("strategyList"),
  metricCards: document.getElementById("metricCards"),
  yearlyTitle: document.getElementById("yearlyTitle"),
  yearlyTableBody: document.querySelector("#yearlyTable tbody"),
  status: document.getElementById("status"),
  metaInfo: document.getElementById("metaInfo"),
  showAllBtn: document.getElementById("showAllBtn"),
  hideAllBtn: document.getElementById("hideAllBtn"),
  visibleHint: document.getElementById("visibleHint"),
};

function pct(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "N/A";
  }
  return `${(value * 100).toFixed(digits)}%`;
}

function money(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "N/A";
  }
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function alphaColor(hexColor, alpha) {
  const hex = hexColor.replace("#", "");
  const bigint = parseInt(hex, 16);
  const red = (bigint >> 16) & 255;
  const green = (bigint >> 8) & 255;
  const blue = bigint & 255;
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function setStatus(message) {
  if (els.status) {
    els.status.textContent = message;
  }
}

async function loadPayload() {
  const dataCandidates = [
    "./data/backtest_dashboard.json",
    "./data/backtest_dashboard.sample.json",
  ];
  const errors = [];

  for (const file of dataCandidates) {
    try {
      const resp = await fetch(file, { cache: "no-store" });
      if (!resp.ok) {
        errors.push(`${file}: ${resp.status}`);
        continue;
      }
      const payload = await resp.json();
      return { payload, source: file };
    } catch (error) {
      errors.push(`${file}: ${error}`);
    }
  }

  throw new Error(errors.join(" | "));
}

function sortedStrategies(payload) {
  return [...payload.strategies].sort((a, b) => b.total_return - a.total_return);
}

function visibleStrategiesArray() {
  if (!state.payload) {
    return [];
  }
  return state.payload.strategies.filter((item) => state.visibleStrategies.has(item.strategy));
}

function sortedVisibleStrategies() {
  return [...visibleStrategiesArray()].sort((a, b) => b.total_return - a.total_return);
}

function colorForStrategy(strategyKey) {
  return state.colorMap.get(strategyKey) || palette[0];
}

function ensureSelectedValid() {
  if (!state.payload) {
    return;
  }
  const exists = state.payload.strategies.some((item) => item.strategy === state.selected);
  if (!exists) {
    const fallback = sortedStrategies(state.payload)[0];
    state.selected = fallback ? fallback.strategy : null;
  }

  if (state.selected && !state.visibleStrategies.has(state.selected)) {
    const fallbackVisible = sortedVisibleStrategies()[0];
    if (fallbackVisible) {
      state.selected = fallbackVisible.strategy;
    }
  }
}

function toggleStrategyVisibility(strategyKey, checked) {
  if (checked) {
    state.visibleStrategies.add(strategyKey);
    return true;
  }

  if (state.visibleStrategies.size <= 1) {
    setStatus("至少保留一个策略显示在图表中");
    return false;
  }

  state.visibleStrategies.delete(strategyKey);
  if (strategyKey === state.selected) {
    const fallback = sortedVisibleStrategies()[0];
    if (fallback) {
      state.selected = fallback.strategy;
    }
  }
  return true;
}

function renderVisibleHint() {
  if (!state.payload || !els.visibleHint) {
    return;
  }
  els.visibleHint.textContent = `图表显示：${state.visibleStrategies.size} / ${state.payload.strategies.length}`;
}

function renderStrategyList() {
  const strategies = sortedStrategies(state.payload);
  els.strategyList.innerHTML = "";

  for (const strategy of strategies) {
    const isVisible = state.visibleStrategies.has(strategy.strategy);

    const row = document.createElement("div");
    row.className = "strategy-item";
    row.tabIndex = 0;
    row.setAttribute("role", "button");
    if (strategy.strategy === state.selected) {
      row.classList.add("active");
    }

    row.innerHTML = `
      <div class="strategy-head">
        <label class="strategy-toggle-wrap">
          <input class="strategy-toggle" type="checkbox" ${isVisible ? "checked" : ""} />
          <span>显示</span>
        </label>
        <span class="strategy-name">${strategyNames[strategy.strategy] || strategy.strategy}</span>
      </div>
      <div class="strategy-brief">
        <span>总收益率</span>
        <span>${pct(strategy.total_return)}</span>
      </div>
      <div class="strategy-brief">
        <span>全周期年化</span>
        <span>${pct(strategy.full_period_xirr)}</span>
      </div>
    `;

    const toggleInput = row.querySelector(".strategy-toggle");
    toggleInput.addEventListener("click", (event) => {
      event.stopPropagation();
    });
    toggleInput.addEventListener("change", (event) => {
      event.stopPropagation();
      const ok = toggleStrategyVisibility(strategy.strategy, toggleInput.checked);
      if (!ok) {
        toggleInput.checked = true;
        return;
      }
      renderAll();
    });

    row.addEventListener("click", () => {
      state.selected = strategy.strategy;
      state.visibleStrategies.add(strategy.strategy);
      renderAll();
    });

    row.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") {
        return;
      }
      event.preventDefault();
      state.selected = strategy.strategy;
      state.visibleStrategies.add(strategy.strategy);
      renderAll();
    });

    els.strategyList.appendChild(row);
  }

  renderVisibleHint();
}

function metricCell(label, value, cls = "") {
  return `
    <div class="metric">
      <div class="metric-label">${label}</div>
      <div class="metric-value ${cls}">${value}</div>
    </div>
  `;
}

function renderMetrics() {
  const strategy = state.payload.strategies.find((item) => item.strategy === state.selected);
  if (!strategy) {
    els.metricCards.innerHTML = "";
    return;
  }

  const totalReturnClass = strategy.total_return >= 0 ? "good" : "bad";
  const fullXirrClass = (strategy.full_period_xirr ?? 0) >= 0 ? "good" : "bad";
  const trailingClass = (strategy.trailing_3y_xirr ?? 0) >= 0 ? "good" : "bad";

  els.metricCards.innerHTML = [
    metricCell("策略", strategyNames[strategy.strategy] || strategy.strategy),
    metricCell("回测区间", `${strategy.start} ~ ${strategy.end}`),
    metricCell("标的", strategy.symbol),
    metricCell("总投入", money(strategy.total_invested)),
    metricCell("期末资产", money(strategy.final_value)),
    metricCell("收益倍数", `${strategy.multiple.toFixed(2)}x`, totalReturnClass),
    metricCell("总收益率", pct(strategy.total_return), totalReturnClass),
    metricCell("全周期年化", pct(strategy.full_period_xirr), fullXirrClass),
    metricCell("近3年年化", pct(strategy.trailing_3y_xirr), trailingClass),
  ].join("");
}

function getAllYears(strategies) {
  const yearSet = new Set();
  for (const strategy of strategies) {
    Object.keys(strategy.yearly_xirr || {}).forEach((year) => yearSet.add(Number(year)));
  }
  return [...yearSet].sort((a, b) => a - b);
}

function buildYearlyDatasets(strategies, years, selectedKey) {
  return strategies.map((strategy) => {
    const baseColor = colorForStrategy(strategy.strategy);
    const isSelected = strategy.strategy === selectedKey;
    const data = years.map((year) => {
      const value = strategy.yearly_xirr?.[String(year)];
      return value === null || value === undefined ? null : value * 100;
    });

    return {
      label: strategyNames[strategy.strategy] || strategy.strategy,
      data,
      borderColor: alphaColor(baseColor, isSelected ? 0.95 : 0.30),
      pointBackgroundColor: alphaColor(baseColor, isSelected ? 0.95 : 0.38),
      borderWidth: isSelected ? 3.4 : 1.8,
      pointRadius: isSelected ? 3.6 : 2,
      pointHoverRadius: isSelected ? 6 : 4,
      spanGaps: true,
      tension: 0.25,
      fill: false,
    };
  });
}

function renderYearlyChart() {
  const visible = visibleStrategiesArray();
  const years = getAllYears(visible);
  const datasets = buildYearlyDatasets(visible, years, state.selected);
  const chartEl = document.getElementById("xirrChart");

  if (!state.charts.yearly) {
    state.charts.yearly = new Chart(chartEl, {
      type: "line",
      data: {
        labels: years,
        datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "nearest",
          intersect: false,
        },
        plugins: {
          legend: {
            labels: {
              color: "#dbeafe",
              boxWidth: 12,
            },
          },
          tooltip: {
            callbacks: {
              label(ctx) {
                const value = ctx.parsed.y;
                if (value === null || value === undefined || Number.isNaN(value)) {
                  return `${ctx.dataset.label}: N/A`;
                }
                return `${ctx.dataset.label}: ${value.toFixed(2)}%`;
              },
            },
          },
        },
        scales: {
          x: {
            ticks: { color: "#9fb0ce" },
            grid: { color: "rgba(159, 176, 206, 0.15)" },
          },
          y: {
            ticks: {
              color: "#9fb0ce",
              callback: (value) => `${value}%`,
            },
            grid: { color: "rgba(159, 176, 206, 0.15)" },
          },
        },
      },
    });
    return;
  }

  state.charts.yearly.data.labels = years;
  state.charts.yearly.data.datasets = datasets;
  state.charts.yearly.update();
}

function renderTotalReturnChart() {
  const visible = sortedVisibleStrategies();
  const labels = visible.map((item) => strategyNames[item.strategy] || item.strategy);
  const values = visible.map((item) => item.total_return * 100);
  const backgroundColors = visible.map((item) =>
    alphaColor(colorForStrategy(item.strategy), item.strategy === state.selected ? 0.86 : 0.46)
  );
  const borderColors = visible.map((item) =>
    alphaColor(colorForStrategy(item.strategy), item.strategy === state.selected ? 1 : 0.72)
  );

  const chartEl = document.getElementById("totalReturnChart");
  if (!state.charts.totalReturn) {
    state.charts.totalReturn = new Chart(chartEl, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "总收益率",
            data: values,
            backgroundColor: backgroundColors,
            borderColor: borderColors,
            borderWidth: 1.4,
            borderRadius: 8,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label(ctx) {
                return `总收益率: ${ctx.parsed.y.toFixed(2)}%`;
              },
            },
          },
        },
        scales: {
          x: {
            ticks: { color: "#9fb0ce", maxRotation: 45, minRotation: 0 },
            grid: { color: "rgba(159, 176, 206, 0.1)" },
          },
          y: {
            ticks: {
              color: "#9fb0ce",
              callback: (value) => `${value}%`,
            },
            grid: { color: "rgba(159, 176, 206, 0.15)" },
          },
        },
      },
    });
    return;
  }

  state.charts.totalReturn.data.labels = labels;
  state.charts.totalReturn.data.datasets[0].data = values;
  state.charts.totalReturn.data.datasets[0].backgroundColor = backgroundColors;
  state.charts.totalReturn.data.datasets[0].borderColor = borderColors;
  state.charts.totalReturn.update();
}

function renderTrailingChart() {
  const visible = sortedVisibleStrategies();
  const labels = visible.map((item) => strategyNames[item.strategy] || item.strategy);
  const values = visible.map((item) =>
    item.trailing_3y_xirr === null || item.trailing_3y_xirr === undefined ? null : item.trailing_3y_xirr * 100
  );
  const backgroundColors = visible.map((item) =>
    alphaColor(colorForStrategy(item.strategy), item.strategy === state.selected ? 0.86 : 0.46)
  );
  const borderColors = visible.map((item) =>
    alphaColor(colorForStrategy(item.strategy), item.strategy === state.selected ? 1 : 0.72)
  );

  const chartEl = document.getElementById("trailingXirrChart");
  if (!state.charts.trailingXirr) {
    state.charts.trailingXirr = new Chart(chartEl, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "近三年 XIRR",
            data: values,
            backgroundColor: backgroundColors,
            borderColor: borderColors,
            borderWidth: 1.4,
            borderRadius: 8,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label(ctx) {
                const value = ctx.parsed.y;
                if (value === null || value === undefined || Number.isNaN(value)) {
                  return "近三年 XIRR: N/A";
                }
                return `近三年 XIRR: ${value.toFixed(2)}%`;
              },
            },
          },
        },
        scales: {
          x: {
            ticks: { color: "#9fb0ce", maxRotation: 45, minRotation: 0 },
            grid: { color: "rgba(159, 176, 206, 0.1)" },
          },
          y: {
            ticks: {
              color: "#9fb0ce",
              callback: (value) => `${value}%`,
            },
            grid: { color: "rgba(159, 176, 206, 0.15)" },
          },
        },
      },
    });
    return;
  }

  state.charts.trailingXirr.data.labels = labels;
  state.charts.trailingXirr.data.datasets[0].data = values;
  state.charts.trailingXirr.data.datasets[0].backgroundColor = backgroundColors;
  state.charts.trailingXirr.data.datasets[0].borderColor = borderColors;
  state.charts.trailingXirr.update();
}

function renderYearlyTable() {
  const strategy = state.payload.strategies.find((item) => item.strategy === state.selected);
  if (!strategy) {
    els.yearlyTableBody.innerHTML = "";
    return;
  }

  els.yearlyTitle.textContent = `${strategyNames[strategy.strategy] || strategy.strategy} - 年度收益明细`;

  const years = Object.keys(strategy.yearly_xirr)
    .map((item) => Number(item))
    .sort((a, b) => a - b);

  els.yearlyTableBody.innerHTML = years
    .map((year) => {
      const value = strategy.yearly_xirr[String(year)];
      const className = value === null ? "neutral" : value >= 0 ? "good" : "bad";
      return `
        <tr>
          <td>${year}</td>
          <td class="${className}">${pct(value)}</td>
        </tr>
      `;
    })
    .join("");
}

function renderMeta() {
  els.metaInfo.textContent = `生成时间：${state.payload.generated_at} ｜ 样本数：${state.payload.count}`;
  renderVisibleHint();
  setStatus(`已加载数据源：${state.source} ｜ 图表显示 ${state.visibleStrategies.size}/${state.payload.strategies.length}`);
}

function renderAll() {
  ensureSelectedValid();
  renderMeta();
  renderStrategyList();
  renderMetrics();
  renderYearlyChart();
  renderTotalReturnChart();
  renderTrailingChart();
  renderYearlyTable();
}

function bindPanelActions() {
  if (els.showAllBtn) {
    els.showAllBtn.addEventListener("click", () => {
      state.visibleStrategies = new Set(state.payload.strategies.map((item) => item.strategy));
      renderAll();
    });
  }

  if (els.hideAllBtn) {
    els.hideAllBtn.addEventListener("click", () => {
      if (state.selected) {
        state.visibleStrategies = new Set([state.selected]);
      }
      renderAll();
    });
  }
}

async function init() {
  try {
    const { payload, source } = await loadPayload();
    if (!payload || !Array.isArray(payload.strategies) || payload.strategies.length === 0) {
      throw new Error("JSON 数据为空或格式错误");
    }

    state.payload = payload;
    state.source = source;
    state.selected = sortedStrategies(payload)[0].strategy;
    state.visibleStrategies = new Set(payload.strategies.map((item) => item.strategy));
    state.colorMap = new Map(payload.strategies.map((item, idx) => [item.strategy, palette[idx % palette.length]]));

    bindPanelActions();
    renderAll();
  } catch (error) {
    console.error(error);
    setStatus(
      "加载数据失败。请先运行回测生成 JSON：python -m backtest.run_backtest --strategy all --json-out frontend/data/backtest_dashboard.json"
    );
    els.metaInfo.textContent = "数据未加载";
  }
}

init();
