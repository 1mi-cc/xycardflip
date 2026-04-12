<template>
  <div class="matching-lab-page">
    <section class="hero-row">
      <div>
        <h1>Matching Lab</h1>
        <p>
          Validate pair matching, label review candidates, and monitor rule quality
          from one place.
        </p>
      </div>
      <div class="hero-actions">
        <n-button type="primary" :loading="validating" @click="validateMatch">
          Validate Pair
        </n-button>
        <n-button secondary :loading="savingSample" @click="saveSample">
          Save Sample
        </n-button>
        <n-button secondary :loading="validatingBatch" @click="validateBatch">
          Validate Batch
        </n-button>
        <n-button secondary :loading="loadingReviewQueue" @click="loadReviewQueue">
          Refresh Queue
        </n-button>
        <n-button secondary :loading="loadingReport" @click="loadReport">
          Refresh Report
        </n-button>
      </div>
    </section>

    <section v-if="lastError" class="panel error-panel">
      <div class="panel-head">
        <div>
          <h3>Last Error</h3>
          <p>The last operation did not complete successfully.</p>
        </div>
      </div>
      <div class="empty-state">{{ lastError }}</div>
    </section>

    <section v-if="report" class="report-grid">
      <article class="panel">
        <div class="panel-head">
          <div>
            <h3>Sample Scorecard</h3>
            <p>Recent performance across saved labeled samples.</p>
          </div>
          <div class="panel-tag" :class="{ pass: report.gate?.passed, fail: !report.gate?.passed }">
            {{ reportStatusLabel }}
          </div>
        </div>
        <div class="result-list">
          <div class="result-row"><span>Total samples</span><strong>{{ report.summary?.total_samples || 0 }}</strong></div>
          <div class="result-row"><span>Scored samples</span><strong>{{ report.summary?.scored_samples || 0 }}</strong></div>
          <div class="result-row"><span>Correct</span><strong>{{ report.summary?.correct_samples || 0 }}</strong></div>
          <div class="result-row"><span>Mismatches</span><strong>{{ report.summary?.mismatch_samples || 0 }}</strong></div>
          <div class="result-row"><span>Hit rate</span><strong>{{ formatPercent(report.summary?.accuracy || 0) }}</strong></div>
        </div>
      </article>

      <article class="panel">
        <div class="panel-head">
          <div>
            <h3>Verdict Distribution</h3>
            <p>Actual predicted verdicts inside the current report window.</p>
          </div>
        </div>
        <div class="preview-list">
          <article
            v-for="item in report.actual_distribution || []"
            :key="`actual-${item.verdict}`"
            class="preview-card"
          >
            <div class="preview-top">
              <h4>{{ item.verdict }}</h4>
              <span class="panel-tag">{{ item.count }}</span>
            </div>
            <div class="result-row">
              <span>Ratio</span>
              <strong>{{ formatPercent(item.ratio || 0) }}</strong>
            </div>
          </article>
        </div>
      </article>
    </section>

    <section class="input-grid">
      <article class="panel">
        <div class="panel-head">
          <div>
            <h3>Left Item</h3>
            <p>Paste a marketplace title or canonical key override.</p>
          </div>
        </div>
        <n-input
          v-model:value="leftTitle"
          type="textarea"
          :autosize="{ minRows: 4, maxRows: 8 }"
          placeholder="Pokemon Card Charizard PSA10 in stock"
        />
        <n-input v-model:value="leftKey" placeholder="Optional canonical key override" />
      </article>

      <article class="panel">
        <div class="panel-head">
          <div>
            <h3>Right Item</h3>
            <p>Compare it against another marketplace title.</p>
          </div>
        </div>
        <n-input
          v-model:value="rightTitle"
          type="textarea"
          :autosize="{ minRows: 4, maxRows: 8 }"
          placeholder="Pokemon Card Charizard PSA 10 flagship listing"
        />
        <n-input v-model:value="rightKey" placeholder="Optional canonical key override" />
      </article>
    </section>

    <section v-if="result" class="result-grid">
      <article class="panel">
        <div class="panel-head">
          <div>
            <h3>Rule Verdict</h3>
            <p>{{ result.reason }}</p>
          </div>
          <div class="panel-tag">{{ result.verdict }}</div>
        </div>
        <div class="result-list">
          <div class="result-row"><span>Left canonical</span><strong>{{ result.left_canonical_key || "--" }}</strong></div>
          <div class="result-row"><span>Right canonical</span><strong>{{ result.right_canonical_key || "--" }}</strong></div>
          <div class="result-row"><span>Exact match</span><strong>{{ result.exact_match ? "Yes" : "No" }}</strong></div>
          <div class="result-row"><span>Token overlap</span><strong>{{ formatPercent(result.token_overlap_ratio || 0) }}</strong></div>
        </div>
      </article>

      <article class="panel">
        <div class="panel-head">
          <div>
            <h3>Token Diff</h3>
            <p>See what the current rule engine kept or dropped.</p>
          </div>
        </div>
        <div class="token-group">
          <div>
            <span>Overlap</span>
            <strong>{{ joinTokens(result.overlap_tokens) }}</strong>
          </div>
          <div>
            <span>Left only</span>
            <strong>{{ joinTokens(result.left_only_tokens) }}</strong>
          </div>
          <div>
            <span>Right only</span>
            <strong>{{ joinTokens(result.right_only_tokens) }}</strong>
          </div>
        </div>
      </article>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div>
          <h3>Review Queue</h3>
          <p>
            Program-selected cross-platform pairs that look worth labeling next.
          </p>
        </div>
      </div>
      <div class="hero-actions review-note-row">
        <n-input v-model:value="reviewNote" placeholder="Optional note attached to the next queue label" />
      </div>
      <div v-if="reviewQueueRows.length" class="preview-list">
        <article v-for="item in reviewQueueRows" :key="item.review_id" class="preview-card">
          <div class="preview-top">
            <div>
              <h4>{{ item.left?.title }}</h4>
              <p>{{ item.reason }}</p>
            </div>
            <span class="panel-tag">{{ item.predicted_verdict }}</span>
          </div>
          <div class="result-list">
            <div class="result-row"><span>Right title</span><strong>{{ item.right?.title || "--" }}</strong></div>
            <div class="result-row"><span>Platforms</span><strong>{{ (item.platforms || []).join(" / ") || "--" }}</strong></div>
            <div class="result-row"><span>Prices</span><strong>{{ formatMoney(item.left?.list_price || 0) }} / {{ formatMoney(item.right?.list_price || 0) }}</strong></div>
            <div class="result-row"><span>Canonical pair</span><strong>{{ item.left?.canonical_key || "--" }} / {{ item.right?.canonical_key || "--" }}</strong></div>
            <div class="result-row"><span>Overlap tokens</span><strong>{{ joinTokens(item.overlap_tokens) }}</strong></div>
            <div class="result-row"><span>Price band</span><strong>{{ item.price_band }} / {{ formatPercent(item.price_gap_ratio || 0) }}</strong></div>
            <div class="result-row"><span>Priority score</span><strong>{{ formatScore(item.priority_score) }}</strong></div>
          </div>
          <div class="hero-actions">
            <n-button
              size="small"
              type="primary"
              :loading="labelingReviewId === `${item.review_id}:same_group`"
              @click="labelReviewQueue(item.review_id, 'same_group')"
            >
              Mark Same Group
            </n-button>
            <n-button
              size="small"
              secondary
              :loading="labelingReviewId === `${item.review_id}:close_match`"
              @click="labelReviewQueue(item.review_id, 'close_match')"
            >
              Mark Close Match
            </n-button>
            <n-button
              size="small"
              tertiary
              :loading="labelingReviewId === `${item.review_id}:different_group`"
              @click="labelReviewQueue(item.review_id, 'different_group')"
            >
              Mark Different
            </n-button>
          </div>
        </article>
      </div>
      <div v-else class="empty-state">No review candidates are waiting right now.</div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div>
          <h3>Shadow Intents</h3>
          <p>Dry-run only automation decisions generated from cross-platform arbitrage candidates.</p>
        </div>
        <div class="panel-tag">{{ shadowStatusLabel }}</div>
      </div>
      <div class="hero-actions review-note-row">
        <n-input v-model:value="shadowReviewNote" placeholder="Optional note for marking a shadow intent reviewed" />
      </div>
      <div v-if="shadowIntentsRows.length" class="preview-list">
        <article v-for="item in shadowIntentsRows" :key="`shadow-${item.id}`" class="preview-card">
          <div class="preview-top">
            <div>
              <h4>{{ item.reference_title || item.intent_key }}</h4>
              <p>{{ item.blocked_reason || "Accepted for shadow dry-run" }}</p>
            </div>
            <span class="panel-tag">{{ item.decision_status }}</span>
          </div>
          <div class="result-list">
            <div class="result-row"><span>Platforms</span><strong>{{ item.buy_platform || "--" }} / {{ item.sell_platform || "--" }}</strong></div>
            <div class="result-row"><span>Type / Mode</span><strong>{{ shadowDecision(item).itemType }} / {{ shadowDecision(item).virtualOnly }}</strong></div>
            <div class="result-row"><span>Net / ROI</span><strong>{{ formatMoney(item.estimated_net_profit || 0) }} / {{ formatPercent(item.estimated_roi || 0) }}</strong></div>
            <div class="result-row"><span>Threshold</span><strong>{{ shadowDecision(item).threshold }}</strong></div>
            <div class="result-row"><span>Buy</span><strong>{{ shadowDecision(item).buy }}</strong></div>
            <div class="result-row"><span>Sell</span><strong>{{ shadowDecision(item).sell }}</strong></div>
            <div class="result-row"><span>Confidence</span><strong>{{ formatPercent(item.confidence_score || 0) }}</strong></div>
            <div class="result-row"><span>Reviewed</span><strong>{{ shadowDecision(item).reviewed }}</strong></div>
            <div class="result-row"><span>Created</span><strong>{{ item.created_at || "--" }}</strong></div>
          </div>
          <div class="hero-actions">
            <n-button
              size="small"
              secondary
              :loading="reviewingShadowId === item.id"
              @click="markShadowReviewed(item.id)"
            >
              Mark Reviewed
            </n-button>
          </div>
        </article>
      </div>
      <div v-else class="empty-state">No shadow intents recorded yet.</div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div>
          <h3>Batch Validation</h3>
          <p>Validate multiple title pairs in one pass with a JSON array.</p>
        </div>
      </div>
      <n-input
        v-model:value="batchJson"
        type="textarea"
        :autosize="{ minRows: 8, maxRows: 16 }"
        placeholder='[{"left_title":"Pokemon Card Charizard PSA10 in stock","right_title":"Pokemon Card Charizard PSA 10 flagship listing"}]'
      />
      <div v-if="batchRows.length" class="preview-list">
        <article v-for="(item, index) in batchRows" :key="`batch-${index}`" class="preview-card">
          <div class="preview-top">
            <div>
              <h4>{{ item.input.left_title }}</h4>
              <p>{{ item.result.reason }}</p>
            </div>
            <span class="panel-tag">{{ item.result.verdict }}</span>
          </div>
          <div class="result-list">
            <div class="result-row"><span>Right title</span><strong>{{ item.input.right_title }}</strong></div>
            <div class="result-row"><span>Canonical pair</span><strong>{{ item.result.left_canonical_key || "--" }} / {{ item.result.right_canonical_key || "--" }}</strong></div>
          </div>
        </article>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div>
          <h3>Saved Samples</h3>
          <p>Keep labeled examples here to grow your regression set.</p>
        </div>
      </div>
      <div class="hero-actions">
        <n-input v-model:value="sampleVerdict" placeholder="Expected verdict, e.g. same_group" />
        <n-input v-model:value="sampleNote" placeholder="Optional note for manual sample save" />
        <n-button secondary :loading="loadingSamples" @click="loadSamples">
          Refresh Samples
        </n-button>
      </div>
      <div v-if="sampleRows.length" class="preview-list">
        <article v-for="item in sampleRows" :key="item.id" class="preview-card">
          <div class="preview-top">
            <div>
              <h4>{{ item.left_title }}</h4>
              <p>{{ item.note || item.expected_verdict || "No note" }}</p>
            </div>
            <span class="panel-tag">{{ item.result?.verdict || "--" }}</span>
          </div>
          <div class="result-list">
            <div class="result-row"><span>Right title</span><strong>{{ item.right_title }}</strong></div>
            <div class="result-row"><span>Expected / Actual</span><strong>{{ item.expected_verdict || "--" }} / {{ item.result?.verdict || "--" }}</strong></div>
          </div>
        </article>
      </div>
      <div v-else class="empty-state">No saved samples yet.</div>
    </section>

    <section v-if="report?.mismatches?.length" class="panel">
      <div class="panel-head">
        <div>
          <h3>Recent Mismatches</h3>
          <p>Saved labels where the current rule result does not match expectation.</p>
        </div>
      </div>
      <div class="preview-list">
        <article v-for="item in report.mismatches" :key="`mismatch-${item.id}`" class="preview-card">
          <div class="preview-top">
            <div>
              <h4>{{ item.left_title }}</h4>
              <p>{{ item.note || "No note" }}</p>
            </div>
            <span class="panel-tag">{{ item.expected_verdict }} / {{ item.actual_verdict }}</span>
          </div>
          <div class="result-list">
            <div class="result-row"><span>Right title</span><strong>{{ item.right_title }}</strong></div>
            <div class="result-row"><span>Created</span><strong>{{ item.created_at }}</strong></div>
          </div>
        </article>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div>
          <h3>Matching Preview Feed</h3>
          <p>Current grouped marketplace items and why they are or are not arbitrage-ready.</p>
        </div>
      </div>
      <div v-if="previewRows.length" class="preview-list">
        <article v-for="item in previewRows" :key="item.arbitrage_key" class="preview-card">
          <div class="preview-top">
            <div>
              <h4>{{ item.reference_title }}</h4>
              <p>{{ item.reason }}</p>
            </div>
            <span class="panel-tag">{{ item.status }}</span>
          </div>
          <div class="result-list">
            <div class="result-row"><span>Platforms</span><strong>{{ item.sources.join(" / ") || "--" }}</strong></div>
            <div class="result-row"><span>Listings</span><strong>{{ item.listing_count }}</strong></div>
            <div class="result-row"><span>Net / ROI</span><strong>{{ formatMoney(item.estimated_net_profit || 0) }} / {{ formatPercent(item.estimated_roi || 0) }}</strong></div>
          </div>
        </article>
      </div>
      <div v-else class="empty-state">No grouped marketplace items yet.</div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

