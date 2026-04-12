<template>
  <div class="ops-page">
    <section class="hero-row">
      <div>
        <h1>Operational Services</h1>
        <p>Review real-source market candidates, operate services, and inspect recent execution from one page.</p>
      </div>
      <div class="hero-actions">
        <button class="ghost-button" type="button" @click="showManualIntakeDrawer = true">Real Intake</button>
        <button class="ghost-button" type="button" @click="exportCsv">Export CSV</button>
        <n-button type="primary" :loading="refreshing" @click="handleRefresh">Refresh</n-button>
      </div>
    </section>

    <n-alert v-if="error" type="error" :show-icon="false">{{ error }}</n-alert>

    <section class="service-grid">
      <article v-for="card in serviceCards" :key="card.id" class="service-card">
        <div class="service-header">
          <div>
            <h3>{{ card.title }}</h3>
            <p>Status: <span :class="`tone-${card.tone}`">{{ card.status }}</span></p>
          </div>
          <div class="service-icon" :class="`tone-${card.tone}`">
            <n-icon size="20"><component :is="card.icon"></component></n-icon>
          </div>
        </div>

        <p class="service-body">{{ card.description }}</p>

        <div class="service-details">
          <div v-for="item in card.details" :key="`${card.id}-${item.label}`" class="detail-row">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>

        <div class="service-actions">
          <n-button
            v-for="action in card.actions"
            :key="`${card.id}-${action.key}`"
            size="small"
            :type="action.primary ? 'primary' : 'default'"
            :loading="actionLoading === action.key"
            :disabled="!canOperate"
            @click="runServiceAction(action.key)"
          >
            {{ action.label }}
          </n-button>
        </div>
      </article>
    </section>

    <section class="opportunities-section">
      <div class="section-head">
        <div>
          <h2>Pending Review Opportunities</h2>
          <p>Real-source candidates only. Simulation rows are excluded from the default review queue.</p>
        </div>
        <button class="section-link" type="button" @click="refreshOpportunityQueues">Refresh Real Queue</button>
      </div>

      <div class="opportunity-grid">
        <article v-for="row in opportunityRows" :key="row.opportunity_id" class="opportunity-card">
          <div class="opportunity-top">
            <div>
              <h3>{{ row.title }}</h3>
              <p>{{ row.riskLabel }}</p>
            </div>
            <span class="strategy-pill">{{ row.scoreLabel }}</span>
          </div>
          <div class="opportunity-tags">
            <span class="strategy-pill">{{ row.sourceLabel }}</span>
            <span class="strategy-pill">{{ row.itemTypeLabel }}</span>
          </div>
          <div class="opportunity-metrics">
            <div class="detail-row">
              <span>List Price</span>
              <strong>{{ row.listPriceText }}</strong>
            </div>
            <div class="detail-row">
              <span>Expected Profit</span>
              <strong>{{ row.profitText }}</strong>
            </div>
            <div class="detail-row">
              <span>ROI</span>
              <strong>{{ row.roiText }}</strong>
            </div>
          </div>
          <div class="service-actions">
            <n-button secondary @click="openOpportunityReview(row)">Review</n-button>
          </div>
        </article>
        <article v-if="!opportunityRows.length" class="opportunity-card empty-card">
          <strong>{{ opportunitiesEmptyTitle }}</strong>
          <p>{{ opportunitiesEmptyDescription }}</p>
        </article>
      </div>

      <template v-if="blockedOpportunityRows.length">
        <div class="section-head sub-section-head">
          <div>
            <h2>Risk-Gated Real Candidates</h2>
            <p>These real listings were blocked by risk controls. You can manually send one into review.</p>
          </div>
        </div>

        <div class="opportunity-grid">
          <article v-for="row in blockedOpportunityRows" :key="`blocked-${row.opportunity_id}`" class="opportunity-card blocked-card">
            <div class="opportunity-top">
              <div>
                <h3>{{ row.title }}</h3>
                <p>{{ row.riskLabel }}</p>
              </div>
              <span class="strategy-pill">{{ row.scoreLabel }}</span>
            </div>
            <div class="opportunity-tags">
              <span class="strategy-pill">{{ row.sourceLabel }}</span>
              <span class="strategy-pill">{{ row.itemTypeLabel }}</span>
            </div>
            <div class="opportunity-metrics">
              <div class="detail-row">
                <span>List Price</span>
                <strong>{{ row.listPriceText }}</strong>
              </div>
              <div class="detail-row">
                <span>Expected Profit</span>
                <strong>{{ row.profitText }}</strong>
              </div>
              <div class="detail-row">
                <span>ROI</span>
                <strong>{{ row.roiText }}</strong>
              </div>
            </div>
            <div class="service-actions">
              <n-button
                secondary
                :loading="moveToReviewLoading === String(row.opportunity_id)"
                :disabled="!canOperate"
                @click="moveBlockedOpportunityToReview(row)"
              >
                Send To Review
              </n-button>
            </div>
          </article>
        </div>
      </template>
    </section>

    <section class="opportunities-section">
      <div class="section-head">
        <div>
          <h2>Cross-Platform Arbitrage Intel</h2>
          <p>Read-only watchlist. Lowest visible source versus highest modeled resale source across the current intake pool.</p>
        </div>
        <button class="section-link" type="button" @click="loadArbitrageCandidates">Refresh Intel</button>
      </div>

      <div class="opportunity-grid">
        <article v-for="row in arbitrageRows" :key="`arb-${row.normalizedKey}`" class="opportunity-card">
          <div class="opportunity-top">
            <div>
              <h3>{{ row.title }}</h3>
              <p>{{ row.pathLabel }}</p>
            </div>
            <span class="strategy-pill">{{ row.roiText }}</span>
          </div>
          <div class="opportunity-tags">
            <span class="strategy-pill">{{ row.buySourceLabel }}</span>
            <span class="strategy-pill">{{ row.sellSourceLabel }}</span>
            <span class="strategy-pill">{{ row.itemTypeLabel }}</span>
          </div>
          <div class="opportunity-metrics">
            <div class="detail-row">
              <span>Buy Price</span>
              <strong>{{ row.buyPriceText }}</strong>
            </div>
            <div class="detail-row">
              <span>Sell Price</span>
              <strong>{{ row.sellPriceText }}</strong>
            </div>
            <div class="detail-row">
              <span>Est. Net Profit</span>
              <strong>{{ row.profitText }}</strong>
            </div>
          </div>
          <div class="drawer-list">
            <div class="detail-row">
              <span>Source Count</span>
              <strong>{{ row.sourceCountText }}</strong>
            </div>
            <div class="detail-row">
              <span>Buy Leg Review</span>
              <strong>{{ row.buyReviewStatusText }}</strong>
            </div>
          </div>
        </article>
        <article v-if="!arbitrageRows.length" class="opportunity-card empty-card">
          <strong>{{ arbitrageEmptyTitle }}</strong>
          <p>{{ arbitrageEmptyDescription }}</p>
        </article>
      </div>
    </section>

    <section ref="transactionsSectionRef" class="transactions-section">
      <div class="section-head">
        <div>
          <h2>Recent Transactions</h2>
          <p>Real-time log of the latest successful and pending market activities.</p>
        </div>
        <button class="section-link" type="button" @click="openReportDrawer">View Reports</button>
      </div>

      <div class="filter-bar">
        <div class="search-box">
          <n-icon size="18"><SearchOutline></SearchOutline></n-icon>
          <input ref="primarySearchRef" v-model="searchQuery" type="text" placeholder="Search by card name..." />
        </div>
        <div class="filter-box">
          <n-select v-model:value="statusFilter" clearable placeholder="Status" :options="statusOptions"></n-select>
        </div>
        <div class="filter-box">
          <n-select v-model:value="strategyFilter" clearable placeholder="Strategy" :options="strategyOptions"></n-select>
        </div>
        <div class="filter-date">
          <n-icon size="16"><CalendarOutline></CalendarOutline></n-icon>
          <input v-model="selectedDate" type="date" />
        </div>
      </div>

      <div class="table-shell">
        <table class="transactions-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Card Name</th>
              <th>Amount</th>
              <th>Strategy</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredTransactionRows" :key="row.id">
              <td>{{ row.time }}</td>
              <td class="name-cell">{{ row.title }}</td>
              <td class="mono-cell">{{ row.amount }}</td>
              <td><span class="strategy-pill">{{ row.strategy }}</span></td>
              <td><span class="status-pill" :class="`tone-${row.statusTone}`">{{ row.statusLabel }}</span></td>
            </tr>
            <tr v-if="!filteredTransactionRows.length">
              <td colspan="5" class="empty-row">
                <strong>{{ emptyStateTitle }}</strong>
                <span>{{ emptyStateDescription }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="banner-panel">
      <h2>Precision Trading. Managed.</h2>
      <p>Verified, filtered, and exported from a single console.</p>
      <div class="banner-actions">
        <n-button type="primary" @click="scrollToTransactions">Start Automating</n-button>
        <button class="banner-link" type="button" @click="openReportDrawer">Documentation</button>
      </div>
    </section>

    <n-drawer v-model:show="showReportDrawer" placement="right" :width="420">
      <n-drawer-content title="Analysis Report" closable>
        <div class="drawer-stack">
          <div class="drawer-panel">
            <strong>Report Summary</strong>
            <p>{{ reportSummary.report_text || "Load the current analysis report from the backend." }}</p>
          </div>
          <div class="drawer-list">
            <div class="detail-row">
              <span>Transactions loaded</span>
              <strong>{{ formatInteger(transactionRows.length) }}</strong>
            </div>
            <div class="detail-row">
              <span>Execution logs loaded</span>
              <strong>{{ formatInteger(executionLogs.length) }}</strong>
            </div>
            <div class="detail-row">
              <span>Report trades</span>
              <strong>{{ formatInteger(reportTradeCount) }}</strong>
            </div>
          </div>
          <div class="service-actions">
            <n-button type="primary" :loading="reportLoading" @click="loadAnalysisReport">Refresh Report</n-button>
            <n-button secondary @click="scrollToTransactions">Go To Transactions</n-button>
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>

    <n-drawer v-model:show="showOpportunityDrawer" placement="right" :width="460">
      <n-drawer-content :title="selectedOpportunity?.title || 'Review Opportunity'" closable>
        <div v-if="selectedOpportunity" class="drawer-stack">
          <div class="drawer-panel">
            <strong>Review Snapshot</strong>
            <p>{{ selectedOpportunity.riskNoteText }}</p>
          </div>
          <div class="drawer-list">
            <div class="detail-row"><span>Source</span><strong>{{ selectedOpportunity.sourceLabel }}</strong></div>
            <div class="detail-row"><span>Seller</span><strong>{{ selectedOpportunity.sellerLabel }}</strong></div>
            <div class="detail-row"><span>Item Type</span><strong>{{ selectedOpportunity.itemTypeLabel }}</strong></div>
            <div class="detail-row"><span>Normalized Key</span><strong>{{ selectedOpportunity.normalizedKeyText }}</strong></div>
            <div class="detail-row"><span>List Price</span><strong>{{ selectedOpportunity.listPriceText }}</strong></div>
            <div class="detail-row"><span>Expected Sale</span><strong>{{ selectedOpportunity.expectedSaleText }}</strong></div>
            <div class="detail-row"><span>Suggested List</span><strong>{{ selectedOpportunity.suggestedListText }}</strong></div>
            <div class="detail-row"><span>Expected Profit</span><strong>{{ selectedOpportunity.profitText }}</strong></div>
            <div class="detail-row"><span>ROI</span><strong>{{ selectedOpportunity.roiText }}</strong></div>
            <div class="detail-row"><span>Score</span><strong>{{ selectedOpportunity.scoreLabel }}</strong></div>
          </div>

          <div v-if="selectedOpportunity.listingUrlText" class="drawer-panel">
            <strong>Listing URL</strong>
            <p>{{ selectedOpportunity.listingUrlText }}</p>
          </div>

          <n-input-number v-model:value="reviewBuyPrice" :min="0" :precision="2" placeholder="Approved buy price"></n-input-number>
          <n-input v-model:value="reviewNote" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }" placeholder="Review note"></n-input>

          <div class="service-actions">
            <n-button
              type="primary"
              :loading="reviewActionLoading === 'approve'"
              :disabled="!canOperate"
              @click="approveSelectedOpportunity"
            >
              Approve
            </n-button>
            <n-button
              :loading="reviewActionLoading === 'reject'"
              :disabled="!canOperate"
              @click="rejectSelectedOpportunity"
            >
              Reject
            </n-button>
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>

    <n-drawer v-model:show="showManualIntakeDrawer" placement="right" :width="520">
      <n-drawer-content title="Manual Intake" closable>
        <div class="drawer-stack">
          <div class="drawer-panel">
            <strong>Paste Real Listings JSON</strong>
            <p>Use this only when you need to import real listings manually. Sample and simulation shortcuts are no longer part of the main workflow.</p>
          </div>

          <n-input
            v-model:value="manualListingsJson"
            type="textarea"
            :autosize="{ minRows: 12, maxRows: 22 }"
            placeholder="Paste a JSON array of real listings."
          ></n-input>

          <div class="drawer-actions">
            <n-button :loading="manualActionLoading === 'import'" @click="importListings(false)">Import Only</n-button>
            <n-button type="primary" :loading="manualActionLoading === 'scan'" @click="importListings(true)">Import And Scan</n-button>
          </div>

          <div v-if="manualResultSummary" class="drawer-panel">
            <strong>Last Intake Result</strong>
            <p>{{ manualResultSummary }}</p>
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<script setup>
import {
  AlertCircleOutline,
  CalendarOutline,
  FlashOutline,
  SearchOutline,
  ServerOutline,
  StatsChartOutline,
} from "@vicons/ionicons5";
import { useMessage } from "naive-ui";
import { computed, nextTick, onMounted, onUnmounted, ref } from "vue";

