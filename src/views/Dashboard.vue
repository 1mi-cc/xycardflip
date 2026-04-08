<template>
  <div class="dashboard-page">
    <section class="header-row">
      <div>
        <h1>System Dashboard</h1>
        <p>{{ generatedAt }}</p>
      </div>
      <div class="header-actions">
        <button
          v-for="item in headerTabs"
          :key="item.value"
          class="header-chip"
          :class="{ active: focusMode === item.value }"
          type="button"
          @click="focusMode = item.value"
        >
          {{ item.label }}
        </button>
        <n-button type="primary" :loading="loading" @click="loadOverview">刷新</n-button>
      </div>
    </section>

    <n-alert v-if="error" type="error" :show-icon="false">{{ error }}</n-alert>

    <section class="stats-grid">
      <article class="overview-card">
        <div class="card-head">
          <span class="card-label">近 7 天利润</span>
          <span class="card-chip" :class="profitTrend.tone">{{ profitTrend.label }}</span>
        </div>
        <div class="card-value">{{ formatMoney(last7d.realized_net_profit || 0) }}</div>
        <div class="mini-progress">
          <div class="mini-progress-track">
            <div class="mini-progress-fill" :style="{ width: percentWidth(profitability.profit_hit_rate || 0) }"></div>
          </div>
          <div class="mini-progress-meta">
            <span>利润命中率</span>
            <strong>{{ formatPercent(profitability.profit_hit_rate || 0) }}</strong>
          </div>
        </div>
      </article>

      <article class="metric-card">
        <div class="card-head">
          <span class="card-label">待审机会</span>
          <span class="card-chip neutral">处理中</span>
        </div>
        <div class="metric-value">{{ formatInteger(profitability.pending_review_count || 0) }}</div>
        <div class="metric-foot">{{ formatInteger(profitability.total_trade_count || 0) }} 笔累计交易</div>
      </article>

      <article class="metric-card">
        <div class="card-head">
          <span class="card-label">在途资金</span>
          <span class="card-chip warm">活跃</span>
        </div>
        <div class="metric-value">{{ formatMoney(inventory.deployed_capital || 0) }}</div>
        <div class="metric-foot">{{ formatInteger(profitability.active_trades_count || 0) }} 笔进行中</div>
      </article>

      <article class="metric-card">
        <div class="card-head">
          <span class="card-label">告警数量</span>
          <span class="card-chip" :class="alertCount > 0 ? 'danger' : 'positive'">
            {{ alertCount > 0 ? '关注' : '正常' }}
          </span>
        </div>
        <div class="metric-value">{{ formatInteger(alertCount) }}</div>
        <div class="metric-foot">{{ runtime.server_ready ? "服务在线" : "服务受限" }}</div>
      </article>
    </section>

    <section class="analytics-grid">
      <article class="panel chart-panel">
        <div class="panel-head">
          <div>
            <h2>Performance Trends</h2>
            <p>{{ focusDescription }}</p>
          </div>
          <div class="toggle-shell">
            <button
              v-for="item in chartToggles"
              :key="item.value"
              class="toggle-button"
              :class="{ active: chartMode === item.value }"
              type="button"
              @click="chartMode = item.value"
            >
              {{ item.label }}
            </button>
          </div>
        </div>

        <div class="bar-chart">
          <div v-for="item in chartItems" :key="item.label" class="bar-column">
            <div class="bar-box">
              <div class="bar-fill" :style="{ height: item.height }"></div>
            </div>
            <span>{{ item.short }}</span>
          </div>
        </div>
      </article>

      <article class="panel donut-panel">
        <div class="panel-head">
          <div>
            <h2>Revenue by Category</h2>
            <p>来源贡献</p>
          </div>
        </div>

        <div class="donut-wrap">
          <div class="donut-chart" :style="{ background: donutGradient }">
            <div class="donut-hole">
              <strong>{{ donutCenterValue }}</strong>
              <span>{{ donutCenterLabel }}</span>
            </div>
          </div>
        </div>

        <div class="legend-list">
          <div v-for="item in donutSlices" :key="item.label" class="legend-row">
            <div class="legend-left">
              <span class="legend-dot" :style="{ backgroundColor: item.color }"></span>
              <span>{{ item.label }}</span>
            </div>
            <strong>{{ item.percentText }}</strong>
          </div>
        </div>
      </article>
    </section>

    <section class="middle-grid">
      <article class="insight-card">
        <div class="insight-kicker">Focus</div>
        <h2>{{ focusHeadline }}</h2>
        <p>{{ focusStatement }}</p>
      </article>

      <article class="panel efficiency-panel">
        <div class="panel-head">
          <div>
            <h2>Efficiency</h2>
            <p>{{ baselineStatusText }}</p>
          </div>
          <span class="efficiency-badge">{{ operatingModeText }}</span>
        </div>

        <div class="efficiency-list">
          <div v-for="item in efficiencyItems" :key="item.label" class="efficiency-row">
            <div class="efficiency-meta">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
            <div class="mini-progress-track">
              <div class="mini-progress-fill" :style="{ width: item.progress }"></div>
            </div>
          </div>
        </div>
      </article>
    </section>

    <section class="bottom-grid">
      <article class="panel table-panel">
        <div class="panel-head">
          <div>
            <h2>Recent Activity</h2>
            <p>最新变化</p>
          </div>
          <button class="link-button" type="button" @click="focusMode = 'alert'">查看告警</button>
        </div>

        <div class="table-wrap">
          <table class="activity-table">
            <thead>
              <tr>
                <th>项目</th>
                <th>类别</th>
                <th>状态</th>
                <th>时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in recentRows" :key="`${row.type}-${row.name}`">
                <td>{{ row.name }}</td>
                <td>{{ row.type }}</td>
                <td>
                  <span class="status-pill" :class="row.tone">{{ row.status }}</span>
                </td>
                <td>{{ row.time }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="panel matrix-panel">
        <div class="panel-head">
          <div>
            <h2>Signal Matrix</h2>
            <p>运行密度</p>
          </div>
        </div>

        <div class="matrix-labels">
          <span v-for="item in matrixColumns" :key="item.short">{{ item.short }}</span>
        </div>
        <div class="matrix-grid">
          <template v-for="level in [4, 3, 2, 1]" :key="level">
            <div
              v-for="item in matrixColumns"
              :key="`${level}-${item.short}`"
              class="matrix-cell"
              :class="{ active: item.score >= level }"
            ></div>
          </template>
        </div>

        <div class="matrix-stats">
          <div class="matrix-stat">
            <span>活跃来源</span>
            <strong>{{ formatInteger(sourceLeaders.length) }}</strong>
          </div>
          <div class="matrix-stat">
            <span>活跃卖家</span>
            <strong>{{ formatInteger(sellerLeaders.length) }}</strong>
          </div>
          <div class="matrix-stat">
            <span>基线信号</span>
            <strong>{{ formatInteger(baselineSignals.length) }}</strong>
          </div>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

import useExecutiveOverview from "@/composables/useExecutiveOverview";

const {
  alertItems,
  baselineSignals,
  baselineStatusText,
  deploymentReadiness,
  error,
  lastLoadedAt,
  loadOverview,
  loading,
  operatingModeText,
  overview,
  profitCockpit,
  profitability,
  runtime,
  serviceSnapshot,
  validationBaseline,
  formatTime,
} = useExecutiveOverview();

const focusMode = ref("profit");
const chartMode = ref("units");

const headerTabs = [
  { label: "利润", value: "profit" },
  { label: "告警", value: "alert" },
  { label: "服务", value: "service" },
];

const chartToggles = [
  { label: "结构", value: "units" },
  { label: "风险", value: "risk" },
];

const today = computed(() => profitCockpit.value?.today || {});
const last7d = computed(() => profitCockpit.value?.last_7d || {});
const inventory = computed(() => profitCockpit.value?.inventory || {});
const generatedAt = computed(() => formatTime(overview.value?.generated_at));
const alertCount = computed(() => Number(alertItems.value.length || 0));
const runningServiceCount = computed(() => serviceSnapshot.value.filter(item => item.running).length);

const focusDescription = computed(() => {
  if (focusMode.value === "alert")
    return "告警和状态分布";
  if (focusMode.value === "service")
    return "服务和执行分布";
  return "利润和交易分布";
});

const focusHeadline = computed(() => {
  if (focusMode.value === "alert")
    return alertCount.value > 0 ? `${alertCount.value} 条告警待处理` : "当前没有活动告警";
  if (focusMode.value === "service")
    return runtime.value?.server_ready ? "后台服务正常" : "后台服务需要关注";
  return Number(last7d.value?.realized_net_profit || 0) > 0 ? "近 7 天利润为正" : "近 7 天利润还没起来";
});

const focusStatement = computed(() => {
  if (focusMode.value === "alert")
    return alertItems.value[0]?.message || "当前没有新的风险提示。";
  if (focusMode.value === "service")
    return runtime.value?.server_ready ? "核心服务在线。" : "服务状态需要关注。";
  return Number(last7d.value?.realized_net_profit || 0) > 0 ? "利润还在延续。" : "收益还没跑出来。";
});

const profitTrend = computed(() => {
  const profit = Number(last7d.value?.realized_net_profit || 0);
  if (profit > 0)
    return { label: "上行", tone: "positive" };
  if (profit < 0)
    return { label: "转弱", tone: "warning" };
  return { label: "持平", tone: "neutral" };
});

const chartItems = computed(() => {
  const base = chartMode.value === "risk"
    ? [
        { label: "告警", short: "警", value: Number(alertCount.value || 0) },
        { label: "待审", short: "待", value: Number(profitability.value?.pending_review_count || 0) },
        { label: "服务", short: "服", value: Math.max(4 - runningServiceCount.value, 0) },
        { label: "基线", short: "基", value: baselineSignals.value.length },
        { label: "进行", short: "进", value: Number(profitability.value?.active_trades_count || 0) },
        { label: "挂售", short: "挂", value: Number(inventory.value?.listed_trade_count || 0) },
        { label: "卖出", short: "卖", value: Number(profitability.value?.sold_count || 0) },
      ]
    : [
        { label: "待审", short: "待", value: Number(profitability.value?.pending_review_count || 0) },
        { label: "进行", short: "进", value: Number(profitability.value?.active_trades_count || 0) },
        { label: "卖出", short: "卖", value: Number(profitability.value?.sold_count || 0) },
        { label: "挂售", short: "挂", value: Number(inventory.value?.listed_trade_count || 0) },
        { label: "来源", short: "源", value: Number(sourceLeaders.value.length || 0) },
        { label: "卖家", short: "家", value: Number(sellerLeaders.value.length || 0) },
        { label: "服务", short: "服", value: Number(runningServiceCount.value || 0) },
      ];
  const maxValue = Math.max(...base.map(item => item.value), 1);
  return base.map(item => ({
    ...item,
    height: `${Math.max((item.value / maxValue) * 100, 14)}%`,
  }));
});

const sourceLeaders = computed(() =>
  (Array.isArray(profitCockpit.value?.source_leaderboard_7d) ? profitCockpit.value.source_leaderboard_7d : [])
    .slice(0, 3)
    .map(item => ({
      label: String(item.source || "未知来源"),
      value: Number(item.realized_net_profit || 0),
    })),
);

const sellerLeaders = computed(() =>
  (Array.isArray(profitCockpit.value?.seller_leaderboard_7d) ? profitCockpit.value.seller_leaderboard_7d : [])
    .slice(0, 3)
    .map(item => ({
      label: String(item.seller_id || "未知卖家"),
      value: Number(item.realized_net_profit || 0),
    })),
);

const donutSlices = computed(() => {
  const rows = sourceLeaders.value.length
    ? sourceLeaders.value
    : [
        { label: "来源 A", value: 1 },
        { label: "来源 B", value: 1 },
        { label: "来源 C", value: 1 },
      ];
  const total = rows.reduce((sum, item) => sum + Math.max(item.value, 0), 0) || 1;
  const colors = ["#0051d5", "#495c94", "#c64f0a"];
  return rows.map((item, index) => {
    const percent = (Math.max(item.value, 0) / total) * 100;
    return {
      ...item,
      color: colors[index % colors.length],
      percent,
      percentText: `${percent.toFixed(0)}%`,
    };
  });
});

const donutGradient = computed(() => {
  let cursor = 0;
  const segments = donutSlices.value.map((item) => {
    const start = cursor;
    const end = cursor + item.percent;
    cursor = end;
    return `${item.color} ${start}% ${end}%`;
  });
  return `conic-gradient(${segments.join(", ")})`;
});

const donutCenterValue = computed(() => formatMoney(last7d.value?.realized_net_profit || 0));
const donutCenterLabel = computed(() => "近 7 天");

const baselineBadge = computed(() => {
  if (validationBaseline.value?.ready_for_scale)
    return "可放量";
  if (validationBaseline.value?.ready_for_tune)
    return "可调优";
  return "观察中";
});

const efficiencyItems = computed(() => {
  const serviceRatio = serviceSnapshot.value.length
    ? runningServiceCount.value / serviceSnapshot.value.length
    : 0;
  const baselineRatio = validationBaseline.value?.ready_for_scale
    ? 1
    : validationBaseline.value?.ready_for_tune ? 0.65 : 0.3;

  return [
    {
      label: "利润命中率",
      value: formatPercent(profitability.value?.profit_hit_rate || 0),
      progress: percentWidth(profitability.value?.profit_hit_rate || 0),
    },
    {
      label: "服务在线率",
      value: `${runningServiceCount.value}/${serviceSnapshot.value.length}`,
      progress: percentWidth(serviceRatio),
    },
    {
      label: "基线完成度",
      value: baselineBadge.value,
      progress: percentWidth(baselineRatio),
    },
  ];
});

const summaryCards = computed(() => [
  {
    label: "今日利润",
    value: formatMoney(today.value?.realized_net_profit || 0),
    note: `今天成交 ${formatInteger(today.value?.sold_count || 0)} 笔`,
    tone: toneByNumber(today.value?.realized_net_profit || 0),
  },
  {
    label: "近 7 天利润",
    value: formatMoney(last7d.value?.realized_net_profit || 0),
    note: `平均 ROI ${formatPercent(last7d.value?.avg_realized_roi || 0)}`,
    tone: toneByNumber(last7d.value?.realized_net_profit || 0),
  },
  {
    label: "在途资金",
    value: formatMoney(inventory.value?.deployed_capital || 0),
    note: `还有 ${formatInteger(inventory.value?.active_trade_count || 0)} 笔在处理`,
    tone: "neutral",
  },
  {
    label: "告警数量",
    value: formatInteger(alertCount.value),
    note: runtime.value?.server_ready ? "服务在线" : "服务受限",
    tone: alertCount.value > 0 ? "warning" : "positive",
  },
]);

const profitabilityRows = computed(() => [
  { label: "累计毛利", value: formatMoney(profitability.value?.gross_profit || 0) },
  { label: "累计净利润", value: formatMoney(profitability.value?.realized_net_profit || 0) },
  { label: "利润命中率", value: formatPercent(profitability.value?.profit_hit_rate || 0) },
  { label: "平均持有天数", value: `${formatNumber(profitability.value?.avg_holding_days || 0, 1)} 天` },
  { label: "目标退出价值", value: formatMoney(inventory.value?.target_exit_value || 0) },
  { label: "预期退出价差", value: formatMoney(inventory.value?.expected_exit_spread || 0) },
]);

const runtimeRows = computed(() => {
  const services = runtime.value?.services || {};
  const automation = runtime.value?.automation || {};
  return [
    {
      label: "自动化总控",
      value: automation.all_running ? "运行中" : "部分运行",
      note: automation.busy ? "处理中" : "空闲",
      time: formatTime(automation.last_run_at),
      type: automation.all_running ? "success" : "warning",
    },
    {
      label: "市场监听",
      value: services.monitor?.is_running ? "运行中" : "已停止",
      note: services.monitor?.circuit_open ? "已熔断" : "正常",
      time: formatTime(services.monitor?.last_run_at),
      type: services.monitor?.is_running ? "success" : "default",
    },
    {
      label: "自动交易审批",
      value: services.autotrade?.running ? "运行中" : "已停止",
      note: `累计通过 ${formatInteger(services.autotrade?.total_approved || 0)} 笔`,
      time: formatTime(services.autotrade?.last_run_at),
      type: services.autotrade?.running ? "success" : "default",
    },
    {
      label: "执行重试",
      value: services.execution_retry?.running ? "运行中" : "已停止",
      note: `累计重试 ${formatInteger(services.execution_retry?.total_retried || 0)} 次`,
      time: formatTime(services.execution_retry?.last_run_at),
      type: services.execution_retry?.running ? "success" : "default",
    },
  ];
});

const recentRows = computed(() => {
  const rows = [];
  for (const item of alertItems.value.slice(0, 3)) {
    rows.push({
      name: item.title,
      type: "告警",
      status: severityText(item.effective_severity || item.severity),
      tone: severityTone(item.effective_severity || item.severity),
      time: generatedAt.value,
    });
  }
  for (const item of sourceLeaders.value) {
    rows.push({
      name: item.label,
      type: "来源",
      status: formatMoney(item.value),
      tone: "positive",
      time: generatedAt.value,
    });
  }
  for (const item of sellerLeaders.value) {
    rows.push({
      name: item.label,
      type: "卖家",
      status: formatMoney(item.value),
      tone: "neutral",
      time: generatedAt.value,
    });
  }
  return rows;
});

const matrixColumns = computed(() => {
  const countScale = (value) => {
    const numeric = Number(value || 0);
    if (numeric >= 10)
      return 4;
    if (numeric >= 5)
      return 3;
    if (numeric >= 1)
      return 2;
    return 1;
  };

  return [
    { short: "待", score: countScale(profitability.value?.pending_review_count) },
    { short: "进", score: countScale(profitability.value?.active_trades_count) },
    { short: "卖", score: countScale(profitability.value?.sold_count) },
    { short: "警", score: countScale(alertCount.value) },
    { short: "服", score: Math.max(runningServiceCount.value, 1) },
    { short: "基", score: validationBaseline.value?.ready_for_scale ? 4 : validationBaseline.value?.ready_for_tune ? 3 : 1 },
    { short: "源", score: countScale(sourceLeaders.value.length) },
  ];
});

const jumpToPanel = (panelId) => {
  document.getElementById(panelId)?.scrollIntoView({ behavior: "smooth", block: "start" });
};

const percentWidth = value => `${Math.max(Math.min(Number(value || 0) * 100, 100), 8)}%`;

const severityText = (severity) => {
  const value = String(severity || "").toLowerCase();
  if (value === "error")
    return "严重";
  if (value === "warning")
    return "预警";
  return "提示";
};

const severityType = (severity) => {
  const value = String(severity || "").toLowerCase();
  if (value === "error")
    return "error";
  if (value === "warning")
    return "warning";
  return "info";
};

const severityTone = (severity) => {
  const value = String(severity || "").toLowerCase();
  if (value === "error")
    return "danger";
  if (value === "warning")
    return "warning";
  return "positive";
};

const toneByNumber = value =>
  Number(value || 0) > 0 ? "positive" : Number(value || 0) < 0 ? "warning" : "neutral";
const formatMoney = value =>
  new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY", maximumFractionDigits: 2 }).format(Number(value || 0));
const formatPercent = value => `${formatNumber(Number(value || 0) * 100, 1)}%`;
const formatInteger = value =>
  new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(Number(value || 0));
const formatNumber = (value, digits = 2) =>
  new Intl.NumberFormat("zh-CN", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(value || 0));
</script>

<style scoped lang="scss">
.dashboard-page {
  display: grid;
  gap: 24px;
}

.header-row,
.stats-grid,
.analytics-grid,
.middle-grid,
.bottom-grid {
  display: grid;
  gap: 20px;
}

.header-row {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
}

.header-row h1 {
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 30px;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.header-row p {
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 13px;
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.header-chip {
  padding: 10px 16px;
  border: 1px solid var(--surface-line);
  border-radius: var(--radius-full);
  background: var(--surface-soft);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 800;
}

.header-chip.active {
  color: #fff;
  background: var(--primary-color);
  border-color: var(--primary-color);
}

.stats-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.analytics-grid {
  grid-template-columns: minmax(0, 2fr) minmax(300px, 1fr);
}

.middle-grid {
  grid-template-columns: minmax(0, 1.25fr) minmax(320px, 1fr);
}

.hero-card,
.metric-card,
.panel,
.insight-card,
.table-panel {
  border-radius: var(--radius-lg);
  background: var(--surface-card);
  border: 1px solid var(--surface-line);
  box-shadow: var(--shadow-medium);
}

.hero-card,
.metric-card,
.panel,
.insight-card,
.table-panel {
  padding: 24px;
}

.card-head,
.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 22px;
}

.card-label,
.section-label {
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.card-value,
.metric-value {
  margin: 14px 0 8px;
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 42px;
  font-weight: 800;
  letter-spacing: -0.05em;
}

.card-chip {
  padding: 6px 10px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.card-chip.positive {
  color: var(--success-color);
  background: rgba(22, 163, 74, 0.08);
}

.card-chip.warning,
.card-chip.warm {
  color: var(--warning-color);
  background: rgba(217, 119, 6, 0.08);
}

.card-chip.neutral {
  color: var(--text-secondary);
  background: var(--surface-soft);
}

.mini-progress {
  margin-top: 22px;
}

.mini-progress-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 13px;
}

.mini-progress-track {
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--surface-soft);
  overflow: hidden;
}

.mini-progress-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #306bf3, #0051d5);
}

.hero-foot {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  margin-top: 24px;
}

.foot-label {
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.foot-value {
  margin-top: 6px;
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 800;
}

.metric-foot {
  color: var(--text-secondary);
  font-size: 13px;
}

.toggle-shell {
  display: flex;
  gap: 6px;
  padding: 4px;
  border-radius: 12px;
  background: var(--surface-soft);
}

.toggle-button {
  padding: 7px 12px;
  border-radius: 10px;
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 800;
}

.toggle-button.active {
  color: var(--primary-color);
  background: #fff;
  box-shadow: var(--shadow-light);
}

.bar-chart {
  display: flex;
  align-items: end;
  gap: 10px;
  height: 260px;
}

.bar-column {
  display: grid;
  flex: 1;
  justify-items: center;
  gap: 10px;
}

.bar-box {
  display: flex;
  align-items: end;
  width: 100%;
  height: 220px;
  border-radius: 12px 12px 6px 6px;
  background: var(--surface-soft);
  overflow: hidden;
}

.bar-fill {
  width: 100%;
  border-radius: 12px 12px 0 0;
  background: linear-gradient(180deg, #4f7df6, #0051d5);
}

.bar-column span {
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.panel h2,
.card-head h2,
.panel-head h2 {
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 800;
}

.panel p,
.card-head p,
.panel-head p {
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 13px;
}

.donut-wrap {
  display: flex;
  justify-content: center;
  margin-bottom: 24px;
}

.donut-chart {
  width: 176px;
  height: 176px;
  padding: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.donut-hole {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: var(--surface-card);
  display: grid;
  place-items: center;
  text-align: center;
}

.donut-hole strong {
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 800;
}

.donut-hole span {
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.legend-list,
.efficiency-list,
.metric-list,
.service-list,
.alert-list {
  display: grid;
  gap: 12px;
}

.legend-row,
.efficiency-row,
.metric-row,
.service-row,
.alert-row {
  padding: 14px 16px;
  border: 1px solid var(--surface-line);
  border-radius: 12px;
  background: var(--surface-soft);
}

.legend-row,
.metric-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--text-secondary);
}

.legend-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex: 0 0 auto;
}

.efficiency-row,
.service-row,
.alert-row {
  display: grid;
  gap: 8px;
}

.efficiency-meta,
.service-side,
.alert-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.metric-row strong,
.legend-row strong,
.efficiency-meta strong,
.service-row strong,
.alert-row strong {
  color: var(--text-primary);
  font-weight: 800;
}

.insight-card {
  color: #fff;
  background: linear-gradient(135deg, #1f5fe2, #0051d5);
  border-color: transparent;
}

.insight-card .panel-head h2,
.insight-card .panel-head p,
.insight-card p,
.insight-card .link-button {
  color: #fff;
}

.insight-card p {
  max-width: 520px;
  font-size: 15px;
  line-height: 1.8;
}

.link-button {
  color: var(--primary-color);
  font-size: 13px;
  font-weight: 800;
}

.efficiency-badge {
  padding: 6px 10px;
  border-radius: var(--radius-full);
  background: var(--surface-soft);
  color: var(--primary-color);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.table-wrap {
  overflow-x: auto;
}

.activity-table {
  width: 100%;
  border-collapse: collapse;
}

.activity-table th,
.activity-table td {
  padding: 16px 8px;
  text-align: left;
}

.activity-table thead th {
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  border-bottom: 1px solid var(--surface-line);
}

.activity-table tbody tr + tr td {
  border-top: 1px solid rgba(195, 198, 215, 0.35);
}

.activity-table tbody td {
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 600;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.status-pill.positive {
  color: var(--success-color);
  background: rgba(22, 163, 74, 0.08);
}

.status-pill.warning {
  color: var(--warning-color);
  background: rgba(217, 119, 6, 0.08);
}

.status-pill.danger {
  color: var(--error-color);
  background: rgba(220, 38, 38, 0.08);
}

.matrix-labels {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 10px;
}

.matrix-labels span {
  text-align: center;
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.matrix-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 8px;
}

.matrix-cell {
  height: 32px;
  border-radius: 8px;
  background: rgba(0, 81, 213, 0.06);
}

.matrix-cell.active {
  background: linear-gradient(180deg, rgba(79, 125, 246, 0.65), rgba(0, 81, 213, 0.95));
}

.matrix-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 20px;
}

.matrix-stat span {
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.matrix-stat strong {
  display: block;
  margin-top: 6px;
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 800;
}

@media (max-width: 1200px) {
  .header-row,
  .stats-grid,
  .analytics-grid,
  .middle-grid,
  .panel-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .header-row {
    grid-template-columns: 1fr;
  }

  .hero-card,
  .metric-card,
  .panel,
  .insight-card,
  .table-panel {
    padding: 20px;
  }

  .header-actions {
    flex-wrap: wrap;
  }

  .hero-value,
  .card-value,
  .metric-value {
    font-size: 36px;
  }

  .bar-chart {
    gap: 8px;
  }

  .summary-grid,
  .matrix-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .summary-grid,
  .matrix-stats {
    grid-template-columns: 1fr;
  }
}
</style>
