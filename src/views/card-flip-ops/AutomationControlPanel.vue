<template>
  <section class="service-panel autotrade-panel">
    <div class="service-head">
      <div class="service-copy">
        <div class="service-kicker">Automation</div>
        <h3>自动化编排</h3>
        <p>统一调度 `monitor`、`scan`、`autotrade` 和 `retry`，并根据当前系统状态自动收紧风险动作。</p>
        <div class="service-tags">
          <n-tag size="small" :type="automationStatus.all_running ? 'success' : 'warning'">
            {{ automationStatus.all_running ? "主链路运行中" : "主链路未完全运行" }}
          </n-tag>
          <n-tag size="small" :type="operatingStateType">
            {{ operatingStateLabel }}
          </n-tag>
          <n-tag size="small" :type="automationStatus.monitor?.is_running ? 'success' : 'default'">
            {{ automationStatus.monitor?.is_running ? "Monitor 运行中" : "Monitor 已停止" }}
          </n-tag>
          <n-tag size="small" :type="automationStatus.autotrade?.running ? 'success' : 'default'">
            {{ automationStatus.autotrade?.running ? "AutoTrade 运行中" : "AutoTrade 已停止" }}
          </n-tag>
          <n-tag size="small" :type="automationStatus.execution_retry?.running ? 'success' : 'default'">
            {{ automationStatus.execution_retry?.running ? "Retry 运行中" : "Retry 已停止" }}
          </n-tag>
        </div>
      </div>

      <n-space>
        <n-button
          size="small"
          type="primary"
          :disabled="!canOperate"
          :loading="automationActionLoading === 'start'"
          @click="$emit('startAutomation')"
        >
          启动
        </n-button>
        <n-button
          size="small"
          :disabled="!canOperate"
          :loading="automationActionLoading === 'stop'"
          @click="$emit('stopAutomation')"
        >
          停止
        </n-button>
        <n-button
          tertiary
          size="small"
          :loading="automationStatusLoading"
          @click="$emit('loadAutomationStatus')"
        >
          刷新状态
        </n-button>
      </n-space>
    </div>

    <div class="service-summary-grid">
      <div class="summary-chip summary-chip-wide">
        <span class="summary-label">当前运行状态</span>
        <strong class="summary-value">
          {{ operatingStateLabel }}
        </strong>
        <span class="summary-meta">{{ operatingReasonsText }}</span>
      </div>

      <div class="summary-chip summary-chip-wide">
        <span class="summary-label">状态机建议</span>
        <strong class="summary-value">
          {{ operatingRecommendationText }}
        </strong>
      </div>

      <div class="summary-chip summary-chip-wide">
        <span class="summary-label">默认链路</span>
        <strong class="summary-value">
          monitor={{ automationStatus.default_include_monitor ? "on" : "off" }}
          / scan={{ automationStatus.default_include_scan ? "on" : "off" }}
          / autotrade={{ automationStatus.default_include_autotrade ? "on" : "off" }}
          / retry={{ automationStatus.default_include_execution_retry ? "on" : "off" }}
        </strong>
      </div>

      <div class="summary-chip">
        <span class="summary-label">默认扫描上限</span>
        <strong class="summary-value">{{ automationStatus.default_scan_limit ?? "-" }}</strong>
      </div>

      <div class="summary-chip summary-chip-wide">
        <span class="summary-label">开机自动启动</span>
        <strong class="summary-value">
          monitor={{ automationStatus.auto_start_monitor ? "on" : "off" }}
          / autotrade={{ automationStatus.auto_start_autotrade ? "on" : "off" }}
          / retry={{ automationStatus.auto_start_execution_retry ? "on" : "off" }}
        </strong>
      </div>

      <div class="summary-chip">
        <span class="summary-label">最近执行</span>
        <strong class="summary-value">{{ automationStatus.last_run_at || "-" }}</strong>
      </div>

      <div class="summary-chip summary-chip-wide">
        <span class="summary-label">最近一次结果</span>
        <strong class="summary-value">{{ lastRunSummary }}</strong>
        <span class="summary-meta">{{ lastAppliedLimitsText }}</span>
      </div>
    </div>

    <div v-if="operatingStateHint" class="status-hint" :class="operatingStateHintClass">
      {{ operatingStateHint }}
    </div>
    <div v-if="monitorStopReasonText" class="status-hint warning">
      {{ monitorStopReasonText }}
    </div>
    <div v-if="monitorCookieStatusHintText" class="status-hint info">
      {{ monitorCookieStatusHintText }}
    </div>

    <div class="service-section">
      <div class="section-title">单次执行</div>
      <div class="section-subtitle">
        `force` 会跳过状态机的收敛策略。默认建议在 `normal` 或人工确认后再放开高风险动作。
      </div>
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
          <template #unchecked>受控</template>
        </n-switch>
        <n-input-number
          placeholder="扫描上限"
          style="width: 140px"
          :max="500"
          :min="0"
          :value="automationScanLimit"
          @update:value="value => $emit('update:automationScanLimit', value)"
        ></n-input-number>
        <n-input-number
          placeholder="审批上限"
          style="width: 150px"
          :max="500"
          :min="0"
          :value="automationAutotradeLimit"
          @update:value="value => $emit('update:automationAutotradeLimit', value)"
        ></n-input-number>
        <n-input-number
          placeholder="重试上限"
          style="width: 140px"
          :max="200"
          :min="0"
          :value="automationExecutionRetryLimit"
          @update:value="value => $emit('update:automationExecutionRetryLimit', value)"
        ></n-input-number>
        <n-button
          type="warning"
          :disabled="!canOperate"
          :loading="automationActionLoading === 'run_once'"
          @click="$emit('runAutomationOnce')"
        >
          运行一次
        </n-button>
      </n-space>
    </div>

    <div v-if="canMaintain" class="service-section">
      <n-collapse>
        <n-collapse-item name="automation-maintenance" title="维护动作">
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
              secondary
              size="small"
              type="error"
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
import { computed } from "vue";