import cardFlipApi from "@/api/cardFlip";
import useExecutiveOverview from "@/composables/useExecutiveOverview";
import { useAuthStore } from "@/stores/auth";

const { alertItems, error, formatTime, loadOverview, loading, profitability, runtime } = useExecutiveOverview();
const authStore = useAuthStore();
const message = useMessage();

const searchQuery = ref("");
const statusFilter = ref(null);
const strategyFilter = ref(null);
const selectedDate = ref("");
const tradeRecords = ref([]);
const executionLogs = ref([]);
const recordsLoading = ref(false);
const recordsError = ref("");
const actionLoading = ref("");
const reportLoading = ref(false);
const reportSummary = ref({});
const showReportDrawer = ref(false);
const opportunities = ref([]);
const opportunitiesLoading = ref(false);
const opportunitiesError = ref("");
const blockedOpportunities = ref([]);
const blockedOpportunitiesLoading = ref(false);
const blockedOpportunitiesError = ref("");
const arbitrageCandidates = ref([]);
const arbitrageLoading = ref(false);
const arbitrageError = ref("");
const showOpportunityDrawer = ref(false);
const selectedOpportunityId = ref(0);
const reviewBuyPrice = ref(null);
const reviewNote = ref("");
const reviewActionLoading = ref("");
const moveToReviewLoading = ref("");
const showManualIntakeDrawer = ref(false);
const manualListingsJson = ref("");
const manualActionLoading = ref("");
const manualResultSummary = ref("");
const transactionsSectionRef = ref(null);
const primarySearchRef = ref(null);

