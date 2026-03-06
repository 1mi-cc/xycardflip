<template>
  <div>
    <section class="hero">
      <div class="hero-main">
        <h1>卡片倒卖助手</h1>
        <p>机会扫描、人工审核、交易流转全流程</p>
        <div class="role-hint">
          <n-tag size="small" :type="roleTagType">
            {{ roleTagText }}
          </n-tag>
          <span v-if="isViewer">当前角色为只读，写入操作已自动禁用或折叠。</span>
        </div>
      </div>
      <div class="hero-actions">
        <n-collapse :default-expanded-names="['quick-actions']">
          <n-collapse-item title="快捷操作" name="quick-actions">
            <n-space>
              <n-input-number
                :value="scanLimit"
                :min="1"
                :max="500"
                @update:value="value => $emit('update:scanLimit', value)"
              />
              <div class="action-with-help">
                <n-button type="primary" :loading="scanLoading" :disabled="!canOperate" @click="$emit('runScan')">
                  扫描机会
                </n-button>
                <n-tooltip trigger="hover">
                  <template #trigger>
                    <span class="help-badge">!</span>
                  </template>
                  仅扫描当前数据库中的 open 商品并重新估价，不会主动去闲鱼抓新数据。
                </n-tooltip>
              </div>
              <div class="action-with-help">
                <n-button
                  type="info"
                  :loading="simulationTrainingLoading"
                  :disabled="!canOperate"
                  @click="$emit('runSimulationTraining')"
                >
                  模拟训练
                </n-button>
                <n-tooltip trigger="hover">
                  <template #trigger>
                    <span class="help-badge">!</span>
                  </template>
                  一键切换为 mock + dry-run，并跳过 Monitor 和扫描，只跑审批训练链路。
                </n-tooltip>
              </div>
              <div v-if="canMaintain" class="action-with-help">
                <n-button :loading="cookieRefreshLoading" @click="$emit('refreshCookie')">
                  刷新 Cookie
                </n-button>
                <n-tooltip trigger="hover">
                  <template #trigger>
                    <span class="help-badge">!</span>
                  </template>
                  从本机浏览器重新提取闲鱼 Cookie，用于修复 401 或令牌过期。
                </n-tooltip>
              </div>
              <n-select
                :value="pricingMode"
                :options="pricingModeOptions"
                style="width: 160px"
                @update:value="value => $emit('update:pricingMode', value)"
              />
              <div class="action-with-help">
                <n-button :loading="batchPricingLoading" @click="$emit('previewBatchReprice')">
                  批量预览定价
                </n-button>
                <n-tooltip trigger="hover">
                  <template #trigger>
                    <span class="help-badge">!</span>
                  </template>
                  按当前模式生成建议价，不写入数据库。
                </n-tooltip>
              </div>
              <div v-if="canBatchApplyPricing" class="action-with-help">
                <n-button
                  type="warning"
                  :loading="batchPricingLoading"
                  :disabled="!canOperate"
                  @click="$emit('applyBatchReprice')"
                >
                  批量应用定价
                </n-button>
                <n-tooltip trigger="hover">
                  <template #trigger>
                    <span class="help-badge">!</span>
                  </template>
                  将建议价写回进行中交易的目标卖价。
                </n-tooltip>
              </div>
              <div class="action-with-help">
                <n-button :loading="loading" @click="$emit('refresh')">
                  刷新
                </n-button>
                <n-tooltip trigger="hover">
                  <template #trigger>
                    <span class="help-badge">!</span>
                  </template>
                  刷新页面数据与各服务状态，不触发交易动作。
                </n-tooltip>
              </div>
            </n-space>
          </n-collapse-item>
        </n-collapse>
      </div>
    </section>

    <section v-if="dataIntegrityAlert || guardAlert" class="health-strip">
      <n-alert v-if="dataIntegrityAlert" type="warning" show-icon :bordered="false">
        {{ dataIntegrityAlert }}
      </n-alert>
      <n-alert v-if="guardAlert" type="info" show-icon :bordered="false">
        {{ guardAlert }}
      </n-alert>
    </section>

    <section class="stats">
      <div class="stat-card">
        <div class="label">待审核</div>
        <div class="value">{{ metrics.pending_review_count }}</div>
      </div>
      <div class="stat-card">
        <div class="label">进行中交易</div>
        <div class="value">{{ metrics.active_trades_count }}</div>
      </div>
      <div class="stat-card">
        <div class="label">已卖出</div>
        <div class="value">{{ metrics.sold_count }}</div>
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
