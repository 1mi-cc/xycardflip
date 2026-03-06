<template>
  <div>
    <section class="hero ops-hero">
      <div class="hero-main">
        <div class="hero-eyebrow">Card Flip Operations</div>
        <h1>卡片倒卖操作台</h1>
        <p>
          把总览、人工审批、自动执行和风控处置收在一个工作台里。高频动作前置，低频调参收折叠。
        </p>
        <div class="role-hint">
          <n-tag size="small" :type="roleTagType">
            {{ roleTagText }}
          </n-tag>
          <span v-if="isViewer">
            当前为只读角色，写入类动作会自动禁用。
          </span>
        </div>
      </div>

      <div class="hero-actions hero-actions-panel">
        <div class="hero-actions-label">主操作</div>
        <n-space class="hero-actions-row" wrap>
          <n-input-number
            :value="scanLimit"
            :min="1"
            :max="500"
            style="width: 140px"
            @update:value="value => $emit('update:scanLimit', value)"
          />

          <n-button
            type="primary"
            :loading="scanLoading"
            :disabled="!canOperate"
            @click="$emit('runScan')"
          >
            扫描机会
          </n-button>

          <n-button
            secondary
            type="info"
            :loading="simulationTrainingLoading"
            :disabled="!canOperate"
            @click="$emit('runSimulationTraining')"
          >
            模拟训练
          </n-button>

          <n-button
            v-if="canMaintain"
            :loading="cookieRefreshLoading"
            @click="$emit('refreshCookie')"
          >
            刷新 Cookie
          </n-button>

          <n-select
            :value="pricingMode"
            :options="pricingModeOptions"
            style="width: 160px"
            @update:value="value => $emit('update:pricingMode', value)"
          />

          <n-button
            :loading="batchPricingLoading"
            @click="$emit('previewBatchReprice')"
          >
            预览批量定价
          </n-button>

          <n-button
            v-if="canBatchApplyPricing"
            type="warning"
            :loading="batchPricingLoading"
            :disabled="!canOperate"
            @click="$emit('applyBatchReprice')"
          >
            应用批量定价
          </n-button>

          <n-button :loading="loading" @click="$emit('refresh')">
            刷新总览
          </n-button>
        </n-space>
        <div class="hero-actions-hint">
          扫描上限即时生效，批量定价遵循当前模式。
        </div>
      </div>
    </section>

    <section v-if="dataIntegrityAlert || guardAlert" class="health-strip">
      <n-alert
        v-if="dataIntegrityAlert"
        type="warning"
        show-icon
        :bordered="false"
      >
        {{ dataIntegrityAlert }}
      </n-alert>
      <n-alert v-if="guardAlert" type="info" show-icon :bordered="false">
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
        <div class="value">￥{{ toMoney(metrics.gross_profit) }}</div>
      </div>
    </section>
  </div>
</template>

<script setup>
defineProps({
  roleTagText: { type: String, required: true },
  roleTagType: { type: String, required: true },
  isViewer: { type: Boolean, default: false },
  canOperate: { type: Boolean, default: false },
  canMaintain: { type: Boolean, default: false },
  canBatchApplyPricing: { type: Boolean, default: false },
  scanLimit: { type: Number, default: 100 },
  pricingMode: { type: String, default: "balanced" },
  pricingModeOptions: { type: Array, default: () => [] },
  scanLoading: { type: Boolean, default: false },
  simulationTrainingLoading: { type: Boolean, default: false },
  cookieRefreshLoading: { type: Boolean, default: false },
  batchPricingLoading: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  dataIntegrityAlert: { type: String, default: "" },
  guardAlert: { type: String, default: "" },
  metrics: { type: Object, default: () => ({}) },
  blockedCount: { type: Number, default: 0 },
  toMoney: { type: Function, required: true },
});

defineEmits([
  "update:scanLimit",
  "update:pricingMode",
  "runScan",
  "runSimulationTraining",
  "refreshCookie",
  "previewBatchReprice",
  "applyBatchReprice",
  "refresh",
]);
</script>
