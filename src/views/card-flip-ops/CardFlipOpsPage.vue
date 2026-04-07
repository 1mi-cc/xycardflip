<template>
  <div class="ops-page">
    <section class="hero-panel">
      <div>
        <div class="hero-kicker">卡片数据台</div>
        <h2>只看数据，不看参数</h2>
        <p>
          这里汇总卡片倒卖的经营结果、服务稳定性、风险状态和验证基线。调参、预设、执行控制和批量动作全部从前台撤下。
        </p>
      </div>
      <n-button type="primary" :loading="loading" @click="loadOverview">刷新数据台</n-button>
    </section>

    <n-alert v-if="error" type="error" :show-icon="false">{{ error }}</n-alert>

    <section class="stat-grid">
      <article v-for="card in summaryCards" :key="card.id" class="stat-card">
        <div class="stat-label">{{ card.label }}</div>
        <div class="stat-value">{{ card.value }}</div>
        <div class="stat-note" :class="card.tone">{{ card.note }}</div>
      </article>
    </section>

    <section class="content-grid">
      <article class="panel">
        <div class="panel-head">
          <div>
            <div class="panel-kicker">交易结果</div>
            <h3>收益与库存</h3>
          </div>
          <span>{{ generatedAt }}</span>
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
        <div class="panel-head">
          <div>
            <div class="panel-kicker">后台状态</div>
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

    <section class="content-grid">
      <article class="panel">
        <div class="panel-head">
          <div>
            <div class="panel-kicker">风险状态</div>
            <h3>当前告警与阻塞</h3>
          </div>
          <span>{{ alertItems.length }} 条</span>
        </div>
        <div v-if="alertItems.length" class="alert-list">
          <div v-for="item in alertItems" :key="item.alert_key || item.code" class="alert-row">
            <div class="alert-title">
              <strong>{{ item.title || item.code || "未知告警" }}</strong>
              <n-tag size="small" :type="severityTagType(item.effective_severity || item.severity)">
                {{ severityText(item.effective_severity || item.severity) }}
              </n-tag>
            </div>
            <p>{{ item.message || item.target || "-" }}</p>
          </div>
        </div>
        <n-empty v-else description="当前没有活动告警"></n-empty>
      </article>

      <article class="panel">
        <div class="panel-head">
          <div>
            <div class="panel-kicker">验证基线</div>
            <h3>前向验证与 readiness</h3>
          </div>
        </div>
        <div class="metric-list">
          <div class="metric-row">
            <span>基线状态</span>
            <strong>{{ baselineStatus }}</strong>
          </div>
          <div class="metric-row">
            <span>可调参</span>
            <strong>{{ readyForTune }}</strong>
          </div>
          <div class="metric-row">
            <span>可扩量</span>
            <strong>{{ readyForScale }}</strong>
          </div>
          <div class="metric-row">
            <span>方向</span>
            <strong>{{ baselineDirection }}</strong>
          </div>
          <div class="metric-row">
            <span>最近建议</span>
            <strong>{{ baselineRecommendation }}</strong>
          </div>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import { computed } from "vue";

import useExecutiveOverview from "@/composables/useExecutiveOverview";

const {
  loading,
  error,
  profitability,
  profitCockpit,
  runtime,
  validationBaseline,
  alerts,
  loadOverview,
  formatTime,
} = useExecutiveOverview();

const formatMoney = value => new Intl.NumberFormat("zh-CN", {
  style: "currency",
  currency: "CNY",
  maximumFractionDigits: 2,
}).format(Number(value || 0));
const formatNumber = (value, digits = 1) => new Intl.NumberFormat("zh-CN", {
  minimumFractionDigits: digits,
  maximumFractionDigits: digits,
}).format(Number(value || 0));
const formatPercent = value => `${formatNumber(Number(value || 0) * 100, 1)}%`;
const formatInteger = value => new Intl.NumberFormat("zh-CN", {
  maximumFractionDigits: 0,
}).format(Number(value || 0));

