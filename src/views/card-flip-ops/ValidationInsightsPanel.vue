<template>
  <section class="service-panel">
    <div class="service-head">
      <div class="service-copy">
        <div class="service-kicker">Validation Loop</div>
        <h3>Forward Validation</h3>
        <p>
          Run a tracked sample batch so you can tune the profit preset with hit
          rate, realized ROI, and holding time instead of only headline profit.
        </p>
      </div>

      <n-space>
        <n-button
          v-if="activeBatch"
          type="warning"
          :disabled="!canOperate"
          :loading="forwardValidationActionLoading === 'close'"
          @click="$emit('closeForwardValidationBatch', activeBatch)"
        >
          Close Batch
        </n-button>
        <n-button
          v-else
          type="primary"
          :disabled="!canOperate"
          :loading="forwardValidationActionLoading === 'create'"
          @click="$emit('openForwardValidationBatchModal')"
        >
          Create Batch
        </n-button>
      </n-space>
    </div>

    <div class="validation-status-row">
      <n-tag size="small" :type="activeBatch ? 'success' : 'default'">
        {{ activeBatch ? `Open #${activeBatch.id}` : "No open batch" }}
      </n-tag>
      <n-tag v-if="activeBatch?.auto_enroll" size="small" type="info">
        Auto Enroll
      </n-tag>
      <n-tag size="small" type="info">
        {{ recentBatches.length }} recent batches
      </n-tag>
    </div>

    <div class="service-section">
      <div class="validation-recommendation-head">
        <div>
          <div class="summary-label">Auto Apply</div>
          <div class="summary-value">
            {{ autotradeStatus?.tuning_auto_apply_enabled ? "Enabled" : "Disabled" }}
          </div>
          <div class="summary-meta">
            Cooldown {{ autotradeStatus?.tuning_cooldown_hours ?? 0 }}h /
            closed batches {{ autotradeStatus?.tuning_min_closed_batches ?? 0 }}
          </div>
        </div>

        <n-space>
          <n-button
            size="small"
            :disabled="!canOperate"
            :loading="autotradeConfigLoading"
            :type="autotradeStatus?.tuning_auto_apply_enabled ? 'success' : 'default'"
            @click="$emit('toggleAutoTuneAutoApply')"
          >
            {{ autotradeStatus?.tuning_auto_apply_enabled ? "Auto Apply On" : "Auto Apply Off" }}
          </n-button>
          <n-button
            size="small"
            :disabled="!canOperate || autotradeConfigLoading"
            @click="$emit('adjustAutoTuneCooldown', -6)"
          >
            -6h
          </n-button>
          <n-button quaternary size="small">
            {{ autotradeStatus?.tuning_cooldown_hours ?? 0 }}h
          </n-button>
          <n-button
            size="small"
            :disabled="!canOperate || autotradeConfigLoading"
            @click="$emit('adjustAutoTuneCooldown', 6)"
          >
            +6h
          </n-button>
        </n-space>
      </div>
    </div>

    <div class="service-section">
      <div class="validation-recommendation-head">
        <div>
          <div class="summary-label">24h Auto-tune Report</div>
          <div class="summary-value">
            {{ tuningDailyReportLoading ? "Loading..." : `${autotradeTuningDailyReport?.activity_count || 0} activities` }}
          </div>
          <div class="summary-meta">
            Latest:
            {{ latestActivitySummary }}
          </div>
        </div>
      </div>

      <div class="validation-grid">
        <div class="summary-chip">
          <div class="summary-label">Applied</div>
          <div class="summary-value">
            {{ tuningCount("auto_tune_applied") }}
          </div>
        </div>
        <div class="summary-chip">
          <div class="summary-label">Blocked</div>
          <div class="summary-value">
            {{ tuningCount("auto_tune_blocked") }}
          </div>
        </div>
        <div class="summary-chip">
          <div class="summary-label">Disabled</div>
          <div class="summary-value">
            {{ tuningCount("auto_tune_disabled") }}
          </div>
        </div>
        <div class="summary-chip">
          <div class="summary-label">Rollbacks</div>
          <div class="summary-value">
            {{ tuningCount("tuning_rollback") }}
          </div>
        </div>
      </div>

      <n-space
        v-if="topBlockedReasons.length > 0"
        wrap
      >
        <n-tag
          v-for="item in topBlockedReasons"
          :key="`${item.reason}-${item.count}`"
          size="small"
          type="warning"
        >
          {{ item.reason }} x{{ item.count }}
        </n-tag>
      </n-space>
    </div>

    <div v-if="recommendation" class="service-section">
      <div class="validation-recommendation-head">
        <div>
          <div class="summary-label">Recommendation</div>
          <div class="summary-value">
            {{ recommendation.title }}
          </div>
          <div class="summary-meta">
            {{ recommendation.summary }}
          </div>
        </div>

        <n-space>
          <n-tag size="small" :type="recommendation.tagType">
            {{ recommendation.confidenceLabel }}
          </n-tag>
          <n-button
            v-if="recommendation.recommendedProfile"
            size="small"
            type="primary"
            :disabled="!canOperate || recommendation.recommendedProfile === strategyProfile"
            :loading="strategyProfileLoading"
            @click="$emit('applyRecommendedStrategyProfile', recommendation.recommendedProfile)"
          >
            Apply {{ recommendation.recommendedLabel }}
          </n-button>
        </n-space>
      </div>

      <n-space wrap>
        <n-tag
          v-for="reason in recommendation.reasons"
          :key="reason"
          size="small"
          :type="recommendation.tagType"
        >
          {{ reason }}
        </n-tag>
      </n-space>
    </div>

    <div v-if="validationAutoTuneProposal" class="service-section">
      <div class="validation-recommendation-head">
        <div>
          <div class="summary-label">Threshold Tune</div>
          <div class="summary-value">
            {{ validationAutoTuneProposal.title }}
          </div>
          <div class="summary-meta">
            {{ validationAutoTuneProposal.summary }}
          </div>
        </div>

        <n-space>
          <n-tag size="small" :type="validationAutoTuneProposal.tagType">
            {{
              validationAutoTuneProposal.shouldApply
                ? (validationAutoTuneGuard?.ready ? "Ready to apply" : "Guarded")
                : "No change"
            }}
          </n-tag>
          <n-button
            size="small"
            type="primary"
            :disabled="!canOperate || !validationAutoTuneProposal.shouldApply || !validationAutoTuneGuard?.ready"
            :loading="autotradeConfigLoading"
            @click="$emit('applyValidationAutoTune', validationAutoTuneProposal)"
          >
            Apply Threshold Tune
          </n-button>
        </n-space>
      </div>

      <div class="validation-grid">
        <div class="summary-chip">
          <div class="summary-label">Min Score</div>
          <div class="summary-value">
            {{ formatScore(validationAutoTuneProposal.current.min_score) }}
            -> {{ formatScore(validationAutoTuneProposal.next.min_score) }}
          </div>
          <div class="summary-meta">
            {{ formatSignedScore(validationAutoTuneProposal.delta.min_score) }}
          </div>
        </div>
        <div class="summary-chip">
          <div class="summary-label">Min ROI</div>
          <div class="summary-value">
            {{ toPercent(validationAutoTuneProposal.current.min_roi) }}
            -> {{ toPercent(validationAutoTuneProposal.next.min_roi) }}
          </div>
          <div class="summary-meta">
            {{ formatSignedPercent(validationAutoTuneProposal.delta.min_roi) }}
          </div>
        </div>
        <div class="summary-chip">
          <div class="summary-label">Max Risk</div>
          <div class="summary-value">
            {{ formatScore(validationAutoTuneProposal.current.max_risk_score) }}
            -> {{ formatScore(validationAutoTuneProposal.next.max_risk_score) }}
          </div>
          <div class="summary-meta">
            {{ formatSignedScore(validationAutoTuneProposal.delta.max_risk_score) }}
          </div>
        </div>
      </div>

      <n-space wrap>
        <n-tag
          v-for="reason in validationAutoTuneProposal.reasons"
          :key="`tune-${reason}`"
          size="small"
          :type="validationAutoTuneProposal.tagType"
        >
          {{ reason }}
        </n-tag>
      </n-space>
      <n-space wrap style="margin-top: 8px">
        <n-tag
          v-for="reason in validationAutoTuneGuard?.reasons || []"
          :key="`guard-${reason}`"
          size="small"
          :type="validationAutoTuneGuard?.ready ? 'success' : 'warning'"
        >
          {{ reason }}
        </n-tag>
      </n-space>
    </div>

    <div v-if="activeBatch" class="validation-grid">
      <div class="summary-chip">
        <div class="summary-label">Batch</div>
        <div class="summary-value">{{ activeBatch.name }}</div>
        <div class="summary-meta">{{ formatBatchProgress(activeBatch) }}</div>
      </div>
      <div class="summary-chip">
        <div class="summary-label">Hit Rate</div>
        <div class="summary-value">{{ toPercent(activeBatch.profit_hit_rate) }}</div>
        <div class="summary-meta">sold {{ activeBatch.sold_count || 0 }}</div>
      </div>
      <div class="summary-chip">
        <div class="summary-label">Avg ROI</div>
        <div class="summary-value">{{ toPercent(activeBatch.avg_realized_roi) }}</div>
        <div class="summary-meta">net {{ toMoney(activeBatch.realized_net_profit) }}</div>
      </div>
      <div class="summary-chip">
        <div class="summary-label">Holding</div>
        <div class="summary-value">{{ formatDays(activeBatch.avg_holding_days) }}</div>
        <div class="summary-meta">created {{ activeBatch.created_at || "-" }}</div>
      </div>
    </div>

    <div v-else class="empty-wrap">
      <n-empty description="No open validation batch"></n-empty>
    </div>

    <div v-if="activeBatch?.items?.length" class="validation-table-block">
      <div class="validation-table-title">Open Batch Items</div>
      <n-table striped class="ops-table" size="small">
        <thead>
          <tr>
            <th>Trade ID</th>
            <th>Title</th>
            <th>Status</th>
            <th>Buy</th>
            <th>Target</th>
            <th>Sold</th>
            <th>Enrolled</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in activeBatch.items" :key="item.trade_id">
            <td>{{ item.trade_id }}</td>
            <td class="title-cell">{{ item.title }}</td>
            <td>
              <n-tag size="small" :type="item.status === 'sold' ? 'success' : 'info'">
                {{ getTradeStatusText(item.status) }}
              </n-tag>
            </td>
            <td>{{ toMoney(item.approved_buy_price) }}</td>
            <td>{{ toMoney(item.target_sell_price) }}</td>
            <td>{{ item.sold_price == null ? "-" : toMoney(item.sold_price) }}</td>
            <td>{{ item.enrolled_at || "-" }}</td>
          </tr>
        </tbody>
      </n-table>
    </div>

    <div class="validation-table-block">
      <div class="validation-table-title">Recent Batches</div>
      <div v-if="recentBatches.length === 0" class="empty-wrap">
        <n-empty description="No validation history"></n-empty>
      </div>

      <n-table v-else striped class="ops-table" size="small">
        <thead>
          <tr>
            <th>Name</th>
            <th>Status</th>
            <th>Progress</th>
            <th>Sold</th>
            <th>Hit Rate</th>
            <th>Avg ROI</th>
            <th>Holding</th>
            <th>Created</th>
            <th>Closed</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="batch in recentBatches" :key="batch.id">
            <td class="title-cell">{{ batch.name }}</td>
            <td>
              <n-tag size="small" :type="batch.status === 'open' ? 'success' : 'default'">
                {{ getValidationStatusText(batch.status) }}
              </n-tag>
            </td>
            <td>{{ formatBatchProgress(batch) }}</td>
            <td>{{ batch.sold_count || 0 }}</td>
            <td>{{ toPercent(batch.profit_hit_rate) }}</td>
            <td>{{ toPercent(batch.avg_realized_roi) }}</td>
            <td>{{ formatDays(batch.avg_holding_days) }}</td>
            <td>{{ batch.created_at || "-" }}</td>
            <td>{{ batch.closed_at || "-" }}</td>
          </tr>
        </tbody>
      </n-table>
    </div>

    <div class="validation-table-block">
      <div class="validation-table-title">Decision Feed</div>
      <div v-if="tuningActivityLoading" class="empty-wrap">
        <n-spin :show="true"></n-spin>
      </div>
      <div v-else-if="autotradeTuningActivity.length === 0" class="empty-wrap">
        <n-empty description="No tuning activity yet"></n-empty>
      </div>

      <n-table v-else striped class="ops-table" size="small">
        <thead>
          <tr>
            <th>Time</th>
            <th>Decision</th>
            <th>Trigger</th>
            <th>Actor</th>
            <th>Summary</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in autotradeTuningActivity" :key="`activity-${item.id}`">
            <td>{{ item.created_at || "-" }}</td>
            <td>
              <n-tag size="small" :type="decisionTagType(item.decision_type)">
                {{ item.decision_type || "-" }}
              </n-tag>
            </td>
            <td class="title-cell">{{ item.trigger_source || "-" }}</td>
            <td>{{ item.actor || "-" }}</td>
            <td class="title-cell">{{ item.summary || "-" }}</td>
          </tr>
        </tbody>
      </n-table>
    </div>

    <div class="validation-table-block">
      <div class="validation-table-title">Tuning Audit Trail</div>
      <div v-if="tuningHistoryLoading" class="empty-wrap">
        <n-spin :show="true"></n-spin>
      </div>
      <div v-else-if="autotradeTuningHistory.length === 0" class="empty-wrap">
        <n-empty description="No tuning history yet"></n-empty>
      </div>

      <n-table v-else striped class="ops-table" size="small">
        <thead>
          <tr>
            <th>ID</th>
            <th>Time</th>
            <th>Source</th>
            <th>Applied By</th>
            <th>Change</th>
            <th>Note</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="event in autotradeTuningHistory" :key="event.id">
            <td>{{ event.id }}</td>
            <td>{{ event.created_at || "-" }}</td>
            <td>{{ event.source || "-" }}</td>
            <td>{{ event.applied_by || "-" }}</td>
            <td class="title-cell">
              score {{ formatScore(event.previous_config?.min_score) }} -> {{ formatScore(event.next_config?.min_score) }}
              / roi {{ toPercent(event.previous_config?.min_roi) }} -> {{ toPercent(event.next_config?.min_roi) }}
              / risk {{ formatScore(event.previous_config?.max_risk_score) }} -> {{ formatScore(event.next_config?.max_risk_score) }}
            </td>
            <td class="title-cell">{{ event.note || "-" }}</td>
            <td>
              <n-button
                tertiary
                size="small"
                type="warning"
                :disabled="!canOperate"
                :loading="tuningHistoryActionLoading === `rollback:${event.id}`"
                @click="$emit('rollbackAutotradeTune', event)"
              >
                Rollback
              </n-button>
            </td>
          </tr>
        </tbody>
      </n-table>
    </div>
  </section>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  canOperate: { type: Boolean, default: false },
  forwardValidation: { type: Object, default: () => ({}) },
  forwardValidationActionLoading: { type: String, default: "" },
  strategyProfile: { type: String, default: "balanced" },
  strategyProfileLoading: { type: Boolean, default: false },
  validationAutoTuneProposal: { type: Object, default: null },
  validationAutoTuneGuard: { type: Object, default: null },
  autotradeConfigLoading: { type: Boolean, default: false },
  autotradeStatus: { type: Object, default: () => ({}) },
  autotradeTuningActivity: { type: Array, default: () => [] },
  autotradeTuningDailyReport: { type: Object, default: () => ({}) },
  autotradeTuningHistory: { type: Array, default: () => [] },
  tuningActivityLoading: { type: Boolean, default: false },
  tuningDailyReportLoading: { type: Boolean, default: false },
  tuningHistoryActionLoading: { type: String, default: "" },
  tuningHistoryLoading: { type: Boolean, default: false },
  toMoney: { type: Function, required: true },
  toPercent: { type: Function, required: true },
});

