<template>
  <div class="dashboard-page">
    <section class="hero card">
      <div>
        <div class="kicker">Admin Transparency</div>
        <h1>{{ isAdmin ? "Profit and runtime at first glance" : "Workspace landing page" }}</h1>
        <p>
          {{
            isAdmin
              ? "Open the software and immediately see P&L, service health, alert pressure, and whether the server-side automation stack is still running."
              : "Your role keeps the operational entry points, but admin-only profitability and server transparency panels remain hidden."
          }}
        </p>
        <div class="hero-tags">
          <n-tag size="small" type="info">Role: {{ currentRoleLabel }}</n-tag>
          <n-tag size="small" :type="isAdmin ? 'success' : 'warning'">
            {{ isAdmin ? "Admin-only visibility enabled" : "Admin-only visibility hidden" }}
          </n-tag>
          <n-tag size="small" :type="tokenStore.hasTokens ? 'success' : 'default'">
            Tokens: {{ tokenStore.gameTokens.length }}
          </n-tag>
          <n-tag v-if="isAdmin" size="small" :type="runtime.serverReady ? 'success' : 'error'">
            Server: {{ runtime.serverReady ? "ready" : "attention" }}
          </n-tag>
          <n-tag v-if="isAdmin" size="small" :type="operatingModeTagType">
            Mode: {{ operatingModeLabel }}
          </n-tag>
          <n-tag v-if="isAdmin" size="small" :type="streamTagType">
            Stream: {{ streamStatusLabel }}
          </n-tag>
        </div>
      </div>
      <div class="hero-actions">
        <n-button type="primary" @click="router.push('/admin/card-flip-ops')">Open Ops Console</n-button>
        <n-button @click="router.push('/tokens')">Manage Tokens</n-button>
        <n-button v-if="isAdmin" :loading="loading" @click="loadOverview()">Refresh</n-button>
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
              <div class="kicker">Profitability</div>
              <h2>Live P&L Snapshot</h2>
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
              <div class="subpanel-title">Top Sources (7d)</div>
              <div v-if="sourceLeaders.length" class="mini-list">
                <div v-for="item in sourceLeaders" :key="item.name" class="metric-row">
                  <span>{{ item.name }}</span>
                  <strong>{{ item.value }}</strong>
                </div>
              </div>
              <n-empty v-else size="small" description="No source leaderboard yet"></n-empty>
            </div>
            <div class="subpanel">
              <div class="subpanel-title">Top Sellers (7d)</div>
              <div v-if="sellerLeaders.length" class="mini-list">
                <div v-for="item in sellerLeaders" :key="item.name" class="metric-row">
                  <span>{{ item.name }}</span>
                  <strong>{{ item.value }}</strong>
                </div>
              </div>
              <n-empty v-else size="small" description="No seller leaderboard yet"></n-empty>
            </div>
          </div>
        </article>

        <article class="card">
          <div class="panel-head">
            <div>
              <div class="kicker">Runtime</div>
              <h2>Server Transparency</h2>
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
              <div class="kicker">Alerts</div>
              <h2>Active Incident Watch</h2>
            </div>
            <span class="muted">{{ alerts.summary.count || 0 }} active</span>
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
                <span>lane: {{ item.delivery_lane || "-" }}</span>
                <span>priority: {{ item.incident_priority || "-" }}</span>
                <span>owner: {{ item.incident_owner || "-" }}</span>
                <span>SLA: {{ item.sla_breached ? "breached" : `${item.sla_remaining_minutes || 0}m left` }}</span>
              </div>
            </div>
          </div>
          <n-empty v-else description="No active alerts"></n-empty>
        </article>

        <article class="card">
          <div class="panel-head">
            <div>
              <div class="kicker">Deployment Readiness</div>
              <h2>Go-Live Checks</h2>
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
              <div class="kicker">Quick Access</div>
              <h2>Workspace Entry Points</h2>
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
  return String(roleKeys[0] || "viewer").toUpperCase();
});

