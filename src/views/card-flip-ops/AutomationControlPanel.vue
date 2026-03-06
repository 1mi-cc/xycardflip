<template>
  <section class="service-panel autotrade-panel">
    <div class="service-head">
      <div class="service-copy">
        <div class="service-kicker">Automation</div>
        <h3>总控编排</h3>
        <p>按 monitor、scan、autotrade、retry 组合执行整条自动化链路。</p>
        <div class="service-tags">
          <n-tag :type="automationStatus.all_running ? 'success' : 'warning'" size="small">
            {{ automationStatus.all_running ? "主链路运行中" : "主链路未完全运行" }}
          </n-tag>
          <n-tag :type="automationStatus.monitor?.is_running ? 'success' : 'default'" size="small">
            {{ automationStatus.monitor?.is_running ? "Monitor 运行中" : "Monitor 已停止" }}
          </n-tag>
          <n-tag :type="automationStatus.autotrade?.running ? 'success' : 'default'" size="small">
            {{ automationStatus.autotrade?.running ? "AutoTrade 运行中" : "AutoTrade 已停止" }}
          </n-tag>
          <n-tag :type="automationStatus.execution_retry?.running ? 'success' : 'default'" size="small">
            {{
              automationStatus.execution_retry?.running
                ? "Retry 运行中"
                : "Retry 已停止"
            }}
          </n-tag>
        </div>
      </div>

      <n-space>
        <n-button
          size="small"
          type="primary"
          :loading="automationActionLoading === 'start'"
          :disabled="!canOperate"
          @click="$emit('startAutomation')"
        >
          启动
        </n-button>
        <n-button
          size="small"
          :loading="automationActionLoading === 'stop'"
          :disabled="!canOperate"
          @click="$emit('stopAutomation')"
        >
          停止
        </n-button>
        <n-button
          size="small"
          tertiary
          :loading="automationStatusLoading"
          @click="$emit('loadAutomationStatus')"
        >
          刷新状态
        </n-button>
      </n-space>
    </div>

    <div class="service-summary-grid">
      <div class="summary-chip summary-chip-wide">
        <span class="summary-label">默认链路</span>
        <strong class="summary-value">
          monitor={{ automationStatus.default_include_monitor ? "on" : "off" }}
          · scan={{ automationStatus.default_include_scan ? "on" : "off" }} ·
          autotrade={{ automationStatus.default_include_autotrade ? "on" : "off" }}
          · retry={{ automationStatus.default_include_execution_retry ? "on" : "off" }}
        </strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">默认扫描上限</span>
        <strong class="summary-value">{{ automationStatus.default_scan_limit ?? "-" }}</strong>
      </div>
      <div class="summary-chip summary-chip-wide">
        <span class="summary-label">开机自动拉起</span>
        <strong class="summary-value">
          monitor={{ automationStatus.auto_start_monitor ? "on" : "off" }} ·
          autotrade={{ automationStatus.auto_start_autotrade ? "on" : "off" }} ·
          retry={{ automationStatus.auto_start_execution_retry ? "on" : "off" }}
        </strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">最近执行</span>
        <strong class="summary-value">{{ automationStatus.last_run_at || "-" }}</strong>
      </div>
    </div>

    <div v-if="monitorStopReason" class="status-hint warning">
      {{ monitorStopReason }}
    </div>
    <div v-if="monitorCookieStatusHint" class="status-hint info">
      {{ monitorCookieStatusHint }}
    </div>

    <div class="service-section">
      <div class="section-title">单次执行</div>
      <div class="section-subtitle">只保留高频开关和条数，执行一次后局部刷新。</div>
      <n-space wrap>
        <n-switch
          :value="automationIncludeMonitor"
          @update:value="value => $emit('update:automationIncludeMonitor', value)"
        >
          <template #checked>Monitor</template>
          <template #unchecked>跳过 Monitor</template>
        </n-switch>
        <n-switch
          :value="automationIncludeScan"
          @update:value="value => $emit('update:automationIncludeScan', value)"
        >
          <template #checked>扫描</template>
          <template #unchecked>跳过扫描</template>
        </n-switch>
        <n-switch
          :value="automationIncludeAutotrade"
          @update:value="value => $emit('update:automationIncludeAutotrade', value)"
        >
          <template #checked>审批</template>
          <template #unchecked>跳过审批</template>
        </n-switch>
        <n-switch
          :value="automationIncludeExecutionRetry"
          @update:value="value => $emit('update:automationIncludeExecutionRetry', value)"
        >
          <template #checked>重试</template>
          <template #unchecked>跳过重试</template>
        </n-switch>
        <n-switch
          :value="automationForce"
          @update:value="value => $emit('update:automationForce', value)"
        >
          <template #checked>强制</template>
          <template #unchecked>严格</template>
        </n-switch>
        <n-input-number
          :value="automationScanLimit"
          :min="0"
          :max="500"
          style="width: 140px"
          placeholder="扫描上限"
          @update:value="value => $emit('update:automationScanLimit', value)"
        />
        <n-input-number
          :value="automationAutotradeLimit"
          :min="0"
          :max="500"
          style="width: 150px"
          placeholder="审批上限"
          @update:value="value => $emit('update:automationAutotradeLimit', value)"
        />
        <n-input-number
          :value="automationExecutionRetryLimit"
          :min="0"
          :max="200"
          style="width: 140px"
          placeholder="重试上限"
          @update:value="value => $emit('update:automationExecutionRetryLimit', value)"
        />
        <n-button
          type="warning"
          :loading="automationActionLoading === 'run_once'"
          :disabled="!canOperate"
          @click="$emit('runAutomationOnce')"
        >
          运行一次
        </n-button>
      </n-space>
    </div>

    <div v-if="canMaintain" class="service-section">
      <n-collapse>
        <n-collapse-item title="维护动作" name="automation-maintenance">
          <n-space wrap>
            <n-button
              size="small"
              type="warning"
              :loading="monitorActionLoading"
              @click="$emit('restartMonitor')"
            >
              重启 Monitor
            </n-button>
            <n-button
              size="small"
              type="error"
              secondary
              :loading="monitorActionLoading"
              @click="$emit('resetMonitorCircuit')"
            >
              重置熔断
            </n-button>
          </n-space>
        </n-collapse-item>
      </n-collapse>
    </div>
  </section>