defineEmits([
  "openForwardValidationBatchModal",
  "closeForwardValidationBatch",
  "applyRecommendedStrategyProfile",
  "applyValidationAutoTune",
  "rollbackAutotradeTune",
  "toggleAutoTuneAutoApply",
  "adjustAutoTuneCooldown",
]);

const activeBatch = computed(() => props.forwardValidation?.active_batch || null);
const recentBatches = computed(() =>
  Array.isArray(props.forwardValidation?.recent_batches)
    ? props.forwardValidation.recent_batches
    : [],
);

const formatDays = (value) => `${Number(value || 0).toFixed(1)}d`;
const formatScore = (value) => Number(value || 0).toFixed(0);
const formatSignedScore = (value) => `${Number(value || 0) > 0 ? "+" : ""}${Number(value || 0).toFixed(0)}`;
const formatSignedPercent = (value) =>
  `${Number(value || 0) > 0 ? "+" : ""}${(Number(value || 0) * 100).toFixed(2)}%`;

const formatBatchProgress = (batch) => {
  const enrolled = Number(batch?.enrolled_count || 0);
  const target = Number(batch?.target_sample_size || 0);
  return target > 0 ? `${enrolled}/${target}` : `${enrolled}`;
};

const latestClosedBatch = computed(() =>
  recentBatches.value.find((batch) => batch?.status === "closed") || null,
);

