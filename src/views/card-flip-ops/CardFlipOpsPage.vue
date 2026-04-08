<template>
  <div class="ops-page">
    <section class="stats-grid">
      <article v-for="card in summaryCards" :key="card.label" class="stat-card">
        <div class="stat-head">
          <span class="stat-label">{{ card.label }}</span>
          <span class="stat-badge" :class="card.tone">{{ card.badge }}</span>
        </div>
        <div class="stat-value">{{ card.value }}</div>
        <div class="stat-note">{{ card.note }}</div>
      </article>
    </section>

    <section class="toolbar-card">
      <div class="search-shell">
        <n-input
          v-model:value="searchText"
          clearable
          placeholder="搜索标题、类别或状态"
        ></n-input>
      </div>

      <div class="filter-row">
        <button
          v-for="item in filterOptions"
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

    <section class="content-grid">
      <div class="feed-column">
        <article
          v-for="entry in filteredEntries"
          :key="entry.id"
          class="entry-card"
        >
          <div class="entry-icon" :class="entry.tone">
            {{ entry.icon }}
          </div>

          <div class="entry-main">
            <div class="entry-top">
              <span class="entry-id">{{ entry.id }}</span>
              <span class="entry-time">{{ entry.time }}</span>
            </div>
            <h3>{{ entry.title }}</h3>
            <div class="entry-meta">
              <span class="status-pill" :class="entry.tone">{{ entry.status }}</span>
              <span>{{ entry.meta }}</span>
            </div>
          </div>

          <div class="entry-side">
            <div class="entry-side-value">{{ entry.sideValue }}</div>
            <div class="entry-side-label">{{ entry.sideLabel }}</div>
          </div>
        </article>

        <div v-if="!filteredEntries.length" class="empty-card">
          当前筛选条件下没有内容
        </div>
      </div>

      <aside class="side-column">
        <article class="side-card">
          <div class="card-head">
            <h3>收益与库存</h3>
            <span>{{ generatedAt }}</span>
          </div>
          <div class="mini-list">
            <div v-for="item in profitRows" :key="item.label" class="mini-row">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </article>

        <article class="side-card">
          <div class="card-head">
            <h3>来源贡献</h3>
            <button class="ghost-link" type="button" @click="activeFilter = 'source'">查看</button>
          </div>
          <div v-if="sourceLeaders.length" class="mini-list">
            <div v-for="item in sourceLeaders" :key="item.name" class="mini-row">
              <span>{{ item.name }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
          <div v-else class="empty-mini">暂无来源数据</div>
        </article>

        <article class="side-card">
          <div class="card-head">
            <h3>基线与服务</h3>
            <button class="ghost-link" type="button" @click="activeFilter = 'baseline'">查看</button>
          </div>
          <div class="mini-list">
            <div class="mini-row">
              <span>基线状态</span>
              <strong>{{ baselineStatusText }}</strong>
            </div>
            <div class="mini-row">
              <span>运行模式</span>
              <strong>{{ operatingModeText }}</strong>
            </div>
            <div class="mini-row">
              <span>服务在线率</span>
              <strong>{{ serviceRatioText }}</strong>
            </div>
          </div>
          <div v-if="baselineSignals.length" class="signal-cloud">
            <span v-for="item in baselineSignals.slice(0, 6)" :key="item.code" class="signal-pill">
              {{ item.label }}
            </span>
          </div>
        </article>
      </aside>
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
  error,
  formatTime,
  loadOverview,
  loading,
  operatingModeText,
  overview,
  profitCockpit,
  profitability,
  runtime,
  serviceSnapshot,
} = useExecutiveOverview();

const searchText = ref("");
const activeFilter = ref("all");

const filterOptions = [
  { label: "全部", value: "all" },
  { label: "告警", value: "alert" },
  { label: "服务", value: "service" },
  { label: "来源", value: "source" },
  { label: "卖家", value: "seller" },
  { label: "基线", value: "baseline" },
];

const inventory = computed(() => profitCockpit.value?.inventory || {});
const last7d = computed(() => profitCockpit.value?.last_7d || {});
const generatedAt = computed(() => formatTime(overview.value?.generated_at));
const runningServiceCount = computed(() => serviceSnapshot.value.filter(item => item.running).length);
const serviceRatio = computed(() =>
  serviceSnapshot.value.length ? runningServiceCount.value / serviceSnapshot.value.length : 0,
);
const serviceRatioText = computed(() => `${runningServiceCount.value}/${serviceSnapshot.value.length}`);

const sourceLeaders = computed(() =>
  (Array.isArray(profitCockpit.value?.source_leaderboard_7d) ? profitCockpit.value.source_leaderboard_7d : [])
    .slice(0, 6)
    .map(item => ({
      name: String(item.source || "未知来源"),
      value: formatMoney(item.realized_net_profit || 0),
    })),
);

