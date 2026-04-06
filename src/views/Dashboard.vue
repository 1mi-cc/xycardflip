<template>
  <div class="dashboard-page">
    <section class="hero card">
      <div>
        <div class="kicker">管理总览</div>
        <h1>{{ isAdmin ? "先看结果，再看风险和服务状态" : "工作台首页" }}</h1>
        <p>
          {{
            isAdmin
              ? "打开软件后直接看到收益、风险、服务状态和观测基线，不再在首页暴露操作参数。"
              : "你当前看到的是精简后的工作台入口，管理员专属的收益和服务器透明度面板会被隐藏。"
          }}
        </p>
        <div class="hero-tags">
          <n-tag size="small" type="info">角色：{{ currentRoleLabel }}</n-tag>
          <n-tag size="small" :type="isAdmin ? 'success' : 'warning'">
            {{ isAdmin ? "已启用管理视图" : "已隐藏管理视图" }}
          </n-tag>
          <n-tag size="small" :type="tokenStore.hasTokens ? 'success' : 'default'">
            账号：{{ tokenStore.gameTokens.length }}
          </n-tag>
          <n-tag v-if="isAdmin" size="small" :type="runtime.serverReady ? 'success' : 'error'">
            服务器：{{ runtime.serverReady ? "就绪" : "关注" }}
          </n-tag>
          <n-tag v-if="isAdmin" size="small" :type="operatingModeTagType">
            模式：{{ operatingModeLabel }}
          </n-tag>
          <n-tag v-if="isAdmin" size="small" :type="streamTagType">
            数据流：{{ streamStatusLabel }}
          </n-tag>
        </div>
      </div>
      <div class="hero-actions">
        <n-button type="primary" @click="router.push('/admin/card-flip-ops')">打开数据总览</n-button>
        <n-button v-if="isAdmin" :loading="loading" @click="loadOverview()">刷新数据</n-button>
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
        <article class="card">
          <div class="panel-head">
            <div>
              <div class="kicker">收益</div>
              <h2>收益快照</h2>
            </div>
            <span class="muted">{{ generatedAtLabel }}</span>
          </div>
          <div class="metric-list">
            <div v-for="item in profitabilityRows" :key="item.label" class="metric-row">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
          <div class="subpanel-grid">
            <div class="subpanel">
              <div class="subpanel-title">近 7 天来源贡献</div>
              <div v-if="sourceLeaders.length" class="mini-list">
                <div v-for="item in sourceLeaders" :key="item.name" class="metric-row">
                  <span>{{ item.name }}</span>
                  <strong>{{ item.value }}</strong>
                </div>
              </div>
              <n-empty v-else size="small" description="暂无来源贡献数据"></n-empty>
            </div>
            <div class="subpanel">
              <div class="subpanel-title">近 7 天卖家贡献</div>
              <div v-if="sellerLeaders.length" class="mini-list">
                <div v-for="item in sellerLeaders" :key="item.name" class="metric-row">
                  <span>{{ item.name }}</span>
                  <strong>{{ item.value }}</strong>
                </div>
              </div>
              <n-empty v-else size="small" description="暂无卖家贡献数据"></n-empty>
            </div>
          </div>
        </article>

        <article class="card">
          <div class="panel-head">
            <div>
              <div class="kicker">服务</div>
              <h2>服务器透明度</h2>
            </div>
            <span class="muted">{{ runtime.healthStatus }}</span>
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
        <article class="card">
          <div class="panel-head">
            <div>
              <div class="kicker">风险</div>
              <h2>活动告警</h2>
            </div>
            <span class="muted">{{ alerts.summary.count || 0 }} 条</span>
          </div>
          <div v-if="alerts.items.length" class="alert-list">
            <div v-for="item in alerts.items" :key="item.alert_key" class="alert-row">
              <div class="alert-top">
                <strong>{{ item.title }}</strong>
                <n-tag size="small" :type="severityTagType(item.effective_severity || item.severity)">
                  {{ item.effective_severity || item.severity }}
                </n-tag>
              </div>
              <div class="muted">{{ item.message }}</div>
              <div class="alert-meta">
                <span>通道：{{ item.delivery_lane || "-" }}</span>
                <span>优先级：{{ item.incident_priority || "-" }}</span>
                <span>责任人：{{ item.incident_owner || "-" }}</span>
                <span>SLA：{{ item.sla_breached ? "已超时" : `${item.sla_remaining_minutes || 0} 分钟` }}</span>
              </div>
            </div>
          </div>
          <n-empty v-else description="当前没有活动告警"></n-empty>
        </article>

        <article class="card">
          <div class="panel-head">
            <div>
              <div class="kicker">部署</div>
              <h2>上线检查</h2>
            </div>
            <span class="muted">{{ lastRefreshedLabel }}</span>
          </div>
          <div class="mini-list">
            <div v-for="item in deploymentRows" :key="item.id" class="activity-row">
              <div class="alert-top">
                <strong>{{ item.title }}</strong>
                <n-tag size="small" :type="item.type">{{ item.value }}</n-tag>
              </div>
              <div>{{ item.message }}</div>
              <div class="muted">{{ item.time }}</div>
            </div>
          </div>
          <div v-if="startupCheckItems.length" class="reason-wrap">
            <span v-for="item in startupCheckItems" :key="item.code" class="reason-pill">
              {{ item.code }}
            </span>
          </div>
          <div v-if="guardrailFailureItems.length" class="reason-wrap">
            <span v-for="item in guardrailFailureItems" :key="item.code" class="reason-pill">
              {{ item.code }}
            </span>
          </div>
        </article>
      </section>
    </template>

    <template v-else>
      <section class="summary-grid">
        <article v-for="card in limitedCards" :key="card.id" class="card summary-card">
          <div class="summary-label">{{ card.label }}</div>
          <div class="summary-value">{{ card.value }}</div>
          <div class="summary-foot" :class="card.tone">{{ card.note }}</div>
        </article>
      </section>

      <section class="content-grid one-column">
        <article class="card">
          <div class="panel-head">
            <div>
              <div class="kicker">入口</div>
              <h2>工作台入口</h2>
            </div>
          </div>
          <div class="quick-grid">
            <button v-for="action in quickActions" :key="action.id" class="quick-card" type="button" @click="router.push(action.action)">
              <div class="quick-title">{{ action.title }}</div>
              <div class="muted">{{ action.description }}</div>
            </button>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import cardFlipApi from "@/api/cardFlip";