const quickActions = [
  { id: "ops", title: "Ops Console", description: "Inspect automation and incident watch.", action: "/admin/card-flip-ops" },
  { id: "sim", title: "Simulation Board", description: "Review dry-run execution trends.", action: "/admin/card-flip/sim" },
  { id: "docs", title: "Runbook", description: "Open the operating guide.", action: "/admin/card-flip/docs" },
  { id: "tokens", title: "Token Workspace", description: "Manage imported accounts.", action: "/tokens" },
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
const sourceLeaders = computed(() => (Array.isArray(cockpit.value.source_leaderboard_7d) ? cockpit.value.source_leaderboard_7d : []).slice(0, 4).map((item) => ({ name: String(item.source || "Unknown"), value: formatMoney(item.realized_net_profit || 0) })));
const sellerLeaders = computed(() => (Array.isArray(cockpit.value.seller_leaderboard_7d) ? cockpit.value.seller_leaderboard_7d : []).slice(0, 4).map((item) => ({ name: String(item.seller_id || "Unknown"), value: formatMoney(item.realized_net_profit || 0) })));
const generatedAtLabel = computed(() => formatTimestamp(overview.value?.generated_at));
const lastRefreshedLabel = computed(() => lastRefreshedAt.value || "Waiting for first refresh");
const streamStatusLabel = computed(() => {
  if (streamStatus.value === "live")
    return "live";
  if (streamStatus.value === "connecting")
    return "connecting";
  if (streamStatus.value === "reconnecting")
    return "reconnecting";
  if (streamStatus.value === "error")
    return "degraded";
  return "idle";
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
const operatingModeLabel = computed(() => String(operatingProfile.value?.mode_label || "Standard"));
const operatingModeTagType = computed(() => {
  if (!operatingProfile.value?.enabled)
    return "default";
  return operatingProfile.value?.aligned ? "success" : "warning";
});
const guardrailFailureItems = computed(() =>
  (Array.isArray(operatingProfile.value?.items) ? operatingProfile.value.items : []).filter((item) => !item?.ok),
);

const summaryCards = computed(() => [
  { id: "today", label: "Today Net Profit", value: formatMoney(today.value.realized_net_profit || 0), note: `${today.value.sold_count || 0} sold / hit ${formatPercent(today.value.profit_hit_rate || 0)}`, tone: moneyTone(today.value.realized_net_profit || 0) },
  { id: "week", label: "Last 7d Net Profit", value: formatMoney(last7d.value.realized_net_profit || 0), note: `ROI ${formatPercent(last7d.value.avg_realized_roi || 0)}`, tone: moneyTone(last7d.value.realized_net_profit || 0) },
  { id: "capital", label: "Deployed Capital", value: formatMoney(inventory.value.deployed_capital || 0), note: `${inventory.value.active_trade_count || 0} active / ${inventory.value.listed_trade_count || 0} listed`, tone: "neutral" },
  { id: "review", label: "Pending Review", value: formatInteger(profit.value.pending_review_count || 0), note: `${profit.value.total_trade_count || 0} total trades`, tone: "neutral" },
  { id: "alerts", label: "Open Alerts", value: formatInteger(alerts.value.summary.count || 0), note: `${alerts.value.summary.counts_by_severity?.error || 0} error / ${alerts.value.summary.counts_by_severity?.warning || 0} warning`, tone: alerts.value.summary.count > 0 ? "warning" : "positive" },
  { id: "server", label: "Server Readiness", value: runtime.value.serverReady ? "Ready" : "Attention", note: runtime.value.serverReady ? "Background services look healthy" : `${runtime.value.healthReasons.length} issues need review`, tone: runtime.value.serverReady ? "positive" : "warning" },
]);

const profitabilityRows = computed(() => [
  { label: "Gross Profit", value: formatMoney(profit.value.gross_profit || 0) },
  { label: "Average ROI", value: formatPercent(profit.value.avg_realized_roi || 0) },
  { label: "Profit Hit Rate", value: formatPercent(profit.value.profit_hit_rate || 0) },
  { label: "Average Holding Days", value: formatNumber(profit.value.avg_holding_days || 0, 1) },
  { label: "Median Holding Days", value: formatNumber(profit.value.median_holding_days || 0, 1) },
  { label: "Expected Exit Spread", value: formatMoney(inventory.value.expected_exit_spread || 0) },
]);

const runtimeRows = computed(() => {
  const services = runtime.value.services || {};
  const automation = runtime.value.automation || {};
  return [
    { id: "automation", label: "Automation", value: automation.all_running ? "running" : "partial", note: automation.busy ? "busy with a coordinated run" : "background orchestrator", type: automation.all_running ? "success" : "warning", time: formatTimestamp(automation.last_run_at) },
    { id: "monitor", label: "Market Monitor", value: services.monitor?.is_running ? "running" : "stopped", note: services.monitor?.circuit_open ? "circuit open" : "listing watcher", type: services.monitor?.is_running ? "success" : "default", time: formatTimestamp(services.monitor?.last_run_at) },
    { id: "autotrade", label: "Autotrade", value: services.autotrade?.running ? "running" : "stopped", note: `approved ${services.autotrade?.total_approved || 0}`, type: services.autotrade?.running ? "success" : "default", time: formatTimestamp(services.autotrade?.last_run_at) },
    { id: "retry", label: "Execution Retry", value: services.execution_retry?.running ? "running" : "stopped", note: `${services.execution_retry?.total_retried || 0} retried`, type: services.execution_retry?.running ? "success" : "default", time: formatTimestamp(services.execution_retry?.last_run_at) },
    { id: "supabase", label: "Supabase Sync", value: services.supabase_sync?.is_running ? "running" : "idle", note: services.supabase_sync?.configured ? "replication configured" : "replication disabled", type: services.supabase_sync?.is_running ? "success" : services.supabase_sync?.configured ? "warning" : "default", time: formatUnixTimestamp(services.supabase_sync?.last_run_at_unix) },
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
      title: "Operating Mode",
      value: operatingProfile.value.mode_label || "Standard",
      type: !operatingProfile.value.enabled ? "default" : operatingProfile.value.aligned ? "success" : "warning",
      message: operatingProfile.value.enabled
        ? (operatingProfile.value.aligned
            ? `Single-account local guardrails are aligned with the ${operatingProfile.value.strategy_profile || "balanced"} strategy.`
            : `Guardrail drift: ${(operatingProfile.value.failing_codes || []).join(", ") || "review required"}`)
        : `Single-account mode is not enabled. Strategy profile: ${operatingProfile.value.strategy_profile || "balanced"}.`,
      time: generatedAtLabel.value,
    },
    {
      id: "validation-baseline",
      title: "Observation Baseline",
      value: validationBaseline.value.ready ? "ready" : validationBaseline.value.status || "observe",
      type: validationBaseline.value.ready ? "success" : validationBaseline.value.status === "blocked" ? "error" : "warning",
      message: latestHourlyBaseline
        ? `Latest ${latestHourlyBaseline.bucket_type || "hour"} snapshot: ${latestHourlyBaseline.status || "-"} / ${latestHourlyBaseline.direction || "flat"}`
        : validationBaseline.value.timeline?.summary
        || validationBaseline.value.recommendation
        || `Baseline drift: ${(validationBaseline.value.blocking_codes || []).join(", ") || "collect more evidence"}`,
      time: generatedAtLabel.value,
    },
    {
      id: "startup-checks",
      title: "Startup Checks",
      value: String(startupChecks.value.status || "ok"),
      type: startupChecks.value.status === "critical" ? "error" : startupChecks.value.status === "warning" ? "warning" : "success",
      message: startupChecks.value.count ? `${startupChecks.value.count} startup findings still need review.` : "No startup blockers are currently detected.",
      time: generatedAtLabel.value,
    },
    {
      id: "live-execution",
      title: "Live Execution",
      value: executionReady.live_ready ? "ready" : "not ready",
      type: executionReady.live_ready ? "success" : executionReady.live_enabled ? "warning" : "default",
      message: executionReady.live_enabled
        ? (executionReady.live_ready ? "Webhook execution is fully configured." : `Missing: ${(executionReady.missing || []).join(", ") || "unknown"}`)
        : "Live execution is currently disabled.",
      time: generatedAtLabel.value,
    },
    {
      id: "alert-channels",
      title: "Alert Channels",
      value: alertDelivery.email_ready || alertDelivery.slack_ready || alertDelivery.telegram_ready || alertDelivery.webhook_ready ? "available" : "offline",
      type: alertDelivery.email_ready || alertDelivery.slack_ready || alertDelivery.telegram_ready || alertDelivery.webhook_ready ? "success" : "warning",
      message: `email ${boolWord(alertDelivery.email_ready)} / slack ${boolWord(alertDelivery.slack_ready)} / telegram ${boolWord(alertDelivery.telegram_ready)} / webhook ${boolWord(alertDelivery.webhook_ready)}`,
      time: generatedAtLabel.value,
    },
    {
      id: "auto-start",
      title: "Auto Start",
      value: Object.values(autoStart).some(Boolean) ? "configured" : "manual",
      type: Object.values(autoStart).some(Boolean) ? "success" : "warning",
      message: `monitor ${boolWord(autoStart.monitor)} / autotrade ${boolWord(autoStart.autotrade)} / retry ${boolWord(autoStart.execution_retry)} / supabase ${boolWord(autoStart.supabase_sync)}`,
      time: generatedAtLabel.value,
    },
  ];
});

const limitedCards = computed(() => [
  { id: "tokens", label: "Imported Tokens", value: formatInteger(tokenStore.gameTokens.length), note: tokenStore.hasTokens ? "Token workspace ready" : "No tokens imported yet", tone: tokenStore.hasTokens ? "positive" : "warning" },
  { id: "selected", label: "Selected Token", value: tokenStore.selectedToken?.name || "None", note: tokenStore.selectedToken?.server || "Choose a token to continue", tone: tokenStore.selectedToken ? "positive" : "warning" },
  { id: "role", label: "Current Role", value: currentRoleLabel.value, note: "Admin-only runtime visibility is intentionally hidden", tone: "neutral" },
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
const boolWord = (value) => (value ? "ready" : "off");
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