import cardFlipApi from "@/api/cardFlip";

const leftTitle = ref("Pokemon Card Charizard PSA10 in stock");
const leftKey = ref("");
const rightTitle = ref("Pokemon Card Charizard PSA 10 flagship listing");
const rightKey = ref("");
const result = ref(null);
const previewRows = ref([]);
const reviewQueueRows = ref([]);
const shadowIntentsRows = ref([]);
const batchJson = ref(
  JSON.stringify(
    [
      {
        left_title: "Pokemon Card Charizard PSA10 in stock",
        right_title: "Pokemon Card Charizard PSA 10 flagship listing",
      },
    ],
    null,
    2,
  ),
);
const batchRows = ref([]);
const sampleVerdict = ref("same_group");
const sampleNote = ref("");
const reviewNote = ref("");
const shadowReviewNote = ref("");
const sampleRows = ref([]);
const report = ref(null);
const lastError = ref("");
const validating = ref(false);
const loadingPreview = ref(false);
const loadingReviewQueue = ref(false);
const loadingShadowIntents = ref(false);
const validatingBatch = ref(false);
const savingSample = ref(false);
const loadingSamples = ref(false);
const loadingReport = ref(false);
const labelingReviewId = ref("");
const reviewingShadowId = ref(null);

const reportStatusLabel = computed(() => {
  if (!report.value?.gate?.ready)
    return "Not Ready";
  return report.value?.gate?.passed ? "Gate Passed" : "Gate Failed";
});

