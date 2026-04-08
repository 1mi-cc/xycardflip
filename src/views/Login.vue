<template>
  <div class="login-page">
    <section class="login-card">
      <div class="login-brand">
        <div class="brand-mark">
          <n-icon size="18">
            <BarChartOutline></BarChartOutline>
          </n-icon>
        </div>
        <div>
          <p class="brand-kicker">Card Trading Console</p>
          <h1>登录后台</h1>
        </div>
      </div>

      <n-form ref="loginFormRef" label-placement="top" :model="loginForm" :rules="loginRules">
        <n-form-item label="账号" path="username">
          <n-input
            v-model:value="loginForm.username"
            placeholder="请输入账号"
            @keydown.enter="handleLogin"
          ></n-input>
        </n-form-item>
        <n-form-item label="密码" path="password">
          <n-input
            v-model:value="loginForm.password"
            type="password"
            show-password-on="click"
            placeholder="请输入密码"
            @keydown.enter="handleLogin"
          ></n-input>
        </n-form-item>
        <n-button
          block
          size="large"
          type="primary"
          :loading="authStore.isLoading"
          @click="handleLogin"
        >
          登录
        </n-button>
      </n-form>
    </section>
  </div>
</template>

<script setup>
import { BarChartOutline } from "@vicons/ionicons5";
import { useMessage } from "naive-ui";
import { onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const authStore = useAuthStore();
const message = useMessage();
const route = useRoute();
const router = useRouter();

const loginFormRef = ref(null);
const loginForm = reactive({
  username: "",
  password: "",
});

const loginRules = {
  username: {
    required: true,
    message: "请输入账号",
    trigger: ["blur", "input"],
  },
  password: {
    required: true,
    message: "请输入密码",
    trigger: ["blur", "input"],
  },
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
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "";
    router.push(redirect || authStore.getDefaultHomeRoute());
  } catch {
    // validation handled in form
  }
};

onMounted(async () => {
  await authStore.initAuth();
  if (authStore.isAuthenticated)
    router.replace(authStore.getDefaultHomeRoute());
});
</script>

<style scoped lang="scss">
.login-page {
  display: flex;
  min-height: 100vh;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(circle at top left, rgba(0, 81, 213, 0.08), transparent 24rem),
    var(--bg-primary);
}

.login-card {
  width: min(440px, 100%);
  padding: 36px;
  border-radius: var(--radius-lg);
  background: var(--surface-card);
  border: 1px solid var(--surface-line);
  box-shadow: var(--shadow-medium);
}

.login-brand {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 28px;
}

.brand-mark {
  width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  color: #fff;
  background: linear-gradient(180deg, #306bf3, #0051d5);
  box-shadow: 0 10px 22px rgba(0, 81, 213, 0.2);
}

.brand-kicker {
  margin: 0 0 4px;
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 32px;
  font-weight: 800;
  letter-spacing: -0.04em;
}

:deep(.n-form-item-label__text) {
  color: var(--text-secondary) !important;
  font-weight: 700;
}

:deep(.n-input) {
  --n-border: 1px solid var(--surface-line) !important;
  --n-border-hover: 1px solid #b4c5ff !important;
  --n-border-focus: 1px solid var(--primary-color) !important;
  --n-box-shadow-focus: 0 0 0 2px rgba(0, 81, 213, 0.12) !important;
}

@media (max-width: 640px) {
  .login-card {
    padding: 28px 22px;
  }
}
</style>