const props = defineProps({
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

const operatingState = computed(() => props.automationStatus?.operating_state || {});
const operatingRecommendations = computed(
  () => operatingState.value?.recommendations || {},
);
const lastRunResult = computed(() => props.automationStatus?.last_run_result || {});
const monitorRuntime = computed(() => props.automationStatus?.monitor || {});

const operatingStateLabel = computed(() => {
  const state = String(operatingState.value?.state || "normal");
  return (
    {
      normal: "NORMAL / 正常",
      cautious: "CAUTIOUS / 谨慎",
      recovery: "RECOVERY / 恢复",
    }[state] || state.toUpperCase()
  );
});

const operatingStateType = computed(() => {
  const state = String(operatingState.value?.state || "normal");
  return (
    {
      normal: "success",
      cautious: "warning",
      recovery: "error",
    }[state] || "default"
  );
});

const operatingReasonsText = computed(() => {
  const reasons = Array.isArray(operatingState.value?.reasons)
    ? operatingState.value.reasons
    : [];
  if (!reasons.length)
    return "未提供额外原因";
  return reasons.join(" / ");
});

const factorText = (value) => {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric))
    return "-";
  return `x${numeric.toFixed(2)}`;
};

const operatingRecommendationText = computed(() => {
  const recommendation = operatingRecommendations.value;
  return [
    `scan ${factorText(recommendation.scan_limit_factor)}`,
    `autotrade ${factorText(recommendation.autotrade_limit_factor)}`,
    `retry ${factorText(recommendation.execution_retry_limit_factor)}`,
    `审批=${recommendation.allow_autotrade ? "允许" : "暂停"}`,
    `重试=${recommendation.allow_execution_retry ? "允许" : "暂停"}`,
  ].join(" / ");
});

const lastRunSummary = computed(() => {
  if (!props.automationStatus?.last_run_at)
    return "暂无执行记录";
  if (!lastRunResult.value || typeof lastRunResult.value !== "object")
    return "最近执行完成";

  const state = lastRunResult.value.success
    ? "成功"
    : lastRunResult.value.had_busy
      ? "部分忙碌"
      : "失败";
  return `结果=${state} / force=${lastRunResult.value.force ? "on" : "off"}`;
});

const lastAppliedLimitsText = computed(() => {
  const applied = lastRunResult.value?.applied_limits;
  if (!applied)
    return "尚未记录最近一次的动态限流结果";
  return [
    `scan ${applied.scan?.requested ?? "-"}→${applied.scan?.effective ?? "-"}`,
    `autotrade ${applied.autotrade?.requested ?? "-"}→${applied.autotrade?.effective ?? "-"}`,
    `retry ${applied.execution_retry?.requested ?? "-"}→${applied.execution_retry?.effective ?? "-"}`,
  ].join(" / ");
});

const operatingStateHint = computed(() => {
  const state = String(operatingState.value?.state || "normal");
  if (state === "recovery") {
    return "当前处于恢复状态。自动审批和失败重试会默认停用，建议先处理监控熔断、执行失败或业务封禁原因。";
  }
  if (state === "cautious") {
    return "当前处于谨慎状态。系统会自动收缩扫描、审批和重试批量，优先观察成功率和异常趋势。";
  }
  return "";
});

const operatingStateHintClass = computed(() =>
  String(operatingState.value?.state || "normal") === "recovery" ? "warning" : "info",
);

const monitorStopReasonText = computed(() => {
  const monitor = monitorRuntime.value;
  if (monitor.is_running)
    return "";
  if (monitor.circuit_open && monitor.circuit_reason) {
    return `熔断中：${monitor.circuit_reason}`;
  }
  if (monitor.last_error) {
    return `最近错误：${String(monitor.last_error)}`;
  }
  return "";
});

const monitorCookieStatusHintText = computed(() => {
  const cookieMeta = monitorRuntime.value?.cookie_meta || {};
  const ttl = Number(cookieMeta?.m_h5_tk_ttl_sec);
  if (!Number.isFinite(ttl))
    return "";
  const expireAt = String(cookieMeta?.m_h5_tk_expire_at || "");
  const expired = Boolean(cookieMeta?.m_h5_tk_expired);
  if (expired || ttl <= 0) {
    return "Cookie token 已过期，建议先刷新 Cookie，再启动 Monitor。";
  }
  if (ttl <= 3600) {
    const mins = Math.max(1, Math.floor(ttl / 60));
    return `Cookie token 将在约 ${mins} 分钟后过期（UTC ${expireAt || "-"}），建议提前刷新。`;
  }
  return "";
});
</script>