import { useAuthStore } from "@/stores/auth";
import { useTokenStore } from "@/stores/tokenStore";

const router = useRouter();
const authStore = useAuthStore();
const tokenStore = useTokenStore();

const loading = ref(false);
const error = ref("");
const overview = ref(null);
const lastRefreshedAt = ref("");
const streamStatus = ref("idle");
const streamError = ref("");
let overviewStreamAbortController = null;
let overviewStreamReconnectTimer = 0;

const isAdmin = computed(() => Boolean(authStore.userInfo?.isAdmin));
const currentRoleLabel = computed(() => {
  const roleKeys = Array.isArray(authStore.userInfo?.roleKeys) ? authStore.userInfo.roleKeys : [];
  const role = String(roleKeys[0] || "viewer").toLowerCase();
  if (role === "admin")
    return "管理员";
  if (role === "ops")
    return "运营";
  if (role === "viewer")
    return "只读";
  return role;
});

const quickActions = [
  { id: "ops", title: "数据总览", description: "查看收益、风险和服务状态。", action: "/admin/card-flip-ops" },
  { id: "sim", title: "模拟盘", description: "查看模拟执行和验证走势。", action: "/admin/card-flip/sim" },
  { id: "docs", title: "使用说明", description: "打开系统说明与运行文档。", action: "/admin/card-flip/docs" },
  { id: "tokens", title: "账号管理", description: "查看已导入的账号与令牌。", action: "/tokens" },
];