const sellerLeaders = computed(() =>
  (Array.isArray(profitCockpit.value?.seller_leaderboard_7d) ? profitCockpit.value.seller_leaderboard_7d : [])
    .slice(0, 6)
    .map(item => ({
      name: String(item.seller_id || "未知卖家"),
      value: formatMoney(item.realized_net_profit || 0),
    })),
);

const summaryCards = computed(() => [
  {
    label: "待审机会",
    value: formatInteger(profitability.value?.pending_review_count || 0),
    note: `累计交易 ${formatInteger(profitability.value?.total_trade_count || 0)} 笔`,
    badge: "当前",
    tone: "neutral",
  },
  {
    label: "进行中交易",
    value: formatInteger(profitability.value?.active_trades_count || 0),
    note: `其中挂售 ${formatInteger(inventory.value?.listed_trade_count || 0)} 笔`,
    badge: "处理中",
    tone: "neutral",
  },
  {
    label: "近 7 天利润",
    value: formatMoney(last7d.value?.realized_net_profit || 0),
    note: `平均 ROI ${formatPercent(last7d.value?.avg_realized_roi || 0)}`,
    badge: profitTone.value,
    tone: Number(last7d.value?.realized_net_profit || 0) > 0 ? "positive" : "warning",
  },
  {
    label: "告警数量",
    value: formatInteger(alertItems.value.length),
    note: runtime.value?.server_ready ? "服务正常" : "服务受限",
    badge: alertItems.value.length ? "关注" : "平稳",
    tone: alertItems.value.length ? "warning" : "positive",
  },
]);

const profitTone = computed(() =>
  Number(last7d.value?.realized_net_profit || 0) > 0 ? "向上" : "观察",
);

const entries = computed(() => {
  const rows = [];

  alertItems.value.forEach((item, index) => {
    rows.push({
      id: `AL-${index + 1}`,
      type: "alert",
      tone: severityTone(item.effective_severity || item.severity),
      icon: "!",
      title: item.title,
      status: severityText(item.effective_severity || item.severity),
      meta: item.message,
      time: generatedAt.value,
      sideValue: item.incident_owner || "-",
      sideLabel: "负责人",
    });
  });

  serviceSnapshot.value.forEach((item, index) => {
    rows.push({
      id: `SV-${index + 1}`,
      type: "service",
      tone: item.running ? "positive" : "warning",
      icon: "•",
      title: item.label,
      status: item.running ? "运行中" : "已停止",
      meta: item.note,
      time: generatedAt.value,
      sideValue: item.running ? "在线" : "离线",
      sideLabel: "状态",
    });
  });

  sourceLeaders.value.forEach((item, index) => {
    rows.push({
      id: `SC-${index + 1}`,
      type: "source",
      tone: "positive",
      icon: "¥",
      title: item.name,
      status: "来源",
      meta: "近 7 天来源贡献",
      time: generatedAt.value,
      sideValue: item.value,
      sideLabel: "净利润",
    });
  });

  sellerLeaders.value.forEach((item, index) => {
    rows.push({
      id: `SL-${index + 1}`,
      type: "seller",
      tone: "neutral",
      icon: "人",
      title: item.name,
      status: "卖家",
      meta: "近 7 天卖家贡献",
      time: generatedAt.value,
      sideValue: item.value,
      sideLabel: "净利润",
    });
  });

  baselineSignals.value.forEach((item, index) => {
    rows.push({
      id: `BL-${index + 1}`,
      type: "baseline",
      tone: "warning",
      icon: "基",
      title: item.label,
      status: baselineStatusText.value,
      meta: operatingModeText.value,
      time: generatedAt.value,
      sideValue: baselineStatusText.value,
      sideLabel: "基线",
    });
  });

  return rows;
});

const filteredEntries = computed(() => {
  const text = searchText.value.trim().toLowerCase();
  return entries.value.filter((entry) => {
    if (activeFilter.value !== "all" && entry.type !== activeFilter.value)
      return false;
    if (!text)
      return true;
    return [
      entry.id,
      entry.title,
      entry.status,
      entry.meta,
      entry.sideLabel,
      entry.sideValue,
    ]
      .join(" ")
      .toLowerCase()
      .includes(text);
  });
});

const profitRows = computed(() => [
  { label: "累计毛利", value: formatMoney(profitability.value?.gross_profit || 0) },
  { label: "累计净利润", value: formatMoney(profitability.value?.realized_net_profit || 0) },
  { label: "平均 ROI", value: formatPercent(profitability.value?.avg_realized_roi || 0) },
  { label: "在途资金", value: formatMoney(inventory.value?.deployed_capital || 0) },
]);

