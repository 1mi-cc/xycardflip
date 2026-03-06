<template>
  <div class="token-import-page">
    <div class="container">
      <div class="page-header">
        <div class="header-content">
          <div class="header-top">
            <img src="/icons/xiaoyugan.png" alt="XYZW" class="brand-logo" />
            <ThemeToggle />
          </div>
          <div class="header-kicker">Account Center</div>
          <h1>游戏 Token 管理</h1>
          <p>统一管理导入账户、默认工作账户和刷新动作，作为整个后台的账户入口。</p>
        </div>
      </div>

      <n-modal
        v-model:show="showImportForm"
        preset="card"
        title="添加游戏 Token"
        style="width: min(720px, calc(100vw - 32px))"
      >
        <div class="card-header">
          <n-radio-group v-model:value="importMethod" class="import-method-tabs" size="small">
            <n-radio-button value="manual">手动输入</n-radio-button>
            <n-radio-button value="url">URL 获取</n-radio-button>
            <n-radio-button value="bin">BIN 获取</n-radio-button>
          </n-radio-group>
        </div>
        <div class="card-body">
          <ManualTokenForm
            v-if="importMethod === 'manual'"
            @cancel="showImportForm = false"
            @ok="handleImportSuccess"
          />
          <UrlTokenForm
            v-else-if="importMethod === 'url'"
            @cancel="showImportForm = false"
            @ok="handleImportSuccess"
          />
          <BinTokenForm
            v-else
            @cancel="showImportForm = false"
            @ok="handleImportSuccess"
          />
        </div>
      </n-modal>

      <div v-if="tokenStore.hasTokens" class="tokens-section">
        <div class="section-header">
          <n-space align="center">
            <h2>我的 Token 列表（{{ tokenStore.gameTokens.length }} 个）</h2>
            <n-radio-group v-model:value="viewMode" size="small">
              <n-radio-button value="card">卡片</n-radio-button>
              <n-radio-button value="list">列表</n-radio-button>
            </n-radio-group>
          </n-space>
          <div class="header-actions">
            <n-button v-if="tokenStore.selectedToken" type="success" @click="goToDashboard">
              <template #icon>
                <n-icon><Home /></n-icon>
              </template>
              返回控制台
            </n-button>

            <n-button type="primary" @click="showImportForm = true">
              <template #icon>
                <n-icon><Add /></n-icon>
              </template>
              添加 Token
            </n-button>

            <n-dropdown :options="bulkOptions" @select="handleBulkAction">
              <n-button>
                <template #icon>
                  <n-icon><Menu /></n-icon>
                </template>
                批量操作
              </n-button>
            </n-dropdown>
          </div>
        </div>

        <div v-if="viewMode === 'card'" class="tokens-grid">
          <n-card
            v-for="(token, index) in tokenStore.gameTokens"
            :key="token.id"
            draggable="true"
            hoverable
            :class="{ 'token-card': true, active: selectedTokenId === token.id }"
            @dragstart="handleDragStart(index, $event)"
            @dragover.prevent
            @drop="handleDrop(index, $event)"
            @click="selectToken(token)"
          >
            <template #header>
              <div class="token-card-head">
                <div class="token-name">
                  <strong>{{ token.name }}</strong>
                  <n-tag v-if="token.server" size="small" type="error">{{ token.server }}</n-tag>
                  <n-tag size="small" :type="statusType(token.id)">
                    {{ getConnectionStatusText(token.id) }}
                  </n-tag>
                </div>
                <n-dropdown :options="getTokenActions(token)" @select="key => handleTokenAction(key, token)">
                  <n-button text @click.stop>
                    <template #icon>
                      <n-icon><EllipsisHorizontal /></n-icon>
                    </template>
                  </n-button>
                </n-dropdown>
              </div>
            </template>

            <div class="token-display">
              <span class="token-label">Token</span>
              <code class="token-value">{{ maskToken(token.token) }}</code>
            </div>

            <div class="token-meta-grid">
              <div class="meta-row">
                <span class="meta-label">创建时间</span>
                <span>{{ formatTime(token.createdAt) }}</span>
              </div>
              <div class="meta-row">
                <span class="meta-label">最近使用</span>
                <span>{{ formatTime(token.lastUsed) }}</span>
              </div>
              <div class="meta-row">
                <span class="meta-label">存储类型</span>
                <n-tag size="small" :type="token.importMethod === 'url' ? 'success' : 'warning'">
                  {{ token.importMethod === "url" ? "长期有效" : "临时存储" }}
                </n-tag>
              </div>
            </div>

            <div class="card-actions">
              <n-button secondary :loading="refreshingTokens.has(token.id)" @click.stop="refreshToken(token)">
                <template #icon>
                  <n-icon><Refresh /></n-icon>
                </template>
                {{ token.sourceUrl ? "刷新" : "重新获取" }}
              </n-button>
              <n-button
                type="primary"
                :loading="connectingTokens.has(token.id)"
                @click.stop="startTaskManagement(token)"
              >
                <template #icon>
                  <n-icon><Home /></n-icon>
                </template>
                开始任务管理
              </n-button>
            </div>
          </n-card>
        </div>

        <div v-else class="tokens-list">
          <n-card
            v-for="(token, index) in tokenStore.gameTokens"
            :key="token.id"
            draggable="true"
            hoverable
            class="token-list-card"
            :class="{ active: selectedTokenId === token.id }"
            @dragstart="handleDragStart(index, $event)"
            @dragover.prevent
            @drop="handleDrop(index, $event)"
            @click="selectToken(token)"
          >
            <div class="token-list-row">
              <div class="token-list-main">
                <strong>{{ token.name }}</strong>
                <n-tag v-if="token.server" size="small" type="error">{{ token.server }}</n-tag>
                <n-tag size="small" :type="statusType(token.id)">
                  {{ getConnectionStatusText(token.id) }}
                </n-tag>
                <n-tag size="small" :type="token.importMethod === 'url' ? 'success' : 'warning'">
                  {{ token.importMethod === "url" ? "长期" : "临时" }}
                </n-tag>
              </div>
              <div class="token-list-actions">
                <n-button
                  size="small"
                  type="primary"
                  :loading="connectingTokens.has(token.id)"
                  @click.stop="startTaskManagement(token)"
                >
                  管理
                </n-button>
                <n-button
                  size="small"
                  secondary
                  :loading="refreshingTokens.has(token.id)"
                  @click.stop="refreshToken(token)"
                >
                  刷新
                </n-button>
                <n-dropdown :options="getTokenActions(token)" @select="key => handleTokenAction(key, token)">
                  <n-button size="small" circle @click.stop>
                    <template #icon>
                      <n-icon><EllipsisHorizontal /></n-icon>
                    </template>
                  </n-button>
                </n-dropdown>
              </div>
            </div>
          </n-card>
        </div>
      </div>

      <div v-else class="empty-state">
        <n-empty description="还没有导入任何 Token">
          <template #extra>
            <n-button type="primary" @click="showImportForm = true">打开 Token 管理</n-button>
          </template>
        </n-empty>
      </div>
    </div>

    <n-modal v-model:show="showEditModal" preset="card" title="编辑 Token" style="width: 520px">
      <n-form ref="editFormRef" :model="editForm" :rules="editRules" label-placement="top">
        <n-form-item label="名称" path="name">
          <n-input v-model:value="editForm.name" />
        </n-form-item>
        <n-form-item label="Token 字符串" path="token">
          <n-input v-model:value="editForm.token" type="textarea" :rows="4" />
        </n-form-item>
        <n-form-item label="服务器">
          <n-input v-model:value="editForm.server" />
        </n-form-item>
        <n-form-item label="WebSocket 地址">
          <n-input v-model:value="editForm.wsUrl" />
        </n-form-item>
      </n-form>

      <template #footer>
        <div class="modal-actions">
          <n-button @click="showEditModal = false">取消</n-button>
          <n-button type="primary" @click="saveEdit">保存</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { useDialog, useMessage } from "naive-ui";