const generatedAt = computed(() => formatTime(runtime.value?.generated_at || runtime.value?.updated_at));
const alertItems = computed(() => Array.isArray(alerts.value?.items) ? alerts.value.items.slice(0, 8) : []);

const summaryCards = computed(() => [
  {
    id: "pending",
    label: "待审机会",
    value: formatInteger(profitability.value?.pending_review_count || 0),
    note: `${profitability.value?.total_trade_count || 0} 笔累计交易`,
    tone: "neutral",
  },
  {
    id: "active",
    label: "进行中交易",
    value: formatInteger(profitability.value?.active_trades_count || 0),
    note: `${profitCockpit.value?.inventory?.listed_trade_count || 0} 笔已挂售`,
    tone: "neutral",
  },
  {
    id: "sold",
    label: "已卖出记录",
    value: formatInteger(profitability.value?.sold_count || 0),
    note: `利润命中率 ${formatPercent(profitability.value?.profit_hit_rate || 0)}`,
    tone: "positive",
  },
  {
    id: "gross",
    label: "累计毛利",
    value: formatMoney(profitability.value?.gross_profit || 0),
    note: `近 7 天净利 ${formatMoney(profitCockpit.value?.last_7d?.realized_net_profit || 0)}`,
    tone: Number(profitability.value?.gross_profit || 0) >= 0 ? "positive" : "warning",
  },
  {
    id: "capital",
    label: "在途资金",
    value: formatMoney(profitCockpit.value?.inventory?.deployed_capital || 0),
    note: `预计价差 ${formatMoney(profitCockpit.value?.inventory?.expected_exit_spread || 0)}`,
    tone: "neutral",
  },
  {
    id: "baseline",
    label: "验证基线",
    value: validationBaseline.value?.ready ? "就绪" : "观察中",
    note: validationBaseline.value?.direction || "暂无方向",
    tone: validationBaseline.value?.ready ? "positive" : "warning",
  },
]);

const profitabilityRows = computed(() => [
  { label: "今日净利", value: formatMoney(profitCockpit.value?.today?.realized_net_profit || 0) },
  { label: "近 7 天净利", value: formatMoney(profitCockpit.value?.last_7d?.realized_net_profit || 0) },
  { label: "平均已实现 ROI", value: formatPercent(profitability.value?.avg_realized_roi || 0) },
  { label: "平均持有天数", value: `${formatNumber(profitability.value?.avg_holding_days || 0, 1)} 天` },
  { label: "中位持有天数", value: `${formatNumber(profitability.value?.median_holding_days || 0, 1)} 天` },
  { label: "目标退出价值", value: formatMoney(profitCockpit.value?.inventory?.target_exit_value || 0) },
]);

const sourceLeaders = computed(() =>
  (Array.isArray(profitCockpit.value?.source_leaderboard_7d) ? profitCockpit.value.source_leaderboard_7d : [])
    .slice(0, 5)
    .map(item => ({
      name: item?.source || "未知来源",
      value: formatMoney(item?.realized_net_profit || 0),
    })),
);

const sellerLeaders = computed(() =>
  (Array.isArray(profitCockpit.value?.seller_leaderboard_7d) ? profitCockpit.value.seller_leaderboard_7d : [])
    .slice(0, 5)
    .map(item => ({
      name: item?.seller_id || "未知卖家",
      value: formatMoney(item?.realized_net_profit || 0),
    })),
);