const shadowStatusLabel = computed(() => {
  if (loadingShadowIntents.value)
    return "Loading";
  const accepted = shadowIntentsRows.value.filter(item => item.decision_status === "accepted").length;
  const blocked = shadowIntentsRows.value.filter(item => item.decision_status === "blocked").length;
  return `${accepted} accepted / ${blocked} blocked`;
});

const captureError = (error) => {
  lastError.value = error?.message || String(error || "Unknown error");
};

const clearError = () => {
  lastError.value = "";
};

const validateMatch = async () => {
  clearError();
  validating.value = true;
  try {
    result.value = await cardFlipApi.validateArbitrageMatch({
      left_title: leftTitle.value,
      right_title: rightTitle.value,
      left_key: leftKey.value,
      right_key: rightKey.value,
    });
  } catch (error) {
    captureError(error);
  } finally {
    validating.value = false;
  }
};

const loadPreview = async () => {
  clearError();
  loadingPreview.value = true;
  try {
    const response = await cardFlipApi.getArbitrageMatchingPreview({
      limit: 20,
      window_hours: 72,
    });
    previewRows.value = Array.isArray(response?.items) ? response.items : [];
  } catch (error) {
    captureError(error);
  } finally {
    loadingPreview.value = false;
  }
};

const loadReviewQueue = async () => {
  clearError();
  loadingReviewQueue.value = true;
  try {
    const response = await cardFlipApi.getArbitrageReviewQueue({
      limit: 20,
      listing_hours: 24 * 30,
      candidate_pool: 300,
      min_token_overlap: 0.35,
    });
    reviewQueueRows.value = Array.isArray(response?.items) ? response.items : [];
  } catch (error) {
    captureError(error);
  } finally {
    loadingReviewQueue.value = false;
  }
};

