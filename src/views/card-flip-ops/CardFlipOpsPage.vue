<template>
  <div class="logs-page">
    <section class="page-header">
      <div>
        <div class="page-kicker">交易台</div>
        <h1>卡片交易</h1>
      </div>
      <div class="page-actions">
        <button class="ghost-button" type="button" @click="activeFilter = 'all'">全部</button>
        <n-button type="primary" :loading="loading" @click="loadOverview">刷新</n-button>
      </div>
    </section>

    <n-alert v-if="error" type="error" :show-icon="false">{{ error }}</n-alert>

    <section class="metric-grid">
      <article v-for="card in metricCards" :key="card.label" class="metric-card">
        <div class="metric-top">
          <div class="metric-icon" :class="card.tone">
            <n-icon size="18">
              <component :is="card.icon"></component>
            </n-icon>
          </div>
          <span class="metric-badge" :class="card.tone">{{ card.badge }}</span>
        </div>
        <div class="metric-label">{{ card.label }}</div>
        <div class="metric-value">{{ card.value }}</div>
        <div class="metric-note">{{ card.note }}</div>
      </article>
    </section>

    <section class="toolbar-card">
      <div class="search-shell">
        <n-input
          v-model:value="searchQuery"
          clearable
          placeholder="搜索告警、服务、来源或卖家"
        >
          <template #prefix>
            <n-icon size="18"><SearchOutline></SearchOutline></n-icon>
          </template>
        </n-input>
      </div>

      <div class="filter-row">
        <button
          v-for="item in filters"
          :key="item.value"
          class="filter-chip"
          :class="{ active: activeFilter === item.value }"
          type="button"
          @click="activeFilter = item.value"
        >
          {{ item.label }}
        </button>
      </div>
    </section>

    <section class="entry-list">
      <article
        v-for="entry in filteredEntries"
        :key="entry.id"
        class="entry-card"
      >
        <div class="entry-icon" :class="entry.tone">
          <n-icon size="20">
            <component :is="entry.icon"></component>
          </n-icon>
        </div>

        <div class="entry-main">
          <div class="entry-head">
            <div class="entry-title-block">
              <div class="entry-code">{{ entry.kindLabel }}</div>
              <h3>{{ entry.title }}</h3>
            </div>
            <div class="entry-side">
              <span class="entry-time">{{ entry.time }}</span>
              <button class="more-button" type="button" @click="activeFilter = entry.kind">
                <n-icon size="18"><EllipsisVerticalOutline></EllipsisVerticalOutline></n-icon>
              </button>
            </div>
          </div>

          <div class="entry-meta">
            <span class="entry-status" :class="entry.tone">{{ entry.status }}</span>
            <span v-if="entry.metric" class="entry-metric">{{ entry.metric }}</span>
          </div>

          <p class="entry-note">{{ entry.note }}</p>
        </div>
      </article>
    </section>

    <button
      v-if="filteredEntries.length < allEntries.length"
      class="load-more"
      type="button"
      @click="activeFilter = 'all'"
    >
      显示全部
    </button>

    <section class="details-grid">
      <article class="detail-card">
        <div class="detail-head">
          <h3>验证基线</h3>
          <span class="detail-badge">{{ baselineStatusText }}</span>
        </div>
        <div class="detail-rows">
          <div v-for="item in baselineRows" :key="item.label" class="detail-row">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
        <div v-if="baselineSignals.length" class="detail-pills">
          <span v-for="item in baselineSignals" :key="item.code" class="pill">{{ item.label }}</span>
        </div>
      </article>

      <article class="detail-card">
        <div class="detail-head">
          <h3>重点来源</h3>
          <span class="detail-badge">近 7 天</span>
        </div>
        <div class="detail-rows">
          <div v-for="item in topSourceRows" :key="item.name" class="detail-row">
            <span>{{ item.name }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import {
  AlertCircleOutline,
  EllipsisVerticalOutline,
  FlashOutline,
  PersonOutline,
  SearchOutline,
  ServerOutline,
  StatsChartOutline,
  TimeOutline,
} from "@vicons/ionicons5";
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
  validationBaseline,
  formatTime,
} = useExecutiveOverview();

const searchQuery = ref("");
const activeFilter = ref("all");

const filters = [
  { label: "全部", value: "all" },
  { label: "告警", value: "alert" },
  { label: "服务", value: "service" },
  { label: "来源", value: "source" },
  { label: "卖家", value: "seller" },
];

