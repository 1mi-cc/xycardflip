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
          <p class="brand-kicker">XYZW</p>
          <h1>Sign In</h1>
        </div>
      </div>

      <n-form ref="loginFormRef" label-placement="top" :model="loginForm" :rules="loginRules">
        <n-form-item label="Username" path="username">
          <n-input
            v-model:value="loginForm.username"
            placeholder="Enter username"
            @keydown.enter="handleLogin"
          ></n-input>
        </n-form-item>
        <n-form-item label="Password" path="password">
          <n-input
            v-model:value="loginForm.password"
            type="password"
            show-password-on="click"
            placeholder="Enter password"
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
          Enter Console
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
    message: "Enter username",
    trigger: ["blur", "input"],
  },
  password: {
    required: true,
    message: "Enter password",
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
      message.error(result.message || "Sign in failed");
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
    radial-gradient(circle at top right, rgba(0, 113, 227, 0.18), transparent 22rem),
    radial-gradient(circle at bottom left, rgba(255, 255, 255, 0.04), transparent 28rem),
    #131313;
}

.login-card {
  width: min(440px, 100%);
  padding: 36px;
  border-radius: 24px;
  background: rgba(20, 21, 24, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 28px 56px rgba(0, 0, 0, 0.32);
}

.login-brand {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 28px;
}

.brand-mark {
  width: 46px;
  height: 46px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  color: #fff;
  background: linear-gradient(180deg, #2890ff, #0071e3);
  box-shadow: 0 18px 36px rgba(0, 113, 227, 0.26);
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
  font-size: 32px;
  font-weight: 800;
  letter-spacing: -0.04em;
}

:deep(.n-form-item-label__text) {
  color: var(--text-secondary) !important;
  font-weight: 700;
}

@media (max-width: 640px) {
  .login-card {
    padding: 28px 22px;
  }
}
</style>
