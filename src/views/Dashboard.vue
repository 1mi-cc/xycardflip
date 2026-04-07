<template>
  <div class="dashboard-page">
    <section class="hero card hero-dark">
      <div>
        <div class="kicker">管理总览</div>
        <h1>{{ isAdmin ? "先看结果，再看风险与服务" : "工作台首页" }}</h1>
        <p>
          {{
            isAdmin
              ? "首页只保留收益、风险、服务器透明度和观测基线，不再暴露执行参数和人工控制项。"
              : "当前角色只显示精简后的工作区入口，管理员专属数据面板默认隐藏。"
          }}
        </p>
        <div class="hero-tags">
          <n-tag size="small" type="info">角色：{{ currentRoleLabel }}</n-tag>
          <n-tag v-if="isAdmin" size="small" :type="runtime.serverReady ? 'success' : 'error'">
            服务器：{{ runtime.serverReady ? "就绪" : "关注" }}
          </n-tag>
          <n-tag v-if="isAdmin" size="small" :type="operatingModeTagType">
            模式：{{ operatingModeLabel }}
          </n-tag>
          <n-tag size="small" :type="tokenStore.hasTokens ? 'success' : 'default'">
            账号：{{ tokenStore.gameTokens.length }}
          </n-tag>
        </div>
      </div>
      <div class="hero-actions">
        <div class="hero-time">最近刷新</div>
        <div class="hero-stamp">{{ lastRefreshedLabel }}</div>
        <n-button v-if="isAdmin" type="primary" :loading="loading" @click="loadOverview()">刷新数据</n-button>
      </div>
    </section>

    <n-alert v-if="error" type="error" :show-icon="false" class="card">{{ error }}</n-alert>

    <template v-if="isAdmin">
      <section class="summary-grid">
        <article v-for="card in summaryCards" :key="card.id" class="card summary-card">
          <div class="summary-label">{{ card.label }}</div>
          <div class="summary-value">{{ card.value }}</div>
          <div class="summary-foot" :class="card.tone">{{ card.note }}</div>
        </article>
      </section>

      <section class="content-grid">
        <article class="card panel">
          <div class="panel-head">
            <div>
              <div class="kicker">收益</div>
              <h2>收益与库存</h2>
            </div>
            <span class="muted">{{ generatedAtLabel }}</span>
          </div>
          <div class="metric-list">
            <div v-for="item in profitabilityRows" :key="item.label" class="metric-row">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
          <div class="sub-grid">
            <div class="subpanel">
              <div class="subpanel-title">近 7 天来源贡献</div>
              <div v-if="sourceLeaders.length" class="mini-list">
                <div v-for="item in sourceLeaders" :key="item.name" class="metric-row compact">
                  <span>{{ item.name }}</span>
                  <strong>{{ item.value }}</strong>
                </div>
              </div>
              <n-empty v-else size="small" description="暂无来源贡献数据"></n-empty>
            </div>
            <div class="subpanel">
              <div class="subpanel-title">近 7 天卖家贡献</div>
              <div v-if="sellerLeaders.length" class="mini-list">
                <div v-for="item in sellerLeaders" :key="item.name" class="metric-row compact">
                  <span>{{ item.name }}</span>
                  <strong>{{ item.value }}</strong>
                </div>
              </div>
              <n-empty v-else size="small" description="暂无卖家贡献数据"></n-empty>
            </div>
          </div>
        </article>

        <article class="card panel">
          <div class="panel-head">
            <div>
              <div class="kicker">服务</div>
              <h2>服务器透明度</h2>
            </div>
            <span class="muted">{{ runtime.serverReady ? "健康" : "受限" }}</span>
          </div>
          <div class="service-list">
            <div v-for="item in runtimeRows" :key="item.id" class="service-row">
              <div>
                <strong>{{ item.label }}</strong>
                <div class="muted">{{ item.note }}</div>
              </div>
              <div class="service-side">
                <n-tag size="small" :type="item.type">{{ item.value }}</n-tag>
                <span class="muted">{{ item.time }}</span>
              </div>
            </div>
          </div>
          <div v-if="runtime.healthReasons.length" class="reason-wrap">
            <span v-for="reason in runtime.healthReasons" :key="reason" class="reason-pill">{{ reason }}</span>
          </div>
        </article>
      </section>

      <section class="content-grid">
        <article class="card panel">
          <div class="panel-head">
            <div>
              <div class="kicker">风险</div>
              <h2>当前告警</h2>
            </div>
            <span class="muted">{{ alerts.summary.count || 0 }} 条</span>
          </div>
          <div v-if="alerts.items.length" class="alert-list">
            <div v-for="item in alerts.items" :key="item.alert_key" class="alert-row">
              <div class="alert-top">
                <strong>{{ item.title }}</strong>
                <n-tag size="small" :type="severityTagType(item.effective_severity || item.severity)">
                  {{ severityText(item.effective_severity || item.severity) }}
                </n-tag>
              </div>
              <div class="muted">{{ item.message }}</div>
              <div class="alert-meta">
                <span>优先级：{{ item.incident_priority || "-" }}</span>
                <span>责任人：{{ item.incident_owner || "-" }}</span>
                <span>SLA：{{ item.sla_breached ? "已超时" : `${item.sla_remaining_minutes || 0} 分钟` }}</span>
              </div>
            </div>
          </div>
          <n-empty v-else description="当前没有活动告警"></n-empty>
        </article>

        <article class="card panel">
          <div class="panel-head">
            <div>
              <div class="kicker">观测</div>
              <h2>上线与基线</h2>
            </div>
          </div>
          <div class="metric-list">
            <div v-for="item in deploymentRows" :key="item.id" class="metric-row">
              <span>{{ item.title }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
          <div class="reason-wrap">
            <span v-for="item in startupCheckItems" :key="`startup-${item.code}`" class="reason-pill">
              {{ item.code }}
            </span>
            <span v-for="item in guardrailFailureItems" :key="`guard-${item.code}`" class="reason-pill">
              {{ item.code }}
            </span>
          </div>
        </article>
      </section>
    </template>

    <template v-else>
      <section class="summary-grid summary-grid-compact">
        <article v-for="card in limitedCards" :key="card.id" class="card summary-card">
          <div class="summary-label">{{ card.label }}</div>
          <div class="summary-value">{{ card.value }}</div>
          <div class="summary-foot" :class="card.tone">{{ card.note }}</div>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";

import cardFlipApi from "@/api/cardFlip";
import { useAuthStore } from "@/stores/auth";
import { useTokenStore } from "@/stores/tokenStore";

const authStore = useAuthStore();
const tokenStore = useTokenStore();

const loading = ref(false);
const error = ref("");
const overview = ref(null);
const lastRefreshedAt = ref("");
let refreshTimer = 0;

const isAdmin = computed(() => Boolean(authStore.userInfo?.isAdmin));
const currentRoleLabel = computed(() => {
  const roleKeys = Array.isArray(authStore.userInfo?.roleKeys) ? authStore.userInfo.roleKeys : [];
  const role = String(roleKeys[0] || "viewer").toLowerCase();
  if (role === "admin")
    return "管理员";
  if (role === "ops")
    return "运营";
  return "只读";
});

const profit = computed(() => overview.value?.profitability || {});
const cockpit = computed(() => profit.value.profit_cockpit || {});
const runtime = computed(() => ({
  serverReady: Boolean(overview.value?.runtime?.server_ready),
  healthReasons: Array.isArray(overview.value?.runtime?.health_reasons) ? overview.value.runtime.health_reasons : [],
  automation: overview.value?.runtime?.automation || {},
  services: overview.value?.runtime?.services || {},
}));
const alerts = computed(() => ({
  summary: overview.value?.alerts?.summary || { count: 0, counts_by_severity: { error: 0, warning: 0, info: 0 } },
  items: Array.isArray(overview.value?.alerts?.items) ? overview.value.alerts.items.slice(0, 6) : [],
}));
const deploymentReadiness = computed(() => overview.value?.deployment_readiness || {});
const operatingProfile = computed(() => overview.value?.runtime?.operating_profile || deploymentReadiness.value.operating_profile || {});
const validationBaseline = computed(() => deploymentReadiness.value.validation_baseline || {});
const latestHourlyBaseline = computed(() =>
  Array.isArray(validationBaseline.value.snapshot_history?.hourly)
    ? validationBaseline.value.snapshot_history.hourly.slice(-1)[0] || null
    : null,
);
const today = computed(() => cockpit.value.today || {});
const last7d = computed(() => cockpit.value.last_7d || {});
const inventory = computed(() => cockpit.value.inventory || {});
const sourceLeaders = computed(() =>
  (Array.isArray(cockpit.value.source_leaderboard_7d) ? cockpit.value.source_leaderboard_7d : [])
    .slice(0, 4)
    .map(item => ({ name: String(item.source || "未知来源"), value: formatMoney(item.realized_net_profit || 0) })),
);
const sellerLeaders = computed(() =>
  (Array.isArray(cockpit.value.seller_leaderboard_7d) ? cockpit.value.seller_leaderboard_7d : [])
    .slice(0, 4)
    .map(item => ({ name: String(item.seller_id || "未知卖家"), value: formatMoney(item.realized_net_profit || 0) })),
);

const generatedAtLabel = computed(() => formatTimestamp(overview.value?.generated_at));
const lastRefreshedLabel = computed(() => lastRefreshedAt.value || "等待首次刷新");
const operatingModeLabel = computed(() => String(operatingProfile.value?.mode_label || "标准"));
const operatingModeTagType = computed(() => {
  if (!operatingProfile.value?.enabled)
    return "default";
  return operatingProfile.value?.aligned ? "success" : "warning";
});
const guardrailFailureItems = computed(() =>
  (Array.isArray(operatingProfile.value?.items) ? operatingProfile.value.items : []).filter(item => !item?.ok),
);
const startupCheckItems = computed(() =>
  (Array.isArray(deploymentReadiness.value?.startup_checks?.items) ? deploymentReadiness.value.startup_checks.items : []).slice(0, 6),
);

const summaryCards = computed(() => [
  { id: "today", label: "今日净利", value: formatMoney(today.value.realized_net_profit || 0), note: `${today.value.sold_count || 0} 笔卖出`, tone: moneyTone(today.value.realized_net_profit || 0) },
  { id: "week", label: "近 7 天净利", value: formatMoney(last7d.value.realized_net_profit || 0), note: `平均 ROI ${formatPercent(last7d.value.avg_realized_roi || 0)}`, tone: moneyTone(last7d.value.realized_net_profit || 0) },
  { id: "capital", label: "在途资金", value: formatMoney(inventory.value.deployed_capital || 0), note: `${inventory.value.active_trade_count || 0} 笔进行中 / ${inventory.value.listed_trade_count || 0} 笔已挂售`, tone: "neutral" },
  { id: "review", label: "待审机会", value: formatInteger(profit.value.pending_review_count || 0), note: `${profit.value.total_trade_count || 0} 笔累计交易`, tone: "neutral" },
  { id: "alerts", label: "活动告警", value: formatInteger(alerts.value.summary.count || 0), note: `${alerts.value.summary.counts_by_severity?.error || 0} 条严重 / ${alerts.value.summary.counts_by_severity?.warning || 0} 条预警`, tone: alerts.value.summary.count > 0 ? "warning" : "positive" },
  { id: "baseline", label: "观测基线", value: validationBaseline.value.ready ? "就绪" : String(validationBaseline.value.status || "观察中"), note: latestHourlyBaseline.value ? `${latestHourlyBaseline.value.direction || "平稳"}` : "暂无快照", tone: validationBaseline.value.ready ? "positive" : "warning" },
]);

const profitabilityRows = computed(() => [
  { label: "累计毛利", value: formatMoney(profit.value.gross_profit || 0) },
  { label: "利润命中率", value: formatPercent(profit.value.profit_hit_rate || 0) },
  { label: "平均持有天数", value: `${formatNumber(profit.value.avg_holding_days || 0, 1)} 天` },
  { label: "中位持有天数", value: `${formatNumber(profit.value.median_holding_days || 0, 1)} 天` },
  { label: "预期退出价差", value: formatMoney(inventory.value.expected_exit_spread || 0) },
  { label: "目标退出价值", value: formatMoney(inventory.value.target_exit_value || 0) },
]);

const runtimeRows = computed(() => {
  const services = runtime.value.services || {};
  const automation = runtime.value.automation || {};
  return [
    { id: "automation", label: "自动化总控", value: automation.all_running ? "运行中" : "部分运行", note: automation.busy ? "后台正在执行任务" : "后台编排服务", type: automation.all_running ? "success" : "warning", time: formatTimestamp(automation.last_run_at) },
    { id: "monitor", label: "市场监听", value: services.monitor?.is_running ? "运行中" : "已停止", note: services.monitor?.circuit_open ? "熔断中" : "采集服务", type: services.monitor?.is_running ? "success" : "default", time: formatTimestamp(services.monitor?.last_run_at) },
    { id: "autotrade", label: "自动交易审批", value: services.autotrade?.running ? "运行中" : "已停止", note: `累计审批 ${services.autotrade?.total_approved || 0} 笔`, type: services.autotrade?.running ? "success" : "default", time: formatTimestamp(services.autotrade?.last_run_at) },
    { id: "retry", label: "执行重试", value: services.execution_retry?.running ? "运行中" : "已停止", note: `累计重试 ${services.execution_retry?.total_retried || 0} 次`, type: services.execution_retry?.running ? "success" : "default", time: formatTimestamp(services.execution_retry?.last_run_at) },
  ];
});

const deploymentRows = computed(() => {
  const executionReady = deploymentReadiness.value.execution_readiness || {};
  const alertDelivery = deploymentReadiness.value.alert_delivery || {};
  return [
    { id: "mode", title: "运行模式", value: operatingModeLabel.value },
    { id: "baseline", title: "基线状态", value: validationBaseline.value.ready ? "就绪" : String(validationBaseline.value.status || "观察中") },
    { id: "tune", title: "可调参", value: validationBaseline.value.ready_for_tune ? "是" : "否" },
    { id: "scale", title: "可扩量", value: validationBaseline.value.ready_for_scale ? "是" : "否" },
    { id: "live", title: "实盘执行", value: executionReady.live_ready ? "就绪" : "未就绪" },
    { id: "alerts", title: "告警通道", value: alertDelivery.email_ready || alertDelivery.slack_ready || alertDelivery.telegram_ready || alertDelivery.webhook_ready ? "可用" : "离线" },
  ];
});

const limitedCards = computed(() => [
  { id: "tokens", label: "已导入账号", value: formatInteger(tokenStore.gameTokens.length), note: tokenStore.hasTokens ? "账号工作区已就绪" : "当前还没有导入账号", tone: tokenStore.hasTokens ? "positive" : "warning" },
  { id: "role", label: "当前角色", value: currentRoleLabel.value, note: "管理员专属面板默认隐藏", tone: "neutral" },
]);

const loadOverview = async () => {
  if (!isAdmin.value)
    return;
  loading.value = true;
  try {
    overview.value = await cardFlipApi.getAdminTransparencyOverview();
    error.value = "";
    lastRefreshedAt.value = new Date().toLocaleString("zh-CN", { hour12: false });
  } catch (requestError) {
    error.value = requestError?.message || "加载数据失败";
  } finally {
    loading.value = false;
  }
};

const startAutoRefresh = () => {
  stopAutoRefresh();
  refreshTimer = window.setInterval(() => {
    loadOverview();
  }, 30000);
};

const stopAutoRefresh = () => {
  if (refreshTimer) {
    window.clearInterval(refreshTimer);
    refreshTimer = 0;
  }
};

const formatMoney = value => new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY", maximumFractionDigits: 2 }).format(Number(value || 0));
const formatPercent = value => `${formatNumber(Number(value || 0) * 100, 1)}%`;
const formatInteger = value => new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(Number(value || 0));
const formatNumber = (value, digits = 2) => new Intl.NumberFormat("zh-CN", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(value || 0));
const moneyTone = value => (Number(value || 0) > 0 ? "positive" : Number(value || 0) < 0 ? "warning" : "neutral");
const formatTimestamp = (value) => {
  const text = String(value || "").trim();
  if (!text)
    return "暂无";
  const parsed = new Date(text);
  return Number.isNaN(parsed.getTime()) ? text : parsed.toLocaleString("zh-CN", { hour12: false });
};
const severityText = (value) => {
  const text = String(value || "").toLowerCase();
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

onMounted(() => {
  tokenStore.initTokenStore();
  if (isAdmin.value) {
    loadOverview();
    startAutoRefresh();
  }
});

onUnmounted(() => {
  stopAutoRefresh();
});
</script>

<style scoped lang="scss">
.dashboard-page {
  display: grid;
  gap: 20px;
  padding: 4px;
}

.card {
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 3px 20px rgba(0, 0, 0, 0.08);
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) 260px;
  gap: 20px;
  padding: 32px;
}

.hero-dark {
  background: #000;
  color: #fff;
}

.kicker {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 980px;
  background: rgba(255, 255, 255, 0.08);
  color: #2997ff;
  font-family: "SF Pro Text", "SF Pro Icons", "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: -0.12px;
}

.hero h1 {
  margin: 16px 0 12px;
  font-family: "SF Pro Display", "SF Pro Icons", "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: clamp(36px, 4vw, 56px);
  font-weight: 600;
  line-height: 1.07;
  letter-spacing: -0.28px;
}

.hero p {
  max-width: 760px;
  color: rgba(255, 255, 255, 0.8);
  font-size: 17px;
  line-height: 1.47;
  letter-spacing: -0.374px;
}

.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 18px;
}