const inventory = computed(() => profitCockpit.value?.inventory || {});
const last7d = computed(() => profitCockpit.value?.last_7d || {});
const generatedAt = computed(() => formatTime(overview.value?.generated_at));

const metricCards = computed(() => [
  {
    label: "待审机会",
    value: formatInteger(profitability.value?.pending_review_count || 0),
    note: `累计交易 ${formatInteger(profitability.value?.total_trade_count || 0)} 笔`,
    badge: "待处理",
    tone: "primary",
    icon: TimeOutline,
  },
  {
    label: "已卖出",
    value: formatInteger(profitability.value?.sold_count || 0),
    note: `命中率 ${formatPercent(profitability.value?.profit_hit_rate || 0)}`,
    badge: "完成",
    tone: "success",
    icon: StatsChartOutline,
  },
  {
    label: "在途资金",
    value: formatMoney(inventory.value?.deployed_capital || 0),
    note: `进行中 ${formatInteger(profitability.value?.active_trades_count || 0)} 笔`,
    badge: "占用中",
    tone: "warning",
    icon: FlashOutline,
  },
  {
    label: "告警数量",
    value: formatInteger(alertItems.value.length),
    note: runtime.value?.server_ready ? "服务正常" : "服务受限",
    badge: alertItems.value.length > 0 ? "关注" : "正常",
    tone: alertItems.value.length > 0 ? "danger" : "success",
    icon: AlertCircleOutline,
  },
]);

const topSourceRows = computed(() =>
  (Array.isArray(profitCockpit.value?.source_leaderboard_7d) ? profitCockpit.value.source_leaderboard_7d : [])
    .slice(0, 6)
    .map(item => ({
      name: String(item.source || "未知来源"),
      value: formatMoney(item.realized_net_profit || 0),
    })),
);

const topSellerRows = computed(() =>
  (Array.isArray(profitCockpit.value?.seller_leaderboard_7d) ? profitCockpit.value.seller_leaderboard_7d : [])
    .slice(0, 6)
    .map(item => ({
      name: String(item.seller_id || "未知卖家"),
      value: formatMoney(item.realized_net_profit || 0),
    })),
);

const baselineRows = computed(() => [
  { label: "当前状态", value: baselineStatusText.value },
  { label: "可调优", value: validationBaseline.value?.ready_for_tune ? "是" : "否" },
  { label: "可扩量", value: validationBaseline.value?.ready_for_scale ? "是" : "否" },
  { label: "运行模式", value: operatingModeText.value },
  { label: "方向", value: String(validationBaseline.value?.direction || "暂无") },
  { label: "最近建议", value: String(validationBaseline.value?.recommendation || "继续观察") },
]);

const serviceEntries = computed(() => {
  const services = runtime.value?.services || {};
  return [
    {
      id: "service-monitor",
      kind: "service",
      kindLabel: "服务",
      title: "市场监听",
      status: services.monitor?.is_running ? "运行中" : "已停止",
      tone: services.monitor?.is_running ? "success" : "warning",
      note: services.monitor?.circuit_open ? "当前已熔断" : "监听状态正常",
      metric: `时间 ${formatTime(services.monitor?.last_run_at)}`,
      time: generatedAt.value,
      icon: ServerOutline,
    },
    {
      id: "service-autotrade",
      kind: "service",
      kindLabel: "服务",
      title: "自动交易审批",
      status: services.autotrade?.running ? "运行中" : "已停止",
      tone: services.autotrade?.running ? "success" : "warning",
      note: `累计通过 ${formatInteger(services.autotrade?.total_approved || 0)} 笔`,
      metric: `时间 ${formatTime(services.autotrade?.last_run_at)}`,
      time: generatedAt.value,
      icon: StatsChartOutline,
    },
    {
      id: "service-retry",
      kind: "service",
      kindLabel: "服务",
      title: "执行重试",
      status: services.execution_retry?.running ? "运行中" : "已停止",
      tone: services.execution_retry?.running ? "success" : "warning",
      note: `累计重试 ${formatInteger(services.execution_retry?.total_retried || 0)} 次`,
      metric: `时间 ${formatTime(services.execution_retry?.last_run_at)}`,
      time: generatedAt.value,
      icon: FlashOutline,
    },
  ];
});