const loadShadowIntents = async () => {
  clearError();
  loadingShadowIntents.value = true;
  try {
    const response = await cardFlipApi.listMarketplaceShadowIntents({ limit: 12 });
    shadowIntentsRows.value = Array.isArray(response?.items) ? response.items : [];
  } catch (error) {
    captureError(error);
  } finally {
    loadingShadowIntents.value = false;
  }
};

const labelReviewQueue = async (reviewId, expectedVerdict) => {
  clearError();
  labelingReviewId.value = `${reviewId}:${expectedVerdict}`;
  try {
    await cardFlipApi.labelArbitrageReviewQueueItem(
      reviewId,
      {
        expected_verdict: expectedVerdict,
        note: reviewNote.value,
      },
      {
        listing_hours: 24 * 30,
        candidate_pool: 300,
        min_token_overlap: 0.35,
      },
    );
    reviewNote.value = "";
    await Promise.all([loadReviewQueue(), loadSamples(), loadReport(), loadShadowIntents()]);
  } catch (error) {
    captureError(error);
  } finally {
    labelingReviewId.value = "";
  }
};

const markShadowReviewed = async (intentId) => {
  clearError();
  reviewingShadowId.value = intentId;
  try {
    await cardFlipApi.markMarketplaceShadowIntentReviewed(intentId, {
      note: shadowReviewNote.value,
    });
    shadowReviewNote.value = "";
    await loadShadowIntents();
  } catch (error) {
    captureError(error);
  } finally {
    reviewingShadowId.value = null;
  }
};

