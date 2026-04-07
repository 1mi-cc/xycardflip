<template>
  <div class="page-shell">
    <section class="page-intro">
      <div>
        <div class="section-label">交易看板</div>
        <h2>卡片交易概况</h2>
        <p>这里看机会、成交、收益和风险。参数调整和执行入口已经放到后台，不放在这个页面里。</p>
      </div>
      <n-button type="primary" :loading="loading" @click="loadOverview">刷新</n-button>
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

      <article class="panel">
        <div class="panel-header">
          <div>
            <div class="section-label">服务</div>
            <h3>自动化与服务</h3>
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

      <article class="panel">
        <div class="panel-header">
          <div>
            <div class="section-label">基线</div>
            <h3>运行护栏</h3>
          </div>
        </div>
        <div class="metric-list">
          <div v-for="item in baselineRows" :key="item.label" class="metric-row">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
        <div v-if="baselineCodes.length" class="pill-list">
          <span v-for="code in baselineCodes" :key="code" class="pill">{{ code }}</span>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import { computed } from "vue";

import useExecutiveOverview from "@/composables/useExecutiveOverview";

const {
  alerts,
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

const last7d = computed(() => profitCockpit.value?.last_7d || {});
const inventory = computed(() => profitCockpit.value?.inventory || {});
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
const generatedAt = computed(() => formatTime(overview.value?.generated_at));
const alertItems = computed(() =>
  Array.isArray(alerts.value?.items) ? alerts.value.items.slice(0, 8) : [],
);
const alertCount = computed(() => Number(alerts.value?.summary?.count || 0));

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
    value: String(validationBaseline.value?.status || "观察中"),
    note: String(validationBaseline.value?.direction || "还没有明显方向"),
    tone: validationBaseline.value?.ready ? "positive" : "warning",
  },
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
  { label: "当前状态", value: String(validationBaseline.value?.status || "观察中") },
  { label: "可以调优", value: validationBaseline.value?.ready_for_tune ? "是" : "否" },
  { label: "可以放量", value: validationBaseline.value?.ready_for_scale ? "是" : "否" },
  { label: "运行模式", value: String(deploymentReadiness.value?.operating_profile?.mode_label || "标准") },
  { label: "方向", value: String(validationBaseline.value?.direction || "暂无") },
  { label: "最近建议", value: String(validationBaseline.value?.recommendation || "继续观察") },
]);

const baselineCodes = computed(() => {
  const codes = [];
  if (Array.isArray(validationBaseline.value?.blocking_codes))
    codes.push(...validationBaseline.value.blocking_codes);
  if (Array.isArray(validationBaseline.value?.tune_blocking_codes))
    codes.push(...validationBaseline.value.tune_blocking_codes);
  return [...new Set(codes.filter(Boolean))].slice(0, 10);
});

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
.summary-card,
.panel,
.sub-panel {
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}

.page-intro {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px;
}

.page-intro h2 {
  margin: 8px 0;
  color: #303133;
  font-size: 22px;
  font-weight: 600;
}

.page-intro p {
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
.alert-meta {
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

.alert-row p {
  margin: 8px 0 0;
  line-height: 1.6;
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
  .summary-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .page-intro,
  .panel-grid,
  .sub-grid {
    grid-template-columns: 1fr;
  }

  .page-intro {
    flex-direction: column;
    align-items: stretch;
  }
}

@media (max-width: 640px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .page-intro,
  .panel,
  .summary-card,
  .sub-panel {
    padding: 16px;
  }
}
</style>
