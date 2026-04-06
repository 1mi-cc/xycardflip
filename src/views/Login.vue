<template>
  <div class="auth-page">
    <div class="auth-shell">
      <section class="auth-intro">
        <p class="eyebrow">XYZW 管理系统</p>
        <h1>管理员登录后台，普通用户通过工单上报问题。</h1>
        <p class="intro-copy">
          这是本地软件的统一登录入口。管理员登录后进入后台操作台，普通用户登录后进入工单中心查看处理进度。
        </p>

        <div class="intro-cards">
          <div class="intro-card">
            <h3>管理员</h3>
            <p>进入控制台、Token 管理、卡片倒卖操作台和工单处理台。</p>
          </div>
          <div class="intro-card">
            <h3>普通用户</h3>
            <p>提交问题、补充截图说明、查看管理员回复和工单状态。</p>
          </div>
        </div>
      </section>

      <section class="auth-card">
        <div class="auth-head">
          <img alt="XYZW" class="brand-logo" src="/icons/xiaoyugan.png">
          <div>
            <h2>登录</h2>
            <p>输入账号密码后进入对应页面。</p>
          </div>
        </div>

        <n-alert
          v-if="setupStatus?.bootstrap_password_mode"
          class="setup-alert"
          type="warning"
          :bordered="false"
        >
          First launch detected. Set a fixed local admin password before regular use.
        </n-alert>

        <n-form ref="loginFormRef" label-placement="top" :model="loginForm" :rules="loginRules">
          <n-form-item label="用户名" path="username">
            <n-input placeholder="管理员或用户账号" v-model:value="loginForm.username"></n-input>
          </n-form-item>
          <n-form-item label="密码" path="password">
            <n-input
              placeholder="输入密码"
              show-password-on="click"
              type="password"
              v-model:value="loginForm.password"
              @keydown.enter="handleLogin"
            ></n-input>
          </n-form-item>
          <div class="auth-actions">
            <n-button v-if="allowRegistration" secondary @click="router.push('/register')">注册普通用户</n-button>
            <span v-else class="auth-footnote">当前服务端未开放自助注册</span>
            <n-button type="primary" :loading="authStore.isLoading" @click="handleLogin">登录</n-button>
          </div>
          <div v-if="setupStatus?.bootstrap_password_mode" class="setup-actions">
            <n-button tertiary type="warning" @click="showSetupModal = true">
              First-run setup
            </n-button>
          </div>
          <p class="credentials-hint">
            当前管理员账号：<code>{{ adminUsernameHint }}</code>。密码以服务器配置为准，不再显示默认值。
          </p>
        </n-form>
      </section>
    </div>

    <n-modal
      preset="card"
      style="width: min(680px, 96vw)"
      title="First-run setup"
      v-model:show="showSetupModal"
    >
      <n-space vertical size="large">
        <n-alert
          v-if="setupStatus?.bootstrap_password_mode"
          type="warning"
          :bordered="false"
        >
          Bootstrap password mode is active. Set a fixed admin password now so you do not need to rely on the generated credential file.
        </n-alert>

        <n-alert
          v-for="item in startupChecks"
          :key="item.code"
          :bordered="false"
          :type="item.severity === 'critical' ? 'error' : item.severity === 'warning' ? 'warning' : 'info'"
        >
          {{ item.message }}
        </n-alert>

        <n-form label-placement="top" :model="setupForm">
          <n-form-item label="Admin password">
            <n-input
              placeholder="At least 6 characters"
              show-password-on="click"
              type="password"
              v-model:value="setupForm.ui_auth_password"
            ></n-input>
          </n-form-item>
          <n-form-item label="Admin nickname">
            <n-input v-model:value="setupForm.ui_auth_nickname"></n-input>
          </n-form-item>
          <n-form-item label="Gemini API key">
            <n-input
              placeholder="Optional"
              show-password-on="click"
              type="password"
              v-model:value="setupForm.gemini_api_key"
            ></n-input>
          </n-form-item>
          <n-form-item label="Gemini key source path">
            <n-input
              placeholder="Optional external gemini-balance directory"
              v-model:value="setupForm.gemini_key_source_path"
            ></n-input>
          </n-form-item>
          <n-form-item label="Enable auto-tune auto apply">
            <n-switch v-model:value="setupForm.auto_tune_auto_apply_enabled"></n-switch>
          </n-form-item>
          <n-form-item label="Auto-tune cooldown (hours)">
            <n-input-number
              style="width: 100%"
              v-model:value="setupForm.auto_tune_cooldown_hours"
              :max="240"
              :min="0"
            ></n-input-number>
          </n-form-item>
          <n-form-item label="Closed batches required">
            <n-input-number
              style="width: 100%"
              v-model:value="setupForm.auto_tune_min_closed_batches"
              :max="10"
              :min="1"
            ></n-input-number>
          </n-form-item>
        </n-form>

        <div class="setup-actions">
          <n-button @click="showSetupModal = false">Close</n-button>
          <n-button type="primary" :loading="setupLoading" @click="handleSetupSave">
            Save setup
          </n-button>
        </div>
      </n-space>
    </n-modal>
  </div>
