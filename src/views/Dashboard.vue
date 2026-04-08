<template>
  <div class="dashboard-page">
    <section class="hero-panel">
      <div class="hero-main">
        <div class="hero-kicker">总览</div>
        <h2>{{ heroHeadline }}</h2>

        <div class="focus-switch">
          <button
            v-for="item in focusOptions"
            :key="item.value"
            class="focus-button"
            :class="{ active: focusMode === item.value }"
            type="button"
            @click="focusMode = item.value"
          >
            {{ item.label }}
          </button>
        </div>
      </div>

      <div class="hero-side">
        <div class="hero-meta">
          <span>最近刷新</span>
          <strong>{{ lastLoadedAt || generatedAt }}</strong>
        </div>
        <n-button type="primary" :loading="loading" @click="loadOverview">刷新数据</n-button>
      </div>
    </section>

    <n-alert v-if="error" type="error" :show-icon="false">{{ error }}</n-alert>

    <section class="pulse-grid">
      <button
        v-for="item in pulseCards"
        :key="item.label"
        class="pulse-card"
        type="button"
        @click="jumpToPanel(item.panel)"
      >
        <div class="pulse-label">{{ item.label }}</div>
        <div class="pulse-value">{{ item.value }}</div>
        <div class="pulse-note" :class="item.tone">{{ item.note }}</div>
        <div class="pulse-bar">
          <span :style="{ width: item.progress }"></span>
        </div>
      </button>
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

    <section class="panel-grid">
      <article id="alert-panel" class="panel">
        <div class="panel-header">
          <div>
            <div class="section-label">告警</div>
            <h3>当前告警</h3>
          </div>
          <span class="panel-meta">{{ alertCount }} 条</span>
        </div>
        <div v-if="alertItems.length" class="alert-list">
          <div v-for="item in alertItems.slice(0, 6)" :key="item.alert_key || item.title" class="alert-row">
            <div class="alert-top">
              <strong>{{ item.title }}</strong>
              <n-tag size="small" :type="severityType(item.effective_severity || item.severity)">
                {{ severityText(item.effective_severity || item.severity) }}
              </n-tag>
            </div>
            <p>{{ item.message }}</p>
          </div>
        </div>
        <n-empty v-else description="当前没有活动告警"></n-empty>
      </article>

      <article id="baseline-panel" class="panel">
        <div class="panel-header">
          <div>
            <div class="section-label">基线</div>
            <h3>验证进度</h3>
          </div>
        </div>
        <div class="metric-list">
          <div v-for="item in baselineRows" :key="item.label" class="metric-row">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
        <div v-if="baselineSignals.length" class="pill-list">
          <span v-for="item in baselineSignals" :key="item.code" class="pill">{{ item.label }}</span>
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
  deploymentReadiness,
  error,
  lastLoadedAt,
  loadOverview,
  loading,
  overview,
  profitCockpit,
  profitability,
  runtime,
  validationBaseline,
  formatTime,
} = useExecutiveOverview();

const focusMode = ref("profit");

const focusOptions = [
  { label: "利润", value: "profit" },
  { label: "告警", value: "alerts" },
  { label: "服务", value: "service" },
];

const today = computed(() => profitCockpit.value?.today || {});
const last7d = computed(() => profitCockpit.value?.last_7d || {});
const inventory = computed(() => profitCockpit.value?.inventory || {});
const generatedAt = computed(() => formatTime(overview.value?.generated_at));
const alertCount = computed(() => Number(overview.value?.alerts?.summary?.count || 0));

const heroHeadline = computed(() => {
  if (focusMode.value === "alerts")
    return alertCount.value > 0 ? `${alertCount.value} 条告警待处理` : "当前没有活动告警";
  if (focusMode.value === "service")
    return runtime.value?.server_ready ? "后台服务正常" : "后台服务需要关注";
  return Number(last7d.value?.realized_net_profit || 0) > 0 ? "近 7 天利润为正" : "近 7 天利润还没起来";
});