</template>

<script setup>
defineProps({
  automationStatus: { type: Object, default: () => ({}) },
  automationStatusLoading: { type: Boolean, default: false },
  automationActionLoading: { type: String, default: "" },
  monitorActionLoading: { type: Boolean, default: false },
  canOperate: { type: Boolean, default: false },
  canMaintain: { type: Boolean, default: false },
  automationIncludeMonitor: { type: Boolean, default: true },
  automationIncludeScan: { type: Boolean, default: true },
  automationIncludeAutotrade: { type: Boolean, default: true },
  automationIncludeExecutionRetry: { type: Boolean, default: true },
  automationForce: { type: Boolean, default: false },
  automationScanLimit: { type: Number, default: 0 },
  automationAutotradeLimit: { type: Number, default: 0 },
  automationExecutionRetryLimit: { type: Number, default: 0 },
  monitorStopReason: { type: String, default: "" },
  monitorCookieStatusHint: { type: String, default: "" },
});

defineEmits([
  "update:automationIncludeMonitor",
  "update:automationIncludeScan",
  "update:automationIncludeAutotrade",
  "update:automationIncludeExecutionRetry",
  "update:automationForce",
  "update:automationScanLimit",
  "update:automationAutotradeLimit",
  "update:automationExecutionRetryLimit",
  "startAutomation",
  "stopAutomation",
  "loadAutomationStatus",
  "runAutomationOnce",
  "restartMonitor",
  "resetMonitorCircuit",
]);
</script>