</template>

<script setup>
import { useMessage } from "naive-ui";
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import systemSettingsApi from "@/api/systemSettings";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const route = useRoute();
const message = useMessage();
const authStore = useAuthStore();
const loginFormRef = ref(null);
const showSetupModal = ref(false);
const setupLoading = ref(false);
const setupStatus = ref(null);

const loginForm = reactive({
  username: "",
  password: "",
});

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

const loginRules = {
  username: {
    required: true,
    message: "请输入用户名",
    trigger: ["blur", "input"],
  },
  password: {
    required: true,
    message: "请输入密码",
    trigger: ["blur", "input"],
  },
};

const startupChecks = computed(() =>
  Array.isArray(setupStatus.value?.startup_checks?.items)
    ? setupStatus.value.startup_checks.items
    : [],
);

const allowRegistration = computed(() => Boolean(setupStatus.value?.values?.ui_auth_allow_registration));
const adminUsernameHint = computed(() =>
  String(setupStatus.value?.values?.ui_auth_username || "operator").trim() || "operator",
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
  loginForm.username = String(values.ui_auth_username || "operator").trim() || "operator";
};

const loadSetupStatus = async () => {
  try {
    const payload = await systemSettingsApi.getStatus();
    setupStatus.value = payload;
    syncSetupForm(payload);
    if (payload?.bootstrap_password_mode)
      showSetupModal.value = true;
  } catch {
    setupStatus.value = null;
  }
};

const handleSetupSave = async () => {
  if (setupForm.ui_auth_password && setupForm.ui_auth_password.length < 6) {
    message.warning("Admin password must be at least 6 characters");
    return;
  }
  try {
    setupLoading.value = true;
    const payload = await systemSettingsApi.apply({ ...setupForm });
    setupStatus.value = payload?.status || setupStatus.value;
    syncSetupForm(payload?.status || setupStatus.value);
    if (setupStatus.value?.values?.ui_auth_username)
      loginForm.username = setupStatus.value.values.ui_auth_username;
    if (setupForm.ui_auth_password)
      loginForm.password = setupForm.ui_auth_password;
    message.success("First-run setup saved");
    showSetupModal.value = false;
  } catch (error) {
    message.error(error instanceof Error ? error.message : "Failed to save setup");
  } finally {
    setupLoading.value = false;
  }
};

const handleLogin = async () => {
  if (!loginFormRef.value)
    return;
  try {
    await loginFormRef.value.validate();
    const result = await authStore.login(loginForm);
    if (!result.success) {
      message.error(result.message || "登录失败");
      return;
    }
    message.success("登录成功");
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "";
    router.push(redirect || authStore.getDefaultHomeRoute());
  } catch {
    // form validation handles field errors
  }
};

