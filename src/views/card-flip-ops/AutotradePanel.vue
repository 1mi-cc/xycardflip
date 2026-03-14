<template>
  <section class="service-panel autotrade-panel">
    <div class="service-head">
      <div class="service-copy">
        <div class="service-kicker">AutoTrade</div>
        <h3>审批引擎</h3>
        <p>负责自动审批、自动买入、自动上架，是操作台里最常用的执行面板。</p>
        <div class="service-tags">
          <n-tag size="small" :type="autotradeStatus.running ? 'success' : 'default'">
            {{ autotradeStatus.running ? "运行中" : "已停止" }}
          </n-tag>
          <n-tag size="small" :type="autotradeStatus.enabled ? 'info' : 'warning'">
            {{ autotradeStatus.enabled ? "已启用" : "未启用" }}
          </n-tag>
          <n-tag size="small" :type="executionStatus.live_enabled ? 'error' : 'warning'">
            {{ executionStatus.live_enabled ? "实盘链路" : "模拟链路" }}
          </n-tag>
        </div>
      </div>

      <n-space>
        <n-button
          size="small"
          type="primary"
          :disabled="!canOperate"
          :loading="autotradeActionLoading === 'start'"
          @click="$emit('startAutotrade')"
        >
          启动
        </n-button>
        <n-button
          size="small"
          :disabled="!canOperate"
          :loading="autotradeActionLoading === 'stop'"
          @click="$emit('stopAutotrade')"
        >
          停止
        </n-button>
        <n-button
          tertiary
          size="small"
          :loading="autotradeStatusLoading"
          @click="$emit('loadAutotradeStatus')"
        >
          刷新状态
        </n-button>
      </n-space>
    </div>

    <div class="service-summary-grid">
      <div class="summary-chip">
        <span class="summary-label">执行通道</span>
        <strong class="summary-value">{{ executionStatus.provider || "-" }}</strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">循环间隔</span>
        <strong class="summary-value">{{ autotradeStatus.interval_sec ?? "-" }}s</strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">批量上限</span>
        <strong class="summary-value">{{ autotradeStatus.batch_size ?? "-" }}</strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">最小评分</span>
        <strong class="summary-value">{{ autotradeStatus.min_score ?? "-" }}</strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">最小 ROI</span>
        <strong class="summary-value">{{ toPercent(autotradeStatus.min_roi || 0) }}</strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">风险阈值</span>
        <strong class="summary-value">{{ autotradeStatus.max_risk_score ?? "-" }}</strong>
      </div>
      <div class="summary-chip summary-chip-wide">
        <span class="summary-label">自动动作</span>
        <strong class="summary-value">
          买入={{ autotradeStatus.auto_execute_buy_on_approve ? "开" : "关" }}
          · 买入模式={{ autotradeStatus.auto_execute_buy_dry_run ? "dry-run" : "live" }}
          · 上架={{ autotradeStatus.auto_execute_list_on_buy_success ? "开" : "关" }}
          · 上架模式={{ autotradeStatus.auto_execute_list_dry_run ? "dry-run" : "live" }}
        </strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">最近运行</span>
        <strong class="summary-value">{{ autotradeStatus.last_run_at || "-" }}</strong>
      </div>
    </div>

    <div class="service-section">
      <div class="section-title">单次执行</div>
      <div class="section-subtitle">高频手动操作保留在主面板，参数调节放到折叠区。</div>
      <n-space wrap>
        <n-input
          placeholder="实盘确认口令"
          show-password-on="click"
          style="width: 220px"
          type="password"
          :disabled="!executionStatus.live_confirm_required"
          :value="executionLiveConfirmToken"
          @update:value="value => $emit('update:executionLiveConfirmToken', value)"
        ></n-input>
        <n-input-number
          placeholder="审批条数"
          style="width: 160px"
          :max="500"
          :min="0"
          :value="autotradeRunLimit"
          @update:value="value => $emit('update:autotradeRunLimit', value)"
        ></n-input-number>
        <n-switch
          :value="autotradeRunForce"
          @update:value="value => $emit('update:autotradeRunForce', value)"
        >
          <template #checked>强制执行</template>
          <template #unchecked>遵循开关</template>
        </n-switch>
        <n-button
          type="warning"
          :loading="autotradeActionLoading === 'run_once'"
          @click="$emit('runAutotradeOnce')"
        >
          运行一次
        </n-button>
      </n-space>
    </div>

    <div v-if="canOperate" class="service-section">
      <n-collapse>
        <n-collapse-item name="exec-live-settings" title="执行设置">
          <n-space wrap>
            <n-button-group size="small">
              <n-button
                :loading="executionConfigLoading"
                :type="executionStatus.provider === 'mock' ? 'primary' : 'default'"
                @click="$emit('setExecutionProvider', 'mock')"
              >
                mock
              </n-button>
              <n-button
                :loading="executionConfigLoading"
                :type="executionStatus.provider === 'webhook' ? 'primary' : 'default'"
                @click="$emit('setExecutionProvider', 'webhook')"
              >
                webhook
              </n-button>
              <n-button
                :loading="executionConfigLoading"
                :type="['disabled', 'none'].includes(executionStatus.provider) ? 'warning' : 'default'"
                @click="$emit('setExecutionProvider', 'disabled')"
              >
                disabled
              </n-button>
            </n-button-group>

            <n-button
              size="small"
              :loading="executionConfigLoading"
              :type="executionStatus.live_enabled ? 'success' : 'default'"
              @click="$emit('toggleExecutionFlag', 'live_enabled')"
            >
              {{ executionStatus.live_enabled ? "实盘执行：开" : "实盘执行：关" }}
            </n-button>

            <n-button
              size="small"
              :loading="executionConfigLoading"
              :type="executionStatus.live_confirm_required ? 'primary' : 'default'"
              @click="$emit('toggleExecutionFlag', 'live_confirm_required')"
            >
              {{ executionStatus.live_confirm_required ? "二次确认：开" : "二次确认：关" }}
            </n-button>

            <n-button-group size="small">
              <n-button
                :disabled="executionConfigLoading"
                @click="$emit('adjustExecutionNumber', 'live_max_buy_price', -5, 0, 1000000)"
              >
                -5 上限
              </n-button>
              <n-button quaternary>
                {{
                  executionStatus.live_max_buy_price > 0
                    ? `买入上限 ￥${toMoney(executionStatus.live_max_buy_price)}`
                    : "买入上限 不限"
                }}
              </n-button>
              <n-button
                :disabled="executionConfigLoading"
                @click="$emit('adjustExecutionNumber', 'live_max_buy_price', 5, 0, 1000000)"
              >
                +5 上限
              </n-button>
            </n-button-group>

            <n-button-group size="small">
              <n-button
                :disabled="executionConfigLoading"
                @click="$emit('adjustExecutionNumber', 'live_min_list_profit_ratio', -0.01, 0, 3)"
              >
                -1% 上架利润率
              </n-button>
              <n-button quaternary>
                上架利润率 {{ toPercent(executionStatus.live_min_list_profit_ratio || 0) }}
              </n-button>
              <n-button
                :disabled="executionConfigLoading"
                @click="$emit('adjustExecutionNumber', 'live_min_list_profit_ratio', 0.01, 0, 3)"
              >
                +1% 上架利润率
              </n-button>
            </n-button-group>

            <n-button-group size="small">
              <n-button
                :disabled="executionConfigLoading"
                @click="$emit('adjustExecutionNumber', 'live_min_sell_profit_ratio', -0.01, 0, 3)"
              >
                -1% 卖出利润率
              </n-button>
              <n-button quaternary>
                卖出利润率 {{ toPercent(executionStatus.live_min_sell_profit_ratio || 0) }}
              </n-button>
              <n-button
                :disabled="executionConfigLoading"
                @click="$emit('adjustExecutionNumber', 'live_min_sell_profit_ratio', 0.01, 0, 3)"
              >
                +1% 卖出利润率
              </n-button>
            </n-button-group>
          </n-space>
        </n-collapse-item>

        <n-collapse-item name="autotrade-quick-tune" title="快速调参">
          <n-space wrap>
            <n-button-group size="small">
              <n-button
                :disabled="autotradeConfigLoading"
                @click="$emit('adjustAutotradeNumber', 'interval_sec', -5, 5, 3600)"
              >
                -5s
              </n-button>
              <n-button quaternary>{{ autotradeStatus.interval_sec ?? "-" }}s</n-button>
              <n-button
                :disabled="autotradeConfigLoading"
                @click="$emit('adjustAutotradeNumber', 'interval_sec', 5, 5, 3600)"
              >
                +5s
              </n-button>
            </n-button-group>

            <n-button-group size="small">
              <n-button
                :disabled="autotradeConfigLoading"
                @click="$emit('adjustAutotradeNumber', 'batch_size', -1, 1, 500)"
              >
                -1 批量
              </n-button>
              <n-button quaternary>批量 {{ autotradeStatus.batch_size ?? "-" }}</n-button>
              <n-button
                :disabled="autotradeConfigLoading"
                @click="$emit('adjustAutotradeNumber', 'batch_size', 1, 1, 500)"
              >
                +1 批量
              </n-button>
            </n-button-group>

            <n-button-group size="small">
              <n-button
                :disabled="autotradeConfigLoading"
                @click="$emit('adjustAutotradeNumber', 'min_score', -1, 0, 100)"
              >
                -1 评分
              </n-button>
              <n-button quaternary>评分 {{ autotradeStatus.min_score ?? "-" }}</n-button>
              <n-button
                :disabled="autotradeConfigLoading"
                @click="$emit('adjustAutotradeNumber', 'min_score', 1, 0, 100)"
              >
                +1 评分
              </n-button>
            </n-button-group>

            <n-button-group size="small">
              <n-button :disabled="autotradeConfigLoading" @click="$emit('adjustAutotradeRoi', -0.01)">
                -1% ROI
              </n-button>
              <n-button quaternary>ROI {{ toPercent(autotradeStatus.min_roi || 0) }}</n-button>
              <n-button :disabled="autotradeConfigLoading" @click="$emit('adjustAutotradeRoi', 0.01)">
                +1% ROI
              </n-button>
            </n-button-group>

            <n-button-group size="small">
              <n-button
                :disabled="autotradeConfigLoading"
                @click="$emit('adjustAutotradeNumber', 'max_risk_score', -1, 0, 100)"
              >
                -1 风险
              </n-button>
              <n-button quaternary>风险 {{ autotradeStatus.max_risk_score ?? "-" }}</n-button>
              <n-button
                :disabled="autotradeConfigLoading"
                @click="$emit('adjustAutotradeNumber', 'max_risk_score', 1, 0, 100)"
              >
                +1 风险
              </n-button>
            </n-button-group>

            <n-button
              size="small"
              :loading="autotradeConfigLoading"
              :type="autotradeStatus.require_risk_score ? 'primary' : 'default'"
              @click="$emit('toggleAutotradeFlag', 'require_risk_score')"
            >
              {{ autotradeStatus.require_risk_score ? "要求风险分：开" : "要求风险分：关" }}
            </n-button>

            <n-button
              size="small"
              :loading="autotradeConfigLoading"
              :type="autotradeStatus.auto_execute_buy_on_approve ? 'success' : 'default'"
              @click="$emit('toggleAutotradeFlag', 'auto_execute_buy_on_approve')"
            >
              {{ autotradeStatus.auto_execute_buy_on_approve ? "自动买入：开" : "自动买入：关" }}
            </n-button>

            <n-button
              size="small"
              :loading="autotradeConfigLoading"
              :type="autotradeStatus.auto_execute_buy_dry_run ? 'warning' : 'error'"
              @click="$emit('toggleAutotradeFlag', 'auto_execute_buy_dry_run')"
            >
              买入模式：{{ autotradeStatus.auto_execute_buy_dry_run ? "dry-run" : "live" }}
            </n-button>

            <n-button
              size="small"
              :loading="autotradeConfigLoading"
              :type="autotradeStatus.auto_execute_list_on_buy_success ? 'success' : 'default'"
              @click="$emit('toggleAutotradeFlag', 'auto_execute_list_on_buy_success')"
            >
              {{ autotradeStatus.auto_execute_list_on_buy_success ? "自动上架：开" : "自动上架：关" }}
            </n-button>

            <n-button
              size="small"
              :loading="autotradeConfigLoading"
              :type="autotradeStatus.auto_execute_list_dry_run ? 'warning' : 'error'"
              @click="$emit('toggleAutotradeFlag', 'auto_execute_list_dry_run')"
            >
              上架模式：{{ autotradeStatus.auto_execute_list_dry_run ? "dry-run" : "live" }}
            </n-button>
          </n-space>
        </n-collapse-item>
      </n-collapse>
    </div>
  </section>
</template>

<script setup>
defineProps({
  autotradeStatus: { type: Object, default: () => ({}) },
  executionStatus: { type: Object, default: () => ({}) },
  autotradeStatusLoading: { type: Boolean, default: false },
  autotradeActionLoading: { type: String, default: "" },
  autotradeConfigLoading: { type: Boolean, default: false },
  executionConfigLoading: { type: Boolean, default: false },
  canOperate: { type: Boolean, default: false },
  autotradeRunLimit: { type: Number, default: 0 },
  autotradeRunForce: { type: Boolean, default: false },
  executionLiveConfirmToken: { type: String, default: "" },
  toMoney: { type: Function, required: true },
  toPercent: { type: Function, required: true },
});

defineEmits([
  "loadAutotradeStatus",
  "startAutotrade",
  "stopAutotrade",
  "setExecutionProvider",
  "toggleExecutionFlag",
  "adjustExecutionNumber",
  "adjustAutotradeNumber",
  "adjustAutotradeRoi",
  "toggleAutotradeFlag",
  "update:executionLiveConfirmToken",
  "update:autotradeRunLimit",
  "update:autotradeRunForce",
  "runAutotradeOnce",
]);
</script>