const topBlockedReasons = computed(() =>
  Array.isArray(props.autotradeTuningDailyReport?.top_blocked_reasons)
    ? props.autotradeTuningDailyReport.top_blocked_reasons
    : [],
);

const latestActivitySummary = computed(() => {
  const latest = props.autotradeTuningDailyReport?.latest_activity;
  if (!latest)
    return "No recent tuning activity";
  return `${latest.decision_type || "unknown"} / ${latest.summary || "-"}`;
});

const tuningCount = (key) =>
  Number(props.autotradeTuningDailyReport?.counts_by_type?.[key] || 0);

const decisionTagType = (decisionType) =>
  ({
    auto_tune_applied: "success",
    auto_tune_blocked: "warning",
    auto_tune_disabled: "default",
    tuning_applied: "info",
    tuning_rollback: "warning",
  })[decisionType] || "default";

const recommendation = computed(() => {
  const source = latestClosedBatch.value || activeBatch.value;
  if (!source)
    return null;

  const soldCount = Number(source.sold_count || 0);
  const hitRate = Number(source.profit_hit_rate || 0);
  const avgRoi = Number(source.avg_realized_roi || 0);
  const holdingDays = Number(source.avg_holding_days || 0);
  const recentNetProfit = Number(source.realized_net_profit || 0);

  const confidenceLabel = soldCount >= 10
    ? "High signal"
    : soldCount >= 5
      ? "Medium signal"
      : "Low signal";

  if (soldCount < 3) {
    return {
      title: "Need more sold samples",
      summary: "Keep the current preset until this batch has at least 3 sold trades.",
      reasons: [
        `Sold trades ${soldCount}`,
        `Current preset ${props.strategyProfile}`,
      ],
      tagType: "info",
      confidenceLabel,
      recommendedProfile: "",
      recommendedLabel: "",
    };
  }

  let recommendedProfile = "balanced";
  let title = "Stay Balanced";
  let summary = "Current validation looks healthy enough for the balanced preset.";
  let tagType = "success";

  if (avgRoi < 0 || hitRate < 0.4 || recentNetProfit < 0) {
    recommendedProfile = "conservative";
    title = "Tighten entry filters";
    summary = "Validation shows weak realized ROI or a low hit rate. Reduce risk before scaling.";
    tagType = "warning";
  } else if (hitRate >= 0.65 && avgRoi >= 0.12 && holdingDays > 0 && holdingDays <= 5) {
    recommendedProfile = "aggressive";
    title = "Lean more aggressive";
    summary = "This batch is clearing quickly with strong ROI, so you can widen the funnel.";
    tagType = "success";
  } else if (holdingDays >= 10 && avgRoi < 0.08) {
    recommendedProfile = "conservative";
    title = "Capital is turning too slowly";
    summary = "Holding time is long relative to realized ROI. Tighten the preset to improve turnover quality.";
    tagType = "warning";
  }

  return {
    title,
    summary,
    reasons: [
      `Source ${source.name || `batch #${source.id}`}`,
      `Hit rate ${props.toPercent(hitRate)}`,
      `Avg ROI ${props.toPercent(avgRoi)}`,
      `Avg holding ${formatDays(holdingDays)}`,
    ],
    tagType,
    confidenceLabel,
    recommendedProfile,
    recommendedLabel: ({
      aggressive: "Aggressive",
      balanced: "Balanced",
      conservative: "Conservative",
    })[recommendedProfile],
  };
});

const getTradeStatusText = (status) =>
  ({
    approved_for_buy: "Approved",
    listed_for_sale: "Listed",
    sold: "Sold",
  })[status] || status || "-";

const getValidationStatusText = (status) =>
  ({
    open: "Open",
    closed: "Closed",
  })[status] || status || "-";
</script>