const profit = computed(() => overview.value?.profitability || {});
const cockpit = computed(() => profit.value.profit_cockpit || {});
const runtime = computed(() => ({
  serverReady: Boolean(overview.value?.runtime?.server_ready),
  healthStatus: String(overview.value?.runtime?.health_status || "unknown"),
  healthReasons: Array.isArray(overview.value?.runtime?.health_reasons) ? overview.value.runtime.health_reasons : [],
  operatingProfile: overview.value?.runtime?.operating_profile || {},
  automation: overview.value?.runtime?.automation || {},
  services: overview.value?.runtime?.services || {},
}));
const alerts = computed(() => ({
  summary: overview.value?.alerts?.summary || { count: 0, counts_by_severity: { error: 0, warning: 0, info: 0 } },
  items: Array.isArray(overview.value?.alerts?.items) ? overview.value.alerts.items : [],
}));
const deploymentReadiness = computed(() => overview.value?.deployment_readiness || {});
const operatingProfile = computed(() => runtime.value.operatingProfile || deploymentReadiness.value.operating_profile || {});
const validationBaseline = computed(() => deploymentReadiness.value.validation_baseline || {});
const today = computed(() => cockpit.value.today || {});
const last7d = computed(() => cockpit.value.last_7d || {});
const inventory = computed(() => cockpit.value.inventory || {});
const sourceLeaders = computed(() => (Array.isArray(cockpit.value.source_leaderboard_7d) ? cockpit.value.source_leaderboard_7d : []).slice(0, 4).map((item) => ({ name: String(item.source || "未知来源"), value: formatMoney(item.realized_net_profit || 0) })));
const sellerLeaders = computed(() => (Array.isArray(cockpit.value.seller_leaderboard_7d) ? cockpit.value.seller_leaderboard_7d : []).slice(0, 4).map((item) => ({ name: String(item.seller_id || "未知卖家"), value: formatMoney(item.realized_net_profit || 0) })));
const generatedAtLabel = computed(() => formatTimestamp(overview.value?.generated_at));
const lastRefreshedLabel = computed(() => lastRefreshedAt.value || "等待首次刷新");
const streamStatusLabel = computed(() => {
  if (streamStatus.value === "live")
    return "实时";
  if (streamStatus.value === "connecting")
    return "连接中";
  if (streamStatus.value === "reconnecting")
    return "重连中";
  if (streamStatus.value === "error")
    return "降级";
  return "空闲";
});
const streamTagType = computed(() => {
  if (streamStatus.value === "live")
    return "success";
  if (streamStatus.value === "connecting" || streamStatus.value === "reconnecting")
    return "warning";
  if (streamStatus.value === "error")
    return "error";
  return "default";
});
const operatingModeLabel = computed(() => String(operatingProfile.value?.mode_label || "标准"));
const operatingModeTagType = computed(() => {
  if (!operatingProfile.value?.enabled)
    return "default";
  return operatingProfile.value?.aligned ? "success" : "warning";
});
const guardrailFailureItems = computed(() =>
  (Array.isArray(operatingProfile.value?.items) ? operatingProfile.value.items : []).filter((item) => !item?.ok),
);

const summaryCards = computed(() => [
  { id: "today", label: "今日净利", value: formatMoney(today.value.realized_net_profit || 0), note: `${today.value.sold_count || 0} 笔卖出 / 命中 ${formatPercent(today.value.profit_hit_rate || 0)}`, tone: moneyTone(today.value.realized_net_profit || 0) },
  { id: "week", label: "近 7 天净利", value: formatMoney(last7d.value.realized_net_profit || 0), note: `ROI ${formatPercent(last7d.value.avg_realized_roi || 0)}`, tone: moneyTone(last7d.value.realized_net_profit || 0) },
  { id: "capital", label: "在途资金", value: formatMoney(inventory.value.deployed_capital || 0), note: `${inventory.value.active_trade_count || 0} 笔进行中 / ${inventory.value.listed_trade_count || 0} 笔已挂售`, tone: "neutral" },
  { id: "review", label: "待审机会", value: formatInteger(profit.value.pending_review_count || 0), note: `${profit.value.total_trade_count || 0} 笔累计交易`, tone: "neutral" },
  { id: "alerts", label: "活动告警", value: formatInteger(alerts.value.summary.count || 0), note: `${alerts.value.summary.counts_by_severity?.error || 0} 条错误 / ${alerts.value.summary.counts_by_severity?.warning || 0} 条警告`, tone: alerts.value.summary.count > 0 ? "warning" : "positive" },
  { id: "server", label: "服务器状态", value: runtime.value.serverReady ? "就绪" : "关注", note: runtime.value.serverReady ? "后台服务运行正常" : `${runtime.value.healthReasons.length} 项需要关注`, tone: runtime.value.serverReady ? "positive" : "warning" },
]);

