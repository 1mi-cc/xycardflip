<template>
  <div class="message-tester">
    <div class="header">
      <div>
        <h3>Message Tester</h3>
        <p>用于查看当前连接状态、发送测试消息和检查最近消息历史。</p>
      </div>
      <div class="status">
        <span class="status-label">状态</span>
        <n-tag :type="wsStatusType">{{ wsStatusText }}</n-tag>
      </div>
    </div>

    <div class="panel">
      <div class="panel-row">
        <div class="field">
          <label>当前 Token</label>
          <div class="token-name">{{ selectedTokenName }}</div>
        </div>
        <div class="actions">
          <n-button @click="connectSelectedToken">重连</n-button>
          <n-button :disabled="!canSendMessage" @click="sendHeartbeat">心跳</n-button>
          <n-button :disabled="!canSendMessage" @click="requestRoleInfo">角色信息</n-button>
        </div>
      </div>

      <div class="field">
        <label>命令</label>
        <n-input placeholder="例如 role_getroleinfo" v-model:value="customCmd"></n-input>
      </div>

      <div class="field">
        <label>消息体 JSON</label>
        <n-input
          placeholder="{ }"
          type="textarea"
          v-model:value="customBody"
          :autosize="{ minRows: 4, maxRows: 10 }"
        ></n-input>
      </div>

      <div class="actions">
        <n-button type="primary" :disabled="!canSendMessage || !customCmd.trim()" @click="sendCustomMessage">
          发送自定义消息
        </n-button>
        <n-button :disabled="messageHistory.length === 0" @click="clearHistory">
          清空历史
        </n-button>
      </div>
    </div>

    <div class="panel">
      <div class="history-header">
        <h4>消息历史</h4>
        <span>{{ messageHistory.length }} 条</span>
      </div>

      <div v-if="messageHistory.length === 0" class="empty-state">
        暂无消息
      </div>

      <div v-else class="history-list">
        <div
          v-for="(historyItem, index) in messageHistory"
          :key="`${historyItem.timestamp}-${index}`"
          class="history-item"
        >
          <div class="history-meta">
            <strong>{{ historyItem.type }}</strong>
            <span>{{ formatTime(historyItem.timestamp) }}</span>
          </div>
          <div class="history-cmd">{{ historyItem.cmd || "无命令" }}</div>
          <pre class="history-body">{{ formatPayload(historyItem.data) }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useMessage } from "naive-ui";
import { computed, ref, watch } from "vue";

import { selectedTokenId, useTokenStore } from "@/stores/tokenStore";

const tokenStore = useTokenStore();
const toast = useMessage();

const customCmd = ref("");
const customBody = ref("{}");
const messageHistory = ref([]);
const lastProcessedTimestamp = ref(null);

const currentToken = computed(() => tokenStore.selectedToken || null);
const selectedTokenName = computed(() => currentToken.value?.name || "未选择");
const currentConnection = computed(() => {
  if (!selectedTokenId.value)
    return null;
  return tokenStore.wsConnections?.[selectedTokenId.value] || null;
});

const wsStatus = computed(() => currentConnection.value?.status || "idle");
const wsStatusText = computed(() => {
  switch (wsStatus.value) {
    case "connected":
      return "Connected";
    case "connecting":
      return "Connecting";
    case "error":
      return "Error";
    default:
      return "Idle";
  }
});

const wsStatusType = computed(() => {
  switch (wsStatus.value) {
    case "connected":
      return "success";
    case "connecting":
      return "warning";
    case "error":
      return "error";
    default:
      return "default";
  }
});

const canSendMessage = computed(() => {
  return !!selectedTokenId.value && wsStatus.value === "connected";
});

const addToHistory = (type, data, cmd = null) => {
  messageHistory.value.unshift({
    type,
    timestamp: new Date().toISOString(),
    cmd,
    data,
  });

  if (messageHistory.value.length > 50) {
    messageHistory.value = messageHistory.value.slice(0, 50);
  }
};

const formatTime = (timestamp) => {
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? String(timestamp) : date.toLocaleString();
};

const formatPayload = (payload) => {
  try {
    return JSON.stringify(payload, null, 2);
  } catch {
    return String(payload);
  }
};

const connectSelectedToken = async () => {
  if (!selectedTokenId.value) {
    toast.error("请先选择一个 Token");
    return;
  }

  await tokenStore.selectToken(selectedTokenId.value, true);
  toast.info("已触发重连");
};

const sendHeartbeat = async () => {
  if (!selectedTokenId.value)
    return;

  await tokenStore.sendHeartbeat(selectedTokenId.value);
  addToHistory("sent", {}, "heart_beat");
  toast.success("心跳消息已发送");
};

const requestRoleInfo = async () => {
  if (!selectedTokenId.value)
    return;

  await tokenStore.sendGetRoleInfo(selectedTokenId.value);
  addToHistory("sent", {}, "role_getroleinfo");
  toast.success("角色信息请求已发送");
};

const sendCustomMessage = async () => {
  if (!selectedTokenId.value || !customCmd.value.trim())
    return;

  try {
    const parsedBody = customBody.value.trim() ? JSON.parse(customBody.value) : {};
    await tokenStore.sendMessage(selectedTokenId.value, customCmd.value.trim(), parsedBody);
    addToHistory("sent", parsedBody, customCmd.value.trim());
    toast.success(`已发送 ${customCmd.value.trim()}`);
  } catch (error) {
    toast.error(`发送失败: ${error.message}`);
  }
};

const clearHistory = () => {
  messageHistory.value = [];
  lastProcessedTimestamp.value = null;
  toast.success("消息历史已清空");
};

watch(
  () => currentConnection.value?.lastMessage,
  (lastMessage) => {
    if (!lastMessage)
      return;

    const nextTimestamp = lastMessage.timestamp || lastMessage.time || Date.now();
    if (nextTimestamp === lastProcessedTimestamp.value)
      return;

    lastProcessedTimestamp.value = nextTimestamp;
    addToHistory(
      "received",
      lastMessage.data || lastMessage,
      lastMessage.cmd || lastMessage.data?.cmd || null,
    );
  },
  { deep: true },
);
</script>

<style scoped>
.message-tester {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin: 0 auto;
  max-width: 960px;
}

.header,
.panel {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
  padding: 16px;
}

.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.header h3,
.history-header h4 {
  margin: 0;
}

.header p {
  margin: 8px 0 0;
  color: #6b7280;
}

.status {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-end;
}

.status-label,
.field label,
.history-header span {
  color: #6b7280;
  font-size: 12px;
}

.panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-row {
  display: flex;
  gap: 16px;
  align-items: flex-end;
  justify-content: space-between;
  flex-wrap: wrap;
}

.field {
  display: flex;
  flex: 1 1 280px;
  flex-direction: column;
  gap: 6px;
}

.token-name {
  min-height: 34px;
  display: flex;
  align-items: center;
  padding: 0 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f9fafb;
}

.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.empty-state {
  padding: 24px 0;
  text-align: center;
  color: #6b7280;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 560px;
  overflow: auto;
}

.history-item {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #f9fafb;
  padding: 12px;
}

.history-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.history-meta span,
.history-cmd {
  color: #6b7280;
  font-size: 12px;
}

.history-body {
  margin: 8px 0 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.5;
}
</style>
