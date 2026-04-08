<template>
  <div class="dashboard-page">
    <section class="top-section">
      <article class="hero-card">
        <div class="section-kicker">本周利润</div>
        <div class="hero-value">{{ formatMoney(last7d.realized_net_profit || 0) }}</div>
        <div class="hero-trend" :class="profitTrend.tone">
          <span>{{ profitTrend.label }}</span>
        </div>

        <div class="hero-progress">
          <div class="hero-progress-meta">
            <span>利润命中率</span>
            <strong>{{ formatPercent(profitability.profit_hit_rate || 0) }}</strong>
          </div>
          <div class="progress-track">
            <div class="progress-fill" :style="{ width: percentWidth(profitability.profit_hit_rate || 0) }"></div>
          </div>
        </div>

        <div class="hero-foot">
          <div>
            <div class="foot-label">已卖出</div>
            <div class="foot-value">{{ formatInteger(profitability.sold_count || 0) }}</div>
          </div>
          <div>
            <div class="foot-label">在途资金</div>
            <div class="foot-value">{{ formatMoney(inventory.deployed_capital || 0) }}</div>
          </div>
        </div>
      </article>

      <article class="chart-card">
        <div class="card-head">
          <div>
            <h3>经营分布</h3>
            <p>当前业务结构</p>
          </div>
          <button class="ghost-chip" type="button" @click="focusMode = nextFocusMode">
            {{ focusModeLabel }}
          </button>
        </div>

        <div class="bar-chart">
          <div v-for="item in chartItems" :key="item.label" class="bar-group">
            <div class="bar-track">
              <div class="bar-fill" :style="{ height: item.height }"></div>
            </div>
            <div class="bar-label">{{ item.short }}</div>
          </div>
        </div>
      </article>
    </section>

    <section class="middle-section">
      <article class="insight-card">
        <div class="card-head card-head-light">
          <div class="title-with-icon">
            <span class="panel-icon">✦</span>
            <h3>核心判断</h3>
          </div>
        </div>
        <p>{{ insightText }}</p>
        <button class="insight-button" type="button" @click="jumpToPanel(insightPanel)">
          查看详情
        </button>
      </article>

      <article class="efficiency-card">
        <div class="card-head">
          <div class="title-with-icon">
            <span class="panel-icon warm">↗</span>
            <h3>效率</h3>
          </div>
          <span class="status-chip">{{ baselineBadge }}</span>
        </div>

        <div class="efficiency-list">
          <div v-for="item in efficiencyItems" :key="item.label" class="efficiency-row">
            <div class="efficiency-meta">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
            <div class="progress-track subtle">
              <div class="progress-fill" :style="{ width: item.progress }"></div>
            </div>
          </div>
        </div>
      </article>
    </section>

    <section class="summary-grid">
      <article v-for="card in summaryCards" :key="card.label" class="summary-card">
        <div class="summary-label">{{ card.label }}</div>
        <div class="summary-value">{{ card.value }}</div>
        <div class="summary-note" :class="card.tone">{{ card.note }}</div>
      </article>
    </section>

    <section class="panel-grid">
      <article id="profit-panel" class="panel">
        <div class="panel-header">
          <div>
            <div class="section-label">收益</div>
            <h3>收益与库存</h3>
          </div>
          <span class="panel-meta">{{ generatedAt }}</span>
        </div>
        <div class="metric-list">
          <div v-for="item in profitabilityRows" :key="item.label" class="metric-row">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </article>

      <article id="service-panel" class="panel">
        <div class="panel-header">
          <div>
            <div class="section-label">服务</div>
            <h3>后台服务</h3>
          </div>
        </div>
        <div class="service-list">
          <div v-for="item in runtimeRows" :key="item.label" class="service-row">
            <div>
              <strong>{{ item.label }}</strong>
              <div class="service-note">{{ item.note }}</div>
            </div>
            <div class="service-side">
              <n-tag size="small" :type="item.type">{{ item.value }}</n-tag>
              <span class="service-time">{{ item.time }}</span>
            </div>
          </div>
        </div>
      </article>
    </section>

    <section class="bottom-section">
      <article id="activity-panel" class="table-card">
        <div class="card-head">
          <h3>最近动态</h3>
          <button class="ghost-link" type="button" @click="jumpToPanel('alert-panel')">查看告警</button>
        </div>

        <div class="table-wrap">
          <table class="event-table">
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
                  <span class="table-status" :class="row.tone">{{ row.status }}</span>
                </td>
                <td>{{ row.time }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </section>

    <n-alert v-if="error" type="error" :show-icon="false">{{ error }}</n-alert>
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

const focusMode = ref("pipeline");
const focusModes = ["pipeline", "alerts", "service"];

const today = computed(() => profitCockpit.value?.today || {});
const last7d = computed(() => profitCockpit.value?.last_7d || {});
const inventory = computed(() => profitCockpit.value?.inventory || {});
const generatedAt = computed(() => formatTime(overview.value?.generated_at));
const alertCount = computed(() => Number(alertItems.value.length || 0));
const runningServiceCount = computed(() => serviceSnapshot.value.filter(item => item.running).length);
const nextFocusMode = computed(() => {
  const currentIndex = focusModes.indexOf(focusMode.value);
  return focusModes[(currentIndex + 1) % focusModes.length];
});
const focusModeLabel = computed(() => ({
  pipeline: "看告警",
  alerts: "看服务",
  service: "看分布",
})[focusMode.value] || "切换");

const profitTrend = computed(() => {
  const profit = Number(last7d.value?.realized_net_profit || 0);
  if (profit > 0)
    return { label: "利润为正", tone: "positive" };
  if (profit < 0)
    return { label: "利润转弱", tone: "warning" };
  return { label: "利润持平", tone: "neutral" };
});

const chartItems = computed(() => {
  const base = [
    { label: "待审", short: "待审", value: Number(profitability.value?.pending_review_count || 0) },
    { label: "进行中", short: "进行", value: Number(profitability.value?.active_trades_count || 0) },
    { label: "卖出", short: "卖出", value: Number(profitability.value?.sold_count || 0) },
    { label: "挂售", short: "挂售", value: Number(inventory.value?.listed_trade_count || 0) },
    { label: "告警", short: "告警", value: Number(alertCount.value || 0) },
    { label: "服务", short: "服务", value: Number(runningServiceCount.value || 0) },
    { label: "基线", short: "基线", value: validationBaseline.value?.ready_for_scale ? 100 : validationBaseline.value?.ready_for_tune ? 60 : 25 },
  ];
  const maxValue = Math.max(...base.map(item => item.value), 1);
  return base.map(item => ({
    ...item,
    height: `${Math.max((item.value / maxValue) * 100, 14)}%`,
  }));
});

const insightText = computed(() => {
  if (focusMode.value === "alerts")
    return alertItems.value[0]?.message || "当前没有新的风险提示。";
  if (focusMode.value === "service")
    return runtime.value?.server_ready ? "核心服务在线。" : "服务状态需要关注。";
  if (Number(profitability.value?.pending_review_count || 0) > 0)
    return "待审机会仍有积压。";
  if (Number(last7d.value?.realized_net_profit || 0) > 0)
    return "近 7 天利润保持为正。";
  return "当前仍在积累样本。";
});

const insightPanel = computed(() => {
  if (focusMode.value === "alerts")
    return "alert-panel";
  if (focusMode.value === "service")
    return "service-panel";
  return "profit-panel";
});

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
    note: runtime.value?.server_ready ? "服务正常" : "服务需要关注",
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
  for (const item of serviceSnapshot.value.slice(0, 2)) {
    rows.push({
      name: item.label,
      type: "服务",
      status: item.running ? "运行中" : "已停止",
      tone: item.running ? "positive" : "warning",
      time: generatedAt.value,
    });
  }
  for (const item of baselineSignals.value.slice(0, 2)) {
    rows.push({
      name: item.label,
      type: "基线",
      status: baselineStatusText.value,
      tone: validationBaseline.value?.ready ? "positive" : "warning",
      time: generatedAt.value,
    });
  }
  return rows;
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

.top-section,
.middle-section,
.panel-grid {
  display: grid;
  gap: 24px;
}

.top-section {
  grid-template-columns: minmax(280px, 0.9fr) minmax(0, 2fr);
}

.middle-section {
  grid-template-columns: minmax(0, 1.4fr) minmax(320px, 1fr);
}

.hero-card,
.chart-card,
.insight-card,
.efficiency-card,
.summary-card,
.panel,
.table-card {
  border-radius: var(--radius-lg);
  background: var(--surface-card);
  border: 1px solid var(--surface-line);
  box-shadow: var(--shadow-medium);
}

.hero-card,
.chart-card,
.insight-card,
.efficiency-card,
.panel,
.table-card {
  padding: 28px;
}

.section-kicker {
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.hero-value {
  margin: 18px 0 8px;
  font-family: var(--font-display);
  font-size: 52px;
  font-weight: 800;
  letter-spacing: -0.05em;
}

.hero-trend {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: var(--radius-full);
  font-size: 13px;
  font-weight: 700;
}

.hero-trend.positive {
  color: var(--success-color);
  background: rgba(22, 163, 74, 0.08);
}

.hero-trend.warning {
  color: var(--warning-color);
  background: rgba(217, 119, 6, 0.08);
}

.hero-trend.neutral {
  color: var(--text-secondary);
  background: rgba(73, 92, 148, 0.08);
}

.hero-progress {
  margin-top: 28px;
}

.hero-progress-meta,
.efficiency-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
  color: var(--text-secondary);
  font-size: 13px;
}

.hero-progress-meta strong,
.efficiency-meta strong {
  color: var(--text-primary);
  font-weight: 800;
}

.progress-track {
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--surface-soft);
  overflow: hidden;
}