const profitabilityRows = computed(() => [
  { label: "累计毛利", value: formatMoney(profit.value.gross_profit || 0) },
  { label: "平均已实现 ROI", value: formatPercent(profit.value.avg_realized_roi || 0) },
  { label: "利润命中率", value: formatPercent(profit.value.profit_hit_rate || 0) },
  { label: "平均持有天数", value: formatNumber(profit.value.avg_holding_days || 0, 1) },
  { label: "中位持有天数", value: formatNumber(profit.value.median_holding_days || 0, 1) },
  { label: "预期退出价差", value: formatMoney(inventory.value.expected_exit_spread || 0) },
]);

const runtimeRows = computed(() => {
  const services = runtime.value.services || {};
  const automation = runtime.value.automation || {};
  return [
    { id: "automation", label: "自动化总控", value: automation.all_running ? "运行中" : "部分运行", note: automation.busy ? "后台正在执行协调任务" : "后台编排服务", type: automation.all_running ? "success" : "warning", time: formatTimestamp(automation.last_run_at) },
    { id: "monitor", label: "市场监听", value: services.monitor?.is_running ? "运行中" : "已停止", note: services.monitor?.circuit_open ? "熔断中" : "采集服务", type: services.monitor?.is_running ? "success" : "default", time: formatTimestamp(services.monitor?.last_run_at) },
    { id: "autotrade", label: "自动交易审批", value: services.autotrade?.running ? "运行中" : "已停止", note: `累计审批 ${services.autotrade?.total_approved || 0} 笔`, type: services.autotrade?.running ? "success" : "default", time: formatTimestamp(services.autotrade?.last_run_at) },
    { id: "retry", label: "执行重试", value: services.execution_retry?.running ? "运行中" : "已停止", note: `累计重试 ${services.execution_retry?.total_retried || 0} 笔`, type: services.execution_retry?.running ? "success" : "default", time: formatTimestamp(services.execution_retry?.last_run_at) },
    { id: "supabase", label: "同步服务", value: services.supabase_sync?.is_running ? "运行中" : "空闲", note: services.supabase_sync?.configured ? "复制链路已配置" : "复制链路未启用", type: services.supabase_sync?.is_running ? "success" : services.supabase_sync?.configured ? "warning" : "default", time: formatUnixTimestamp(services.supabase_sync?.last_run_at_unix) },
  ];
});

const activityFeed = computed(() => {
  const services = runtime.value.services || {};
  return [
    { id: "refresh", title: "Overview Refresh", message: `Admin snapshot generated at ${generatedAtLabel.value}.`, time: lastRefreshedLabel.value },
    { id: "profit", title: "Today Profit", message: `${formatMoney(today.value.realized_net_profit || 0)} across ${today.value.sold_count || 0} sold trades.`, time: generatedAtLabel.value },
    { id: "monitor", title: "Monitor State", message: services.monitor?.is_running ? "Market monitor is still running on the server." : `Market monitor stopped${services.monitor?.last_error ? `: ${services.monitor.last_error}` : ""}.`, time: formatTimestamp(services.monitor?.last_run_at) },
    { id: "autotrade", title: "Autotrade State", message: services.autotrade?.running ? `Autotrade approved ${services.autotrade?.total_approved || 0} items so far.` : `Autotrade is not running${services.autotrade?.last_error ? `: ${services.autotrade.last_error}` : ""}.`, time: formatTimestamp(services.autotrade?.last_run_at) },
  ];
});