const canOperate = computed(() => {
  if (authStore.userInfo?.isAdmin)
    return true;
  const roles = Array.isArray(authStore.userInfo?.roleKeys) ? authStore.userInfo.roleKeys : [];
  return roles.map(item => String(item || "").toLowerCase()).includes("ops");
});

const serviceState = computed(() => runtime.value?.services || {});
const executionReadiness = computed(() => runtime.value?.execution_readiness || {});
const refreshing = computed(() => loading.value || recordsLoading.value || reportLoading.value);

const approvalRunning = computed(() => Boolean(serviceState.value.autotrade?.running));
const monitorRunning = computed(() => Boolean(serviceState.value.monitor?.is_running));
const retryRunning = computed(() => Boolean(serviceState.value.execution_retry?.running));

const autoApprovalMessage = computed(() =>
  alertItems.value.find(item => /auto/i.test(String(item.title || "")))?.message || "Manual intervention required for all incoming trade requests.",
);

const serviceCards = computed(() => [
  {
    id: "autotrade",
    title: "Auto Approval",
    status: approvalRunning.value ? "Running" : "Severe",
    tone: approvalRunning.value ? "positive" : "danger",
    icon: AlertCircleOutline,
    description: approvalRunning.value ? "Auto approval is active for incoming trade requests." : autoApprovalMessage.value,
    details: [
      { label: "Approved", value: formatInteger(serviceState.value.autotrade?.total_approved || 0) },
      { label: "Runs", value: formatInteger(serviceState.value.autotrade?.total_runs || 0) },
      { label: "Last run", value: formatTime(serviceState.value.autotrade?.last_run_at) },
    ],
    actions: [
      { key: "autotrade-start", label: "Start", primary: !approvalRunning.value },
      { key: "autotrade-stop", label: "Stop", primary: false },
      { key: "autotrade-run", label: "Run Once", primary: false },
    ],
  },
  {
    id: "monitor",
    title: "Market Monitoring",
    status: monitorRunning.value ? "Running" : "Stopped",
    tone: monitorRunning.value ? "positive" : "neutral",
    icon: ServerOutline,
    description: monitorRunning.value ? "Listening for market shifts and rare card listings is active." : "Listening for market shifts and rare card listings is currently paused.",
    details: [
      { label: "Health", value: humanizeHealth(serviceState.value.monitor?.health) },
      { label: "Circuit", value: serviceState.value.monitor?.circuit_open ? "Open" : "Normal" },
      { label: "Last run", value: formatTime(serviceState.value.monitor?.last_run_at) },
    ],
    actions: [
      { key: "monitor-start", label: "Start", primary: !monitorRunning.value },
      { key: "monitor-stop", label: "Stop", primary: false },
      { key: "monitor-run", label: "Run Once", primary: false },
    ],
  },
  {
    id: "report",
    title: "Auto Trading Approval",
    status: approvalRunning.value ? "Running" : "Stopped",
    tone: approvalRunning.value ? "positive" : "neutral",
    icon: StatsChartOutline,
    description: executionReadiness.value.live_ready ? "Webhook execution is ready for approval flow reporting." : "Webhook execution is not fully ready yet.",
    details: [
      { label: "Live mode", value: executionReadiness.value.live_enabled ? "Enabled" : "Disabled" },
      { label: "Provider", value: executionReadiness.value.webhook_provider ? "Webhook" : String(executionReadiness.value.provider || "None") },
      { label: "Sold trades", value: formatInteger(profitability.value?.sold_count || 0) },
    ],
    actions: [
      { key: "report-load", label: "View Reports", primary: true },
      { key: "report-scroll", label: "Focus Table", primary: false },
    ],
  },
  {
    id: "retry",
    title: "Retry Execution",
    status: retryRunning.value ? "Running" : "Stopped",
    tone: retryRunning.value ? "positive" : "neutral",
    icon: FlashOutline,
    description: retryRunning.value ? "Retry logic is handling failed trade executions and API timeouts." : "Automatic retry logic is currently offline.",
    details: [
      { label: "Retried", value: formatInteger(serviceState.value.execution_retry?.total_retried || 0) },
      { label: "Succeeded", value: formatInteger(serviceState.value.execution_retry?.total_succeeded || 0) },
      { label: "Last run", value: formatTime(serviceState.value.execution_retry?.last_run_at) },
    ],
    actions: [
      { key: "retry-start", label: "Start", primary: !retryRunning.value },
      { key: "retry-stop", label: "Stop", primary: false },
      { key: "retry-run", label: "Run Once", primary: false },
    ],
  },
]);