import {
  Add,
  Create,
  EllipsisHorizontal,
  Home,
  Menu,
  Refresh,
  Star,
  TrashBin,
} from "@vicons/ionicons5";
import { selectedTokenId, useTokenStore } from "@/stores/tokenStore";
import ManualTokenForm from "./manual.vue";
import UrlTokenForm from "./url.vue";
import BinTokenForm from "./bin.vue";

const props = defineProps({
  token: String,
  name: String,
  server: String,
  wsUrl: String,
  api: String,
  auto: Boolean,
});

const router = useRouter();
const message = useMessage();
const dialog = useDialog();
const tokenStore = useTokenStore();

const showImportForm = ref(false);
const showEditModal = ref(false);
const importMethod = ref("manual");
const viewMode = ref("card");
const refreshingTokens = ref(new Set());
const connectingTokens = ref(new Set());
const dragIndex = ref(null);
const editFormRef = ref(null);
const editingTokenId = ref("");

const editForm = reactive({
  name: "",
  token: "",
  server: "",
  wsUrl: "",
});

const editRules = {
  name: [{ required: true, message: "请输入名称", trigger: "blur" }],
  token: [{ required: true, message: "请输入 Token 字符串", trigger: "blur" }],
};

const bulkOptions = computed(() => [
  { label: "刷新可自动刷新的 Token", key: "refreshAll" },
  { label: "导出 Token", key: "export" },
  { label: "导入备份文件", key: "import" },
  { label: "清理 24 小时未使用 Token", key: "clean" },
  { label: "断开全部连接", key: "disconnect" },
  { label: "清空全部 Token", key: "clear" },
]);

