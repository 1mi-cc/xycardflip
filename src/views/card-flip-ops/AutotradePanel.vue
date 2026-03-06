<template>
  <section class="autotrade-panel">
    <div class="autotrade-head">
      <div class="autotrade-title-wrap">
        <h3>AutoTrade 审批引擎</h3>
        <div class="autotrade-tags">
          <n-tag :type="autotradeStatus.running ? 'success' : 'default'" size="small">
            {{ autotradeStatus.running ? "运行中" : "已停止" }}
          </n-tag>
          <n-tag :type="autotradeStatus.enabled ? 'info' : 'warning'" size="small">
            {{ autotradeStatus.enabled ? "已启用" : "环境未启用" }}
          </n-tag>
        </div>
      </div>
      <n-space>
        <div class="action-with-help">
          <n-button
            size="small"
            type="primary"
            :loading="autotradeActionLoading === 'start'"
            :disabled="!canOperate"
            @click="$emit('startAutotrade')"
          >
            启动
          </n-button>
          <n-tooltip trigger="hover">
            <template #trigger>
              <span class="help-badge">!</span>
            </template>
            启动后台审批循环服务，按配置周期自动审批候选机会。
          </n-tooltip>
        </div>
        <div class="action-with-help">
          <n-button
            size="small"
            :loading="autotradeActionLoading === 'stop'"
            :disabled="!canOperate"
            @click="$emit('stopAutotrade')"
          >
            停止
          </n-button>
          <n-tooltip trigger="hover">
            <template #trigger>
              <span class="help-badge">!</span>
            </template>
            仅停止自动审批循环，不会改动现有交易状态。
          </n-tooltip>
        </div>
        <div class="action-with-help">
          <n-button size="small" tertiary :loading="autotradeStatusLoading" @click="$emit('loadAutotradeStatus')">
            刷新状态
          </n-button>
          <n-tooltip trigger="hover">
            <template #trigger>
              <span class="help-badge">!</span>
            </template>
            从后端重新拉取审批引擎状态与统计信息。
          </n-tooltip>
        </div>
      </n-space>
    </div>

    <div class="autotrade-metrics">
      <span>执行通道: {{ executionStatus.provider || "-" }}</span>
      <span>实盘开关 {{ executionStatus.live_enabled ? "开启" : "关闭" }}</span>
      <span>实盘二次确认: {{ executionStatus.live_confirm_required ? "已启用" : "未启用" }}</span>
      <span>实盘价格上限: {{ executionStatus.live_max_buy_price > 0 ? `CNY ${toMoney(executionStatus.live_max_buy_price)}` : "不限" }}</span>
      <span>实盘上架最小利润率: {{ toPercent(executionStatus.live_min_list_profit_ratio || 0) }}</span>
      <span>实盘卖出最小利润率: {{ toPercent(executionStatus.live_min_sell_profit_ratio || 0) }}</span>
      <span>循环间隔: {{ autotradeStatus.interval_sec ?? "-" }}s</span>
      <span>批量上限: {{ autotradeStatus.batch_size ?? "-" }}</span>
      <span>最小评分 {{ autotradeStatus.min_score ?? "-" }}</span>
      <span>最小 ROI: {{ toPercent(autotradeStatus.min_roi || 0) }}</span>
      <span>最大风险分: {{ autotradeStatus.max_risk_score ?? "-" }}</span>
    </div>
    <div class="autotrade-metrics">
      <span>累计执行: {{ autotradeStatus.total_runs ?? 0 }}</span>
      <span>累计审批: {{ autotradeStatus.total_approved ?? 0 }}</span>
      <span>审批后自动买入 {{ autotradeStatus.auto_execute_buy_on_approve ? "开启" : "关闭" }}</span>
      <span>自动买入模式: {{ autotradeStatus.auto_execute_buy_dry_run ? "dry-run" : "live" }}</span>
      <span>买入后自动上架 {{ autotradeStatus.auto_execute_list_on_buy_success ? "开启" : "关闭" }}</span>
      <span>自动上架模式: {{ autotradeStatus.auto_execute_list_dry_run ? "dry-run" : "live" }}</span>
      <span>最近运行 {{ autotradeStatus.last_run_at || "-" }}</span>
    </div>

    <div v-if="canOperate" class="quick-adjust-card">
      <n-collapse :default-expanded-names="['exec-live-settings']">
        <n-collapse-item title="执行小设置（即时生效）" name="exec-live-settings">
          <n-space wrap>
            <n-button-group size="small">
              <n-button
                :type="executionStatus.provider === 'mock' ? 'primary' : 'default'"
                :loading="executionConfigLoading"
                @click="$emit('setExecutionProvider', 'mock')"
              >
                mock
              </n-button>
              <n-button
                :type="executionStatus.provider === 'webhook' ? 'primary' : 'default'"
                :loading="executionConfigLoading"
                @click="$emit('setExecutionProvider', 'webhook')"
              >
                webhook
              </n-button>
              <n-button
                :type="['disabled', 'none'].includes(executionStatus.provider) ? 'warning' : 'default'"
                :loading="executionConfigLoading"
                @click="$emit('setExecutionProvider', 'disabled')"
              >
                disabled
              </n-button>
            </n-button-group>
            <n-button
              size="small"
              :type="executionStatus.live_enabled ? 'success' : 'default'"
              :loading="executionConfigLoading"
              @click="$emit('toggleExecutionFlag', 'live_enabled')"
            >
              {{ executionStatus.live_enabled ? "实盘开关: 开" : "实盘开关: 关" }}
            </n-button>
            <n-button
              size="small"
              :type="executionStatus.live_confirm_required ? 'primary' : 'default'"
              :loading="executionConfigLoading"
              @click="$emit('toggleExecutionFlag', 'live_confirm_required')"
            >
              {{ executionStatus.live_confirm_required ? "二次确认: 开" : "二次确认: 关" }}
            </n-button>
            <n-button-group size="small">
              <n-button :disabled="executionConfigLoading" @click="$emit('adjustExecutionNumber', 'live_max_buy_price', -5, 0, 1000000)">-5 上限</n-button>
              <n-button quaternary>
                {{ executionStatus.live_max_buy_price > 0 ? `买入上限 ￥${toMoney(executionStatus.live_max_buy_price)}` : "买入上限 不限" }}
              </n-button>
              <n-button :disabled="executionConfigLoading" @click="$emit('adjustExecutionNumber', 'live_max_buy_price', 5, 0, 1000000)">+5 上限</n-button>
            </n-button-group>
            <n-button-group size="small">
              <n-button :disabled="executionConfigLoading" @click="$emit('adjustExecutionNumber', 'live_min_list_profit_ratio', -0.01, 0, 3)">-1% 上架利率</n-button>
              <n-button quaternary>上架利率 {{ toPercent(executionStatus.live_min_list_profit_ratio || 0) }}</n-button>
              <n-button :disabled="executionConfigLoading" @click="$emit('adjustExecutionNumber', 'live_min_list_profit_ratio', 0.01, 0, 3)">+1% 上架利率</n-button>
            </n-button-group>
            <n-button-group size="small">
              <n-button :disabled="executionConfigLoading" @click="$emit('adjustExecutionNumber', 'live_min_sell_profit_ratio', -0.01, 0, 3)">-1% 卖出利率</n-button>
              <n-button quaternary>卖出利率 {{ toPercent(executionStatus.live_min_sell_profit_ratio || 0) }}</n-button>
              <n-button :disabled="executionConfigLoading" @click="$emit('adjustExecutionNumber', 'live_min_sell_profit_ratio', 0.01, 0, 3)">+1% 卖出利率</n-button>
            </n-button-group>
          </n-space>
        </n-collapse-item>
      </n-collapse>
    </div>

    <div v-if="canOperate" class="quick-adjust-card">
      <n-collapse :default-expanded-names="['autotrade-quick-tune']">
        <n-collapse-item title="快速调参（即时生效）" name="autotrade-quick-tune">
          <n-space wrap>
            <n-button-group size="small">
              <n-button :disabled="autotradeConfigLoading" @click="$emit('adjustAutotradeNumber', 'interval_sec', -5, 5, 3600)">-5s</n-button>
              <n-button quaternary>{{ autotradeStatus.interval_sec ?? "-" }}s</n-button>
              <n-button :disabled="autotradeConfigLoading" @click="$emit('adjustAutotradeNumber', 'interval_sec', 5, 5, 3600)">+5s</n-button>
            </n-button-group>
            <n-button-group size="small">
              <n-button :disabled="autotradeConfigLoading" @click="$emit('adjustAutotradeNumber', 'batch_size', -1, 1, 500)">-1 批量</n-button>
              <n-button quaternary>批量 {{ autotradeStatus.batch_size ?? "-" }}</n-button>
              <n-button :disabled="autotradeConfigLoading" @click="$emit('adjustAutotradeNumber', 'batch_size', 1, 1, 500)">+1 批量</n-button>
            </n-button-group>
            <n-button-group size="small">
              <n-button :disabled="autotradeConfigLoading" @click="$emit('adjustAutotradeNumber', 'min_score', -1, 0, 100)">-1 评分</n-button>
              <n-button quaternary>评分 {{ autotradeStatus.min_score ?? "-" }}</n-button>
              <n-button :disabled="autotradeConfigLoading" @click="$emit('adjustAutotradeNumber', 'min_score', 1, 0, 100)">+1 评分</n-button>
            </n-button-group>
            <n-button-group size="small">
              <n-button :disabled="autotradeConfigLoading" @click="$emit('adjustAutotradeRoi', -0.01)">-1% ROI</n-button>
              <n-button quaternary>ROI {{ toPercent(autotradeStatus.min_roi || 0) }}</n-button>
              <n-button :disabled="autotradeConfigLoading" @click="$emit('adjustAutotradeRoi', 0.01)">+1% ROI</n-button>
            </n-button-group>
            <n-button-group size="small">
              <n-button :disabled="autotradeConfigLoading" @click="$emit('adjustAutotradeNumber', 'max_risk_score', -1, 0, 100)">-1 风险</n-button>
              <n-button quaternary>风险 {{ autotradeStatus.max_risk_score ?? "-" }}</n-button>
              <n-button :disabled="autotradeConfigLoading" @click="$emit('adjustAutotradeNumber', 'max_risk_score', 1, 0, 100)">+1 风险</n-button>
            </n-button-group>
            <n-button
              size="small"
              :type="autotradeStatus.require_risk_score ? 'primary' : 'default'"
              :loading="autotradeConfigLoading"
              @click="$emit('toggleAutotradeFlag', 'require_risk_score')"
            >
              {{ autotradeStatus.require_risk_score ? "要求风险分: 开" : "要求风险分: 关" }}
            </n-button>
            <n-button
              size="small"
              :type="autotradeStatus.auto_execute_buy_on_approve ? 'success' : 'default'"
              :loading="autotradeConfigLoading"
              @click="$emit('toggleAutotradeFlag', 'auto_execute_buy_on_approve')"
            >
              {{ autotradeStatus.auto_execute_buy_on_approve ? "自动买入: 开" : "自动买入: 关" }}
            </n-button>
            <n-button
              size="small"
              :type="autotradeStatus.auto_execute_buy_dry_run ? 'warning' : 'error'"
              :loading="autotradeConfigLoading"
              @click="$emit('toggleAutotradeFlag', 'auto_execute_buy_dry_run')"
            >
              买入模式: {{ autotradeStatus.auto_execute_buy_dry_run ? "dry-run" : "live" }}
            </n-button>
            <n-button
              size="small"
              :type="autotradeStatus.auto_execute_list_on_buy_success ? 'success' : 'default'"
              :loading="autotradeConfigLoading"
              @click="$emit('toggleAutotradeFlag', 'auto_execute_list_on_buy_success')"
            >
              {{ autotradeStatus.auto_execute_list_on_buy_success ? "自动上架: 开" : "自动上架: 关" }}
            </n-button>
            <n-button
              size="small"
              :type="autotradeStatus.auto_execute_list_dry_run ? 'warning' : 'error'"
              :loading="autotradeConfigLoading"
              @click="$emit('toggleAutotradeFlag', 'auto_execute_list_dry_run')"
            >
              上架模式: {{ autotradeStatus.auto_execute_list_dry_run ? "dry-run" : "live" }}
            </n-button>
          </n-space>
        </n-collapse-item>
      </n-collapse>
    </div>

    <div v-if="canOperate" class="autotrade-once">
      <n-collapse>
        <n-collapse-item title="单次执行（按需展开）" name="autotrade-run-once">
          <n-space style="margin-bottom: 8px">
            <n-input
              :value="executionLiveConfirmToken"
              type="password"
              show-password-on="click"
              placeholder="实盘确认口令（EXECUTION_LIVE_CONFIRM_TOKEN）"
              style="width: 320px"
              :disabled="!executionStatus.live_confirm_required"
              @update:value="value => $emit('update:executionLiveConfirmToken', value)"
            />
          </n-space>
          <n-space>
            <n-input-number
              :value="autotradeRunLimit"
              :min="0"
              :max="500"
              style="width: 160px"
              placeholder="单次处理数(0=默认)"
              @update:value="value => $emit('update:autotradeRunLimit', value)"
            />
            <n-switch :value="autotradeRunForce" @update:value="value => $emit('update:autotradeRunForce', value)">
              <template #checked>强制执行</template>
              <template #unchecked>遵循环境开关</template>
            </n-switch>
            <div class="action-with-help">
              <n-button type="warning" :loading="autotradeActionLoading === 'run_once'" @click="$emit('runAutotradeOnce')">
                运行一次
              </n-button>
              <n-tooltip trigger="hover">
                <template #trigger>
                  <span class="help-badge">!</span>
                </template>
                立刻执行一次审批流程，适合验证参数效果；不会自动持续循环。
              </n-tooltip>
            </div>
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
