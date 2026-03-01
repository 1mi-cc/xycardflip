import axios from "axios";

const cardFlipRequest = axios.create({
  baseURL: import.meta.env.VITE_CARD_FLIP_API_BASE || "/card-api",
  timeout: 15000,
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
    return Promise.reject(new Error(message));
  },
);

const cardFlipApi = {
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
  getMetrics() {
    return cardFlipRequest.get("/trades/metrics-summary");
  },
  getListing(listingRowId) {
    return cardFlipRequest.get(`/listings/${listingRowId}`);
  },
};

export default cardFlipApi;
