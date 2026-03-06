<template>
  <section class="autotrade-panel">
    <div class="autotrade-head">
      <div class="autotrade-title-wrap">
        <h3>Automation 全自动总控</h3>
        <div class="autotrade-tags">
          <n-tag :type="automationStatus.all_running ? 'success' : 'warning'" size="small">
            {{ automationStatus.all_running ? "全链路运行中" : "部分或全部未运行" }}
          </n-tag>
          <n-tag :type="automationStatus.monitor?.is_running ? 'success' : 'default'" size="small">
            {{ automationStatus.monitor?.is_running ? "Monitor 运行中" : "Monitor 已停止" }}
          </n-tag>
          <n-tag :type="automationStatus.autotrade?.running ? 'success' : 'default'" size="small">
            {{ automationStatus.autotrade?.running ? "AutoTrade 运行中" : "AutoTrade 已停止" }}
          </n-tag>
          <n-tag :type="automationStatus.execution_retry?.running ? 'success' : 'default'" size="small">
            {{ automationStatus.execution_retry?.running ? "ExecRetry 运行中" : "ExecRetry 已停止" }}
          </n-tag>
        </div>
      </div>
      <n-space>
        <div class="action-with-help">
          <n-button
            size="small"
            type="primary"
            :loading="automationActionLoading === 'start'"
            :disabled="!canOperate"
            @click="$emit('startAutomation')"
          >
            一键启动
          </n-button>
          <n-tooltip trigger="hover">
            <template #trigger>
              <span class="help-badge">!</span>
            </template>
            启动 monitor、autotrade、retry。
          </n-tooltip>
        </div>
        <div class="action-with-help">
          <n-button
            size="small"
            :loading="automationActionLoading === 'stop'"
            :disabled="!canOperate"
            @click="$emit('stopAutomation')"
          >
            一键停止
          </n-button>
          <n-tooltip trigger="hover">
            <template #trigger>
              <span class="help-badge">!</span>
            </template>
            停止 monitor、autotrade、retry。
          </n-tooltip>
        </div>
        <div class="action-with-help">
          <n-button size="small" tertiary :loading="automationStatusLoading" @click="$emit('loadAutomationStatus')">
            刷新状态
          </n-button>
          <n-tooltip trigger="hover">
            <template #trigger>
              <span class="help-badge">!</span>
            </template>
            仅拉取服务状态，便于排错。
          </n-tooltip>
        </div>
      </n-space>
    </div>

    <div class="autotrade-metrics">
      <span>默认链路: monitor={{ automationStatus.default_include_monitor ? "on" : "off" }}, scan={{ automationStatus.default_include_scan ? "on" : "off" }}, autotrade={{ automationStatus.default_include_autotrade ? "on" : "off" }}, retry={{ automationStatus.default_include_execution_retry ? "on" : "off" }}</span>
      <span>默认扫描上限: {{ automationStatus.default_scan_limit ?? "-" }}</span>
      <span>启动自拉起: monitor={{ automationStatus.auto_start_monitor ? "on" : "off" }}, autotrade={{ automationStatus.auto_start_autotrade ? "on" : "off" }}, retry={{ automationStatus.auto_start_execution_retry ? "on" : "off" }}</span>
      <span>最近编排执行: {{ automationStatus.last_run_at || "-" }}</span>
    </div>

    <div v-if="monitorStopReason" class="status-hint warning">
      Monitor 已停止：{{ monitorStopReason }}
    </div>
    <div v-if="monitorCookieStatusHint" class="status-hint info">
      {{ monitorCookieStatusHint }}
    </div>

    <div class="autotrade-once">
      <n-space>
        <n-switch :value="automationIncludeMonitor" @update:value="value => $emit('update:automationIncludeMonitor', value)">
          <template #checked>monitor</template>
          <template #unchecked>no monitor</template>
        </n-switch>
        <n-switch :value="automationIncludeScan" @update:value="value => $emit('update:automationIncludeScan', value)">
          <template #checked>scan</template>
          <template #unchecked>no scan</template>
        </n-switch>
        <n-switch :value="automationIncludeAutotrade" @update:value="value => $emit('update:automationIncludeAutotrade', value)">
          <template #checked>autotrade</template>
          <template #unchecked>no autotrade</template>
        </n-switch>
        <n-switch :value="automationIncludeExecutionRetry" @update:value="value => $emit('update:automationIncludeExecutionRetry', value)">
          <template #checked>retry</template>
          <template #unchecked>no retry</template>
        </n-switch>
        <n-switch :value="automationForce" @update:value="value => $emit('update:automationForce', value)">
          <template #checked>force</template>
          <template #unchecked>strict</template>
        </n-switch>
        <n-input-number
          :value="automationScanLimit"
          :min="0"
          :max="500"
          style="width: 140px"
          placeholder="scan limit"
          @update:value="value => $emit('update:automationScanLimit', value)"
        />
        <n-input-number
          :value="automationAutotradeLimit"
          :min="0"
          :max="500"
          style="width: 150px"
          placeholder="autotrade limit"
          @update:value="value => $emit('update:automationAutotradeLimit', value)"
        />
        <n-input-number
          :value="automationExecutionRetryLimit"
          :min="0"
          :max="200"
          style="width: 140px"
          placeholder="retry limit"
          @update:value="value => $emit('update:automationExecutionRetryLimit', value)"
        />
        <div class="action-with-help">
          <n-button
            type="warning"
            :loading="automationActionLoading === 'run_once'"
            :disabled="!canOperate"
            @click="$emit('runAutomationOnce')"
          >
            链路运行一次
          </n-button>
          <n-tooltip trigger="hover">
            <template #trigger>
              <span class="help-badge">!</span>
            </template>
            按当前开关顺序执行 monitor、scan、autotrade、retry 各一步。
          </n-tooltip>
        </div>
      </n-space>
    </div>

    <div v-if="canMaintain" class="quick-adjust-card">
      <n-collapse>
        <n-collapse-item title="系统维护（低频/危险）" name="automation-maintenance">
          <n-space wrap>
            <div class="action-with-help">
              <n-button size="small" type="warning" :loading="monitorActionLoading" @click="$emit('restartMonitor')">
                重启 Monitor
              </n-button>
              <n-tooltip trigger="hover">
                <template #trigger>
                  <span class="help-badge">!</span>
                </template>
                仅重启采集器，不影响审批和重试模块。
              </n-tooltip>
            </div>
            <div class="action-with-help">
              <n-button size="small" type="error" secondary :loading="monitorActionLoading" @click="$emit('resetMonitorCircuit')">
                解熔断
              </n-button>
              <n-tooltip trigger="hover">
                <template #trigger>
                  <span class="help-badge">!</span>
                </template>
                清空熔断计数并允许 Monitor 重新启动，不会清理数据库数据。
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