const validateBatch = async () => {
  clearError();
  validatingBatch.value = true;
  try {
    const parsed = JSON.parse(batchJson.value || "[]");
    const response = await cardFlipApi.validateArbitrageBatch(parsed);
    batchRows.value = Array.isArray(response?.items) ? response.items : [];
  } catch (error) {
    batchRows.value = [];
    captureError(error);
  } finally {
    validatingBatch.value = false;
  }
};

const saveSample = async () => {
  clearError();
  savingSample.value = true;
  try {
    const created = await cardFlipApi.createArbitrageMatchSample({
      left_title: leftTitle.value,
      right_title: rightTitle.value,
      left_key: leftKey.value,
      right_key: rightKey.value,
      expected_verdict: sampleVerdict.value,
      note: sampleNote.value,
    });
    if (created?.id)
      sampleNote.value = "";
    await Promise.all([loadSamples(), loadReport(), loadReviewQueue(), loadShadowIntents()]);
  } catch (error) {
    captureError(error);
  } finally {
    savingSample.value = false;
  }
};

const loadSamples = async () => {
  clearError();
  loadingSamples.value = true;
  try {
    const response = await cardFlipApi.listArbitrageMatchSamples({ limit: 20 });
    sampleRows.value = Array.isArray(response?.items) ? response.items : [];
  } catch (error) {
    captureError(error);
  } finally {
    loadingSamples.value = false;
  }
};

const loadReport = async () => {
  clearError();
  loadingReport.value = true;
  try {
    report.value = await cardFlipApi.getArbitrageMatchSampleReport({
      days: 30,
      limit: 2000,
      accuracy_threshold: 0.8,
      min_scored_samples: 10,
    });
  } catch (error) {
    captureError(error);
  } finally {
    loadingReport.value = false;
  }
};

onMounted(() => {
  void Promise.all([
    validateMatch(),
    validateBatch(),
    loadPreview(),
    loadReviewQueue(),
    loadShadowIntents(),
    loadSamples(),
    loadReport(),
  ]);
});

