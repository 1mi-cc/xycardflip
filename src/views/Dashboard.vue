<template>
  <div class="page-shell">
    <section class="page-intro">
      <div>
        <div class="section-label">总览</div>
        <h2>今天先看什么</h2>
        <p>别先埋头看表。先用一句话判断今天的状态，再决定往下看利润、告警还是服务。</p>
      </div>
      <n-button type="primary" :loading="loading" @click="loadOverview">刷新数据</n-button>
    </section>

    <n-alert v-if="error" type="error" :show-icon="false">{{ error }}</n-alert>

    <section class="story-card">
      <div class="story-head">
        <div>
          <div class="section-label">一句判断</div>
          <h3>{{ spotlight.title }}</h3>
          <p>{{ spotlight.description }}</p>
        </div>
        <div class="story-switch">
          <n-button
            v-for="item in focusOptions"
            :key="item.value"
            size="small"
            :type="focusMode === item.value ? 'primary' : 'default'"
            @click="focusMode = item.value"
          >
            {{ item.label }}
          </n-button>
        </div>
      </div>
      <div class="story-pills">
        <span v-for="item in spotlight.pills" :key="item" class="pill">{{ item }}</span>
      </div>
    </section>

    <section class="summary-grid">
      <article v-for="card in summaryCards" :key="card.label" class="summary-card">
        <div class="summary-label">{{ card.label }}</div>
        <div class="summary-value">{{ card.value }}</div>
        <div class="summary-note" :class="card.tone">{{ card.note }}</div>
      </article>
    </section>

    <section class="panel-grid">
      <article class="panel">
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

      <article class="panel">
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
      <article class="panel">
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

      <article class="panel">
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
        <div class="recommendation-card">
          <div class="recommendation-label">最近建议</div>
          <p>{{ baselineRecommendation }}</p>
        </div>
        <div v-if="baselineSignals.length" class="story-pills">
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
  baselineRecommendation,
  baselineSignals,
  deploymentReadiness,
  error,
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

const spotlight = computed(() => {
  if (focusMode.value === "alerts") {
    return {
      title: alertCount.value > 0 ? `先处理这 ${alertCount.value} 条告警` : "今天没有新的告警压力",
      description: alertCount.value > 0
        ? "先看告警，再决定要不要调整节奏。别一上来就去翻每个指标。"
        : "告警面比较平静，可以把注意力放在利润和成交样本上。",
      pills: [
        `${alertCount.value} 条活动告警`,
        runtime.value?.server_ready ? "服务正常" : "服务需要关注",
        validationBaseline.value?.status || "观察中",
      ],
    };
  }

  if (focusMode.value === "service") {
    const runningCount = (runtime.value?.services
      ? Object.values(runtime.value.services).filter(item => item?.running || item?.is_running).length
      : 0);
    return {
      title: runtime.value?.server_ready ? "服务面基本稳住了" : "先看服务，再谈结果",
      description: runtime.value?.server_ready
        ? "后台服务现在能接任务，接下来重点看成交和利润有没有跟上。"
        : "只要服务状态不稳，利润数字就没法解释，先把运行面看清楚。",
      pills: [
        `运行服务 ${runningCount} 个`,
        runtime.value?.automation?.busy ? "后台正在处理任务" : "当前没有排队任务",
        validationBaseline.value?.ready_for_tune ? "可以调优" : "先继续观察",
      ],
    };
  }

  return {
    title: Number(last7d.value?.realized_net_profit || 0) > 0 ? "利润还在往上走" : "这周利润还没起来",
    description: Number(last7d.value?.realized_net_profit || 0) > 0
      ? "先看近 7 天利润和在途资金，确认这波收益是不是可持续。"
      : "今天先别急着解读大盘，先看样本够不够、监听和审批有没有跑起来。",
    pills: [
      `近 7 天利润 ${formatMoney(last7d.value?.realized_net_profit || 0)}`,
      `在途资金 ${formatMoney(inventory.value?.deployed_capital || 0)}`,
      `平均 ROI ${formatPercent(last7d.value?.avg_realized_roi || 0)}`,
    ],
  };
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
  { label: "可以调优", value: validationBaseline.value?.ready_for_tune ? "是" : "否" },
  { label: "可以放量", value: validationBaseline.value?.ready_for_scale ? "是" : "否" },
  { label: "运行模式", value: String(deploymentReadiness.value?.operating_profile?.mode_label || "标准") },
  { label: "方向", value: String(validationBaseline.value?.direction || "暂无") },
]);

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
.page-shell {
  display: grid;
  gap: 16px;
}

.page-intro,
.story-card,
.summary-card,
.panel,
.sub-panel {
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}

.page-intro,
.story-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.page-intro {
  padding: 20px 24px;
}

.story-card {
  padding: 20px 24px;
  border-left: 4px solid #409eff;
}

.page-intro h2,
.story-card h3 {
  margin: 8px 0;
  color: #303133;
  font-size: 22px;
  font-weight: 600;
}

.page-intro p,
.story-card p {
  margin: 0;
  color: #606266;
  line-height: 1.7;
}

.section-label {
  color: #409eff;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.story-switch,
.story-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.story-pills {
  margin-top: 16px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 16px;
}

.panel-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.summary-card {
  padding: 18px 20px;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.summary-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(0, 21, 41, 0.12);
}

.summary-label {
  color: #909399;
  font-size: 13px;
}

.summary-value {
  margin: 10px 0 8px;
  color: #303133;
  font-size: 28px;
  font-weight: 600;
  line-height: 1;
}

.summary-note {
  color: #606266;
  font-size: 13px;
}

.summary-note.positive {
  color: #67c23a;
}

.summary-note.warning {
  color: #e6a23c;
}

.panel {
  padding: 20px 24px;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
}

.panel-header h3 {
  margin: 8px 0 0;
  color: #303133;
  font-size: 18px;
  font-weight: 600;
}

.panel-meta,
.service-note,
.service-time,
.alert-row p,
.alert-meta,
.recommendation-label {
  color: #909399;
  font-size: 13px;
}

.metric-list,
.service-list,
.alert-list {
  display: grid;
  gap: 12px;
}

.metric-row,
.service-row,
.alert-row,
.recommendation-card {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fafafa;
}

.service-row,
.alert-row,
.recommendation-card {
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

.sub-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 16px;
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

.alert-row p,
.recommendation-card p {
  margin: 8px 0 0;
  line-height: 1.6;
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
  .summary-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .page-intro,
  .story-head,
  .panel-grid,
  .sub-grid {
    grid-template-columns: 1fr;
  }

  .page-intro,
  .story-head {
    flex-direction: column;
    align-items: stretch;
  }
}

@media (max-width: 640px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .page-intro,
  .story-card,
  .panel,
  .summary-card,
  .sub-panel {
    padding: 16px;
  }
}
</style>
