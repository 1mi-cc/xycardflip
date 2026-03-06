import axios from "axios";

const cardFlipRequest = axios.create({
  baseURL: import.meta.env.VITE_CARD_FLIP_API_BASE || "/card-api",
  timeout: 60000,
  proxy: false,
  headers: {
    "Content-Type": "application/json",
  },
});

cardFlipRequest.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message =
      error?.response?.data?.detail
      || error?.response?.data?.message
      || error?.message
      || "request failed";
    const wrapped = new Error(message);
    wrapped.status = error?.response?.status || 0;
    wrapped.payload = error?.response?.data || null;
    return Promise.reject(wrapped);
  },
);

const cardFlipApi = {
  refreshMonitorCookie(killBrowsers = true) {
    return cardFlipRequest.post("/monitor/refresh-cookie", null, {
      params: {
        kill_browsers: killBrowsers,
      },
    });
  },
  getMonitorStatus() {
    return cardFlipRequest.get("/monitor/status");
  },
  startMonitor() {
    return cardFlipRequest.post("/monitor/start");
  },
  resetMonitorCircuit(reason = "manual reset") {
    return cardFlipRequest.post("/monitor/reset-circuit", null, {
      params: { reason },
    });
  },
  scanOpportunities(limit = 100) {
    return cardFlipRequest.post("/opportunities/scan", null, {
      params: { limit },
    });
  },
  listOpportunities(status = "pending_review", limit = 200) {
    return cardFlipRequest.get("/opportunities", {
      params: { status, limit },
    });
  },
  approveTrade(payload) {
    return cardFlipRequest.post("/trades/approve", payload);
  },
  listTrades(status = null, limit = 200) {
    const params = { limit };
    if (status)
      params.status = status;
    return cardFlipRequest.get("/trades", {
      params,
    });
  },
  markTradeListed(tradeId, payload) {
    return cardFlipRequest.post(`/trades/${tradeId}/mark-listed`, payload);
  },
  markTradeSold(tradeId, payload) {
    return cardFlipRequest.post(`/trades/${tradeId}/mark-sold`, payload);
  },
  getTradePricingPlan(tradeId, mode = "balanced") {
    return cardFlipRequest.get(`/trades/${tradeId}/pricing-plan`, {
      params: { mode },
    });
  },
  applyTradePricingPlan(tradeId, mode = "balanced", note = "auto pricing plan") {
    return cardFlipRequest.post(`/trades/${tradeId}/apply-pricing-plan`, null, {
      params: { mode, note },
    });
  },
  repriceOpenTrades(mode = "balanced", limit = 100, apply = false, note = "batch auto pricing plan") {
    return cardFlipRequest.post("/trades/reprice-open", null, {
      params: { mode, limit, apply, note },
    });
  },
  rejectOpportunity(opportunityId, note = "manual reject from ui") {
    return cardFlipRequest.post(`/opportunities/${opportunityId}/reject`, null, {
      params: { note },
    });
  },
  sendOpportunityToReview(opportunityId, note = "manual review override from ui") {
    return cardFlipRequest.post(`/opportunities/${opportunityId}/send-to-review`, null, {
      params: { note },
    });
  },
  sendBlockedToReviewBatch(maxRiskScore = 45, limit = 200, note = "manual batch review override from ui") {
    return cardFlipRequest.post("/opportunities/send-to-review/batch", null, {
      params: {
        max_risk_score: maxRiskScore,
        limit,
        note,
      },
    });
  },
  rejectBlockedBatch(limit = 200, note = "manual batch reject from blocked list ui") {
    return cardFlipRequest.post("/opportunities/reject/batch", null, {
      params: { limit, note },
    });
  },
  getMetrics() {
    return cardFlipRequest.get("/trades/metrics-summary");
  },
  getHealth() {
    return cardFlipRequest.get("/health");
  },
  getListing(listingRowId) {
    return cardFlipRequest.get(`/listings/${listingRowId}`);
  },
  getAutomationStatus() {
    return cardFlipRequest.get("/automation/status");
  },
  startAutomation(
    includeMonitor = true,
    includeAutotrade = true,
    includeExecutionRetry = true,
  ) {
    return cardFlipRequest.post("/automation/start", null, {
      params: {
        include_monitor: includeMonitor,
        include_autotrade: includeAutotrade,
        include_execution_retry: includeExecutionRetry,
      },
    });
  },
  stopAutomation(
    includeMonitor = true,
    includeAutotrade = true,
    includeExecutionRetry = true,
  ) {
    return cardFlipRequest.post("/automation/stop", null, {
      params: {
        include_monitor: includeMonitor,
        include_autotrade: includeAutotrade,
        include_execution_retry: includeExecutionRetry,
      },
    });
  },
  runAutomationOnce(
    {
      includeMonitor = true,
      includeScan = true,
      includeAutotrade = true,
      includeExecutionRetry = true,
      scanLimit = 0,
      autotradeLimit = 0,
      executionRetryLimit = 0,
      force = false,
      confirmToken = "",
    } = {},
  ) {
    const params = {
      include_monitor: includeMonitor,
      include_scan: includeScan,
      include_autotrade: includeAutotrade,
      include_execution_retry: includeExecutionRetry,
      scan_limit: scanLimit,
      autotrade_limit: autotradeLimit,
      execution_retry_limit: executionRetryLimit,
      force,
    };
    if (confirmToken)
      params.confirm_token = confirmToken;
    return cardFlipRequest.post("/automation/run-once", null, { params });
  },
  bootstrapSimulationData(count = 6) {
    return cardFlipRequest.post("/automation/simulation-bootstrap", null, {
      params: { count },
    });
  },
  getAutotradeStatus() {
    return cardFlipRequest.get("/autotrade/status");
  },
  startAutotrade() {
    return cardFlipRequest.post("/autotrade/start");
  },
  stopAutotrade() {
    return cardFlipRequest.post("/autotrade/stop");
  },
  runAutotradeOnce(limit = 0, force = false) {
    return cardFlipRequest.post("/autotrade/run-once", null, {
      params: { limit, force },
    });
  },
  updateAutotradeConfig(payload = {}) {
    return cardFlipRequest.post("/autotrade/config", payload);
  },
  getExecutionRetryStatus() {
    return cardFlipRequest.get("/execution-retry/status");
  },
  startExecutionRetry() {
    return cardFlipRequest.post("/execution-retry/start");
  },
  stopExecutionRetry() {
    return cardFlipRequest.post("/execution-retry/stop");
  },
  runExecutionRetryOnce(
    limit = 0,
    force = false,
    action = null,
    dryRun = null,
    executionForce = null,
    confirmToken = "",
  ) {
    const params = { limit, force };
    if (action)
      params.action = action;
    if (typeof dryRun === "boolean")
      params.dry_run = dryRun;
    if (typeof executionForce === "boolean")
      params.execution_force = executionForce;
    if (confirmToken)
      params.confirm_token = confirmToken;
    return cardFlipRequest.post("/execution-retry/run-once", null, { params });
  },
  updateExecutionRetryConfig(payload = {}) {
    return cardFlipRequest.post("/execution-retry/config", payload);
  },
  getExecutionStatus() {
    return cardFlipRequest.get("/execution/status");
  },
  updateExecutionConfig(payload = {}) {
    return cardFlipRequest.post("/execution/config", payload);
  },
  executeBuy(tradeId, dryRun = true, force = false, confirmToken = "") {
    const params = { dry_run: dryRun, force };
    if (confirmToken)
      params.confirm_token = confirmToken;
    return cardFlipRequest.post(`/execution/buy/${tradeId}`, null, {
      params,
    });
  },
  executeList(
    tradeId,
    dryRun = true,
    force = false,
    confirmToken = "",
    listingUrl = "",
    updateTradeState = true,
    note = "",
  ) {
    const params = { dry_run: dryRun, force, update_trade_state: updateTradeState };
    if (confirmToken)
      params.confirm_token = confirmToken;
    if (listingUrl)
      params.listing_url = listingUrl;
    if (note)
      params.note = note;
    return cardFlipRequest.post(`/execution/list/${tradeId}`, null, {
      params,
    });
  },
  executeSell(
    tradeId,
    dryRun = true,
    force = false,
    confirmToken = "",
    soldPrice = null,
    updateTradeState = true,
    note = "",
  ) {
    const params = { dry_run: dryRun, force, update_trade_state: updateTradeState };
    if (confirmToken)
      params.confirm_token = confirmToken;
    if (typeof soldPrice === "number")
      params.sold_price = soldPrice;
    if (note)
      params.note = note;
    return cardFlipRequest.post(`/execution/sell/${tradeId}`, null, {
      params,
    });
  },
  retryFailedExecution(action = null, limit = 20, dryRun = true, force = false, confirmToken = "") {
    const params = { limit, dry_run: dryRun, force };
    if (action)
      params.action = action;
    if (confirmToken)
      params.confirm_token = confirmToken;
    return cardFlipRequest.post("/execution/retry-failed", null, { params });
  },
  listExecutionLogs(params = {}) {
    return cardFlipRequest.get("/execution/logs", { params });
  },
};

export default cardFlipApi;