function joinTokens(tokens) {
  return Array.isArray(tokens) && tokens.length ? tokens.join(", ") : "--";
}

function formatPercent(value) {
  return `${new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(Number(value || 0) * 100)}%`;
}

function formatMoney(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "CNY",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

function formatScore(value) {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

function shadowDecision(item) {
  const pack = item?.decision_pack || {};
  const snapshot = item?.snapshot || {};
  const candidate = snapshot.candidate || {};
  const decision = snapshot.decision || {};
  const buy = pack.buy || candidate.buy || {};
  const sell = pack.sell || candidate.sell || {};
  const thresholdParts = [
    pack.threshold_source || decision.threshold_source || "--",
    formatMoney(pack.min_net_profit || decision.min_net_profit || 0),
    formatPercent(pack.min_roi || decision.min_roi || 0),
    formatPercent(pack.min_confidence || decision.min_confidence || 0),
  ];
  const reviewedAt = item?.reviewed_at || pack.reviewed_at || "";
  const reviewNoteText = item?.review_note || pack.review_note || "";
  return {
    itemType: pack.item_type || candidate.item_type || decision.item_type || "--",
    virtualOnly: (pack.virtual_only ?? decision.virtual_only) ? "virtual-only" : "mixed",
    threshold: thresholdParts.join(" / "),
    buy: `${buy.platform || buy.source || item?.buy_platform || "--"} ${formatMoney(buy.list_price || 0)}`,
    sell: `${sell.platform || sell.source || item?.sell_platform || "--"} ${formatMoney(sell.list_price || 0)}`,
    reviewed: reviewedAt ? `${reviewedAt}${reviewNoteText ? ` / ${reviewNoteText}` : ""}` : "Not reviewed",
  };
}
</script>

<style scoped lang="scss">
.matching-lab-page {
  display: grid;
  gap: 24px;
}

.hero-row,
.panel-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.hero-row {
  align-items: end;
}

.hero-row h1 {
  color: var(--text-primary);
  font-size: 40px;
  font-weight: 800;
  letter-spacing: -0.05em;
}

.hero-row p {
  margin-top: 8px;
  color: var(--text-muted);
  font-size: 16px;
  max-width: 820px;
}

.hero-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.review-note-row :deep(.n-input) {
  min-width: min(100%, 420px);
}

.input-grid,
.result-grid,
.report-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.panel {
  display: grid;
  gap: 16px;
  padding: 24px;
  border-radius: 20px;
  background: var(--surface-card);
  border: 1px solid var(--surface-line);
  box-shadow: var(--shadow-medium);
}

.error-panel {
  border-color: rgba(251, 113, 133, 0.24);
}

.panel-head h3 {
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 700;
}

.panel-head p {
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 12px;
}

.panel-tag {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  color: #5eb2ff;
  background: rgba(0, 113, 227, 0.12);
  border: 1px solid rgba(0, 113, 227, 0.22);
  font-size: 11px;
  font-weight: 700;
}

.panel-tag.pass {
  color: #34d399;
  background: rgba(52, 211, 153, 0.12);
  border-color: rgba(52, 211, 153, 0.22);
}

.panel-tag.fail {
  color: #fb7185;
  background: rgba(251, 113, 133, 0.12);
  border-color: rgba(251, 113, 133, 0.22);
}

.result-list,
.token-group,
.preview-list {
  display: grid;
  gap: 12px;
}

.result-row,
.token-group > div,
.preview-card {
  padding: 14px 16px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.result-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.result-row span,
.token-group span,
.preview-top p {
  color: var(--text-muted);
}

.result-row strong,
.token-group strong,
.preview-top h4 {
  color: var(--text-primary);
}

.preview-card {
  display: grid;
  gap: 14px;
}

.preview-top {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: start;
}

.empty-state {
  padding: 20px;
  border-radius: 16px;
  border: 1px dashed rgba(255, 255, 255, 0.1);
  color: var(--text-muted);
}

@media (max-width: 900px) {
  .input-grid,
  .result-grid,
  .report-grid {
    grid-template-columns: 1fr;
  }

  .hero-row {
    flex-direction: column;
    align-items: stretch;
  }
}

@media (max-width: 640px) {
  .hero-row h1 {
    font-size: 32px;
  }
}
</style>
