<template>
  <div>
    <section class="hero ops-hero">
      <div class="hero-main">
        <div class="hero-eyebrow">Card Flip Operations</div>
        <h1>卡牌倒卖操作台</h1>
        <p>
          把总览、人工审核、执行控制、前向验证和收益复盘放在同一个工作台里，方便你做日常盯盘和批量维护。
        </p>
        <div class="role-hint">
          <n-tag size="small" :type="roleTagType">
            {{ resolvedRoleTagText }}
          </n-tag>
          <span v-if="isViewer">
            当前是只读角色，写入类操作会自动禁用。
          </span>
        </div>
      </div>

      <div class="hero-actions hero-actions-panel">
        <div class="hero-actions-label">主操作</div>
        <n-space wrap class="hero-actions-row">
          <n-input-number
            style="width: 140px"
            :max="500"
            :min="1"
            :value="scanLimit"
            @update:value="value => emit('update:scanLimit', value)"
          ></n-input-number>

          <n-button
            type="primary"
            :disabled="!canOperate"
            :loading="scanLoading"
            @click="handleRunScan"
            @mousedown.left="handleRunScan"
          >
            扫描机会
          </n-button>

          <n-button
            secondary
            type="info"
            :disabled="!canOperate"
            :loading="simulationTrainingLoading"
            @click="handleRunSimulationTraining"
            @mousedown.left="handleRunSimulationTraining"
          >
            注入模拟样本
          </n-button>

          <n-button
            v-if="canMaintain"
            :loading="cookieRefreshLoading"
            @click="handleRefreshCookie"
            @mousedown.left="handleRefreshCookie"
          >
            刷新 Cookie
          </n-button>

          <n-select
            style="width: 160px"
            :options="pricingModeOptions"
            :value="pricingMode"
            @update:value="value => emit('update:pricingMode', value)"
          ></n-select>

          <n-button
            :loading="batchPricingLoading"
            @click="handlePreviewBatchReprice"
            @mousedown.left="handlePreviewBatchReprice"
          >
            预览批量定价
          </n-button>

          <n-button
            v-if="canBatchApplyPricing"
            type="warning"
            :disabled="!canOperate"
            :loading="batchPricingLoading"
            @click="handleApplyBatchReprice"
            @mousedown.left="handleApplyBatchReprice"
          >
            应用批量定价
          </n-button>

          <n-select
            style="width: 160px"
            :options="strategyProfileOptions"
            :value="strategyProfile"
            @update:value="value => emit('update:strategyProfile', value)"
          ></n-select>

          <n-button
            type="success"
            :disabled="!canOperate"
            :loading="strategyProfileLoading"
            @click="handleApplyStrategyProfile"
            @mousedown.left="handleApplyStrategyProfile"
          >
            Apply Preset
          </n-button>

          <n-button :loading="loading" @click="handleRefresh" @mousedown.left="handleRefresh">
            刷新总览
          </n-button>
        </n-space>
        <div class="hero-actions-hint">
          Preset {{ resolvedStrategyProfileLabel }}:
          ROI >= {{ formatPercent(strategyThresholds.min_roi) }},
          score >= {{ formatScore(strategyThresholds.min_score) }},
          risk &lt;= {{ formatScore(strategyThresholds.max_risk_score) }}
        </div>
        <div class="hero-actions-hint">
          扫描上限会立刻生效。批量定价会按当前模式生成建议，并在应用时刷新交易数据。
        </div>
      </div>
    </section>

    <section
      v-if="startupCheckAlert || geminiAlert || profitProtectionAlert || dataIntegrityAlert || guardAlert"
      class="health-strip"
    >
      <n-alert
        v-if="startupCheckAlert"
        show-icon
        :bordered="false"
        :type="startupCheckAlertType"
      >
        {{ startupCheckAlert }}
      </n-alert>
      <n-alert
        v-if="geminiAlert"
        show-icon
        :bordered="false"
        :type="geminiAlertType"
      >
        {{ geminiAlert }}
      </n-alert>
      <n-alert
        v-if="profitProtectionAlert"
        show-icon
        :bordered="false"
        :type="profitProtectionAlertType"
      >
        {{ profitProtectionAlert }}
      </n-alert>
      <n-alert
        v-if="dataIntegrityAlert"
        show-icon
        type="warning"
        :bordered="false"
      >
        {{ dataIntegrityAlert }}
      </n-alert>
      <n-alert v-if="guardAlert" show-icon type="info" :bordered="false">
        {{ guardAlert }}
      </n-alert>
    </section>

    <section class="stats stats-compact">
      <div class="stat-card">
        <div class="label">待审核机会</div>
        <div class="value">{{ metrics.pending_review_count || 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="label">进行中交易</div>
        <div class="value">{{ metrics.active_trades_count || 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="label">已卖出记录</div>
        <div class="value">{{ metrics.sold_count || 0 }}</div>
      </div>
      <div class="stat-card warning">
        <div class="label">风控拦截</div>
        <div class="value">{{ blockedCount }}</div>
      </div>
      <div class="stat-card profit">
        <div class="label">累计毛利</div>
        <div class="value">¥{{ toMoney(metrics.gross_profit) }}</div>
      </div>
      <div class="stat-card">
        <div class="label">盈利命中率</div>
        <div class="value">{{ formatPercent(metrics.profit_hit_rate) }}</div>
      </div>
      <div class="stat-card">
        <div class="label">平均周转</div>
        <div class="value">{{ formatDays(metrics.avg_holding_days) }}</div>
      </div>
      <div class="stat-card">
        <div class="label">前向验证</div>
        <div class="value">{{ validationProgress }}</div>
      </div>
      <div class="stat-card" :class="geminiStatusVariant">
        <div class="label">Gemini Pool</div>
        <div class="value">{{ geminiStatusText }}</div>
      </div>
      <div class="stat-card" :class="webhookReady ? 'profit' : 'warning'">
        <div class="label">Webhook 实盘</div>
        <div class="value">{{ webhookReady ? "已就绪" : "未就绪" }}</div>
      </div>
    </section>

    <section class="profit-cockpit">
      <div class="profit-cockpit-head">
        <div>
          <div class="hero-eyebrow">Profit Cockpit</div>
          <h3>收益驾驶舱</h3>
        </div>
        <n-tag size="small" :type="profitProtectionTagType">
          {{ profitProtectionStatusText }}
        </n-tag>
      </div>

      <div class="profit-cockpit-grid">
        <div class="cockpit-card" :class="todayNetProfit >= 0 ? 'profit' : 'warning'">
          <div class="label">今日净利润</div>
          <div class="value">¥{{ toMoney(todayNetProfit) }}</div>
          <div class="meta">
            sold {{ todaySoldCount }} | hit {{ formatPercent(todayHitRate) }}
          </div>
        </div>
        <div class="cockpit-card" :class="last7dNetProfit >= 0 ? 'profit' : 'warning'">
          <div class="label">近 7 天净利润</div>
          <div class="value">¥{{ toMoney(last7dNetProfit) }}</div>
          <div class="meta">
            sold {{ last7dSoldCount }} | hit {{ formatPercent(last7dHitRate) }}
          </div>
        </div>
        <div class="cockpit-card" :class="currentLossStreak > 0 ? 'warning' : 'profit'">
          <div class="label">连续亏损</div>
          <div class="value">{{ currentLossStreak }}</div>
          <div class="meta">loss total ¥{{ toMoney(currentLossTotal) }}</div>
        </div>
        <div class="cockpit-card">
          <div class="label">库存占用</div>
          <div class="value">¥{{ toMoney(inventoryCapital) }}</div>
          <div class="meta">
            {{ inventoryTradeCount }} active | exit ¥{{ toMoney(inventoryTargetValue) }}
          </div>
        </div>
      </div>

      <div class="profit-cockpit-notes">
        <span>Best 7d source: {{ bestSourceText }}</span>
        <span>Weakest 7d source: {{ weakestSourceText }}</span>
        <span>Best seller: {{ bestSellerText }}</span>
        <span>Weakest seller: {{ weakestSellerText }}</span>
        <span>Frozen sellers: {{ frozenSellerCount }}</span>
        <span>Observe sellers: {{ observeSellerCount }}</span>
      </div>
      <div v-if="sourceStrategyItems.length" class="source-strategy-row">
        <span
          v-for="item in sourceStrategyItems"
          :key="item.source"
          class="source-strategy-pill"
          :class="`is-${item.strategy_mode || 'hold'}`"
        >
          {{ item.source }} · {{ item.strategy_mode || "hold" }} · ¥{{ toMoney(item.realized_net_profit || 0) }}
        </span>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  roleTagText: { type: String, required: true },
  roleTagType: { type: String, required: true },
  isViewer: { type: Boolean, default: false },
  canOperate: { type: Boolean, default: false },
  canMaintain: { type: Boolean, default: false },
  canBatchApplyPricing: { type: Boolean, default: false },
  scanLimit: { type: Number, default: 100 },
  pricingMode: { type: String, default: "balanced" },
  pricingModeOptions: { type: Array, default: () => [] },
  strategyProfile: { type: String, default: "balanced" },
  strategyProfileLoading: { type: Boolean, default: false },
  strategyProfileOptions: { type: Array, default: () => [] },
  strategyThresholds: { type: Object, default: () => ({}) },
  scanLoading: { type: Boolean, default: false },
  simulationTrainingLoading: { type: Boolean, default: false },
  cookieRefreshLoading: { type: Boolean, default: false },
  batchPricingLoading: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  dataIntegrityAlert: { type: String, default: "" },
  guardAlert: { type: String, default: "" },
  startupCheckAlert: { type: String, default: "" },
  startupCheckAlertType: { type: String, default: "info" },
  geminiAlert: { type: String, default: "" },
  geminiAlertType: { type: String, default: "info" },
  geminiStatusText: { type: String, default: "Unavailable" },
  geminiStatusVariant: { type: String, default: "" },
  profitProtectionAlert: { type: String, default: "" },
  profitProtectionAlertType: { type: String, default: "warning" },
  profitProtectionStatusText: { type: String, default: "Armed" },
  metrics: { type: Object, default: () => ({}) },
  blockedCount: { type: Number, default: 0 },
  onApplyBatchReprice: { type: Function, default: null },
  onPreviewBatchReprice: { type: Function, default: null },
  onRefresh: { type: Function, default: null },
  onRefreshCookie: { type: Function, default: null },
  onRunScan: { type: Function, default: null },
  onRunSimulationTraining: { type: Function, default: null },
  onApplyStrategyProfile: { type: Function, default: null },
  toMoney: { type: Function, required: true },
});

const emit = defineEmits([
  "update:scanLimit",
  "update:pricingMode",
  "update:strategyProfile",
  "runScan",
  "runSimulationTraining",
  "refreshCookie",
  "previewBatchReprice",
  "applyBatchReprice",
  "applyStrategyProfile",
  "refresh",
]);

const resolvedRoleTagText = computed(() => {
  if (props.isViewer)
    return "viewer 只读模式";
  if (props.roleTagType === "info")
    return "ops 运营模式";
  return "admin 管理模式";
});

const validationProgress = computed(() => {
  const batch = props.metrics?.forward_validation?.active_batch;
  if (!batch)
    return "未启动";
  const enrolled = Number(batch.enrolled_count || 0);
  const target = Number(batch.target_sample_size || 0);
  return target > 0 ? `${enrolled}/${target}` : `${enrolled}`;
});

const webhookReady = computed(() =>
  Boolean(props.metrics?.execution_readiness?.live_ready),
);

const profitCockpit = computed(() => props.metrics?.profit_cockpit || {});
const todayProfit = computed(() => profitCockpit.value?.today || {});
const last7dProfit = computed(() => profitCockpit.value?.last_7d || {});
const inventoryExposure = computed(() => profitCockpit.value?.inventory || {});
const lossStreak = computed(() => profitCockpit.value?.loss_streak || {});
const todayNetProfit = computed(() => Number(todayProfit.value?.realized_net_profit || 0));
const todaySoldCount = computed(() => Number(todayProfit.value?.sold_count || 0));
const todayHitRate = computed(() => Number(todayProfit.value?.profit_hit_rate || 0));
const last7dNetProfit = computed(() => Number(last7dProfit.value?.realized_net_profit || 0));
const last7dSoldCount = computed(() => Number(last7dProfit.value?.sold_count || 0));
const last7dHitRate = computed(() => Number(last7dProfit.value?.profit_hit_rate || 0));
const currentLossStreak = computed(() => Number(lossStreak.value?.current_consecutive_losses || 0));
const currentLossTotal = computed(() => Number(lossStreak.value?.current_loss_total || 0));
const inventoryCapital = computed(() => Number(inventoryExposure.value?.deployed_capital || 0));
const inventoryTradeCount = computed(() => Number(inventoryExposure.value?.active_trade_count || 0));
const inventoryTargetValue = computed(() => Number(inventoryExposure.value?.target_exit_value || 0));
const bestSourceText = computed(() => {
  const source = profitCockpit.value?.best_source_7d;
  if (!source)
    return "n/a";
  return `${source.source} | ¥${props.toMoney(source.realized_net_profit || 0)} | ${source.sold_count || 0} sold`;
});
const weakestSourceText = computed(() => {
  const source = profitCockpit.value?.weakest_source_7d;
  if (!source)
    return "n/a";
  return `${source.source} | ¥${props.toMoney(source.realized_net_profit || 0)} | ${source.sold_count || 0} sold`;
});
const bestSellerText = computed(() => {
  const seller = profitCockpit.value?.best_seller_7d;
  if (!seller)
    return "n/a";
  return `${seller.source}/${seller.seller_id} | ¥${props.toMoney(seller.realized_net_profit || 0)} | ${seller.sold_count || 0} sold`;
});
const weakestSellerText = computed(() => {
  const seller = profitCockpit.value?.weakest_seller_7d;
  if (!seller)
    return "n/a";
  return `${seller.source}/${seller.seller_id} | ¥${props.toMoney(seller.realized_net_profit || 0)} | ${seller.sold_count || 0} sold`;
});
const frozenSellerCount = computed(() => Number(profitCockpit.value?.seller_controls?.active_freeze_count || 0));
const observeSellerCount = computed(() => Number(profitCockpit.value?.seller_controls?.active_observe_count || 0));
const sourceStrategyItems = computed(() =>
  (profitCockpit.value?.source_leaderboard_7d || []).slice(0, 3),
);
const profitProtectionTagType = computed(() => {
  if (props.profitProtectionStatusText === "Blocked")
    return "error";
  if (props.profitProtectionStatusText === "Disabled")
    return "default";
  return "success";
});

const resolvedStrategyProfileLabel = computed(() =>
  ({
    aggressive: "Aggressive",
    balanced: "Balanced",
    conservative: "Conservative",
  })[props.strategyProfile] || props.strategyProfile || "Balanced",
);

const formatPercent = (value) => `${(Number(value || 0) * 100).toFixed(1)}%`;
const formatDays = (value) => `${Number(value || 0).toFixed(1)}d`;
const formatScore = (value) => Number(value || 0).toFixed(0);

const lastTriggerAt = new Map();

const invoke = (key, propHandler, eventName) => {
  const now = Date.now();
  const last = lastTriggerAt.get(key) || 0;
  if (now - last < 350)
    return undefined;
  lastTriggerAt.set(key, now);
  if (typeof propHandler === "function")
    return propHandler();
  return emit(eventName);
};

const handleRunScan = () => invoke("runScan", props.onRunScan, "runScan");
const handleRunSimulationTraining = () =>
  invoke("runSimulationTraining", props.onRunSimulationTraining, "runSimulationTraining");
const handleRefreshCookie = () => invoke("refreshCookie", props.onRefreshCookie, "refreshCookie");
const handlePreviewBatchReprice = () =>
  invoke("previewBatchReprice", props.onPreviewBatchReprice, "previewBatchReprice");
const handleApplyBatchReprice = () =>
  invoke("applyBatchReprice", props.onApplyBatchReprice, "applyBatchReprice");
const handleApplyStrategyProfile = () =>
  invoke("applyStrategyProfile", () => props.onApplyStrategyProfile?.(props.strategyProfile), "applyStrategyProfile");
const handleRefresh = () => invoke("refresh", props.onRefresh, "refresh");
</script>