const startupChecks = computed(() => deploymentReadiness.value.startup_checks || { status: "ok", count: 0, items: [] });
const startupCheckItems = computed(() => (Array.isArray(startupChecks.value.items) ? startupChecks.value.items : []).slice(0, 6));
const deploymentRows = computed(() => {
  const executionReady = deploymentReadiness.value.execution_readiness || {};
  const alertDelivery = deploymentReadiness.value.alert_delivery || {};
  const autoStart = deploymentReadiness.value.auto_start || {};
  const latestHourlyBaseline = Array.isArray(validationBaseline.value.snapshot_history?.hourly)
    ? validationBaseline.value.snapshot_history.hourly.slice(-1)[0]
    : null;
  return [
    {
      id: "operating-mode",
      title: "运行模式",
      value: operatingProfile.value.mode_label || "标准",
      type: !operatingProfile.value.enabled ? "default" : operatingProfile.value.aligned ? "success" : "warning",
      message: operatingProfile.value.enabled
        ? (operatingProfile.value.aligned
            ? `单账号本地护栏已与 ${operatingProfile.value.strategy_profile || "balanced"} 策略对齐。`
            : `护栏漂移：${(operatingProfile.value.failing_codes || []).join(", ") || "需要复核"}`)
        : `当前未启用单账号模式。策略档位：${operatingProfile.value.strategy_profile || "balanced"}。`,
      time: generatedAtLabel.value,
    },
    {
      id: "validation-baseline",
      title: "观测基线",
      value: validationBaseline.value.ready ? "就绪" : validationBaseline.value.status || "观察中",
      type: validationBaseline.value.ready ? "success" : validationBaseline.value.status === "blocked" ? "error" : "warning",
      message: latestHourlyBaseline
        ? `最近 ${latestHourlyBaseline.bucket_type || "小时"} 快照：${latestHourlyBaseline.status || "-"} / ${latestHourlyBaseline.direction || "平稳"}`
        : validationBaseline.value.timeline?.summary
        || validationBaseline.value.recommendation
        || `基线阻塞：${(validationBaseline.value.blocking_codes || []).join(", ") || "继续观察"}`,
      time: generatedAtLabel.value,
    },
    {
      id: "startup-checks",
      title: "启动检查",
      value: String(startupChecks.value.status || "ok"),
      type: startupChecks.value.status === "critical" ? "error" : startupChecks.value.status === "warning" ? "warning" : "success",
      message: startupChecks.value.count ? `${startupChecks.value.count} 项启动检查仍需关注。` : "当前没有启动阻塞项。",
      time: generatedAtLabel.value,
    },
    {
      id: "live-execution",
      title: "实盘执行",
      value: executionReady.live_ready ? "就绪" : "未就绪",
      type: executionReady.live_ready ? "success" : executionReady.live_enabled ? "warning" : "default",
      message: executionReady.live_enabled
        ? (executionReady.live_ready ? "Webhook 执行链已完整配置。" : `缺失项：${(executionReady.missing || []).join(", ") || "未知"}`)
        : "当前未启用实盘执行。",
      time: generatedAtLabel.value,
    },
    {
      id: "alert-channels",
      title: "告警通道",
      value: alertDelivery.email_ready || alertDelivery.slack_ready || alertDelivery.telegram_ready || alertDelivery.webhook_ready ? "可用" : "离线",
      type: alertDelivery.email_ready || alertDelivery.slack_ready || alertDelivery.telegram_ready || alertDelivery.webhook_ready ? "success" : "warning",
      message: `邮件 ${boolWord(alertDelivery.email_ready)} / Slack ${boolWord(alertDelivery.slack_ready)} / Telegram ${boolWord(alertDelivery.telegram_ready)} / Webhook ${boolWord(alertDelivery.webhook_ready)}`,
      time: generatedAtLabel.value,
    },
    {
      id: "auto-start",
      title: "自动启动",
      value: Object.values(autoStart).some(Boolean) ? "已配置" : "手动",
      type: Object.values(autoStart).some(Boolean) ? "success" : "warning",
      message: `监听 ${boolWord(autoStart.monitor)} / 自动交易 ${boolWord(autoStart.autotrade)} / 重试 ${boolWord(autoStart.execution_retry)} / 同步 ${boolWord(autoStart.supabase_sync)}`,
      time: generatedAtLabel.value,
    },
  ];
});

const limitedCards = computed(() => [
  { id: "tokens", label: "已导入账号", value: formatInteger(tokenStore.gameTokens.length), note: tokenStore.hasTokens ? "账号工作区已就绪" : "当前还没有导入账号", tone: tokenStore.hasTokens ? "positive" : "warning" },
  { id: "selected", label: "当前账号", value: tokenStore.selectedToken?.name || "未选择", note: tokenStore.selectedToken?.server || "先选择一个账号再继续", tone: tokenStore.selectedToken ? "positive" : "warning" },
  { id: "role", label: "当前角色", value: currentRoleLabel.value, note: "管理员专属的服务器透明度面板已隐藏", tone: "neutral" },
]);

const loadOverview = async ({ silent = false } = {}) => {
  if (!isAdmin.value) return;
  if (!silent) loading.value = true;
  try {
    if (!streamError.value)
      error.value = "";
    overview.value = await cardFlipApi.getAdminTransparencyOverview();
    lastRefreshedAt.value = new Date().toLocaleString("en-US", { hour12: false });
  } catch (requestError) {
    error.value = requestError?.message || "Failed to load admin overview";
  } finally {
    loading.value = false;
  }
};