const pulseCards = computed(() => {
  if (focusMode.value === "alerts") {
    return [
      {
        label: "告警数量",
        value: formatInteger(alertCount.value),
        note: alertItems.value[0]?.title || "暂无",
        tone: alertCount.value > 0 ? "warning" : "positive",
        progress: `${Math.min(alertCount.value * 24, 100)}%`,
        panel: "alert-panel",
      },
      {
        label: "服务状态",
        value: runtime.value?.server_ready ? "正常" : "受限",
        note: runtime.value?.server_ready ? "整体可用" : "需要回看服务",
        tone: runtime.value?.server_ready ? "positive" : "warning",
        progress: runtime.value?.server_ready ? "100%" : "40%",
        panel: "service-panel",
      },
      {
        label: "最新告警",
        value: alertItems.value[0]?.title || "暂无",
        note: alertItems.value[0]?.message || "没有新的风险提示",
        tone: alertItems.value[0] ? "warning" : "neutral",
        progress: alertItems.value[0] ? "72%" : "0%",
        panel: "alert-panel",
      },
    ];
  }

  if (focusMode.value === "service") {
    const services = runtime.value?.services || {};
    return [
      {
        label: "自动化总控",
        value: runtime.value?.automation?.all_running ? "运行中" : "部分运行",
        note: runtime.value?.automation?.busy ? "处理中" : "空闲",
        tone: runtime.value?.automation?.all_running ? "positive" : "warning",
        progress: runtime.value?.automation?.all_running ? "100%" : "56%",
        panel: "service-panel",
      },
      {
        label: "市场监听",
        value: services.monitor?.is_running ? "运行中" : "已停止",
        note: services.monitor?.circuit_open ? "已熔断" : "正常",
        tone: services.monitor?.is_running ? "positive" : "warning",
        progress: services.monitor?.is_running ? "100%" : "28%",
        panel: "service-panel",
      },
      {
        label: "自动审批",
        value: services.autotrade?.running ? "运行中" : "已停止",
        note: `累计通过 ${formatInteger(services.autotrade?.total_approved || 0)} 笔`,
        tone: services.autotrade?.running ? "positive" : "warning",
        progress: services.autotrade?.running ? "100%" : "28%",
        panel: "service-panel",
      },
    ];
  }

  return [
    {
      label: "今日利润",
      value: formatMoney(today.value?.realized_net_profit || 0),
      note: `今天成交 ${formatInteger(today.value?.sold_count || 0)} 笔`,
      tone: toneByNumber(today.value?.realized_net_profit || 0),
      progress: `${Math.min(Math.abs(Number(today.value?.realized_net_profit || 0)) / 10, 100)}%`,
      panel: "profit-panel",
    },
    {
      label: "近 7 天利润",
      value: formatMoney(last7d.value?.realized_net_profit || 0),
      note: `平均 ROI ${formatPercent(last7d.value?.avg_realized_roi || 0)}`,
      tone: toneByNumber(last7d.value?.realized_net_profit || 0),
      progress: `${Math.min(Math.abs(Number(last7d.value?.realized_net_profit || 0)) / 20, 100)}%`,
      panel: "profit-panel",
    },
    {
      label: "在途资金",
      value: formatMoney(inventory.value?.deployed_capital || 0),
      note: `${formatInteger(inventory.value?.active_trade_count || 0)} 笔在处理`,
      tone: "neutral",
      progress: `${Math.min(Number(inventory.value?.deployed_capital || 0) / 10, 100)}%`,
      panel: "profit-panel",
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
      note: automation.busy ? "后台正在处理任务" : "当前没有排队任务",
      time: formatTime(automation.last_run_at),
      type: automation.all_running ? "success" : "warning",
    },
    {
      label: "市场监听",
      value: services.monitor?.is_running ? "运行中" : "已停止",
      note: services.monitor?.circuit_open ? "当前已熔断" : "监听状态正常",
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

const baselineRows = computed(() => [
  { label: "当前状态", value: String(validationBaseline.value?.status || "观察中") },
  { label: "可调优", value: validationBaseline.value?.ready_for_tune ? "是" : "否" },
  { label: "可扩量", value: validationBaseline.value?.ready_for_scale ? "是" : "否" },
  { label: "运行模式", value: String(deploymentReadiness.value?.operating_profile?.mode_label || "标准模式") },
  { label: "方向", value: String(validationBaseline.value?.direction || "暂无") },
]);

const jumpToPanel = (panelId) => {
  document.getElementById(panelId)?.scrollIntoView({ behavior: "smooth", block: "start" });
};

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
.ops-page {
  display: grid;
  gap: 16px;
}

.hero-panel,
.pulse-card,
.summary-card,
.panel,
.story-card,
.sub-panel {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}

.hero-panel {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 24px;
}

.hero-main {
  display: grid;
  gap: 14px;
}

.hero-kicker,
.section-label,
.story-label {
  color: #409eff;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero-panel h2,
.panel h3 {
  margin: 0;
  color: #303133;
  font-size: 28px;
  font-weight: 600;
}

.hero-panel p,
.service-note,
.service-time,
.alert-row p,
.alert-meta {
  color: #606266;
  line-height: 1.7;
}

.focus-switch {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.focus-button {
  min-width: 76px;
  padding: 8px 14px;
  border: 1px solid #dcdfe6;
  border-radius: 999px;
  background: #fff;
  color: #606266;
  transition: all 0.2s ease;
}

.focus-button:hover,
.focus-button.active {
  border-color: #409eff;
  background: rgba(64, 158, 255, 0.08);
  color: #409eff;
}

.hero-side {
  display: grid;
  align-content: start;
  justify-items: end;
  gap: 12px;
}

.hero-meta {
  display: grid;
  gap: 4px;
  text-align: right;
  color: #909399;
  font-size: 13px;
}

.hero-meta strong {
  color: #303133;
  font-size: 18px;
}

.pulse-grid,
.summary-grid,
.panel-grid,
.sub-grid {
  display: grid;
  gap: 16px;
}

.pulse-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.summary-grid {
  grid-template-columns: repeat(6, minmax(0, 1fr));
}

.panel-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.sub-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 16px;
}

.pulse-card,
.summary-card {
  padding: 18px 20px;
  text-align: left;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.pulse-card:hover,
.summary-card:hover,
.panel:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px rgba(0, 21, 41, 0.08);
}

.pulse-label,
.summary-label {
  color: #909399;
  font-size: 13px;
}

.pulse-value,
.summary-value {
  margin: 10px 0 8px;
  color: #303133;
  font-size: 28px;
  font-weight: 600;
  line-height: 1;
}

.pulse-note,
.summary-note {
  color: #606266;
  font-size: 13px;
}

.pulse-note.positive,
.summary-note.positive {
  color: #67c23a;
}

.pulse-note.warning,
.summary-note.warning {
  color: #e6a23c;
}

.pulse-bar {
  height: 6px;
  margin-top: 14px;
  border-radius: 999px;
  background: #f0f2f5;
  overflow: hidden;
}

.pulse-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #409eff, #67c23a);
}

.panel {
  padding: 20px 24px;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.panel h3 {
  font-size: 20px;
}

.panel-meta {
  color: #909399;
  font-size: 13px;
}

.panel-summary {
  margin: 0 0 16px;
  color: #606266;
  line-height: 1.7;
}

.metric-list,
.service-list,
.alert-list {
  display: grid;
  gap: 12px;
}

.metric-row,
.service-row,
.alert-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fafafa;
}

.service-row,
.alert-row {
  display: grid;
}

.metric-row strong,
.service-row strong,
.alert-row strong {
  color: #303133;
}

.service-side {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.sub-panel {
  padding: 16px;
}

.sub-title {
  margin-bottom: 12px;
  color: #303133;
  font-size: 14px;
  font-weight: 600;
}

.compact-list .metric-row {
  padding: 12px 14px;
}

.alert-top,
.alert-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.alert-row p {
  margin: 8px 0 0;
}

.pill-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.pill {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(64, 158, 255, 0.1);
  color: #409eff;
  font-size: 12px;
  font-weight: 600;
}

@media (max-width: 1400px) {
  .pulse-grid,
  .summary-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .hero-panel,
  .panel-grid,
  .sub-grid {
    grid-template-columns: 1fr;
  }

  .hero-panel {
    flex-direction: column;
  }

  .hero-side {
    justify-items: start;
    text-align: left;
  }
}

@media (max-width: 640px) {
  .pulse-grid,
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .hero-panel,
  .pulse-card,
  .summary-card,
  .panel,
  .sub-panel {
    padding: 16px;
  }

  .hero-panel h2 {
    font-size: 24px;
  }
}
</style>
