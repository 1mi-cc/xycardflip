<template>
  <div class="system-settings-page">
    <div class="page-header">
      <h1>系统设置</h1>
      <p>管理本地管理员配置、Gemini Key 与自动调参安全护栏。</p>
    </div>

    <n-space vertical size="large">
      <n-alert
        v-if="setupStatus?.bootstrap_password_mode"
        type="warning"
        :bordered="false"
      >
        当前仍处于 bootstrap 密码模式。建议尽快设置固定管理员密码。
      </n-alert>

      <n-alert
        v-for="item in startupChecks"
        :key="item.code"
        :bordered="false"
        :type="item.severity === 'critical' ? 'error' : item.severity === 'warning' ? 'warning' : 'info'"
      >
        {{ item.message }}
      </n-alert>

      <n-card title="基础配置" :bordered="false">
        <n-form label-placement="top" :model="setupForm">
          <n-form-item label="管理员密码">
            <n-input
              placeholder="留空表示不修改当前密码"
              show-password-on="click"
              type="password"
              v-model:value="setupForm.ui_auth_password"
            ></n-input>
          </n-form-item>
          <n-form-item label="管理员昵称">
            <n-input v-model:value="setupForm.ui_auth_nickname"></n-input>
          </n-form-item>
          <n-form-item label="Gemini API Key">
            <n-input
              placeholder="可选"
              show-password-on="click"
              type="password"
              v-model:value="setupForm.gemini_api_key"
            ></n-input>
          </n-form-item>
          <n-form-item label="Gemini key source path">
            <n-input
              placeholder="例如 C:\\Users\\25901\\Desktop\\filess_backup\\gemini-balance"
              v-model:value="setupForm.gemini_key_source_path"
            ></n-input>
          </n-form-item>
          <div class="meta-grid">
            <div class="meta-item">
              <span class="meta-label">配置文件</span>
              <span class="meta-value">{{ setupStatus?.config_path || "-" }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">Bootstrap 文件</span>
              <span class="meta-value">{{ setupStatus?.bootstrap_credentials_path || "-" }}</span>
            </div>
          </div>
          <div v-if="geminiRuntimeStatus" class="gemini-runtime-panel">
            <div class="gemini-runtime-header">
              <span class="meta-label">Current Gemini source</span>
              <span class="gemini-source-pill" :class="`is-${geminiRuntimeStatus.source_type || 'none'}`">
                {{ geminiSourceLabel }}
              </span>
            </div>
            <div class="meta-grid gemini-runtime-grid">
              <div class="meta-item">
                <span class="meta-label">Active keys</span>
                <span class="meta-value">{{ geminiRuntimeStatus.key_count ?? 0 }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">External pool keys</span>
                <span class="meta-value">{{ geminiRuntimeStatus.external_key_count ?? 0 }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">Local fallback keys</span>
                <span class="meta-value">{{ geminiRuntimeStatus.local_key_count ?? 0 }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">Current model</span>
                <span class="meta-value">{{ geminiRuntimeStatus.model || "-" }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">Resolved source</span>
                <span class="meta-value">{{ geminiRuntimeStatus.resolved_key_source_path || "-" }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">Rate-limited keys</span>
                <span class="meta-value">{{ geminiRuntimeStatus.rate_limited_key_count ?? 0 }}</span>
              </div>
            </div>
            <n-alert
              v-if="geminiRuntimeStatus.external_source_configured && !geminiRuntimeStatus.external_source_found"
              style="margin-top: 12px"
              type="warning"
              :bordered="false"
            >
              Configured Gemini key source path was not found on disk.
            </n-alert>
          </div>
          <div class="page-actions" style="margin-top: 12px; justify-content: flex-start">
            <n-button :loading="geminiTestLoading" @click="testGeminiConnection">
              测试 Gemini 连接
            </n-button>
          </div>
          <n-alert
            v-if="geminiTestResult"
            style="margin-top: 12px"
            :bordered="false"
            :type="geminiTestResult.success ? 'success' : 'warning'"
          >
            {{
              geminiTestResult.success
                ? `Gemini connected (${geminiTestResult.model})`
                : `Gemini test failed: ${geminiTestResult.error || 'unknown error'}`
            }}
            <template v-if="geminiTestResult.key_source_path">
              / source {{ geminiTestResult.key_source_path }}
            </template>
            <template v-if="geminiTestResult.resolved_key_source_path">
              / resolved {{ geminiTestResult.resolved_key_source_path }}
            </template>
            <template v-if="typeof geminiTestResult.key_count === 'number'">
              / {{ geminiTestResult.key_count }} keys
            </template>
          </n-alert>
        </n-form>
      </n-card>

      <n-card title="自动调参护栏" :bordered="false">
        <n-form label-placement="top" :model="setupForm">
          <n-form-item label="启用自动应用">
            <n-switch v-model:value="setupForm.auto_tune_auto_apply_enabled"></n-switch>
          </n-form-item>
          <n-form-item label="冷却期（小时）">
            <n-input-number
              style="width: 100%"
              v-model:value="setupForm.auto_tune_cooldown_hours"
              :max="240"
              :min="0"
            ></n-input-number>
          </n-form-item>
          <n-form-item label="最少关闭批次数">
            <n-input-number
              style="width: 100%"
              v-model:value="setupForm.auto_tune_min_closed_batches"
              :max="10"
              :min="1"
            ></n-input-number>
          </n-form-item>
          <n-form-item label="最近一批最少卖出数">
            <n-input-number
              style="width: 100%"
              v-model:value="setupForm.auto_tune_latest_min_sold_count"
              :max="100"
              :min="1"
            ></n-input-number>
          </n-form-item>
          <n-form-item label="上一批最少卖出数">
            <n-input-number
              style="width: 100%"
              v-model:value="setupForm.auto_tune_previous_min_sold_count"
              :max="100"
              :min="1"
            ></n-input-number>
          </n-form-item>
        </n-form>
      </n-card>

      <n-card title="最近配置变更" :bordered="false">
        <div v-if="auditLoading" class="audit-loading">
          <n-spin :show="true"></n-spin>
        </div>
        <n-empty v-else-if="auditItems.length === 0" description="暂无配置变更记录"></n-empty>
        <n-table v-else striped size="small">
          <thead>
            <tr>
              <th>时间</th>
              <th>操作者</th>
              <th>来源</th>
              <th>变更项</th>
              <th>摘要</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in auditItems" :key="item.id">
              <td>{{ item.created_at || "-" }}</td>
              <td>{{ item.actor || "-" }}</td>
              <td>{{ item.source || "-" }}</td>
              <td class="audit-cell">
                {{ Array.isArray(item.changed_keys) ? item.changed_keys.join(", ") : "-" }}
              </td>
              <td class="audit-cell">{{ item.summary || "-" }}</td>
              <td>
                <n-button
                  tertiary
                  size="small"
                  type="warning"
                  :disabled="!canRollback(item)"
                  :loading="rollbackLoadingId === item.id"
                  @click="rollbackAudit(item)"
                >
                  回滚
                </n-button>
              </td>
            </tr>
          </tbody>
        </n-table>
      </n-card>

      <div class="page-actions">
        <n-button :loading="loading" @click="loadSettings">刷新</n-button>
        <n-button type="primary" :loading="saving" @click="saveSettings">保存设置</n-button>
      </div>
    </n-space>
  </div>
</template>

<script setup>
import { useMessage } from "naive-ui";
import { computed, onMounted, reactive, ref } from "vue";

import systemSettingsApi from "@/api/systemSettings";
import { useAuthStore } from "@/stores/auth";

const message = useMessage();
const authStore = useAuthStore();

const loading = ref(false);
const saving = ref(false);
const auditLoading = ref(false);
const geminiTestLoading = ref(false);
const rollbackLoadingId = ref(0);
const setupStatus = ref(null);
const auditItems = ref([]);
const geminiTestResult = ref(null);

const setupForm = reactive({
  ui_auth_password: "",
  ui_auth_nickname: "Local Admin",
  gemini_api_key: "",
  gemini_key_source_path: "",
  auto_tune_auto_apply_enabled: false,
  auto_tune_cooldown_hours: 24,
  auto_tune_min_closed_batches: 2,
  auto_tune_latest_min_sold_count: 5,
  auto_tune_previous_min_sold_count: 3,
});

const startupChecks = computed(() =>
  Array.isArray(setupStatus.value?.startup_checks?.items)
    ? setupStatus.value.startup_checks.items
    : [],
);

const geminiRuntimeStatus = computed(() => setupStatus.value?.values?.gemini_runtime_status || null);

const GEMINI_SOURCE_LABELS = {
  none: "Unconfigured",
  local_env: "Local key",
  external_pool: "External pool",
  mixed: "Mixed",
};

const geminiSourceLabel = computed(
  () => GEMINI_SOURCE_LABELS[geminiRuntimeStatus.value?.source_type] || "Unknown",
);

const syncSetupForm = (status) => {
  const values = status?.values || {};
  setupForm.ui_auth_password = "";
  setupForm.ui_auth_nickname = values.ui_auth_nickname || "Local Admin";
  setupForm.gemini_api_key = "";
  setupForm.gemini_key_source_path = values.gemini_key_source_path || "";
  setupForm.auto_tune_auto_apply_enabled = Boolean(values.auto_tune_auto_apply_enabled);
  setupForm.auto_tune_cooldown_hours = Number(values.auto_tune_cooldown_hours || 24);
  setupForm.auto_tune_min_closed_batches = Number(values.auto_tune_min_closed_batches || 2);
  setupForm.auto_tune_latest_min_sold_count = Number(values.auto_tune_latest_min_sold_count || 5);
  setupForm.auto_tune_previous_min_sold_count = Number(values.auto_tune_previous_min_sold_count || 3);
};

const loadSettings = async () => {
  try {
    loading.value = true;
    const payload = await systemSettingsApi.getStatus(authStore.token);
    setupStatus.value = payload;
    syncSetupForm(payload);
  } catch (error) {
    message.error(error instanceof Error ? error.message : "加载系统设置失败");
  } finally {
    loading.value = false;
  }
};

const loadAudit = async () => {
  try {
    auditLoading.value = true;
    const payload = await systemSettingsApi.listAudit(30, authStore.token);
    auditItems.value = Array.isArray(payload?.items) ? payload.items : [];
  } catch (error) {
    message.error(error instanceof Error ? error.message : "加载配置审计失败");
  } finally {
    auditLoading.value = false;
  }
};

const canRollback = (item) => {
  const keys = Array.isArray(item?.changed_keys) ? item.changed_keys : [];
  return !keys.some((key) => ["UI_AUTH_PASSWORD", "GEMINI_API_KEY"].includes(String(key)));
};

const rollbackAudit = async (item) => {
  if (!item?.id)
    return;
  try {
    rollbackLoadingId.value = item.id;
    const payload = await systemSettingsApi.rollbackAudit(item.id, authStore.token);
    setupStatus.value = payload?.status || setupStatus.value;
    syncSetupForm(payload?.status || setupStatus.value);
    await authStore.fetchUserInfo();
    await loadAudit();
    message.success("设置已回滚");
  } catch (error) {
    message.error(error instanceof Error ? error.message : "回滚设置失败");
  } finally {
    rollbackLoadingId.value = 0;
  }
};

const testGeminiConnection = async () => {
  try {
    geminiTestLoading.value = true;
    geminiTestResult.value = await systemSettingsApi.testGemini(authStore.token);
  } catch (error) {
    geminiTestResult.value = {
      success: false,
      error: error instanceof Error ? error.message : "Gemini test failed",
    };
  } finally {
    geminiTestLoading.value = false;
  }
};

const saveSettings = async () => {
  if (setupForm.ui_auth_password && setupForm.ui_auth_password.length < 6) {
    message.warning("管理员密码至少 6 位");
    return;
  }
  try {
    saving.value = true;
    const payload = await systemSettingsApi.apply({ ...setupForm }, authStore.token);
    setupStatus.value = payload?.status || setupStatus.value;
    syncSetupForm(payload?.status || setupStatus.value);
    await authStore.fetchUserInfo();
    await loadAudit();
    if (
      setupStatus.value?.values?.gemini_runtime_status?.enabled
      || setupStatus.value?.values?.gemini_runtime_status?.external_source_configured
    ) {
      await testGeminiConnection();
    }
    message.success("系统设置已保存");
  } catch (error) {
    message.error(error instanceof Error ? error.message : "保存系统设置失败");
  } finally {
    saving.value = false;
  }
};

onMounted(async () => {
  await Promise.all([loadSettings(), loadAudit()]);
});
</script>

<style scoped lang="scss">
.system-settings-page {
  display: grid;
  gap: 20px;
}

.page-header {
  h1 {
    margin: 0 0 8px;
    font-size: 30px;
    color: var(--text-primary);
  }

  p {
    margin: 0;
    color: var(--text-secondary);
    line-height: 1.7;
  }
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 8px;
}

.meta-item {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  background: #fbfcff;
}

.meta-label {
  color: var(--text-tertiary);
  font-size: 12px;
}

.meta-value {
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.6;
  word-break: break-all;
}

.gemini-runtime-panel {
  display: grid;
  gap: 12px;
  margin-top: 12px;
}

.gemini-runtime-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.gemini-source-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
  background: #e2e8f0;
}

.gemini-source-pill.is-local_env {
  background: #dbeafe;
  color: #1d4ed8;
}

.gemini-source-pill.is-external_pool {
  background: #dcfce7;
  color: #15803d;
}

.gemini-source-pill.is-mixed {
  background: #fef3c7;
  color: #b45309;
}

.gemini-source-pill.is-none {
  background: #e5e7eb;
  color: #4b5563;
}

.page-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.audit-loading {
  padding: 24px 0;
}

.audit-cell {
  max-width: 320px;
  word-break: break-word;
}

@media (max-width: 900px) {
  .meta-grid {
    grid-template-columns: 1fr;
  }

  .page-actions {
    flex-direction: column;
  }
}
</style>