const handleImportSuccess = () => {
  showImportForm.value = false;
  message.success("Token 已添加");
};

const statusType = (tokenId) => {
  const status = tokenStore.getWebSocketStatus(tokenId);
  if (status === "connected") return "success";
  if (status === "connecting") return "warning";
  if (status === "error") return "error";
  return "default";
};

const getConnectionStatusText = (tokenId) => {
  const status = tokenStore.getWebSocketStatus(tokenId);
  if (status === "connected") return "已连接";
  if (status === "connecting") return "连接中";
  if (status === "error") return "连接异常";
  return "未连接";
};

const handleDragStart = (index, event) => {
  dragIndex.value = index;
  event.dataTransfer.effectAllowed = "move";
};

const handleDrop = (dropIndex) => {
  if (dragIndex.value === null || dragIndex.value === dropIndex) return;
  const tokens = [...tokenStore.gameTokens];
  const [moved] = tokens.splice(dragIndex.value, 1);
  tokens.splice(dropIndex, 0, moved);
  tokenStore.gameTokens = tokens;
  dragIndex.value = null;
  message.success("Token 顺序已更新");
};

const maskToken = (token) => {
  if (!token) return "";
  if (token.length <= 12) return token;
  return `${token.slice(0, 6)}...${token.slice(-6)}`;
};

const formatTime = (timestamp) => {
  if (!timestamp) return "-";
  return new Date(timestamp).toLocaleString("zh-CN");
};

const goToDashboard = () => {
  router.push("/admin/dashboard");
};

const selectToken = (token, forceReconnect = false) => {
  tokenStore.selectToken(token.id, forceReconnect);
  message.success(`已切换到 ${token.name}`);
};

const startTaskManagement = async (token) => {
  connectingTokens.value.add(token.id);
  try {
    tokenStore.selectToken(token.id, true);
    router.push("/admin/dashboard");
  } finally {
    connectingTokens.value.delete(token.id);
  }
};