const clearOverviewReconnectTimer = () => {
  if (overviewStreamReconnectTimer) {
    window.clearTimeout(overviewStreamReconnectTimer);
    overviewStreamReconnectTimer = 0;
  }
};

const closeOverviewStream = () => {
  clearOverviewReconnectTimer();
  if (overviewStreamAbortController) {
    overviewStreamAbortController.abort();
    overviewStreamAbortController = null;
  }
};

const handleOverviewStreamChunk = (chunk) => {
  const lines = String(chunk || "").split(/\r?\n/);
  let eventName = "message";
  const dataLines = [];
  for (const line of lines) {
    if (line.startsWith("event:"))
      eventName = line.slice(6).trim();
    else if (line.startsWith("data:"))
      dataLines.push(line.slice(5).trim());
  }
  const dataText = dataLines.join("\n");
  if (!dataText)
    return;
  if (eventName === "overview") {
    try {
      overview.value = JSON.parse(dataText);
      lastRefreshedAt.value = new Date().toLocaleString("en-US", { hour12: false });
      streamError.value = "";
      error.value = "";
    } catch (parseError) {
      streamError.value = parseError?.message || "Failed to parse live overview payload";
      error.value = streamError.value;
    }
    return;
  }
  if (eventName === "heartbeat") {
    streamError.value = "";
  }
};

const scheduleOverviewReconnect = () => {
  clearOverviewReconnectTimer();
  streamStatus.value = "reconnecting";
  overviewStreamReconnectTimer = window.setTimeout(() => {
    connectOverviewStream();
  }, 3000);
};

const connectOverviewStream = async () => {
  if (!isAdmin.value || !authStore.token)
    return;
  closeOverviewStream();
  streamStatus.value = "connecting";
  const controller = new AbortController();
  overviewStreamAbortController = controller;

  try {
    const response = await cardFlipApi.openAdminTransparencyOverviewStream({
      signal: controller.signal,
      intervalSeconds: 5,
    });
    if (!response.ok) {
      const streamResponseError = new Error(`overview stream failed: ${response.status}`);
      streamResponseError.status = response.status;
      throw streamResponseError;
    }
    if (!response.body) {
      throw new Error("overview stream body missing");
    }
    streamStatus.value = "live";
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done)
        break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split(/\r?\n\r?\n/);
      buffer = chunks.pop() || "";
      for (const chunk of chunks) {
        handleOverviewStreamChunk(chunk);
      }
    }
    if (!controller.signal.aborted)
      throw new Error("overview stream closed");
  } catch (streamFailure) {
    if (controller.signal.aborted)
      return;
    streamError.value = streamFailure?.message || "overview stream disconnected";
    error.value = streamError.value;
    streamStatus.value = "error";
    await loadOverview({ silent: true });
    const status = Number(streamFailure?.status || 0);
    if (![401, 403].includes(status))
      scheduleOverviewReconnect();
  }
};

