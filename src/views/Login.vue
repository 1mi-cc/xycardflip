<template>
  <div class="login-page">
    <div class="login-mask"></div>
    <section class="login-card">
      <div class="login-brand">
        <img alt="XYCardFlip" class="brand-logo" src="/icons/xiaoyugan.png">
        <div>
          <p class="brand-kicker">卡片倒卖后台</p>
          <h1>管理员登录</h1>
        </div>
      </div>

      <p class="login-copy">
        登录后进入管理总览，只保留卡片倒卖业务的收益、风险、执行与服务状态。
      </p>

      <n-form ref="loginFormRef" label-placement="top" :model="loginForm" :rules="loginRules">
        <n-form-item label="用户名" path="username">
          <n-input
            v-model:value="loginForm.username"
            placeholder="请输入用户名"
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
          登录后台
        </n-button>
      </n-form>
    </section>
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
    message: "请输入用户名",
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
});
</script>

<style scoped lang="scss">
.login-page {
  position: relative;
  min-height: 100vh;
  display: grid;
  place-items: center;
  overflow: hidden;
  background: linear-gradient(135deg, #2d3a4b 0%, #1f2d3d 100%);
}

.login-mask {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at top left, rgba(64, 158, 255, 0.32), transparent 26rem),
    radial-gradient(circle at bottom right, rgba(54, 79, 107, 0.8), transparent 20rem);
}

.login-card {
  position: relative;
  z-index: 1;
  width: min(420px, calc(100vw - 32px));
  padding: 32px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.2);
}

.login-brand {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-logo {
  width: 52px;
  height: 52px;
  border-radius: 8px;
}

.brand-kicker {
  margin: 0 0 4px;
  color: #409eff;
  font-size: 13px;
  font-weight: 600;
}

.login-brand h1 {
  margin: 0;
  color: #303133;
  font-size: 24px;
  font-weight: 600;
}

.login-copy {
  margin: 18px 0 24px;
  color: #606266;
  line-height: 1.7;
}

:deep(.n-form-item-label__text) {
  color: #303133;
  font-weight: 600;
}
</style>