function extractRiskScore(note) {
  const text = String(note || "").trim();
  if (!text)
    return null;
  for (const part of text.split(";")) {
    const segment = String(part || "").trim();
    if (!segment.startsWith("risk_score="))
      continue;
    const parsed = Number(segment.split("=")[1]);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function buildOpportunityRow(item, mode = "pending") {
  const riskNote = String(item.risk_note || "");
  const source = String(item.source || "unknown");
  const itemType = String(item.item_type || "unknown");
  const riskScore = extractRiskScore(riskNote);
  return {
    ...item,
    listPriceText: formatMoney(item.list_price),
    expectedSaleText: formatMoney(item.expected_sale_price),
    suggestedListText: formatMoney(item.suggested_list_price),
    profitText: formatMoney(item.expected_profit),
    roiText: formatPercent(item.roi),
    scoreLabel: `${formatNumber(item.score, 1)} pts`,
    riskLabel: mode === "blocked"
      ? riskScore === null
        ? "risk gate"
        : `risk score ${formatNumber(riskScore, 0)}`
      : "live review queue",
    riskNoteText: riskNote || "No risk note.",
    sourceLabel: source,
    sellerLabel: String(item.seller_id || "n/a"),
    itemTypeLabel: itemType,
    normalizedKeyText: String(item.normalized_key || "n/a"),
    listingUrlText: String(item.listing_url || ""),
  };
}

const opportunityRows = computed(() =>
  opportunities.value.map(item => buildOpportunityRow(item, "pending")),
);

const blockedOpportunityRows = computed(() =>
  blockedOpportunities.value.map(item => buildOpportunityRow(item, "blocked")),
);

function buildArbitrageRow(item) {
  const buyReviewStatus = String(item.buy_review_status || "").trim();
  return {
    normalizedKey: String(item.normalized_key || ""),
    title: String(item.normalized_title || item.normalized_key || "Untitled"),
    itemTypeLabel: String(item.item_type || "unknown"),
    buySourceLabel: String(item.buy_source_label || item.buy_source || "buy"),
    sellSourceLabel: String(item.sell_source_label || item.sell_source || "sell"),
    buyPriceText: formatMoney(item.buy_price),
    sellPriceText: formatMoney(item.sell_price),
    profitText: formatMoney(item.expected_profit),
    roiText: formatPercent(item.roi),
    sourceCountText: formatInteger(item.source_count),
    buyReviewStatusText: buyReviewStatus || "not in review",
    pathLabel: `Buy on ${String(item.buy_source_label || item.buy_source || "buy")} and exit on ${String(item.sell_source_label || item.sell_source || "sell")}`,
  };
}

const arbitrageRows = computed(() =>
  arbitrageCandidates.value.map(item => buildArbitrageRow(item)),
);

const selectedOpportunity = computed(() =>
  opportunityRows.value.find(item => Number(item.opportunity_id) === Number(selectedOpportunityId.value)) || null,
);

const opportunitiesEmptyTitle = computed(() => {
  if (opportunitiesLoading.value)
    return "Loading real pending opportunities...";
  if (opportunitiesError.value)
    return "Real pending opportunities failed to load.";
  if (blockedOpportunityRows.value.length)
    return "No real opportunities are waiting for review.";
  return "No real pending review opportunities.";
});

const opportunitiesEmptyDescription = computed(() => {
  if (opportunitiesLoading.value)
    return "Waiting for live-source review candidates.";
  if (opportunitiesError.value)
    return opportunitiesError.value;
  if (blockedOpportunityRows.value.length)
    return "The live queue is empty right now, but real candidates are available in the risk-gated section below.";
  if (blockedOpportunitiesError.value)
    return blockedOpportunitiesError.value;
  if (blockedOpportunitiesLoading.value)
    return "Checking the risk-gated live queue.";
  return "Run a live monitor cycle or import real listings to build a real review queue.";
});

const arbitrageEmptyTitle = computed(() => {
  if (arbitrageLoading.value)
    return "Loading cross-platform candidates...";
  if (arbitrageError.value)
    return "Cross-platform candidates failed to load.";
  return "No cross-platform spread candidates yet.";
});

const arbitrageEmptyDescription = computed(() => {
  if (arbitrageLoading.value)
    return "Comparing normalized listings across active sources.";
  if (arbitrageError.value)
    return arbitrageError.value;
  return "You need at least two real sources with matching normalized listings before arbitrage candidates will appear.";
});

const latestLogByTradeId = computed(() => {
  const map = new Map();
  for (const row of executionLogs.value) {
    if (!map.has(row.trade_id))
      map.set(row.trade_id, row);
  }
  return map;
});

const transactionRows = computed(() => {
  const rows = tradeRecords.value.length
    ? tradeRecords.value.map((trade) => {
        const latestLog = latestLogByTradeId.value.get(trade.trade_id);
        const tradeStatus = String(trade.status || "").toLowerCase();
        let statusLabel = "Pending";
        let statusTone = "pending";
        if (tradeStatus === "sold") {
          statusLabel = "Success";
          statusTone = "success";
        } else if (latestLog && latestLog.success === false) {
          statusLabel = "Failed";
          statusTone = "failed";
        } else if (["approved_for_buy", "listed_for_sale"].includes(tradeStatus)) {
          statusLabel = "Processing";
          statusTone = "processing";
        }
        return {
          id: `trade-${trade.trade_id}`,
          title: String(trade.title || "Untitled trade"),
          strategy: latestLog?.action ? humanizeStrategy(latestLog.action) : "--",
          statusLabel,
          statusTone,
          time: formatTime(trade.updated_at || trade.created_at),
          rawTime: String(trade.updated_at || trade.created_at || ""),
          amount: formatMoney(trade.sold_price ?? trade.target_sell_price ?? trade.approved_buy_price ?? 0),
        };
      })
    : executionLogs.value.map((log, index) => {
        const payload = parsePayload(log.request_json);
        let statusLabel = "Pending";
        let statusTone = "pending";
        if (log.success === false) {
          statusLabel = "Failed";
          statusTone = "failed";
        } else if (String(log.trade_status || "").toLowerCase() === "sold") {
          statusLabel = "Success";
          statusTone = "success";
        } else if (log.success === true) {
          statusLabel = "Processing";
          statusTone = "processing";
        }
        return {
          id: `log-${log.id || index}`,
          title: String(payload.title || `Execution #${log.id || index + 1}`),
          strategy: humanizeStrategy(log.action),
          statusLabel,
          statusTone,
          time: formatTime(log.created_at),
          rawTime: String(log.created_at || ""),
          amount: formatMoney(payload.sold_price ?? payload.target_sell_price ?? payload.buy_price ?? 0),
        };
      });
  return rows.sort((a, b) => new Date(b.rawTime).getTime() - new Date(a.rawTime).getTime());
});

const strategyOptions = computed(() =>
  [...new Set(transactionRows.value.map(item => item.strategy).filter(item => item && item !== "--"))]
    .map(item => ({ label: item, value: item })),
);
const statusOptions = [
  { label: "Success", value: "success" },
  { label: "Processing", value: "processing" },
  { label: "Failed", value: "failed" },
  { label: "Pending", value: "pending" },
];
const filteredTransactionRows = computed(() => {
  const query = String(searchQuery.value || "").trim().toLowerCase();
  return transactionRows.value.filter((row) => {
    if (statusFilter.value && row.statusTone !== statusFilter.value)
      return false;
    if (strategyFilter.value && row.strategy !== strategyFilter.value)
      return false;
    if (selectedDate.value && !String(row.rawTime || "").startsWith(selectedDate.value))
      return false;
    return !query || `${row.title} ${row.strategy} ${row.statusLabel}`.toLowerCase().includes(query);
  });
});

const reportTradeCount = computed(() => Number(reportSummary.value?.data_layer?.trade_records?.length || 0));
const emptyStateTitle = computed(() => {
  if (recordsLoading.value)
    return "Loading transaction data...";
  if (recordsError.value)
    return "Transaction data failed to load.";
  return "No transactions available.";
});
const emptyStateDescription = computed(() => {
  if (recordsLoading.value)
    return "The report table is waiting for trade records and execution logs.";
  if (recordsError.value)
    return recordsError.value;
  if (searchQuery.value || statusFilter.value || strategyFilter.value || selectedDate.value)
    return "Current filters returned no rows. Clear a filter and try again.";
  return "No trade records or execution logs are currently available in this environment.";
});

async function loadTransactionData() {
  recordsLoading.value = true;
  recordsError.value = "";
  try {
    const [tradeResponse, logResponse] = await Promise.all([
      cardFlipApi.getTradeRecords({ limit: 50 }),
      cardFlipApi.listExecutionLogs({ limit: 100 }),
    ]);
    tradeRecords.value = Array.isArray(tradeResponse?.items) ? tradeResponse.items : [];
    executionLogs.value = Array.isArray(logResponse?.items) ? logResponse.items : [];
  } catch (requestError) {
    tradeRecords.value = [];
    executionLogs.value = [];
    recordsError.value = requestError instanceof Error ? requestError.message : "Unable to load trade records.";
  } finally {
    recordsLoading.value = false;
  }
}

async function loadAnalysisReport() {
  reportLoading.value = true;
  try {
    reportSummary.value = await cardFlipApi.getAnalysisReport({ limit: 50 });
    showReportDrawer.value = true;
  } catch (requestError) {
    message.error(requestError instanceof Error ? requestError.message : "Unable to load analysis report.");
  } finally {
    reportLoading.value = false;
  }
}

async function loadOpportunities() {
  opportunitiesLoading.value = true;
  opportunitiesError.value = "";
  try {
    const response = await cardFlipApi.listOpportunities({
      status: "pending_review",
      limit: 20,
      include_simulation: false,
    });
    opportunities.value = Array.isArray(response?.items) ? response.items : [];
  } catch (requestError) {
    opportunities.value = [];
    opportunitiesError.value = requestError instanceof Error ? requestError.message : "Unable to load opportunities.";
  } finally {
    opportunitiesLoading.value = false;
  }
}

async function loadBlockedOpportunities() {
  blockedOpportunitiesLoading.value = true;
  blockedOpportunitiesError.value = "";
  try {
    const response = await cardFlipApi.listOpportunities({
      status: "blocked_risk",
      limit: 20,
      include_simulation: false,
    });
    blockedOpportunities.value = Array.isArray(response?.items) ? response.items : [];
  } catch (requestError) {
    blockedOpportunities.value = [];
    blockedOpportunitiesError.value = requestError instanceof Error ? requestError.message : "Unable to load blocked opportunities.";
  } finally {
    blockedOpportunitiesLoading.value = false;
  }
}

async function loadArbitrageCandidates() {
  arbitrageLoading.value = true;
  arbitrageError.value = "";
  try {
    const response = await cardFlipApi.getArbitrageCandidates({
      limit: 10,
      listing_hours: 24 * 30,
      min_distinct_sources: 2,
      min_expected_profit: 0,
      min_roi: 0,
    });
    arbitrageCandidates.value = Array.isArray(response?.items) ? response.items : [];
  } catch (requestError) {
    arbitrageCandidates.value = [];
    arbitrageError.value = requestError instanceof Error ? requestError.message : "Unable to load arbitrage intel.";
  } finally {
    arbitrageLoading.value = false;
  }
}

async function refreshOpportunityQueues() {
  await Promise.all([loadOpportunities(), loadBlockedOpportunities()]);
}

async function handleRefresh() {
  await Promise.all([loadOverview(), loadTransactionData(), loadOpportunities(), loadBlockedOpportunities(), loadArbitrageCandidates()]);
}

async function scrollToTransactions() {
  await nextTick();
  transactionsSectionRef.value?.scrollIntoView({ behavior: "smooth", block: "start" });
  await nextTick();
  primarySearchRef.value?.focus?.();
}

async function handleServiceAction(card) {
  if (card.id === "report") {
    await loadAnalysisReport();
    return;
  }
  if (card.id === "monitor" && !monitorRunning.value) {
    await runServiceAction("monitor-start");
    return;
  }
  message.info("Use the service controls on the card to operate this service.");
}

async function runServiceAction(action) {
  if (!canOperate.value) {
    message.warning("Current account cannot operate services.");
    return;
  }
  actionLoading.value = action;
  try {
    if (action === "autotrade-start")
      await cardFlipApi.startAutotrade();
    else if (action === "autotrade-stop")
      await cardFlipApi.stopAutotrade();
    else if (action === "autotrade-run")
      await cardFlipApi.runAutotradeOnce();
    else if (action === "monitor-start")
      await cardFlipApi.startMonitor();
    else if (action === "monitor-stop")
      await cardFlipApi.stopMonitor();
    else if (action === "monitor-run")
      await cardFlipApi.runMonitorOnce();
    else if (action === "retry-start")
      await cardFlipApi.startExecutionRetry();
    else if (action === "retry-stop")
      await cardFlipApi.stopExecutionRetry();
    else if (action === "retry-run")
      await cardFlipApi.runExecutionRetryOnce();
    else if (action === "report-load")
      await loadAnalysisReport();
    else if (action === "report-scroll")
      await scrollToTransactions();
    await handleRefresh();
    message.success("Service action completed.");
  } catch (requestError) {
    message.error(requestError instanceof Error ? requestError.message : "Service action failed.");
  } finally {
    actionLoading.value = "";
  }
}

function openReportDrawer() {
  void loadAnalysisReport();
}

function openOpportunityReview(row) {
  selectedOpportunityId.value = Number(row.opportunity_id);
  reviewBuyPrice.value = Number(row.list_price || 0);
  reviewNote.value = "manual review";
  showOpportunityDrawer.value = true;
}

async function approveSelectedOpportunity() {
  if (!selectedOpportunity.value)
    return;
  reviewActionLoading.value = "approve";
  try {
    await cardFlipApi.approveTrade({
      opportunity_id: selectedOpportunity.value.opportunity_id,
      approved_buy_price: Number(reviewBuyPrice.value || 0),
      approved_by: authStore.userInfo?.username || "operator",
      note: reviewNote.value || "manual review",
    });
    showOpportunityDrawer.value = false;
    await handleRefresh();
    message.success("Opportunity approved.");
  } catch (requestError) {
    message.error(requestError instanceof Error ? requestError.message : "Approve failed.");
  } finally {
    reviewActionLoading.value = "";
  }
}

async function rejectSelectedOpportunity() {
  if (!selectedOpportunity.value)
    return;
  reviewActionLoading.value = "reject";
  try {
    await cardFlipApi.rejectOpportunity(selectedOpportunity.value.opportunity_id, {
      note: reviewNote.value || "manual reject",
    });
    showOpportunityDrawer.value = false;
    await handleRefresh();
    message.success("Opportunity rejected.");
  } catch (requestError) {
    message.error(requestError instanceof Error ? requestError.message : "Reject failed.");
  } finally {
    reviewActionLoading.value = "";
  }
}

async function moveBlockedOpportunityToReview(row) {
  if (!canOperate.value) {
    message.warning("Current account cannot operate services.");
    return;
  }
  moveToReviewLoading.value = String(row.opportunity_id);
  try {
    await cardFlipApi.sendOpportunityToReview(row.opportunity_id, {
      note: "manual review override from live queue",
    });
    await Promise.all([loadOverview(), loadOpportunities(), loadBlockedOpportunities()]);
    const moved = opportunityRows.value.find(item => Number(item.opportunity_id) === Number(row.opportunity_id));
    if (moved)
      openOpportunityReview(moved);
    message.success("Real candidate moved into the review queue.");
  } catch (requestError) {
    message.error(requestError instanceof Error ? requestError.message : "Unable to move candidate into review.");
  } finally {
    moveToReviewLoading.value = "";
  }
}

async function importListings(runScan) {
  manualActionLoading.value = runScan ? "scan" : "import";
  manualResultSummary.value = "";
  try {
    const parsed = JSON.parse(manualListingsJson.value || "[]");
    if (!Array.isArray(parsed) || !parsed.length)
      throw new Error("Paste a non-empty JSON array of listings.");

    const normalized = parsed.map((item, index) => ({
      source: String(item?.source || "manual_import"),
      listing_id: item?.listing_id ? String(item.listing_id) : `manual-${Date.now()}-${index}`,
      seller_id: item?.seller_id ? String(item.seller_id) : null,
      title: String(item?.title || "").trim(),
      description: String(item?.description || ""),
      list_price: Number(item?.list_price || 0),
      listed_at: String(item?.listed_at || new Date().toISOString()),
      status: String(item?.status || "open"),
      raw: item?.raw && typeof item.raw === "object" ? item.raw : item,
    }));

    if (normalized.some(item => !item.title || !Number.isFinite(item.list_price) || item.list_price <= 0))
      throw new Error("Each listing must include a title and positive list_price.");

    const importResult = await cardFlipApi.ingestListings(normalized);
    let summary = `Imported ${Number(importResult?.inserted || 0)} listings.`;
    if (runScan) {
      const scanResult = await cardFlipApi.scanOpportunities({ limit: 50 });
      summary += ` Scan created ${Number(scanResult?.created || 0)} opportunities, blocked ${Number(scanResult?.blocked || 0)}, ignored ${Number(scanResult?.ignored || 0)}.`;
    }
    manualResultSummary.value = summary;
    await handleRefresh();
    message.success(summary);
  } catch (requestError) {
    const text = requestError instanceof Error ? requestError.message : "Manual intake failed.";
    manualResultSummary.value = text;
    message.error(text);
  } finally {
    manualActionLoading.value = "";
  }
}

function exportCsv() {
  const lines = [["Time", "Card Name", "Amount", "Strategy", "Status"].join(",")].concat(
    filteredTransactionRows.value.map(row => [
      escapeCsv(row.time),
      escapeCsv(row.title),
      escapeCsv(row.amount),
      escapeCsv(row.strategy),
      escapeCsv(row.statusLabel),
    ].join(",")),
  );
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "recent-transactions.csv";
  link.click();
  URL.revokeObjectURL(url);
}

function focusSearchHandler() {
  primarySearchRef.value?.focus?.();
}

onMounted(() => {
  void loadTransactionData();
  void loadOpportunities();
  void loadBlockedOpportunities();
  void loadArbitrageCandidates();
  window.addEventListener("focus-card-trading-search", focusSearchHandler);
});

onUnmounted(() => {
  window.removeEventListener("focus-card-trading-search", focusSearchHandler);
});

function parsePayload(raw) {
  if (!raw)
    return {};
  if (typeof raw === "object")
    return raw;
  if (typeof raw !== "string")
    return {};
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function humanizeStrategy(value) {
  const text = String(value || "").trim();
  return text ? text.replace(/^./, match => match.toUpperCase()) : "--";
}

function humanizeHealth(value) {
  if (!value)
    return "None";
  if (typeof value === "string")
    return value;
  if (typeof value === "object")
    return Object.entries(value).map(([key, item]) => `${key}:${item}`).join(" | ");
  return String(value);
}

function escapeCsv(value) {
  const text = String(value ?? "");
  return `"${text.replace(/"/g, "\"\"")}"`;
}

function formatMoney(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

function formatInteger(value) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(Number(value || 0));
}

function formatPercent(value) {
  return `${new Intl.NumberFormat("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(value || 0) * 100)}%`;
}

function formatNumber(value, digits = 1) {
  return new Intl.NumberFormat("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(value || 0));
}
</script>

<style scoped lang="scss">
.ops-page { display:grid; gap:28px; }
.hero-row, .service-header, .section-head { display:flex; justify-content:space-between; gap:16px; }
.hero-row { align-items:end; }
.hero-row h1 { color:var(--text-primary); font-size:40px; font-weight:800; letter-spacing:-.05em; }
.hero-row p { max-width:760px; margin-top:8px; color:rgba(245,247,251,.48); font-size:17px; line-height:1.6; }
.hero-actions, .service-actions, .banner-actions, .drawer-actions { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
.ghost-button, .section-link, .banner-link { color:#5eb2ff; font-size:14px; font-weight:600; }
.ghost-button { height:40px; padding:0 16px; border-radius:999px; background:rgba(255,255,255,.05); }
.service-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:20px; }
.service-card, .transactions-section, .banner-panel { border-radius:20px; background:var(--surface-card); border:1px solid var(--surface-line); box-shadow:var(--shadow-medium); }
.service-card, .transactions-section { padding:24px; }
.service-header h3, .section-head h2 { color:var(--text-primary); font-size:22px; font-weight:700; }
.service-header p, .section-head p { margin-top:4px; color:rgba(245,247,251,.42); font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:.08em; }
.service-icon { width:44px; height:44px; display:inline-flex; align-items:center; justify-content:center; border-radius:14px; }
.tone-positive { color:var(--success-color); background:rgba(52,211,153,.12); }
.tone-danger { color:var(--error-color); background:rgba(251,113,133,.12); }
.tone-neutral { color:var(--text-secondary); background:rgba(255,255,255,.06); }
.service-body { margin:18px 0; color:rgba(245,247,251,.82); line-height:1.7; }
.service-details, .drawer-list { display:grid; gap:10px; }
.detail-row, .drawer-panel { padding:12px 14px; border-radius:12px; background:rgba(255,255,255,.04); }
.detail-row { display:flex; justify-content:space-between; gap:12px; }
.detail-row span { color:var(--text-secondary); }
.detail-row strong, .drawer-panel strong { color:var(--text-primary); }
.service-actions { margin-top:18px; }
.opportunities-section { display:grid; gap:18px; }
.sub-section-head { margin-top:4px; }
.opportunity-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:20px; }
.opportunity-card { padding:20px; border-radius:20px; background:var(--surface-card); border:1px solid var(--surface-line); box-shadow:var(--shadow-medium); }
.blocked-card { border-color:rgba(251,113,133,.2); }
.opportunity-top { display:flex; align-items:start; justify-content:space-between; gap:12px; }
.opportunity-top h3 { color:var(--text-primary); font-size:20px; font-weight:700; }
.opportunity-top p { margin-top:4px; color:rgba(245,247,251,.42); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }
.opportunity-tags { display:flex; gap:8px; flex-wrap:wrap; margin-top:14px; }
.opportunity-metrics { display:grid; gap:10px; margin-top:16px; }
.empty-card strong { color:var(--text-primary); font-size:15px; }
.empty-card p { margin-top:8px; color:var(--text-secondary); line-height:1.6; }
.filter-bar { display:flex; gap:10px; flex-wrap:wrap; margin-top:20px; padding:10px 12px; border-radius:18px 18px 0 0; background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.05); border-bottom:none; }
.search-box { display:flex; align-items:center; gap:10px; flex:1; min-width:220px; color:rgba(245,247,251,.2); }
.search-box input, .filter-date input { width:100%; background:transparent; border:none; outline:none; color:rgba(245,247,251,.82); }
.filter-box, .filter-date { display:flex; align-items:center; gap:8px; min-width:150px; padding:8px 12px; border-radius:12px; background:rgba(0,0,0,.16); }
.filter-box :deep(.n-base-selection) { background:transparent !important; border:none !important; box-shadow:none !important; }
.filter-box :deep(.n-base-selection-label) { color:rgba(245,247,251,.82) !important; }
.filter-box :deep(.n-base-selection-placeholder) { color:rgba(245,247,251,.42) !important; }
.table-shell { overflow-x:auto; border:1px solid rgba(255,255,255,.05); border-radius:0 0 18px 18px; }
.transactions-table { width:100%; border-collapse:collapse; }
.transactions-table th, .transactions-table td { padding:16px 18px; text-align:left; }
.transactions-table thead th { color:rgba(245,247,251,.42); font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:.06em; border-bottom:1px solid rgba(255,255,255,.05); background:rgba(255,255,255,.02); }
.transactions-table tbody tr + tr td { border-top:1px solid rgba(255,255,255,.05); }
.transactions-table tbody td { color:rgba(245,247,251,.82); font-size:14px; }
.name-cell { color:var(--text-primary); font-weight:600; }
.mono-cell { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }
.strategy-pill, .status-pill { display:inline-flex; align-items:center; padding:4px 10px; border-radius:999px; font-size:12px; }
.strategy-pill { background:rgba(255,255,255,.08); color:rgba(245,247,251,.58); }
.status-pill.tone-success { color:var(--success-color); background:rgba(52,211,153,.12); }
.status-pill.tone-processing { color:#5eb2ff; background:rgba(0,113,227,.12); }
.status-pill.tone-failed { color:var(--error-color); background:rgba(251,113,133,.12); }
.status-pill.tone-pending { color:rgba(245,247,251,.58); background:rgba(255,255,255,.08); }
.empty-row { text-align:center; color:rgba(245,247,251,.42); }
.empty-row strong, .empty-row span { display:block; }
.empty-row strong { color:var(--text-primary); font-size:15px; }
.empty-row span { margin-top:6px; font-size:13px; }
.banner-panel { padding:40px; background:linear-gradient(135deg, rgba(0,113,227,.12), rgba(255,255,255,.02)), #111214; }
.banner-panel h2 { color:var(--text-primary); font-size:48px; font-weight:800; letter-spacing:-.05em; }
.banner-panel p { margin-top:14px; color:rgba(245,247,251,.68); font-size:18px; }
.drawer-stack { display:grid; gap:18px; }
.drawer-panel p { margin-top:8px; color:var(--text-secondary); line-height:1.7; }
@media (max-width:1200px) { .service-grid,.opportunity-grid { grid-template-columns:1fr; } }
@media (max-width:900px) { .hero-row, .section-head { flex-direction:column; align-items:stretch; } .filter-bar { flex-direction:column; align-items:stretch; } }
@media (max-width:640px) { .hero-row h1 { font-size:32px; } .banner-panel h2 { font-size:36px; } }
</style>
