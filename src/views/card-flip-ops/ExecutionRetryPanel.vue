<template>
  <section class="service-panel autotrade-panel">
    <div class="service-head">
      <div class="service-copy">
        <div class="service-kicker">ExecutionRetry</div>
        <h3>失败重试引擎</h3>
        <p>用于兜底处理失败执行记录，既支持后台循环，也支持人工补跑一次。</p>
        <div class="service-tags">
          <n-tag
            size="small"
            :type="executionRetryServiceStatus.running ? 'success' : 'default'"
          >
            {{ executionRetryServiceStatus.running ? "运行中" : "已停止" }}
          </n-tag>
          <n-tag
            size="small"
            :type="executionRetryServiceStatus.enabled ? 'info' : 'warning'"
          >
            {{ executionRetryServiceStatus.enabled ? "已启用" : "未启用" }}
          </n-tag>
          <n-tag
            size="small"
            :type="executionRetryServiceStatus.dry_run ? 'warning' : 'error'"
          >
            {{ executionRetryServiceStatus.dry_run ? "默认 dry-run" : "默认 live" }}
          </n-tag>
        </div>
      </div>

      <n-space>
        <n-button
          size="small"
          type="primary"
          :disabled="!canOperate"
          :loading="executionRetryServiceActionLoading === 'start'"
          @click="$emit('startExecutionRetryService')"
        >
          启动
        </n-button>
        <n-button
          size="small"
          :disabled="!canOperate"
          :loading="executionRetryServiceActionLoading === 'stop'"
          @click="$emit('stopExecutionRetryService')"
        >
          停止
        </n-button>
        <n-button
          tertiary
          size="small"
          :loading="executionRetryServiceStatusLoading"
          @click="$emit('loadExecutionRetryServiceStatus')"
        >
          刷新状态
        </n-button>
      </n-space>
    </div>

    <div class="service-summary-grid">
      <div class="summary-chip">
        <span class="summary-label">循环间隔</span>
        <strong class="summary-value">{{ executionRetryServiceStatus.interval_sec ?? "-" }}s</strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">批量上限</span>
        <strong class="summary-value">{{ executionRetryServiceStatus.batch_size ?? "-" }}</strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">默认动作</span>
        <strong class="summary-value">{{ executionRetryServiceStatus.action || "all" }}</strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">确认口令</span>
        <strong class="summary-value">
          {{ executionRetryServiceStatus.confirm_token_configured ? "已配置" : "未配置" }}
        </strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">累计轮次</span>
        <strong class="summary-value">{{ executionRetryServiceStatus.total_runs ?? 0 }}</strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">累计成功</span>
        <strong class="summary-value">{{ executionRetryServiceStatus.total_succeeded ?? 0 }}</strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">累计失败</span>
        <strong class="summary-value">{{ executionRetryServiceStatus.total_failed ?? 0 }}</strong>
      </div>
      <div class="summary-chip summary-chip-wide">
        <span class="summary-label">最近错误</span>
        <strong class="summary-value">{{ executionRetryServiceStatus.last_error || "-" }}</strong>
      </div>
    </div>

    <div class="service-section">
      <div class="section-title">手动重试一次</div>
      <div class="section-subtitle">常用于发布后兜底，默认参数沿用服务配置。</div>
      <n-space wrap>
        <n-select
          style="width: 150px"
          :options="executionRetryActionOptions"
          :value="executionRetryServiceAction"
          @update:value="value => $emit('update:executionRetryServiceAction', value)"
        ></n-select>
        <n-input-number
          placeholder="重试条数"
          style="width: 130px"
          :max="200"
          :min="0"
          :value="executionRetryServiceRunLimit"
          @update:value="value => $emit('update:executionRetryServiceRunLimit', value)"
        ></n-input-number>
        <n-switch
          :value="executionRetryServiceDryRun"
          @update:value="value => $emit('update:executionRetryServiceDryRun', value)"
        >
          <template #checked>dry-run</template>
          <template #unchecked>live</template>
        </n-switch>
        <n-switch
          :value="executionRetryServiceExecutionForce"
          @update:value="value => $emit('update:executionRetryServiceExecutionForce', value)"
        >
          <template #checked>强制执行</template>
          <template #unchecked>严格校验</template>
        </n-switch>
        <n-switch
          :value="executionRetryServiceRunForce"
          @update:value="value => $emit('update:executionRetryServiceRunForce', value)"
        >
          <template #checked>忽略服务开关</template>
          <template #unchecked>遵循服务开关</template>
        </n-switch>
        <n-button
          type="warning"
          :loading="executionRetryServiceActionLoading === 'run_once'"
          @click="$emit('runExecutionRetryServiceOnce')"
        >
          运行一次
        </n-button>
      </n-space>
    </div>

    <div v-if="canOperate" class="service-section">
      <n-collapse>
        <n-collapse-item name="retry-quick-tune" title="服务参数">
          <n-space wrap>
            <n-button-group size="small">
              <n-button
                :disabled="executionRetryConfigLoading"
                @click="$emit('adjustExecutionRetryNumber', 'interval_sec', -5, 5, 3600)"
              >
                -5s
              </n-button>
              <n-button quaternary>{{ executionRetryServiceStatus.interval_sec ?? "-" }}s</n-button>
              <n-button
                :disabled="executionRetryConfigLoading"
                @click="$emit('adjustExecutionRetryNumber', 'interval_sec', 5, 5, 3600)"
              >
                +5s
              </n-button>
            </n-button-group>

            <n-button-group size="small">
              <n-button
                :disabled="executionRetryConfigLoading"
                @click="$emit('adjustExecutionRetryNumber', 'batch_size', -1, 1, 200)"
              >
                -1 批量
              </n-button>
              <n-button quaternary>批量 {{ executionRetryServiceStatus.batch_size ?? "-" }}</n-button>
              <n-button
                :disabled="executionRetryConfigLoading"
                @click="$emit('adjustExecutionRetryNumber', 'batch_size', 1, 1, 200)"
              >
                +1 批量
              </n-button>
            </n-button-group>

            <n-button-group size="small">
              <n-button
                :loading="executionRetryConfigLoading"
                :type="executionRetryServiceStatus.action === 'all' ? 'primary' : 'default'"
                @click="$emit('setExecutionRetryDefaultAction', 'all')"
              >
                全部
              </n-button>
              <n-button
                :loading="executionRetryConfigLoading"
                :type="executionRetryServiceStatus.action === 'buy' ? 'primary' : 'default'"
                @click="$emit('setExecutionRetryDefaultAction', 'buy')"
              >
                买入
              </n-button>
              <n-button
                :loading="executionRetryConfigLoading"
                :type="executionRetryServiceStatus.action === 'list' ? 'primary' : 'default'"
                @click="$emit('setExecutionRetryDefaultAction', 'list')"
              >
                上架
              </n-button>
              <n-button
                :loading="executionRetryConfigLoading"
                :type="executionRetryServiceStatus.action === 'sell' ? 'primary' : 'default'"
                @click="$emit('setExecutionRetryDefaultAction', 'sell')"
              >
                卖出
              </n-button>
            </n-button-group>

            <n-button
              size="small"
              :loading="executionRetryConfigLoading"
              :type="executionRetryServiceStatus.dry_run ? 'warning' : 'error'"
              @click="$emit('toggleExecutionRetryFlag', 'dry_run')"
            >
              默认模式：{{ executionRetryServiceStatus.dry_run ? "dry-run" : "live" }}
            </n-button>

            <n-button
              size="small"
              :loading="executionRetryConfigLoading"
              :type="executionRetryServiceStatus.force ? 'primary' : 'default'"
              @click="$emit('toggleExecutionRetryFlag', 'force')"
            >
              默认强制：{{ executionRetryServiceStatus.force ? "开" : "关" }}
            </n-button>
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