const pipelineRows = computed(() => [
  { label: "待审机会", value: formatInteger(profitability.value?.pending_review_count || 0) },
  { label: "进行中交易", value: formatInteger(profitability.value?.active_trades_count || 0) },
  { label: "已卖出", value: formatInteger(profitability.value?.sold_count || 0) },
  { label: "累计交易", value: formatInteger(profitability.value?.total_trade_count || 0) },
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

const severityTone = (severity) => {
  const value = String(severity || "").toLowerCase();
  if (value === "error")
    return "danger";
  if (value === "warning")
    return "warning";
  return "positive";
};

const formatMoney = value =>
  new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY", maximumFractionDigits: 2 }).format(Number(value || 0));
const formatPercent = value =>
  `${new Intl.NumberFormat("zh-CN", { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(value || 0) * 100)}%`;
const formatInteger = value =>
  new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(Number(value || 0));
</script>

<style scoped lang="scss">
.ops-page {
  display: grid;
  gap: 24px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.stat-card,
.toolbar-card,
.entry-card,
.side-card {
  border-radius: var(--radius-lg);
  background: var(--surface-card);
  border: 1px solid var(--surface-line);
  box-shadow: var(--shadow-light);
}

.stat-card {
  padding: 20px;
}

.stat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.stat-label {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.stat-badge {
  padding: 4px 8px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.stat-badge.positive {
  color: var(--success-color);
  background: rgba(22, 163, 74, 0.08);
}

.stat-badge.warning {
  color: var(--warning-color);
  background: rgba(217, 119, 6, 0.08);
}

.stat-badge.neutral {
  color: var(--text-secondary);
  background: var(--surface-soft);
}

.stat-value {
  margin: 14px 0 10px;
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 36px;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.stat-note {
  color: var(--text-secondary);
  font-size: 13px;
}

.toolbar-card {
  padding: 18px;
}

.search-shell {
  margin-bottom: 14px;
}

.filter-row {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.filter-chip {
  padding: 10px 16px;
  border: 1px solid var(--surface-line);
  border-radius: var(--radius-full);
  background: var(--surface-soft);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
  transition: all 0.18s ease;
}

.filter-chip.active,
.filter-chip:hover {
  color: #fff;
  background: var(--primary-color);
  border-color: var(--primary-color);
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(280px, 0.9fr);
  gap: 24px;
}

.feed-column {
  display: grid;
  gap: 14px;
}

.entry-card {
  display: flex;
  gap: 16px;
  align-items: center;
  padding: 18px;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.entry-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-medium);
  border-color: rgba(48, 107, 243, 0.22);
}

.entry-icon {
  width: 52px;
  height: 52px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  font-size: 18px;
  font-weight: 800;
}

.entry-icon.positive {
  color: var(--primary-color);
  background: rgba(48, 107, 243, 0.08);
}

.entry-icon.warning {
  color: var(--warning-color);
  background: rgba(217, 119, 6, 0.08);
}

.entry-icon.danger {
  color: var(--error-color);
  background: rgba(220, 38, 38, 0.08);
}

.entry-icon.neutral {
  color: var(--text-secondary);
  background: var(--surface-soft);
}

.entry-main {
  flex: 1;
  min-width: 0;
}

.entry-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.entry-id,
.entry-time {
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.entry-main h3 {
  margin: 6px 0 8px;
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.entry-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 12px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 4px 9px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.1em;
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

.status-pill.neutral {
  color: var(--text-secondary);
  background: var(--surface-soft);
}

.entry-side {
  min-width: 96px;
  text-align: right;
}

.entry-side-value {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 800;
}

.entry-side-label {
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.empty-card {
  padding: 20px;
  border: 1px dashed var(--surface-line);
  border-radius: var(--radius-lg);
  color: var(--text-muted);
  text-align: center;
  background: var(--surface-soft);
}

.side-column {
  display: grid;
  gap: 16px;
  align-content: start;
}

.side-card {
  padding: 20px;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.card-head h3 {
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.card-head span {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
}

.mini-list {
  display: grid;
  gap: 12px;
}

.mini-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--surface-soft);
  color: var(--text-secondary);
}

.mini-row strong {
  color: var(--text-primary);
  font-weight: 800;
}

.empty-mini {
  color: var(--text-muted);
  font-size: 13px;
}

.signal-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.signal-pill {
  padding: 6px 10px;
  border-radius: var(--radius-full);
  color: var(--primary-color);
  background: rgba(48, 107, 243, 0.08);
  font-size: 12px;
  font-weight: 700;
}

.ghost-link {
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 800;
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .content-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .entry-card {
    align-items: flex-start;
  }

  .entry-side {
    min-width: 72px;
  }
}
</style>
