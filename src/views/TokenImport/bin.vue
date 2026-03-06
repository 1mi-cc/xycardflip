<template>
  <div class="bin-import">
    <n-form label-placement="top" size="large">
      <n-form-item label="上传 bin / dmp 文件">
        <input
          ref="fileInputRef"
          class="file-input"
          type="file"
          accept=".bin,.dmp"
          multiple
          @change="handleFileChange"
        />
        <div class="upload-hint">
          选择一个或多个本地文件。系统会尝试把文件内容转换成可用 Token，并加入待导入列表。
        </div>
      </n-form-item>
    </n-form>

    <div v-if="roles.length" class="role-list">
      <article v-for="role in roles" :key="role.name" class="role-card">
        <div class="role-head">
          <strong>{{ role.name }}</strong>
          <n-tag size="small" type="info">{{ role.server || "未指定服务器" }}</n-tag>
        </div>
        <div class="role-token">{{ role.token }}</div>
      </article>
    </div>

    <div class="form-actions">
      <n-button type="primary" block :loading="submitting" @click="handleSubmit">
        添加 Token
      </n-button>
      <n-button v-if="tokenStore.hasTokens" block @click="handleCancel">
        取消
      </n-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useMessage } from "naive-ui";
import { useTokenStore } from "@/stores/tokenStore";
import { transformToken } from "@/utils/token";

type RoleItem = {
  name: string;
  token: string;
  server: string;
  wsUrl: string;
};

const emit = defineEmits(["cancel", "ok"]);
const tokenStore = useTokenStore();
const message = useMessage();
const fileInputRef = ref<HTMLInputElement | null>(null);
const roles = ref<RoleItem[]>([]);
const submitting = ref(false);

const handleCancel = () => {
  roles.value = [];
  if (fileInputRef.value) {
    fileInputRef.value.value = "";
  }
  emit("cancel");
};

const handleFileChange = async (event: Event) => {
  const target = event.target as HTMLInputElement;
  const files = Array.from(target.files || []);
  if (!files.length) return;

  for (const file of files) {
    try {
      const buffer = await file.arrayBuffer();
      const token = await transformToken(buffer);
      const name = file.name.replace(/\.(bin|dmp)$/i, "");
      roles.value.push({
        name,
        token,
        server: "",
        wsUrl: "",
      });
    } catch (error: any) {
      message.error(`${file.name} 转换失败：${error?.message || "未知错误"}`);
    }
  }
};

const handleSubmit = async () => {
  if (!roles.value.length) {
    message.warning("请先上传 bin 文件");
    return;
  }

  submitting.value = true;
  try {
    for (const role of roles.value) {
      tokenStore.addToken({
        name: role.name,
        token: role.token,
        server: role.server,
        wsUrl: role.wsUrl,
        importMethod: "bin",
      });
    }
    message.success(`已导入 ${roles.value.length} 个 Token`);
    roles.value = [];
    if (fileInputRef.value) {
      fileInputRef.value.value = "";
    }
    emit("ok");
  } finally {
    submitting.value = false;
  }
};
</script>

<style scoped lang="scss">
.file-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px dashed var(--border-medium);
  border-radius: 12px;
  background: #fff;
}

.upload-hint {
  margin-top: 10px;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.7;
}

.role-list {
  display: grid;
  gap: 12px;
  margin-top: 8px;
}

.role-card {
  padding: 14px 16px;
  border: 1px solid var(--border-light);
  border-radius: 14px;
  background: linear-gradient(180deg, #ffffff 0%, #f9fbff 100%);
}

.role-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.role-token {
  margin-top: 10px;
  font-family: Consolas, "Courier New", monospace;
  font-size: 12px;
  line-height: 1.7;
  word-break: break-all;
  color: var(--text-secondary);
}

.form-actions {
  display: grid;
  gap: 12px;
  margin-top: 20px;
}
</style>
