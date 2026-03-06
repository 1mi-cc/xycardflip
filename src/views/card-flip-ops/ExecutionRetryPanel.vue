<template>
  <section class="autotrade-panel">
    <div class="autotrade-head">
      <div class="autotrade-title-wrap">
        <h3>ExecutionRetry 失败重试引擎</h3>
        <div class="autotrade-tags">
          <n-tag :type="executionRetryServiceStatus.running ? 'success' : 'default'" size="small">
            {{ executionRetryServiceStatus.running ? "运行中" : "已停止" }}
          </n-tag>
          <n-tag :type="executionRetryServiceStatus.enabled ? 'info' : 'warning'" size="small">
            {{ executionRetryServiceStatus.enabled ? "已启用" : "环境未启用" }}
          </n-tag>
        </div>
      </div>
      <n-space>
        <div class="action-with-help">
          <n-button
            size="small"
            type="primary"
            :loading="executionRetryServiceActionLoading === 'start'"
            :disabled="!canOperate"
            @click="$emit('startExecutionRetryService')"
          >
            启动
          </n-button>
          <n-tooltip trigger="hover">
            <template #trigger>
              <span class="help-badge">!</span>
            </template>
            启动失败执行重试循环，按默认动作与间隔自动重试。
          </n-tooltip>
        </div>
        <div class="action-with-help">
          <n-button
            size="small"
            :loading="executionRetryServiceActionLoading === 'stop'"
            :disabled="!canOperate"
            @click="$emit('stopExecutionRetryService')"
          >
            停止
          </n-button>
          <n-tooltip trigger="hover">
            <template #trigger>
              <span class="help-badge">!</span>
            </template>
            停止失败重试循环，不会删除已有执行日志。
          </n-tooltip>
        </div>
        <div class="action-with-help">
          <n-button size="small" tertiary :loading="executionRetryServiceStatusLoading" @click="$emit('loadExecutionRetryServiceStatus')">
            刷新状态
          </n-button>
          <n-tooltip trigger="hover">
            <template #trigger>
              <span class="help-badge">!</span>
            </template>
            重新读取重试服务状态、统计和最后错误信息。
          </n-tooltip>
        </div>
      </n-space>
    </div>

    <div class="autotrade-metrics">
      <span>循环间隔: {{ executionRetryServiceStatus.interval_sec ?? "-" }}s</span>
      <span>批量上限: {{ executionRetryServiceStatus.batch_size ?? "-" }}</span>
      <span>默认动作: {{ executionRetryServiceStatus.action || "all" }}</span>
      <span>默认模式: {{ executionRetryServiceStatus.dry_run ? "dry-run" : "live" }}</span>
      <span>默认强制: {{ executionRetryServiceStatus.force ? "开启" : "关闭" }}</span>
      <span>确认口令: {{ executionRetryServiceStatus.confirm_token_configured ? "已配置" : "未配置" }}</span>
      <span>最近运行: {{ executionRetryServiceStatus.last_run_at || "-" }}</span>
    </div>
    <div class="autotrade-metrics">
      <span>累计轮次: {{ executionRetryServiceStatus.total_runs ?? 0 }}</span>
      <span>累计重试: {{ executionRetryServiceStatus.total_retried ?? 0 }}</span>
      <span>累计成功: {{ executionRetryServiceStatus.total_succeeded ?? 0 }}</span>
      <span>累计失败: {{ executionRetryServiceStatus.total_failed ?? 0 }}</span>
      <span>最近错误: {{ executionRetryServiceStatus.last_error || "-" }}</span>
    </div>

    <div v-if="canOperate" class="quick-adjust-card">
      <n-collapse :default-expanded-names="['retry-quick-tune']">
        <n-collapse-item title="重试引擎参数（即时生效）" name="retry-quick-tune">
          <n-space wrap>
            <n-button-group size="small">
              <n-button :disabled="executionRetryConfigLoading" @click="$emit('adjustExecutionRetryNumber', 'interval_sec', -5, 5, 3600)">-5s</n-button>
              <n-button quaternary>{{ executionRetryServiceStatus.interval_sec ?? "-" }}s</n-button>
              <n-button :disabled="executionRetryConfigLoading" @click="$emit('adjustExecutionRetryNumber', 'interval_sec', 5, 5, 3600)">+5s</n-button>
            </n-button-group>
            <n-button-group size="small">
              <n-button :disabled="executionRetryConfigLoading" @click="$emit('adjustExecutionRetryNumber', 'batch_size', -1, 1, 200)">-1 批量</n-button>
              <n-button quaternary>批量 {{ executionRetryServiceStatus.batch_size ?? "-" }}</n-button>
              <n-button :disabled="executionRetryConfigLoading" @click="$emit('adjustExecutionRetryNumber', 'batch_size', 1, 1, 200)">+1 批量</n-button>
            </n-button-group>
            <n-button-group size="small">
              <n-button
                :type="executionRetryServiceStatus.action === 'all' ? 'primary' : 'default'"
                :loading="executionRetryConfigLoading"
                @click="$emit('setExecutionRetryDefaultAction', 'all')"
              >
                全部
              </n-button>
              <n-button
                :type="executionRetryServiceStatus.action === 'buy' ? 'primary' : 'default'"
                :loading="executionRetryConfigLoading"
                @click="$emit('setExecutionRetryDefaultAction', 'buy')"
              >
                买入
              </n-button>
              <n-button
                :type="executionRetryServiceStatus.action === 'list' ? 'primary' : 'default'"
                :loading="executionRetryConfigLoading"
                @click="$emit('setExecutionRetryDefaultAction', 'list')"
              >
                上架
              </n-button>
              <n-button
                :type="executionRetryServiceStatus.action === 'sell' ? 'primary' : 'default'"
                :loading="executionRetryConfigLoading"
                @click="$emit('setExecutionRetryDefaultAction', 'sell')"
              >
                卖出
              </n-button>
            </n-button-group>
            <n-button
              size="small"
              :type="executionRetryServiceStatus.dry_run ? 'warning' : 'error'"
              :loading="executionRetryConfigLoading"
              @click="$emit('toggleExecutionRetryFlag', 'dry_run')"
            >
              默认模式: {{ executionRetryServiceStatus.dry_run ? "dry-run" : "live" }}
            </n-button>
            <n-button
              size="small"
              :type="executionRetryServiceStatus.force ? 'primary' : 'default'"
              :loading="executionRetryConfigLoading"
              @click="$emit('toggleExecutionRetryFlag', 'force')"
            >
              默认强制: {{ executionRetryServiceStatus.force ? "开" : "关" }}
            </n-button>
          </n-space>
        </n-collapse-item>
      </n-collapse>
    </div>

    <div v-if="canOperate" class="autotrade-once">
      <n-collapse>
        <n-collapse-item title="手动重试一次（按需展开）" name="retry-run-once">
          <n-space>
            <n-select
              :value="executionRetryServiceAction"
              :options="executionRetryActionOptions"
              style="width: 140px"
              @update:value="value => $emit('update:executionRetryServiceAction', value)"
            />
            <n-input-number
              :value="executionRetryServiceRunLimit"
              :min="0"
              :max="200"
              style="width: 130px"
              placeholder="单次条数(0=默认)"
              @update:value="value => $emit('update:executionRetryServiceRunLimit', value)"
            />
            <n-switch :value="executionRetryServiceDryRun" @update:value="value => $emit('update:executionRetryServiceDryRun', value)">
              <template #checked>dry-run</template>
              <template #unchecked>live</template>
            </n-switch>
            <n-switch :value="executionRetryServiceExecutionForce" @update:value="value => $emit('update:executionRetryServiceExecutionForce', value)">
              <template #checked>force</template>
              <template #unchecked>strict</template>
            </n-switch>
            <n-switch :value="executionRetryServiceRunForce" @update:value="value => $emit('update:executionRetryServiceRunForce', value)">
              <template #checked>忽略启用开关</template>
              <template #unchecked>遵循启用开关</template>
            </n-switch>
            <div class="action-with-help">
              <n-button
                type="warning"
                :loading="executionRetryServiceActionLoading === 'run_once'"
                @click="$emit('runExecutionRetryServiceOnce')"
              >
                运行一次
              </n-button>
              <n-tooltip trigger="hover">
                <template #trigger>
                  <span class="help-badge">!</span>
                </template>
                仅执行一轮失败任务重试，常用于人工兜底或发布后回归验证。
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
  executionRetryServiceStatus: { type: Object, default: () => ({}) },
  executionRetryServiceStatusLoading: { type: Boolean, default: false },
  executionRetryServiceActionLoading: { type: String, default: "" },
  executionRetryConfigLoading: { type: Boolean, default: false },
  canOperate: { type: Boolean, default: false },
  executionRetryServiceAction: { type: String, default: "all" },
  executionRetryServiceRunLimit: { type: Number, default: 0 },
  executionRetryServiceRunForce: { type: Boolean, default: false },
  executionRetryServiceDryRun: { type: Boolean, default: true },
  executionRetryServiceExecutionForce: { type: Boolean, default: false },
  executionRetryActionOptions: { type: Array, default: () => [] },
});

defineEmits([
  "loadExecutionRetryServiceStatus",
  "startExecutionRetryService",
  "stopExecutionRetryService",
  "adjustExecutionRetryNumber",
  "setExecutionRetryDefaultAction",
  "toggleExecutionRetryFlag",
  "update:executionRetryServiceAction",
  "update:executionRetryServiceRunLimit",
  "update:executionRetryServiceRunForce",
  "update:executionRetryServiceDryRun",
  "update:executionRetryServiceExecutionForce",
  "runExecutionRetryServiceOnce",
]);
</script>