.hero-actions {
  display: grid;
  align-content: start;
  justify-items: end;
  gap: 10px;
}

.hero-time {
  color: rgba(255, 255, 255, 0.6);
  font-size: 12px;
}

.hero-stamp {
  font-size: 18px;
  font-weight: 600;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.summary-grid-compact {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.summary-card {
  padding: 20px;
  display: grid;
  gap: 8px;
}

.summary-label {
  color: rgba(0, 0, 0, 0.48);
  font-size: 12px;
}

.summary-value {
  color: #1d1d1f;
  font-family: "SF Pro Display", "SF Pro Icons", "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 32px;
  font-weight: 600;
  line-height: 1.1;
}

.summary-foot {
  color: rgba(0, 0, 0, 0.8);
  font-size: 14px;
  line-height: 1.43;
}

.summary-foot.warning {
  color: #c2410c;
}

.summary-foot.positive {
  color: #15803d;
}

.content-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.panel {
  padding: 24px;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 18px;
}

.panel-head h2 {
  margin: 12px 0 0;
  color: #1d1d1f;
  font-family: "SF Pro Display", "SF Pro Icons", "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 28px;
  font-weight: 400;
  line-height: 1.14;
  letter-spacing: 0.196px;
}

.metric-list,
.mini-list,
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
  border-radius: 12px;
  background: #f5f5f7;
  color: #1d1d1f;
}

.metric-row strong,
.service-row strong,
.alert-row strong {
  color: #1d1d1f;
}

.metric-row,
.service-row,
.alert-row {
  font-size: 14px;
}

.service-row,
.alert-row {
  display: grid;
}

.service-side {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}

.sub-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
}

.subpanel {
  padding: 16px;
  border-radius: 12px;
  background: #f5f5f7;
}

.subpanel-title {
  margin-bottom: 12px;
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 600;
}

.alert-top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}

.muted,
.alert-meta,
.hero-time {
  color: rgba(0, 0, 0, 0.8);
}

.alert-meta,
.reason-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
  font-size: 12px;
}

.reason-pill {
  padding: 6px 10px;
  border-radius: 980px;
  background: rgba(0, 113, 227, 0.08);
  color: #0066cc;
  font-size: 12px;
  font-weight: 600;
}

@media (max-width: 1180px) {
  .hero,
  .summary-grid,
  .content-grid,
  .sub-grid {
    grid-template-columns: 1fr;
  }

  .hero-actions {
    justify-items: start;
  }
}

@media (max-width: 720px) {
  .summary-grid-compact,
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .hero,
  .panel,
  .summary-card {
    padding: 18px;
  }

  .hero h1 {
    font-size: 32px;
  }
}
</style>
