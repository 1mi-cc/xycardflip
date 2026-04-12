import axios from "axios";

import { useAuthStore } from "@/stores/auth";

const request = axios.create({
  baseURL: import.meta.env.VITE_CARD_FLIP_API_BASE || "/card-api",
  timeout: 60000,
  headers: {
    "Content-Type": "application/json",
  },
});

const stringifyError = (value) => {
  if (typeof value === "string") {
    const text = value.trim();
    return text && text !== "[object Object]" ? text : "";
  }
  if (Array.isArray(value)) {
    return value.map(item => stringifyError(item)).filter(Boolean).join("; ");
  }
  if (!value || typeof value !== "object")
    return "";

  for (const key of ["detail", "message", "reason", "error", "msg"]) {
    const text = stringifyError(value[key]);
    if (text)
      return text;
  }

  return Object.values(value)
    .map(item => stringifyError(item))
    .filter(Boolean)
    .join("; ");
};

request.interceptors.request.use((config) => {
  const authStore = useAuthStore();
  if (authStore.token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${authStore.token}`;
  }
  return config;
});

request.interceptors.response.use(
  response => response.data,
  (error) => {
    const message = stringifyError(error?.response?.data)
      || stringifyError(error?.message)
      || "请求失败，请稍后重试";
    const wrapped = new Error(message);
    wrapped.status = error?.response?.status || 0;
    wrapped.payload = error?.response?.data || null;
    return Promise.reject(wrapped);
  },
);

const cardFlipApi = {
  getAdminTransparencyOverview() {
    return request.get("/analysis/admin-overview");
  },
  getAnalysisReport(params = {}) {
    return request.get("/analysis/report", {
      params: {
        ...params,
        limit: Number.isFinite(Number(params.limit))
          ? Math.min(500, Math.max(1, Math.trunc(Number(params.limit))))
          : 100,
      },
    });
  },
  getPriceHistory(params = {}) {
    return request.get("/analysis/data/price-history", {
      params: {
        ...params,
        limit: Number.isFinite(Number(params.limit))
          ? Math.min(500, Math.max(1, Math.trunc(Number(params.limit))))
          : 30,
      },
    });
  },
  getArbitrageOpportunities(params = {}) {
    return request.get("/analysis/arbitrage/opportunities", {
      params: {
        ...params,
        limit: Number.isFinite(Number(params.limit))
          ? Math.min(100, Math.max(1, Math.trunc(Number(params.limit))))
          : 10,
      },
    });
  },
  getArbitrageMatchingPreview(params = {}) {
    return request.get("/analysis/arbitrage/matching-preview", {
      params: {
        ...params,
        limit: Number.isFinite(Number(params.limit))
          ? Math.min(100, Math.max(1, Math.trunc(Number(params.limit))))
          : 10,
      },
    });
  },
  validateArbitrageMatch(payload) {
    return request.post("/analysis/arbitrage/validate-match", payload);
  },
  validateArbitrageBatch(payload) {
    return request.post("/analysis/arbitrage/validate-batch", payload);
  },
  createArbitrageMatchSample(payload) {
    return request.post("/analysis/arbitrage/match-samples", payload);
  },
  listArbitrageMatchSamples(params = {}) {
    return request.get("/analysis/arbitrage/match-samples", {
      params: {
        ...params,
        limit: Number.isFinite(Number(params.limit))
          ? Math.min(500, Math.max(1, Math.trunc(Number(params.limit))))
          : 50,
      },
    });
  },
  getArbitrageMatchSampleReport(params = {}) {
    return request.get("/analysis/arbitrage/match-samples/report", {
      params,
    });
  },
  getArbitrageReviewQueue(params = {}) {
    return request.get("/analysis/arbitrage/review-queue", {
      params: {
        ...params,
        limit: Number.isFinite(Number(params.limit))
          ? Math.min(100, Math.max(1, Math.trunc(Number(params.limit))))
          : 20,
      },
    });
  },
  labelArbitrageReviewQueueItem(reviewId, payload, params = {}) {
    return request.post(`/analysis/arbitrage/review-queue/${reviewId}/label`, payload, {
      params,
    });
  },
  ingestMarketplaceOffers(rows) {
    return request.post("/marketplace/offers/ingest", rows);
  },
  ingestTaobaoSnapshot(payload) {
    return request.post("/marketplace/providers/taobao/ingest-snapshot", payload);
  },
  getTaobaoProviderStatus() {
    return request.get("/marketplace/providers/taobao/status");
  },
  syncTaobaoOnce(params = {}) {
    return request.post("/marketplace/providers/taobao/sync-once", null, {
      params,
    });
  },
  ingestPinduoduoSnapshot(payload) {
    return request.post("/marketplace/providers/pinduoduo/ingest-snapshot", payload);
  },
  getPinduoduoProviderStatus() {
    return request.get("/marketplace/providers/pinduoduo/status");
  },
  syncPinduoduoOnce(params = {}) {
    return request.post("/marketplace/providers/pinduoduo/sync-once", null, {
      params,
    });
  },
  ingestJdSnapshot(payload) {
    return request.post("/marketplace/providers/jd/ingest-snapshot", payload);
  },
  getJdProviderStatus() {
    return request.get("/marketplace/providers/jd/status");
  },
  syncJdOnce(params = {}) {
    return request.post("/marketplace/providers/jd/sync-once", null, {
      params,
    });
  },
  listMarketplaceOffers(params = {}) {
    return request.get("/marketplace/offers", {
      params: {
        ...params,
        limit: Number.isFinite(Number(params.limit))
          ? Math.min(500, Math.max(1, Math.trunc(Number(params.limit))))
          : 50,
      },
    });
  },
  getMarketplacePlatformHealth(params = {}) {
    return request.get("/marketplace/platforms/health", {
      params,
    });
  },
  getMarketplaceProviderStatus(params = {}) {
    return request.get("/marketplace/providers/status", {
      params,
    });
  },
  getMarketplaceShadowStatus() {
    return request.get("/marketplace/shadow/status");
  },
  getMarketplaceShadowVirtualReport(params = {}) {
    return request.get("/marketplace/shadow/virtual-report", {
      params: {
        ...params,
        limit: Number.isFinite(Number(params.limit))
          ? Math.min(500, Math.max(1, Math.trunc(Number(params.limit))))
          : 200,
      },
    });
  },
  runMarketplaceShadowOnce(params = {}) {
    return request.post("/marketplace/shadow/run-once", null, {
      params,
    });
  },
  listMarketplaceShadowIntents(params = {}) {
    return request.get("/marketplace/shadow/intents", {
      params: {
        ...params,
        limit: Number.isFinite(Number(params.limit))
          ? Math.min(500, Math.max(1, Math.trunc(Number(params.limit))))
        : 50,
      },
    });
  },
  getMarketplaceShadowIntent(intentId) {
    return request.get(`/marketplace/shadow/intents/${intentId}`);
  },
  markMarketplaceShadowIntentReviewed(intentId, payload = {}) {
    return request.post(`/marketplace/shadow/intents/${intentId}/review`, payload);
  },
  markMarketplaceShadowIntentOutcome(intentId, payload = {}) {
    return request.post(`/marketplace/shadow/intents/${intentId}/outcome`, payload);
  },
  listMarketplaceShadowRuns(params = {}) {
    return request.get("/marketplace/shadow/runs", {
      params: {
        ...params,
        limit: Number.isFinite(Number(params.limit))
          ? Math.min(200, Math.max(1, Math.trunc(Number(params.limit))))
          : 20,
      },
    });
  },
  backfillMarketplaceOffers(params = {}) {
    return request.post("/marketplace/offers/backfill", null, {
      params,
    });
  },
  getTradeRecords(params = {}) {
    return request.get("/analysis/data/trade-records", {
      params: {
        ...params,
        limit: Number.isFinite(Number(params.limit))
          ? Math.min(500, Math.max(1, Math.trunc(Number(params.limit))))
          : 50,
      },
    });
  },
  ingestListings(rows) {
    return request.post("/ingest/listings", rows);
  },
  scanOpportunities(params = {}) {
    return request.post("/opportunities/scan", null, {
      params: {
        ...params,
        limit: Number.isFinite(Number(params.limit))
          ? Math.min(500, Math.max(1, Math.trunc(Number(params.limit))))
          : 50,
      },
    });
  },
  listOpportunities(params = {}) {
    return request.get("/opportunities", {
      params: {
        ...params,
        limit: Number.isFinite(Number(params.limit))
          ? Math.min(500, Math.max(1, Math.trunc(Number(params.limit))))
        : 50,
      },
    });
  },
  getArbitrageCandidates(params = {}) {
    return request.get("/arbitrage/candidates", {
      params: {
        ...params,
        limit: Number.isFinite(Number(params.limit))
          ? Math.min(100, Math.max(1, Math.trunc(Number(params.limit))))
          : 12,
      },
    });
  },
  getArbitrageSourceHealth(params = {}) {
    return request.get("/arbitrage/sources/health", {
      params,
    });
  },
  approveTrade(payload) {
    return request.post("/trades/approve", payload);
  },
  rejectOpportunity(opportunityId, params = {}) {
    return request.post(`/opportunities/${opportunityId}/reject`, null, {
      params,
    });
  },
  sendOpportunityToReview(opportunityId, params = {}) {
    return request.post(`/opportunities/${opportunityId}/send-to-review`, null, {
      params,
    });
  },
  getMetrics() {
    return request.get("/trades/metrics-summary");
  },
  getAutotradeStatus() {
    return request.get("/autotrade/status");
  },
  startAutotrade() {
    return request.post("/autotrade/start");
  },
  stopAutotrade() {
    return request.post("/autotrade/stop");
  },
  runAutotradeOnce(params = {}) {
    return request.post("/autotrade/run-once", null, {
      params,
    });
  },
  getMonitorStatus() {
    return request.get("/monitor/status");
  },
  getAutomationStatus() {
    return request.get("/automation/status");
  },
  startAutomation(params = {}) {
    return request.post("/automation/start", null, {
      params,
    });
  },
  stopAutomation(params = {}) {
    return request.post("/automation/stop", null, {
      params,
    });
  },
  runAutomationOnce(params = {}) {
    return request.post("/automation/run-once", null, {
      params,
    });
  },
  startMonitor() {
    return request.post("/monitor/start");
  },
  stopMonitor() {
    return request.post("/monitor/stop");
  },
  runMonitorOnce() {
    return request.post("/monitor/run-once");
  },
  getExecutionRetryStatus() {
    return request.get("/execution-retry/status");
  },
  startExecutionRetry() {
    return request.post("/execution-retry/start");
  },
  stopExecutionRetry() {
    return request.post("/execution-retry/stop");
  },
  runExecutionRetryOnce(params = {}) {
    return request.post("/execution-retry/run-once", null, {
      params,
    });
  },
  listExecutionLogs(params = {}) {
    return request.get("/execution/logs", {
      params: {
        ...params,
        limit: Number.isFinite(Number(params.limit))
          ? Math.min(500, Math.max(1, Math.trunc(Number(params.limit))))
          : 100,
      },
    });
  },
};

export default cardFlipApi;
