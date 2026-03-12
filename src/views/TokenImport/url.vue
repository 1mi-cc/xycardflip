<template>
  <n-form
    ref="formRef"
    label-placement="top"
    size="large"
    :model="form"
    :rules="rules"
  >
    <n-form-item label="账户名称" path="name">
      <n-input
        clearable
        placeholder="例如：主号战士"
        v-model:value="form.name"
      ></n-input>
    </n-form-item>

    <n-form-item label="Token 获取地址" path="url">
      <n-input
        clearable
        placeholder="输入返回 JSON 的接口地址"
        v-model:value="form.url"
      ></n-input>
      <template #feedback>
        <div class="form-tips">
          <span>接口应返回包含 `token` 字段的 JSON。</span>
          <span>如果是跨域地址，目标服务需要支持 CORS。</span>
        </div>
      </template>
    </n-form-item>

    <div class="optional-fields">
      <n-form-item label="服务器">
        <n-input placeholder="可选" v-model:value="form.server"></n-input>
      </n-form-item>
      <n-form-item label="WebSocket 地址">
        <n-input placeholder="留空则使用默认地址" v-model:value="form.wsUrl"></n-input>
      </n-form-item>
    </div>

    <div class="form-actions">
      <n-button block type="primary" :loading="submitting" @click="handleSubmit">
        获取并添加 Token
      </n-button>
      <n-button v-if="tokenStore.hasTokens" block @click="$emit('cancel')">
        取消
      </n-button>
    </div>
  </n-form>
</template>

<script setup lang="ts">
import { useMessage } from "naive-ui";
import { reactive, ref } from "vue";

import { useTokenStore } from "@/stores/tokenStore";

const emit = defineEmits(["cancel", "ok"]);
const tokenStore = useTokenStore();
const message = useMessage();
const formRef = ref();
const submitting = ref(false);

const form = reactive({
  name: "",
  url: "",
  server: "",
  wsUrl: "",
});

const rules = {
  name: [{ required: true, message: "请输入账户名称", trigger: "blur" }],
  url: [
    { required: true, message: "请输入 Token 获取地址", trigger: "blur" },
    { type: "url", message: "请输入有效的 URL", trigger: "blur" },
  ],
};

const reset = () => {
  form.name = "";
  form.url = "";
  form.server = "";
  form.wsUrl = "";
};

const handleSubmit = async () => {
  try {
    await formRef.value?.validate();
  } catch {
    return;
  }

  submitting.value = true;
  try {
    const response = await fetch(form.url, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      throw new Error(`请求失败：${response.status} ${response.statusText}`);
    }

    const payload = await response.json();
    if (!payload?.token) {
      throw new Error("接口返回中没有 token 字段");
    }

    const result = tokenStore.importBase64Token(form.name, payload.token, {
      server: form.server || payload.server || "",
      wsUrl: form.wsUrl || payload.wsUrl || "",
      sourceUrl: form.url,
      importMethod: "url",
    });

    if (!result?.success) {
      throw new Error(result?.message || "导入失败");
    }

    message.success(result.message || "Token 已添加");
    reset();
    emit("ok");
  } catch (error: any) {
    message.error(error?.message || "获取 Token 失败");
  } finally {
    submitting.value = false;
  }
};
</script>

<style scoped lang="scss">
.optional-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.form-actions {
  display: grid;
  gap: 12px;
  margin-top: 20px;
}

.form-tips {
  display: grid;
  gap: 4px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-tertiary);
}

@media (max-width: 640px) {
  .optional-fields {
    grid-template-columns: 1fr;
  }
}
</style>