.progress-track.subtle {
  height: 6px;
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #306bf3, #0051d5);
}

.hero-foot {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
  margin-top: 28px;
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

.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
}

.card-head h3 {
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.card-head p {
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 13px;
}

.ghost-chip {
  padding: 8px 14px;
  border: 1px solid var(--surface-line);
  border-radius: 10px;
  background: var(--surface-soft);
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 800;
}

.bar-chart {
  display: flex;
  align-items: end;
  gap: 14px;
  height: 220px;
  padding: 0 6px;
}

.bar-group {
  display: grid;
  justify-items: center;
  gap: 12px;
  flex: 1;
}

.bar-track {
  display: flex;
  align-items: end;
  width: 100%;
  height: 180px;
  border-radius: 12px 12px 6px 6px;
  background: var(--surface-soft);
  overflow: hidden;
}

.bar-fill {
  width: 100%;
  border-radius: 12px 12px 0 0;
  background: linear-gradient(180deg, #4f7df6, #0051d5);
  box-shadow: 0 10px 22px rgba(0, 81, 213, 0.18);
}

.bar-label {
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.insight-card {
  color: #fff;
  background: linear-gradient(135deg, #1f5fe2, #0051d5);
  border-color: transparent;
}

.card-head-light h3 {
  color: #fff;
}

.title-with-icon {
  display: flex;
  align-items: center;
  gap: 10px;
}

.panel-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 10px;
  color: #fff;
  background: rgba(255, 255, 255, 0.16);
  font-size: 14px;
}

.panel-icon.warm {
  color: var(--tertiary-color);
  background: rgba(198, 79, 10, 0.08);
}

.insight-card p {
  max-width: 560px;
  margin: 0 0 28px;
  color: rgba(255, 255, 255, 0.84);
  font-size: 15px;
  line-height: 1.8;
}

.insight-button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 18px;
  border-radius: 12px;
  color: #fff;
  background: rgba(255, 255, 255, 0.14);
  font-size: 13px;
  font-weight: 800;
}

.status-chip {
  padding: 6px 10px;
  border-radius: 999px;
  color: var(--primary-color);
  background: var(--surface-soft);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.efficiency-list,
.summary-grid,
.metric-list,
.service-list,
.alert-list {
  display: grid;
  gap: 14px;
}

.summary-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.summary-card {
  padding: 22px;
}

.summary-label {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
}

.summary-value {
  margin: 12px 0 8px;
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 36px;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.summary-note {
  color: var(--text-secondary);
  font-size: 13px;
}

.summary-note.positive {
  color: var(--success-color);
}

.summary-note.warning {
  color: var(--warning-color);
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.panel-header h3 {
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 800;
}

.panel-meta {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
}

.metric-row,
.service-row,
.alert-row {
  padding: 16px 18px;
  border: 1px solid var(--surface-line);
  border-radius: 12px;
  background: var(--surface-soft);
}

.metric-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--text-secondary);
}

.metric-row strong,
.service-row strong,
.alert-row strong {
  color: var(--text-primary);
  font-weight: 800;
}

.service-row,
.alert-row {
  display: grid;
  gap: 8px;
}

.service-side,
.alert-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.service-note,
.service-time,
.alert-row p {
  color: var(--text-secondary);
  font-size: 13px;
}

.bottom-section {
  display: grid;
}

.table-wrap {
  overflow-x: auto;
}

.event-table {
  width: 100%;
  border-collapse: collapse;
}

.event-table th,
.event-table td {
  padding: 16px 8px;
  text-align: left;
}

.event-table thead th {
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  border-bottom: 1px solid var(--surface-line);
}

.event-table tbody tr + tr td {
  border-top: 1px solid rgba(195, 198, 215, 0.35);
}

.event-table tbody td {
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 600;
}

.table-status {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.table-status.positive {
  color: var(--success-color);
  background: rgba(22, 163, 74, 0.08);
}

.table-status.warning {
  color: var(--warning-color);
  background: rgba(217, 119, 6, 0.08);
}

.table-status.danger {
  color: var(--error-color);
  background: rgba(220, 38, 38, 0.08);
}

.ghost-link {
  color: var(--primary-color);
  font-size: 13px;
  font-weight: 800;
}

@media (max-width: 1200px) {
  .top-section,
  .middle-section,
  .panel-grid,
  .summary-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .hero-card,
  .chart-card,
  .insight-card,
  .efficiency-card,
  .panel,
  .table-card {
    padding: 20px;
  }

  .hero-value {
    font-size: 42px;
  }

  .bar-chart {
    gap: 8px;
  }
}
</style>