const formatMoney = (value) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(Number(value || 0));
const formatPercent = (value) => `${new Intl.NumberFormat("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(value || 0))}%`;
const formatInteger = (value) => new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(Number(value || 0));
const formatNumber = (value, digits = 2) => new Intl.NumberFormat("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(value || 0));
const boolWord = (value) => (value ? "已就绪" : "关闭");
const moneyTone = (value) => (Number(value || 0) > 0 ? "positive" : Number(value || 0) < 0 ? "warning" : "neutral");
const formatTimestamp = (value) => {
  const text = String(value || "").trim();
  if (!text) return "No recent signal";
  const parsed = new Date(text);
  return Number.isNaN(parsed.getTime()) ? text : parsed.toLocaleString("en-US", { hour12: false });
};
const formatUnixTimestamp = (value) => (Number(value || 0) ? new Date(Number(value) * 1000).toLocaleString("en-US", { hour12: false }) : "No recent sync");
const severityTagType = (severity) => {
  const text = String(severity || "").toLowerCase();
  if (text === "error") return "error";
  if (text === "warning") return "warning";
  return "info";
};

onMounted(() => {
  tokenStore.initTokenStore();
  if (isAdmin.value) {
    loadOverview();
    connectOverviewStream();
  }
});

onUnmounted(() => {
  closeOverviewStream();
});

watch(isAdmin, (nextIsAdmin) => {
  error.value = "";
  streamError.value = "";
  if (nextIsAdmin) {
    loadOverview();
    connectOverviewStream();
  } else {
    closeOverviewStream();
    streamStatus.value = "idle";
    overview.value = null;
  }
});
</script>

<style scoped lang="scss">
.dashboard-page { display: grid; gap: 20px; padding: 4px; }
.card { border: 1px solid var(--border-light); background: var(--panel-bg); box-shadow: var(--shadow-light); border-radius: 16px; padding: 22px 24px; }
.hero { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr); gap: 20px; }
.kicker { display: inline-flex; padding: 4px 10px; border-radius: 999px; background: var(--primary-color-light); color: var(--primary-color); font-size: 12px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }
.hero h1 { margin: 16px 0 10px; font-size: clamp(28px, 3vw, 40px); line-height: 1.08; color: var(--text-primary); }
.hero p { margin: 0; color: var(--text-secondary); line-height: 1.8; max-width: 760px; }
.hero-tags, .hero-actions { display: flex; flex-wrap: wrap; gap: 10px; }
.hero-tags { margin-top: 18px; }
.hero-actions { align-content: start; justify-content: flex-end; }
.summary-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.summary-card { display: grid; gap: 8px; }
.summary-label, .muted { color: var(--text-tertiary); font-size: 13px; }
.summary-value { color: var(--text-primary); font-size: 24px; line-height: 1.1; font-weight: 700; }
.summary-foot { color: var(--text-secondary); font-size: 13px; }
.summary-foot.warning { color: var(--warning-color); }
.summary-foot.positive { color: var(--success-color); }
.content-grid { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(340px, 0.8fr); gap: 20px; }
.content-grid.one-column { grid-template-columns: 1fr; }
.panel-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; margin-bottom: 18px; }
.panel-head h2 { margin: 10px 0 0; color: var(--text-primary); font-size: 24px; line-height: 1.1; }
.metric-list, .mini-list, .service-list, .alert-list { display: grid; gap: 12px; }
.metric-row, .service-row, .alert-row, .activity-row { display: flex; justify-content: space-between; gap: 12px; padding: 14px 16px; border-radius: 14px; background: #fafcff; border: 1px solid var(--border-light); color: #0f172a; }
.metric-row span, .metric-row strong, .service-row strong, .service-row .muted, .activity-row strong, .activity-row div, .alert-row strong, .alert-row div, .alert-meta span { color: #0f172a; }
.service-row .muted, .activity-row .muted, .alert-row .muted { color: #475569; }
.service-row, .activity-row, .alert-row { display: grid; }
.service-side { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.subpanel-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-top: 18px; }
.subpanel { padding: 16px; border-radius: 14px; background: #fafcff; border: 1px solid var(--border-light); color: #0f172a; }
.subpanel-title { margin-bottom: 12px; color: var(--text-primary); font-size: 14px; font-weight: 700; }
.reason-wrap, .alert-meta { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.reason-pill { padding: 6px 10px; border-radius: 999px; background: rgba(197, 48, 48, 0.08); color: #c53030; font-size: 12px; font-weight: 600; }
.alert-top { display: flex; justify-content: space-between; gap: 10px; align-items: center; }
.quick-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.quick-card { padding: 16px; border: 1px solid var(--border-light); border-radius: 14px; background: linear-gradient(180deg, #fff 0%, #f9fbff 100%); text-align: left; transition: transform var(--transition-fast), box-shadow var(--transition-fast), border-color var(--transition-fast); }
.quick-card:hover { transform: translateY(-2px); border-color: rgba(64, 158, 255, 0.35); box-shadow: var(--shadow-light); }
.quick-title { margin: 0 0 8px; color: var(--text-primary); font-size: 16px; font-weight: 700; }
@media (max-width: 1180px) { .hero, .summary-grid, .content-grid, .subpanel-grid { grid-template-columns: 1fr; } .hero-actions { justify-content: flex-start; } }
@media (max-width: 720px) { .quick-grid { grid-template-columns: 1fr; } .card { padding: 20px; } .hero h1 { font-size: 28px; } }
</style>
