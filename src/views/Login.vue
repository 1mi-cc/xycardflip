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
            <n-button secondary @click="router.push('/register')">注册普通用户</n-button>
            <n-button type="primary" :loading="authStore.isLoading" @click="handleLogin">登录</n-button>
          </div>
          <p class="credentials-hint">
            默认管理员账号：<code>operator</code>，密码：<code>admin123456</code>
          </p>
        </n-form>
      </section>
    </div>
  </div>
</template>

<script setup>
import { useMessage } from "naive-ui";
import { onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const route = useRoute();
const message = useMessage();
const authStore = useAuthStore();
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
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: 0 28px 60px rgba(15, 23, 42, 0.08);
}

.eyebrow {
  margin: 0;
  color: #2563eb;
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
  color: #475569;
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

  h3 {
    margin: 0 0 8px;
    color: #0f172a;
  }

  p {
    margin: 0;
    color: #475569;
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
  }

  p {
    margin: 4px 0 0;
    color: #64748b;
  }
}

.brand-logo {
  width: 56px;
  height: 56px;
  border-radius: 16px;
}

.credentials-hint {
  margin: 12px 0 0;
  font-size: 12px;
  color: #94a3b8;
  text-align: center;

  code {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    background: #f1f5f9;
    padding: 1px 5px;
    border-radius: 4px;
    color: #475569;
    font-size: 11px;
  }
}

.auth-actions {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 8px;
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