const sourceEntries = computed(() =>
  topSourceRows.value.map((item, index) => ({
    id: `source-${index}`,
    kind: "source",
    kindLabel: "来源",
    title: item.name,
    status: "贡献",
    tone: "primary",
    note: "近 7 天来源贡献",
    metric: item.value,
    time: generatedAt.value,
    icon: FlashOutline,
  })),
);

const sellerEntries = computed(() =>
  topSellerRows.value.map((item, index) => ({
    id: `seller-${index}`,
    kind: "seller",
    kindLabel: "卖家",
    title: item.name,
    status: "贡献",
    tone: "primary",
    note: "近 7 天卖家贡献",
    metric: item.value,
    time: generatedAt.value,
    icon: PersonOutline,
  })),
);

const allEntries = computed(() => [
  ...alertItems.value.map((item, index) => ({
    id: item.alert_key || `alert-${index}`,
    kind: "alert",
    kindLabel: "告警",
    title: item.title,
    status: severityText(item.effective_severity || item.severity),
    tone: severityTone(item.effective_severity || item.severity),
    note: item.message,
    metric: item.incident_owner ? `负责人 ${item.incident_owner}` : "",
    time: generatedAt.value,
    icon: AlertCircleOutline,
  })),
  ...serviceEntries.value,
  ...sourceEntries.value,
  ...sellerEntries.value,
]);

const filteredEntries = computed(() => {
  const query = String(searchQuery.value || "").trim().toLowerCase();
  return allEntries.value.filter((entry) => {
    if (activeFilter.value !== "all" && entry.kind !== activeFilter.value)
      return false;
    if (!query)
      return true;
    return [entry.title, entry.note, entry.metric, entry.kindLabel]
      .join(" ")
      .toLowerCase()
      .includes(query);
  });
});

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

const severityTone = (severity) => {
  const value = String(severity || "").toLowerCase();
  if (value === "error")
    return "danger";
  if (value === "warning")
    return "warning";
  return "success";
};

const severityType = (severity) => {
  const value = String(severity || "").toLowerCase();
  if (value === "error")
    return "error";
  if (value === "warning")
    return "warning";
  return "info";
};

const percentWidth = value => `${Math.max(Math.min(Number(value || 0) * 100, 100), 8)}%`;
const toneByNumber = value =>
  Number(value || 0) > 0 ? "success" : Number(value || 0) < 0 ? "warning" : "primary";
const formatMoney = value =>
  new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY", maximumFractionDigits: 2 }).format(Number(value || 0));
const formatPercent = value => `${formatNumber(Number(value || 0) * 100, 1)}%`;
const formatInteger = value =>
  new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(Number(value || 0));
const formatNumber = (value, digits = 2) =>
  new Intl.NumberFormat("zh-CN", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(value || 0));
</script>

<style scoped lang="scss">
.logs-page {
  display: grid;
  gap: 24px;
}

.page-header,
.metric-card,
.toolbar-card,
.entry-card,
.detail-card {
  border-radius: var(--radius-lg);
  background: var(--surface-card);
  border: 1px solid var(--surface-line);
  box-shadow: var(--shadow-medium);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 28px;
}