const refreshToken = async (token) => {
  if (!token.sourceUrl) {
    message.info("手动导入或 BIN 导入的 Token 请重新上传原始内容");
    return;
  }

  refreshingTokens.value.add(token.id);
  try {
    const response = await fetch(token.sourceUrl, {
      method: "GET",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      throw new Error(`请求失败：${response.status}`);
    }
    const payload = await response.json();
    if (!payload?.token) {
      throw new Error("接口返回中没有 token 字段");
    }
    tokenStore.updateToken(token.id, {
      token: payload.token,
      server: payload.server || token.server,
      wsUrl: payload.wsUrl || token.wsUrl,
      lastUsed: new Date().toISOString(),
    });
    message.success(`${token.name} 已刷新`);
  } catch (error) {
    message.error(error?.message || "刷新失败");
  } finally {
    refreshingTokens.value.delete(token.id);
  }
};

const openEditModal = (token) => {
  editingTokenId.value = token.id;
  editForm.name = token.name || "";
  editForm.token = token.token || "";
  editForm.server = token.server || "";
  editForm.wsUrl = token.wsUrl || "";
  showEditModal.value = true;
};

const saveEdit = async () => {
  try {
    await editFormRef.value?.validate();
  } catch {
    return;
  }
  tokenStore.updateToken(editingTokenId.value, {
    name: editForm.name,
    token: editForm.token,
    server: editForm.server,
    wsUrl: editForm.wsUrl,
  });
  showEditModal.value = false;
  message.success("Token 已更新");
};

const removeToken = (token) => {
  dialog.error({
    title: "删除 Token",
    content: `确定要删除“${token.name}”吗？此操作无法恢复。`,
    positiveText: "删除",
    negativeText: "取消",
    onPositiveClick: () => {
      tokenStore.removeToken(token.id);
      message.success("Token 已删除");
    },
  });
};

const upgradeToken = (token) => {
  dialog.warning({
    title: "升级为长期有效",
    content: `确定要把“${token.name}”升级为长期有效吗？升级后不会再按 24 小时规则清理。`,
    positiveText: "升级",
    negativeText: "取消",
    onPositiveClick: () => {
      const success = tokenStore.upgradeTokenToPermanent(token.id);
      if (success) {
        message.success("已升级为长期有效");
      } else {
        message.warning("当前 Token 已经是长期有效");
      }
    },
  });
};

const disconnectToken = (token) => {
  tokenStore.closeWebSocketConnection(token.id);
  message.success(`${token.name} 已断开连接`);
};

const getTokenActions = token => [
  { label: "选为当前账户", key: "select" },
  { label: "刷新 Token", key: "refresh" },
  { label: "编辑", key: "edit" },
  ...(token.importMethod !== "url" ? [{ label: "升级为长期有效", key: "upgrade" }] : []),
  { label: "断开连接", key: "disconnect" },
  { label: "删除", key: "delete" },
];

const handleTokenAction = async (key, token) => {
  if (key === "select") {
    selectToken(token);
    return;
  }
  if (key === "refresh") {
    await refreshToken(token);
    return;
  }
  if (key === "edit") {
    openEditModal(token);
    return;
  }
  if (key === "upgrade") {
    upgradeToken(token);
    return;
  }
  if (key === "disconnect") {
    disconnectToken(token);
    return;
  }
  if (key === "delete") {
    removeToken(token);
  }
};

const exportTokens = () => {
  const data = tokenStore.exportTokens();
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `tokens_backup_${new Date().toISOString().slice(0, 10)}.json`;
  link.click();
  URL.revokeObjectURL(url);
  message.success("Token 已导出");
};

const importTokenFile = () => {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".json";
  input.onchange = event => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const payload = JSON.parse(String(reader.result || "{}"));
        const result = tokenStore.importTokens(payload);
        if (result.success) {
          message.success(result.message);
        } else {
          message.error(result.message);
        }
      } catch {
        message.error("导入文件格式错误");
      }
    };
    reader.readAsText(file);
  };
  input.click();
};

const refreshAllTokens = async () => {
  const urlTokens = tokenStore.gameTokens.filter(token => token.sourceUrl);
  if (!urlTokens.length) {
    message.warning("没有可自动刷新的 Token");
    return;
  }
  for (const token of urlTokens) {
    await refreshToken(token);
  }
};

const clearAllTokens = () => {
  dialog.error({
    title: "清空全部 Token",
    content: "确定要清空全部 Token 吗？此操作无法恢复。",
    positiveText: "清空",
    negativeText: "取消",
    onPositiveClick: () => {
      tokenStore.clearAllTokens();
      message.success("已清空全部 Token");
    },
  });
};

const handleBulkAction = async (key) => {
  if (key === "refreshAll") return refreshAllTokens();
  if (key === "export") return exportTokens();
  if (key === "import") return importTokenFile();
  if (key === "clean") {
    const count = tokenStore.cleanExpiredTokens();
    return message.success(`已清理 ${count} 个过期 Token`);
  }
  if (key === "disconnect") {
    tokenStore.gameTokens.forEach(token => tokenStore.closeWebSocketConnection(token.id));
    return message.success("已断开全部连接");
  }
  if (key === "clear") return clearAllTokens();
};

