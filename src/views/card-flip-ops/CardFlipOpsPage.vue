<template>
  <div class="ops-page">
    <section class="hero-panel">
      <div class="hero-main">
        <div class="hero-kicker">卡片交易</div>
        <h2>{{ heroHeadline }}</h2>
        <p>{{ heroDescription }}</p>

        <div class="focus-switch">
          <button
            v-for="item in focusTabs"
            :key="item.key"
            class="focus-button"
            :class="{ active: activeFocus === item.key }"
            type="button"
            @click="setFocus(item.key)"
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
        <n-button type="primary" :loading="loading" @click="loadOverview">刷新</n-button>
      </div>
    </section>

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

    <section class="story-grid">
      <article class="story-card">
        <div class="story-label">现在该盯什么</div>
        <h3>{{ focusStoryTitle }}</h3>
        <p>{{ focusStoryText }}</p>
      </article>

      <article class="story-card">
        <div class="story-label">一句建议</div>
        <h3>{{ actionHeadline }}</h3>
        <p>{{ actionText }}</p>
      </article>
    </section>

    <n-alert v-if="error" type="error" :show-icon="false">{{ error }}</n-alert>

    <section class="summary-grid">
      <article v-for="card in summaryCards" :key="card.label" class="summary-card">
        <div class="summary-label">{{ card.label }}</div>
        <div class="summary-value">{{ card.value }}</div>
        <div class="summary-note" :class="card.tone">{{ card.note }}</div>
      </article>
    </section>

    <section class="panel-grid">
      <article id="pipeline-panel" class="panel">
        <div class="panel-header">
          <div>
            <div class="section-label">进度</div>
            <h3>机会和成交</h3>
          </div>
          <span class="panel-meta">{{ generatedAt }}</span>
        </div>
        <p class="panel-summary">{{ pipelineSummary }}</p>
        <div class="metric-list">
          <div v-for="item in pipelineRows" :key="item.label" class="metric-row">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </article>

      <article id="profit-panel" class="panel">
        <div class="panel-header">
          <div>
            <div class="section-label">收益</div>
            <h3>收益与库存</h3>
          </div>
        </div>
        <p class="panel-summary">{{ profitSummary }}</p>
        <div class="metric-list">
          <div v-for="item in profitabilityRows" :key="item.label" class="metric-row">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
        <div class="sub-grid">
          <div class="sub-panel">
            <div class="sub-title">近 7 天来源贡献</div>
            <div v-if="sourceLeaders.length" class="metric-list compact-list">
              <div v-for="item in sourceLeaders" :key="item.name" class="metric-row">
                <span>{{ item.name }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>
            <n-empty v-else description="暂无来源贡献数据" size="small"></n-empty>
          </div>
          <div class="sub-panel">
            <div class="sub-title">近 7 天卖家贡献</div>
            <div v-if="sellerLeaders.length" class="metric-list compact-list">
              <div v-for="item in sellerLeaders" :key="item.name" class="metric-row">
                <span>{{ item.name }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>
            <n-empty v-else description="暂无卖家贡献数据" size="small"></n-empty>
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
        <p class="panel-summary">{{ alertSummary }}</p>
        <div v-if="alertItems.length" class="alert-list">
          <div v-for="item in alertItems" :key="item.alert_key || item.title" class="alert-row">
            <div class="alert-top">
              <strong>{{ item.title }}</strong>
              <n-tag size="small" :type="severityType(item.effective_severity || item.severity)">
                {{ severityText(item.effective_severity || item.severity) }}
              </n-tag>
            </div>
            <p>{{ item.message }}</p>
            <div class="alert-meta">
              <span>负责人：{{ item.incident_owner || "-" }}</span>
              <span>优先级：{{ item.incident_priority || "-" }}</span>
            </div>
          </div>
        </div>
        <n-empty v-else description="当前没有活动告警"></n-empty>
      </article>

      <article id="baseline-panel" class="panel">
        <div class="panel-header">
          <div>
            <div class="section-label">基线</div>
            <h3>运行护栏</h3>
          </div>
        </div>
        <p class="panel-summary">{{ baselineRecommendation }}</p>
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

    <section class="panel-grid">
      <article id="service-panel" class="panel">
        <div class="panel-header">
          <div>
            <div class="section-label">服务</div>
            <h3>自动化与服务</h3>
          </div>
        </div>
        <p class="panel-summary">{{ serviceSummary }}</p>
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
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

import useExecutiveOverview from "@/composables/useExecutiveOverview";

const {
  alertItems,
  baselineDirectionText,
  baselineRecommendation,
  baselineSignals,
  baselineStatusText,
  deploymentReadiness,
  error,
  formatTime,
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
} = useExecutiveOverview();

const activeFocus = ref("pipeline");
const focusTabs = [
  { key: "pipeline", label: "进度" },
  { key: "profit", label: "收益" },
  { key: "alerts", label: "告警" },
  { key: "baseline", label: "基线" },
  { key: "service", label: "服务" },
];

const inventory = computed(() => profitCockpit.value?.inventory || {});
const last7d = computed(() => profitCockpit.value?.last_7d || {});
const generatedAt = computed(() => formatTime(overview.value?.generated_at));
const alertCount = computed(() => Number(alertItems.value.length || 0));
const serviceRunningCount = computed(() => serviceSnapshot.value.filter(item => item.running).length);

const sourceLeaders = computed(() =>
  (Array.isArray(profitCockpit.value?.source_leaderboard_7d) ? profitCockpit.value.source_leaderboard_7d : [])
    .slice(0, 5)
    .map(item => ({
      name: String(item.source || "未知来源"),
      value: formatMoney(item.realized_net_profit || 0),
    })),
);

const sellerLeaders = computed(() =>
  (Array.isArray(profitCockpit.value?.seller_leaderboard_7d) ? profitCockpit.value.seller_leaderboard_7d : [])
    .slice(0, 5)
    .map(item => ({
      name: String(item.seller_id || "未知卖家"),
      value: formatMoney(item.realized_net_profit || 0),
    })),
);

const focusCopyMap = computed(() => ({
  pipeline: {
    headline: "先看机会有没有堵住",
    description: "待审机会、进行中交易和卖出速度，决定今天该盯哪一段。",
    storyTitle: "交易进度",
    storyText: Number(profitability.value?.pending_review_count || 0) > 0
      ? "待审机会还在堆着，先看有没有需要尽快处理的部分。"
      : "机会没有明显堆积，可以把注意力转到收益和服务状态。",
    actionHeadline: "当前节奏",
    actionText: `待审 ${formatInteger(profitability.value?.pending_review_count || 0)} 笔，进行中 ${formatInteger(profitability.value?.active_trades_count || 0)} 笔。`,
  },
  profit: {
    headline: "再看利润是不是跑出来了",
    description: "有利润的时候看效率，没利润的时候看样本和资金。",
    storyTitle: "收益状态",
    storyText: Number(last7d.value?.realized_net_profit || 0) > 0
      ? "近 7 天已经有正向利润，可以继续盯资金占用和成交效率。"
      : "现在更像在积累样本，先别急着追求结果。",
    actionHeadline: "当前判断",
    actionText: `近 7 天利润 ${formatMoney(last7d.value?.realized_net_profit || 0)}，在途资金 ${formatMoney(inventory.value?.deployed_capital || 0)}。`,
  },
  alerts: {
    headline: "有告警就先处理告警",
    description: "先把挡路的事清掉，再看收益和放量。",
    storyTitle: "风险状态",
    storyText: alertCount.value > 0
      ? `当前有 ${alertCount.value} 条告警，建议先看第一条。`
      : "当前没有明显告警，可以回去盯机会和收益。",
    actionHeadline: "最需要关注",
    actionText: alertItems.value[0]?.message || "现在没有新的风险提示。",
  },
  baseline: {
    headline: "基线没站稳，就先别放量",
    description: "样本不够时，判断会很飘，先把基线做扎实。",
    storyTitle: "验证状态",
    storyText: baselineStatusText.value === "已就绪"
      ? "基线已经基本到位，可以谨慎考虑下一步。"
      : "现在更适合继续观察，把样本做厚一点。",
    actionHeadline: "最近建议",
    actionText: baselineRecommendation.value,
  },
  service: {
    headline: "最后确认后台是不是顺着跑",
    description: "服务掉线的时候，前面所有数据都会失真。",
    storyTitle: "服务状态",
    storyText: serviceRunningCount.value >= 2
      ? "核心服务基本在线，可以继续盯业务数据。"
      : "有服务没跑起来，先把服务状态理顺再说。",
    actionHeadline: "当前状态",
    actionText: `${serviceRunningCount.value}/${serviceSnapshot.value.length} 个核心服务正在运行。`,
  },
}));

const heroHeadline = computed(() => focusCopyMap.value[activeFocus.value].headline);
const heroDescription = computed(() => focusCopyMap.value[activeFocus.value].description);
const focusStoryTitle = computed(() => focusCopyMap.value[activeFocus.value].storyTitle);
const focusStoryText = computed(() => focusCopyMap.value[activeFocus.value].storyText);
const actionHeadline = computed(() => focusCopyMap.value[activeFocus.value].actionHeadline);
const actionText = computed(() => focusCopyMap.value[activeFocus.value].actionText);

const pulseCards = computed(() => {
  if (activeFocus.value === "profit") {
    return [
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
      {
        label: "预期价差",
        value: formatMoney(inventory.value?.expected_exit_spread || 0),
        note: "看库存还有没有利润空间",
        tone: "neutral",
        progress: `${Math.min(Number(inventory.value?.expected_exit_spread || 0) / 5, 100)}%`,
        panel: "profit-panel",
      },
    ];
  }

  if (activeFocus.value === "alerts") {
    return [
      {
        label: "告警数量",
        value: formatInteger(alertCount.value),
        note: alertCount.value > 0 ? "先看第一条" : "现在比较安静",
        tone: alertCount.value > 0 ? "warning" : "positive",
        progress: `${Math.min(alertCount.value * 24, 100)}%`,
        panel: "alert-panel",
      },
      {
        label: "最新告警",
        value: alertItems.value[0]?.title || "暂无",
        note: alertItems.value[0]?.message || "没有新的风险提示",
        tone: alertItems.value[0] ? "warning" : "neutral",
        progress: alertItems.value[0] ? "72%" : "0%",
        panel: "alert-panel",
      },
      {
        label: "服务总状态",
        value: runtime.value?.server_ready ? "正常" : "受限",
        note: runtime.value?.server_ready ? "整体可用" : "建议回头看服务卡片",
        tone: runtime.value?.server_ready ? "positive" : "warning",
        progress: runtime.value?.server_ready ? "100%" : "40%",
        panel: "service-panel",
      },
    ];
  }

  if (activeFocus.value === "baseline") {
    return [
      {
        label: "当前状态",
        value: baselineStatusText.value,
        note: baselineDirectionText.value,
        tone: validationBaseline.value?.ready ? "positive" : "warning",
        progress: validationBaseline.value?.ready ? "100%" : validationBaseline.value?.ready_for_tune ? "62%" : "28%",
        panel: "baseline-panel",
      },
      {
        label: "运行模式",
        value: operatingModeText.value,
        note: validationBaseline.value?.ready_for_scale ? "可以看放量" : "现在更适合观察",
        tone: "neutral",
        progress: validationBaseline.value?.ready_for_scale ? "82%" : "38%",
        panel: "baseline-panel",
      },
      {
        label: "最近建议",
        value: baselineRecommendation.value,
        note: "基于最近样本自动生成",
        tone: "neutral",
        progress: "58%",
        panel: "baseline-panel",
      },
    ];
  }

  if (activeFocus.value === "service") {
    return serviceSnapshot.value.map(item => ({
      label: item.label,
      value: item.running ? "运行中" : "已停止",
      note: item.note,
      tone: item.running ? "positive" : "warning",
      progress: item.running ? "100%" : "28%",
      panel: "service-panel",
    }));
  }

  return [
    {
      label: "待审机会",
      value: formatInteger(profitability.value?.pending_review_count || 0),
      note: "看有没有堆积",
      tone: "neutral",
      progress: `${Math.min(Number(profitability.value?.pending_review_count || 0) * 10, 100)}%`,
      panel: "pipeline-panel",
    },
    {
      label: "进行中交易",
      value: formatInteger(profitability.value?.active_trades_count || 0),
      note: `其中挂售 ${formatInteger(inventory.value?.listed_trade_count || 0)} 笔`,
      tone: "neutral",
      progress: `${Math.min(Number(profitability.value?.active_trades_count || 0) * 12, 100)}%`,
      panel: "pipeline-panel",
    },
    {
      label: "已卖出",
      value: formatInteger(profitability.value?.sold_count || 0),
      note: `命中率 ${formatPercent(profitability.value?.profit_hit_rate || 0)}`,
      tone: "positive",
      progress: `${Math.min(Number(profitability.value?.sold_count || 0) * 12, 100)}%`,
      panel: "pipeline-panel",
    },
  ];
});

const summaryCards = computed(() => [
  {
    label: "待审机会",
    value: formatInteger(profitability.value?.pending_review_count || 0),
    note: `累计交易 ${formatInteger(profitability.value?.total_trade_count || 0)} 笔`,
    tone: "neutral",
  },
  {
    label: "进行中交易",
    value: formatInteger(profitability.value?.active_trades_count || 0),
    note: `其中挂售 ${formatInteger(inventory.value?.listed_trade_count || 0)} 笔`,
    tone: "neutral",
  },
  {
    label: "已卖出",
    value: formatInteger(profitability.value?.sold_count || 0),
    note: `命中率 ${formatPercent(profitability.value?.profit_hit_rate || 0)}`,
    tone: "positive",
  },
  {
    label: "累计毛利",
    value: formatMoney(profitability.value?.gross_profit || 0),
    note: `近 7 天利润 ${formatMoney(last7d.value?.realized_net_profit || 0)}`,
    tone: toneByNumber(profitability.value?.gross_profit || 0),
  },
  {
    label: "在途资金",
    value: formatMoney(inventory.value?.deployed_capital || 0),
    note: `预计价差 ${formatMoney(inventory.value?.expected_exit_spread || 0)}`,
    tone: "neutral",
  },
  {
    label: "验证基线",
    value: baselineStatusText.value,
    note: baselineDirectionText.value,
    tone: validationBaseline.value?.ready ? "positive" : "warning",
  },
]);

const pipelineRows = computed(() => [
  { label: "待审机会", value: formatInteger(profitability.value?.pending_review_count || 0) },
  { label: "进行中交易", value: formatInteger(profitability.value?.active_trades_count || 0) },
  { label: "已卖出", value: formatInteger(profitability.value?.sold_count || 0) },
  { label: "累计交易", value: formatInteger(profitability.value?.total_trade_count || 0) },
  { label: "已挂售", value: formatInteger(inventory.value?.listed_trade_count || 0) },
  { label: "目标退出价值", value: formatMoney(inventory.value?.target_exit_value || 0) },
]);

const profitabilityRows = computed(() => [
  { label: "近 7 天利润", value: formatMoney(last7d.value?.realized_net_profit || 0) },
  { label: "累计净利润", value: formatMoney(profitability.value?.realized_net_profit || 0) },
  { label: "平均 ROI", value: formatPercent(profitability.value?.avg_realized_roi || 0) },
  { label: "平均持有天数", value: `${formatNumber(profitability.value?.avg_holding_days || 0, 1)} 天` },
  { label: "中位持有天数", value: `${formatNumber(profitability.value?.median_holding_days || 0, 1)} 天` },
  { label: "目标退出价值", value: formatMoney(inventory.value?.target_exit_value || 0) },
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
  { label: "当前状态", value: baselineStatusText.value },
  { label: "可以调优", value: validationBaseline.value?.ready_for_tune ? "是" : "否" },
  { label: "可以放量", value: validationBaseline.value?.ready_for_scale ? "是" : "否" },
  { label: "运行模式", value: operatingModeText.value },
  { label: "方向", value: baselineDirectionText.value },
  { label: "最近建议", value: baselineRecommendation.value },
]);

const pipelineSummary = computed(() => {
  if (Number(profitability.value?.pending_review_count || 0) > 0)
    return "待审机会还有积压，今天先看哪些需要尽快过一遍。";
  return "机会没有明显堆积，当前节奏还算顺。";
});

const profitSummary = computed(() => {
  if (Number(last7d.value?.realized_net_profit || 0) > 0)
    return "近 7 天已经跑出正向利润，接下来重点看资金占用和成交效率。";
  return "当前更像在积累样本，先别急着给结果下结论。";
});

const alertSummary = computed(() => {
  if (!alertCount.value)
    return "现在没有需要立刻处理的告警，可以回去盯机会和收益。";
  return `当前最值得先看的是：${alertItems.value[0]?.title || "最新告警"}。`;
});

const serviceSummary = computed(() => {
  if (serviceRunningCount.value === serviceSnapshot.value.length)
    return "核心服务都在线，当前更适合盯业务数据本身。";
  return "有服务没有跑起来，先把服务状态理顺再谈结果。";
});

const setFocus = (key) => {
  activeFocus.value = key;
};

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
.story-card,
.summary-card,
.panel,
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
.story-card h3,
.panel h3 {
  margin: 0;
  color: #303133;
  font-size: 28px;
  font-weight: 600;
}

.hero-panel p,
.story-card p,
.panel-summary,
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
.story-grid,
.summary-grid,
.panel-grid,
.sub-grid {
  display: grid;
  gap: 16px;
}

.pulse-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.story-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
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

.story-card {
  padding: 18px 20px;
}

.story-card h3 {
  margin-top: 10px;
  font-size: 20px;
}

.story-card p {
  margin: 10px 0 0;
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
  .story-grid,
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
  .story-grid,
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .hero-panel,
  .pulse-card,
  .story-card,
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