onMounted(async () => {
  await authStore.initAuth();
  if (authStore.isAuthenticated)
    router.replace(authStore.getDefaultHomeRoute());
  else
    await loadSetupStatus();
});
</script>

<style scoped lang="scss">
.auth-page {
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(circle at top left, rgba(37, 99, 235, 0.16), transparent 24rem),
    linear-gradient(135deg, #f8fbff 0%, #eef4ff 100%);
}

.auth-shell {
  width: min(1120px, 100%);
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  gap: 28px;
  align-items: stretch;
}

.auth-intro,
.auth-card {
  border-radius: 28px;
  padding: 36px;
  color: #0f172a;
  background: rgba(255, 255, 255, 0.97);
  border: 1px solid rgba(148, 163, 184, 0.22);
  box-shadow: 0 28px 60px rgba(15, 23, 42, 0.12);
}

.auth-intro,
.auth-intro * ,
.auth-card,
.auth-card * {
  color: #0f172a;
}

.eyebrow {
  margin: 0;
  color: #2563eb !important;
  font-size: 13px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.auth-intro h1 {
  margin: 14px 0 16px;
  font-size: 40px;
  line-height: 1.15;
  color: #0f172a;
}

.intro-copy {
  margin: 0;
  max-width: 620px;
  color: #475569 !important;
  line-height: 1.8;
}

.intro-cards {
  margin-top: 28px;
  display: grid;
  gap: 16px;
}

.intro-card {
  padding: 18px 20px;
  border-radius: 20px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #0f172a !important;

  h3 {
    margin: 0 0 8px;
    color: #0f172a !important;
  }

  p {
    margin: 0;
    color: #475569 !important;
    line-height: 1.7;
  }
}

.auth-head {
  display: flex;
  gap: 14px;
  align-items: center;
  margin-bottom: 22px;

  h2 {
    margin: 0;
    font-size: 28px;
    color: #0f172a;
  }

  p {
    margin: 4px 0 0;
    color: #475569 !important;
  }
}

.brand-logo {
  width: 56px;
  height: 56px;
  border-radius: 16px;
}

.credentials-hint {
  margin: 14px 0 0;
  font-size: 13px;
  color: #475569;
  text-align: left;
  line-height: 1.6;

  code {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    background: #e2e8f0;
    padding: 2px 6px;
    border-radius: 6px;
    color: #0f172a;
    font-size: 12px;
  }
}

.auth-footnote {
  display: inline-flex;
  align-items: center;
  min-height: 40px;
  color: #64748b !important;
  font-size: 13px;
}

:deep(.n-form-item-label__text) {
  color: #0f172a !important;
  font-weight: 600;
}

:deep(.n-input),
:deep(.n-input-wrapper) {
  background: #fff !important;
}

:deep(.n-input) {
  --n-border: 1px solid #cbd5e1 !important;
  --n-border-hover: 1px solid #94a3b8 !important;
  --n-border-focus: 1px solid #2563eb !important;
  --n-box-shadow-focus: 0 0 0 2px rgba(37, 99, 235, 0.15) !important;
}

:deep(.n-input__input-el),
:deep(.n-input__textarea-el) {
  color: #0f172a !important;
  caret-color: #0f172a !important;
}

:deep(.n-input__placeholder) {
  color: #94a3b8 !important;
}

.setup-alert {
  margin-bottom: 16px;
}

.auth-actions {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 8px;
}

.setup-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 12px;
}

@media (max-width: 900px) {
  .auth-shell {
    grid-template-columns: 1fr;
  }

  .auth-intro h1 {
    font-size: 30px;
  }
}

@media (max-width: 640px) {
  .auth-page {
    padding: 16px;
  }

  .auth-intro,
  .auth-card {
    padding: 24px 20px;
  }

  .auth-actions {
    flex-direction: column;
  }
}
</style>