.page-kicker {
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.page-header h1 {
  margin-top: 10px;
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 30px;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.page-actions {
  display: flex;
  gap: 10px;
}

.ghost-button {
  padding: 0 16px;
  border: 1px solid var(--surface-line);
  border-radius: 12px;
  background: var(--surface-soft);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.metric-card {
  padding: 22px;
}

.metric-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.metric-icon {
  width: 38px;
  height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
}

.metric-icon.primary {
  color: var(--primary-color);
  background: rgba(0, 81, 213, 0.08);
}

.metric-icon.success {
  color: var(--success-color);
  background: rgba(22, 163, 74, 0.08);
}

.metric-icon.warning {
  color: var(--warning-color);
  background: rgba(217, 119, 6, 0.08);
}

.metric-icon.danger {
  color: var(--error-color);
  background: rgba(220, 38, 38, 0.08);
}

.metric-badge {
  padding: 6px 10px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.metric-badge.primary {
  color: var(--primary-color);
  background: rgba(0, 81, 213, 0.08);
}

.metric-badge.success {
  color: var(--success-color);
  background: rgba(22, 163, 74, 0.08);
}

.metric-badge.warning {
  color: var(--warning-color);
  background: rgba(217, 119, 6, 0.08);
}

.metric-badge.danger {
  color: var(--error-color);
  background: rgba(220, 38, 38, 0.08);
}

.metric-label {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
}

.metric-value {
  margin: 12px 0 8px;
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 34px;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.metric-note {
  color: var(--text-secondary);
  font-size: 13px;
}

.toolbar-card {
  display: grid;
  gap: 16px;
  padding: 20px;
}

.filter-row {
  display: flex;
  gap: 10px;
  overflow-x: auto;
}

.filter-chip {
  padding: 10px 16px;
  border: 1px solid var(--surface-line);
  border-radius: var(--radius-full);
  background: var(--surface-card);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.filter-chip.active {
  color: #fff;
  background: var(--primary-color);
  border-color: var(--primary-color);
  box-shadow: 0 10px 22px rgba(0, 81, 213, 0.18);
}

.entry-list {
  display: grid;
  gap: 14px;
}

.entry-card {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 18px;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.entry-card:hover {
  transform: translateY(-2px);
  border-color: rgba(0, 81, 213, 0.28);
  box-shadow: var(--shadow-heavy);
}

.entry-icon {
  width: 48px;
  height: 48px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  flex: 0 0 auto;
}

.entry-icon.primary {
  color: var(--primary-color);
  background: rgba(0, 81, 213, 0.08);
}

.entry-icon.success {
  color: var(--success-color);
  background: rgba(22, 163, 74, 0.08);
}

.entry-icon.warning {
  color: var(--warning-color);
  background: rgba(217, 119, 6, 0.08);
}

.entry-icon.danger {
  color: var(--error-color);
  background: rgba(220, 38, 38, 0.08);
}

.entry-main {
  flex: 1;
  min-width: 0;
}

.entry-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.entry-title-block {
  min-width: 0;
}

.entry-code {
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.entry-title-block h3 {
  margin-top: 4px;
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.entry-side {
  display: flex;
  align-items: start;
  gap: 8px;
}

.entry-time {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.more-button {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  color: var(--text-muted);
}

.more-button:hover {
  background: var(--surface-soft);
  color: var(--primary-color);
}

.entry-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
}

.entry-status {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.entry-status.primary {
  color: var(--primary-color);
  background: rgba(0, 81, 213, 0.08);
}

.entry-status.success {
  color: var(--success-color);
  background: rgba(22, 163, 74, 0.08);
}

.entry-status.warning {
  color: var(--warning-color);
  background: rgba(217, 119, 6, 0.08);
}

.entry-status.danger {
  color: var(--error-color);
  background: rgba(220, 38, 38, 0.08);
}

.entry-metric {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.entry-note {
  margin-top: 12px;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.7;
}

.load-more {
  width: 100%;
  padding: 14px 18px;
  border: 1px dashed rgba(0, 81, 213, 0.2);
  border-radius: 14px;
  color: var(--primary-color);
  background: rgba(0, 81, 213, 0.02);
  font-size: 13px;
  font-weight: 800;
}

.details-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.detail-card {
  padding: 22px;
}

.detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
}

.detail-head h3 {
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 800;
}

.detail-badge {
  padding: 6px 10px;
  border-radius: var(--radius-full);
  color: var(--primary-color);
  background: rgba(0, 81, 213, 0.08);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.detail-rows {
  display: grid;
  gap: 12px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--surface-soft);
  color: var(--text-secondary);
}

.detail-row strong {
  color: var(--text-primary);
  font-weight: 800;
}

.detail-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.pill {
  padding: 6px 10px;
  border-radius: var(--radius-full);
  background: rgba(0, 81, 213, 0.08);
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 700;
}

@media (max-width: 1200px) {
  .metric-grid,
  .details-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .entry-card,
  .page-header,
  .top-section,
  .details-grid {
    grid-template-columns: 1fr;
  }

  .page-header {
    flex-direction: column;
    align-items: stretch;
  }

  .entry-card {
    flex-direction: column;
    align-items: stretch;
  }

  .entry-side {
    justify-content: space-between;
  }
}

@media (max-width: 640px) {
  .metric-grid {
    grid-template-columns: 1fr;
  }

  .page-header,
  .metric-card,
  .toolbar-card,
  .entry-card,
  .detail-card {
    padding: 18px;
  }

  .hero-value {
    font-size: 42px;
  }

  .entry-title-block h3 {
    font-size: 19px;
  }
}
</style>