const handleUrlParams = async () => {
  if (props.api) {
    try {
      const response = await fetch(props.api, {
        method: "GET",
        headers: { Accept: "application/json" },
      });
      const payload = await response.json();
      if (payload?.token) {
        const result = tokenStore.importBase64Token(props.name || "通过 API 导入的 Token", payload.token, {
          server: props.server || payload.server || "",
          wsUrl: props.wsUrl || payload.wsUrl || "",
          sourceUrl: props.api,
          importMethod: "url",
        });
        if (result?.success) {
          message.success(result.message);
          if (props.auto && result.token) {
            tokenStore.selectToken(result.token.id, true);
            router.push("/admin/dashboard");
          }
        }
      }
    } catch (error) {
      message.error(error?.message || "处理 URL 参数失败");
    }
    return;
  }

  if (props.token) {
    const result = tokenStore.importBase64Token(props.name || "通过 URL 导入的 Token", props.token, {
      server: props.server || "",
      wsUrl: props.wsUrl || "",
      importMethod: "manual",
    });
    if (result?.success) {
      message.success(result.message);
      if (props.auto && result.token) {
        tokenStore.selectToken(result.token.id, true);
        router.push("/admin/dashboard");
      }
    }
  }
};

onMounted(async () => {
  tokenStore.initTokenStore();
  showImportForm.value = !tokenStore.hasTokens;
  if (props.token || props.api) {
    await handleUrlParams();
  }
});
</script>

<style scoped lang="scss">
.token-import-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #f5f7fb 0%, #eef3f8 100%);
  padding: 24px 0 32px;
}

[data-theme="dark"] .token-import-page {
  background: linear-gradient(180deg, #0f172a 0%, #162032 100%);
}

.container {
  max-width: 1320px;
  margin: 0 auto;
  padding: 0 var(--spacing-lg);
}

.page-header {
  margin-bottom: 22px;
}

.header-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 28px 32px;
  border: 1px solid var(--border-light);
  border-radius: 18px;
  background: var(--panel-bg);
  box-shadow: var(--shadow-light);
  color: var(--text-primary);
  text-align: center;
}

.header-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.header-kicker {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--primary-color-light);
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.brand-logo {
  width: 52px;
  height: 52px;
  border-radius: 12px;
  filter: drop-shadow(0 8px 18px rgba(15, 23, 42, 0.16));
}

.header-content h1 {
  margin: 0;
  font-size: clamp(30px, 3vw, 40px);
  color: var(--text-primary);
}

.header-content p {
  max-width: 720px;
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.8;
}

.card-header {
  margin-bottom: 18px;
}

.tokens-section {
  background: var(--panel-bg);
  border: 1px solid var(--border-light);
  border-radius: 18px;
  padding: var(--spacing-xl);
  box-shadow: var(--shadow-light);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 22px;
}

.section-header h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: 24px;
}

.header-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.tokens-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.token-card,
.token-list-card {
  border: 1px solid var(--border-light);
  border-radius: 14px;
  background: linear-gradient(180deg, #ffffff 0%, #f9fbff 100%);
  transition:
    transform var(--transition-fast),
    box-shadow var(--transition-fast),
    border-color var(--transition-fast);
}

.token-card:hover,
.token-list-card:hover {
  transform: translateY(-2px);
  border-color: rgba(64, 158, 255, 0.35);
  box-shadow: var(--shadow-light);
}

.token-card.active,
.token-list-card.active {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 4px rgba(64, 158, 255, 0.12);
}

.token-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.token-name {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.token-display {
  display: grid;
  gap: 8px;
  padding: 12px;
  border-radius: 12px;
  background: var(--bg-tertiary);
}

.token-label {
  color: var(--text-tertiary);
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
}

.token-value {
  font-family: Consolas, "Courier New", monospace;
  word-break: break-all;
  color: var(--text-primary);
}

.token-meta-grid {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.meta-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  color: var(--text-secondary);
}

.meta-label {
  color: var(--text-tertiary);
  font-size: 12px;
}

.card-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 18px;
}

.tokens-list {
  display: grid;
  gap: 12px;
}

.token-list-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.token-list-main,
.token-list-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.empty-state {
  display: grid;
  place-items: center;
  min-height: 400px;
  background: var(--panel-bg);
  border-radius: 18px;
  border: 1px solid var(--border-light);
  box-shadow: var(--shadow-light);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 900px) {
  .section-header,
  .token-list-row {
    flex-direction: column;
    align-items: stretch;
  }

  .card-actions {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .container {
    padding: 0 12px;
  }

  .header-content,
  .tokens-section {
    padding: 20px;
  }

  .header-top {
    flex-direction: column;
    gap: 12px;
  }

  .tokens-grid {
    grid-template-columns: 1fr;
  }
}
</style>