const runtimeRows = computed(() => [
  {
    label: "市场监听",
    value: runtime.value?.services?.monitor?.is_running ? "运行中" : "已停止",
    note: runtime.value?.services?.monitor?.circuit_open ? "当前熔断中" : "后台采集服务",
    time: formatTime(runtime.value?.services?.monitor?.last_run_at),
    type: runtime.value?.services?.monitor?.is_running ? "success" : "default",
  },
  {
    label: "自动审批",
    value: runtime.value?.services?.autotrade?.running ? "运行中" : "已停止",
    note: `累计审批 ${runtime.value?.services?.autotrade?.total_approved || 0} 笔`,
    time: formatTime(runtime.value?.services?.autotrade?.last_run_at),
    type: runtime.value?.services?.autotrade?.running ? "success" : "default",
  },
  {
    label: "执行重试",
    value: runtime.value?.services?.execution_retry?.running ? "运行中" : "已停止",
    note: `累计重试 ${runtime.value?.services?.execution_retry?.total_retried || 0} 次`,
    time: formatTime(runtime.value?.services?.execution_retry?.last_run_at),
    type: runtime.value?.services?.execution_retry?.running ? "success" : "default",
  },
  {
    label: "服务总状态",
    value: runtime.value?.server_ready ? "就绪" : "受限",
    note: "由健康检查与阻塞原因共同决定",
    time: formatTime(runtime.value?.generated_at),
    type: runtime.value?.server_ready ? "success" : "warning",
  },
]);

const baselineStatus = computed(() => validationBaseline.value?.status || "观察中");
const readyForTune = computed(() => (validationBaseline.value?.ready_for_tune ? "是" : "否"));
const readyForScale = computed(() => (validationBaseline.value?.ready_for_scale ? "是" : "否"));
const baselineDirection = computed(() => validationBaseline.value?.direction || "暂无方向");
const baselineRecommendation = computed(() => validationBaseline.value?.recommendation || "继续观察");

const severityText = (severity) => {
  const text = String(severity || "").toLowerCase();
  if (text === "error")
    return "严重";
  if (text === "warning")
    return "预警";
  return "提示";
};

const severityTagType = (severity) => {
  const text = String(severity || "").toLowerCase();
  if (text === "error")
    return "error";
  if (text === "warning")
    return "warning";
  return "info";
};
</script>

<style scoped lang="scss">
.ops-page {
  display: grid;
  gap: 16px;
}

.hero-panel,
.panel,
.stat-card {
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}

.hero-panel {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 24px;
}

.hero-kicker,
.section-label,
.panel-kicker {
  display: inline-block;
  color: #409eff;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
}

.hero-panel h2,
.panel h3 {
  margin: 10px 0 0;
  color: #303133;
  font-size: 22px;
  font-weight: 600;
}

.hero-panel p {
  margin: 12px 0 0;
  color: #606266;
  line-height: 1.7;
}

.stat-grid,
.content-grid,
.sub-grid {
  display: grid;
  gap: 16px;
}

.stat-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.content-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.sub-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 16px;
}

.stat-card {
  padding: 20px;
}

.stat-label {
  color: #909399;
  font-size: 13px;
}

.stat-value {
  margin-top: 10px;
  color: #303133;
  font-size: 30px;
  font-weight: 700;
  line-height: 1;
}

.stat-note {
  margin-top: 10px;
  color: #606266;
  font-size: 13px;
}

.stat-note.positive {
  color: #67c23a;
}

.stat-note.warning {
  color: #e6a23c;
}

.panel {
  padding: 20px;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
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
  padding: 12px 14px;
  border-radius: 4px;
  background: #f5f7fa;
  color: #606266;
}

.metric-row strong,
.service-row strong,
.alert-row strong {
  color: #303133;
}

.service-row,
.alert-row {
  display: grid;
}

.service-note,
.service-time {
  color: #909399;
  font-size: 13px;
}

.service-side {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.sub-panel {
  padding: 16px;
  border-radius: 4px;
  background: #f5f7fa;
}

.sub-title {
  margin-bottom: 12px;
  color: #303133;
  font-size: 14px;
  font-weight: 600;
}

.compact-list .metric-row {
  padding-left: 0;
  padding-right: 0;
}

.alert-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.alert-row p {
  margin: 10px 0 0;
  color: #606266;
  line-height: 1.6;
}

@media (max-width: 1200px) {
  .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .hero-panel {
    flex-direction: column;
  }

  .content-grid,
  .sub-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .stat-grid {
    grid-template-columns: 1fr;
  }
}
</style>
