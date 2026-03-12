<template>
  <div class="register-page">
    <div class="register-card">
      <div class="register-head">
        <img alt="XYZW" class="brand-logo" src="/icons/xiaoyugan.png">
        <div>
          <p class="eyebrow">普通用户注册</p>
          <h1>创建账号后，你可以提交工单并持续跟踪问题处理进度。</h1>
        </div>
      </div>

      <n-form ref="registerFormRef" label-placement="top" :model="registerForm" :rules="registerRules">
        <div class="form-grid">
          <n-form-item label="用户名" path="username">
            <n-input placeholder="3-32 位字母、数字或 ._@-" v-model:value="registerForm.username"></n-input>
          </n-form-item>
          <n-form-item label="昵称" path="nickname">
            <n-input placeholder="用于工单显示" v-model:value="registerForm.nickname"></n-input>
          </n-form-item>
        </div>
        <n-form-item label="邮箱" path="email">
          <n-input placeholder="可选，但建议填写，便于管理员识别" v-model:value="registerForm.email"></n-input>
        </n-form-item>
        <div class="form-grid">
          <n-form-item label="密码" path="password">
            <n-input show-password-on="click" type="password" v-model:value="registerForm.password"></n-input>
          </n-form-item>
          <n-form-item label="确认密码" path="confirmPassword">
            <n-input
              show-password-on="click"
              type="password"
              v-model:value="registerForm.confirmPassword"
              @keydown.enter="handleRegister"
            ></n-input>
          </n-form-item>
        </div>
        <div class="form-actions">
          <n-button @click="router.push('/login')">返回登录</n-button>
          <n-button type="primary" :loading="authStore.isLoading" @click="handleRegister">注册账号</n-button>
        </div>
      </n-form>
    </div>
  </div>
</template>

<script setup>
import { useMessage } from "naive-ui";
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const message = useMessage();
const authStore = useAuthStore();
const registerFormRef = ref(null);

const registerForm = reactive({
  username: "",
  nickname: "",
  email: "",
  password: "",
  confirmPassword: "",
});

const registerRules = {
  username: [
    { required: true, message: "请输入用户名", trigger: ["blur", "input"] },
    { min: 3, max: 32, message: "用户名长度需在 3-32 位之间", trigger: ["blur", "input"] },
  ],
  password: [
    { required: true, message: "请输入密码", trigger: ["blur", "input"] },
    { min: 6, message: "密码至少 6 位", trigger: ["blur", "input"] },
  ],
  confirmPassword: [
    { required: true, message: "请再次输入密码", trigger: ["blur", "input"] },
    {
      validator: (_rule, value) => value === registerForm.password,
      message: "两次输入的密码不一致",
      trigger: ["blur", "input"],
    },
  ],
};

const handleRegister = async () => {
  if (!registerFormRef.value)
    return;
  try {
    await registerFormRef.value.validate();
    const result = await authStore.register({
      username: registerForm.username,
      nickname: registerForm.nickname,
      email: registerForm.email,
      password: registerForm.password,
    });
    if (!result.success) {
      message.error(result.message || "注册失败");
      return;
    }
    message.success("注册成功，请登录");
    router.push("/login");
  } catch {
    // field validation handles errors
  }
};
</script>

<style scoped lang="scss">
.register-page {
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.12), transparent 22rem),
    linear-gradient(180deg, #f8fbff 0%, #eef5ff 100%);
}

.register-card {
  width: min(760px, 100%);
  border-radius: 28px;
  padding: 34px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(148, 163, 184, 0.2);
  box-shadow: 0 24px 56px rgba(15, 23, 42, 0.08);
}

.register-head {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 22px;

  h1 {
    margin: 8px 0 0;
    font-size: 30px;
    line-height: 1.25;
    color: #0f172a;
  }
}

.eyebrow {
  margin: 0;
  color: #2563eb;
  font-size: 13px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.brand-logo {
  width: 56px;
  height: 56px;
  border-radius: 16px;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
}

@media (max-width: 640px) {
  .register-page {
    padding: 16px;
  }

  .register-card {
    padding: 24px 20px;
  }

  .register-head {
    flex-direction: column;
  }

  .register-head h1 {
    font-size: 24px;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .form-actions {
    flex-direction: column;
  }
}
</style>
