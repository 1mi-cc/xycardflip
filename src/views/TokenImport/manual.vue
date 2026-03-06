<template>
  <n-form
    ref="formRef"
    :model="form"
    :rules="rules"
    label-placement="top"
    size="large"
  >
    <n-form-item label="账户名称" path="name">
      <n-input
        v-model:value="form.name"
        placeholder="例如：主号战士"
        clearable
      />
    </n-form-item>

    <n-form-item label="Token 字符串" path="token">
      <n-input
        v-model:value="form.token"
        type="textarea"
        :rows="4"
        placeholder="粘贴 Base64 Token 或接口返回的 token 字符串"
        clearable
      />
    </n-form-item>

    <div class="optional-fields">
      <n-form-item label="服务器">
        <n-input v-model:value="form.server" placeholder="可选" />
      </n-form-item>
      <n-form-item label="WebSocket 地址">
        <n-input v-model:value="form.wsUrl" placeholder="留空则使用默认地址" />
      </n-form-item>
    </div>

    <div class="form-actions">
      <n-button type="primary" block :loading="submitting" @click="handleSubmit">
        添加 Token
      </n-button>
      <n-button v-if="tokenStore.hasTokens" block @click="$emit('cancel')">
        取消
      </n-button>
    </div>
  </n-form>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { useMessage } from "naive-ui";
import { useTokenStore } from "@/stores/tokenStore";

const emit = defineEmits(["cancel", "ok"]);
const tokenStore = useTokenStore();
const message = useMessage();
const formRef = ref();
const submitting = ref(false);

const form = reactive({
  name: "",
  token: "",
  server: "",
  wsUrl: "",
});

const rules = {
  name: [{ required: true, message: "请输入账户名称", trigger: "blur" }],
  token: [{ required: true, message: "请输入 Token 字符串", trigger: "blur" }],
};

const reset = () => {
  form.name = "";
  form.token = "";
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
    const result = tokenStore.importBase64Token(form.name, form.token, {
      server: form.server,
      wsUrl: form.wsUrl,
      importMethod: "manual",
    });

    if (!result?.success) {
      throw new Error(result?.message || "导入失败");
    }

    message.success(result.message || "Token 已添加");
    reset();
    emit("ok");
  } catch (error: any) {
    message.error(error?.message || "添加 Token 失败");
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

@media (max-width: 640px) {
  .optional-fields {
    grid-template-columns: 1fr;
  }
}
</style>
