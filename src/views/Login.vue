<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <img alt="XYZW" class="brand-logo" src="/icons/xiaoyugan.png">
        <div>
          <p class="brand-kicker">XYZW 卡片交易后台</p>
          <h1>登录</h1>
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
    </div>
  </div>
</template>

<script setup>
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
    // 表单校验会直接显示字段错误
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
  background: #2d3a4b;
}

.login-card {
  width: min(420px, 100%);
  padding: 40px 36px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.18);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.22);
}

.login-brand {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.brand-logo {
  width: 56px;
  height: 56px;
  border-radius: 10px;
}

.brand-kicker {
  margin: 0 0 6px;
  color: rgba(255, 255, 255, 0.72);
  font-size: 13px;
}

h1 {
  margin: 0;
  color: #fff;
  font-size: 28px;
  font-weight: 600;
}

:deep(.n-form-item-label__text) {
  color: rgba(255, 255, 255, 0.88) !important;
}

:deep(.n-input) {
  --n-color: rgba(0, 0, 0, 0.2) !important;
  --n-color-focus: rgba(0, 0, 0, 0.2) !important;
  --n-color-disabled: rgba(0, 0, 0, 0.2) !important;
  --n-border: 1px solid rgba(255, 255, 255, 0.12) !important;
  --n-border-hover: 1px solid rgba(255, 255, 255, 0.28) !important;
  --n-border-focus: 1px solid #409eff !important;
  --n-box-shadow-focus: 0 0 0 2px rgba(64, 158, 255, 0.15) !important;
}

:deep(.n-input-wrapper) {
  background: rgba(0, 0, 0, 0.18) !important;
}

:deep(.n-input__input-el),
:deep(.n-input__textarea-el),
:deep(.n-input__placeholder) {
  color: #fff !important;
}
</style>
