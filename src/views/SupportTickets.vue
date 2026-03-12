<template>
  <div class="support-ticket-page" :class="{ standalone: isStandalonePortal }">
    <section v-if="isStandalonePortal" class="portal-hero">
      <div>
        <p class="portal-eyebrow">问题上报中心</p>
        <h1>登录后可以随时提交工单，管理员会在这里回复你。</h1>
        <p class="portal-copy">
          适合上报软件报错、功能异常、实战盘配置问题和使用疑问。提交后可以持续查看处理进度。
        </p>
      </div>
      <div class="portal-actions">
        <NButton type="primary" @click="showCreateModal = true">提交新工单</NButton>
        <NButton secondary @click="logoutAndBack">退出登录</NButton>
      </div>
    </section>

    <div class="support-content">
      <section class="stats-grid">
        <n-card v-for="card in summaryCards" :key="card.key" class="stat-card" size="small">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value">{{ card.value }}</div>
          <div class="stat-help">{{ card.help }}</div>
        </n-card>
      </section>

      <n-card class="toolbar-card" size="small">
        <div class="toolbar-row">
          <div class="toolbar-copy">
            <h2>{{ canManage ? "工单处理台" : "我的工单" }}</h2>
            <p>{{ canManage ? "查看全部工单、回复用户、调整状态。" : "查看自己提交的问题和管理员回复。" }}</p>
          </div>
          <div class="toolbar-actions">
            <NButton v-if="canCreate" type="primary" @click="showCreateModal = true">新建工单</NButton>
            <NButton @click="loadTickets">刷新列表</NButton>
          </div>
        </div>

        <div class="filter-grid">
          <n-select clearable placeholder="按状态筛选" v-model:value="filters.status" :options="statusOptions"></n-select>
          <n-select clearable placeholder="按分类筛选" v-model:value="filters.category" :options="categoryOptions"></n-select>
          <n-input clearable placeholder="搜索工单号、标题或描述" v-model:value="filters.keyword"></n-input>
          <NButton secondary @click="loadTickets">应用筛选</NButton>
        </div>
      </n-card>

      <n-card class="table-card" size="small">
        <n-data-table
          remote
          :bordered="false"
          :columns="columns"
          :data="tickets"
          :loading="loading"
          :pagination="false"
        ></n-data-table>
        <n-empty v-if="!loading && !tickets.length" class="empty-state" description="当前没有工单记录"></n-empty>
      </n-card>
    </div>

    <n-modal class="ticket-modal" preset="card" title="提交新工单" v-model:show="showCreateModal">
      <n-form label-placement="top">
        <n-form-item label="问题标题">
          <n-input maxlength="80" placeholder="例如：模拟盘打开后一直转圈" v-model:value="createForm.title"></n-input>
        </n-form-item>
        <div class="modal-grid">
          <n-form-item label="问题分类">
            <n-select v-model:value="createForm.category" :options="categoryOptions"></n-select>
          </n-form-item>
          <n-form-item label="紧急程度">
            <n-select v-model:value="createForm.priority" :options="priorityOptions"></n-select>
          </n-form-item>
        </div>
        <n-form-item label="详细描述">
          <n-input
            placeholder="请尽量写清楚：你做了什么、哪里报错、能否复现。"
            type="textarea"
            v-model:value="createForm.description"
            :autosize="{ minRows: 5, maxRows: 8 }"
          ></n-input>
        </n-form-item>
        <div class="modal-actions">
          <NButton @click="showCreateModal = false">取消</NButton>
          <NButton type="primary" :loading="submittingCreate" @click="submitCreate">提交工单</NButton>
        </div>
      </n-form>
    </n-modal>

    <n-drawer placement="right" v-model:show="showDetailDrawer" :width="760">
      <n-drawer-content :title="selectedTicket?.ticketNo || '工单详情'">
        <template v-if="selectedTicket">
          <n-card class="detail-card" size="small">
            <div class="detail-head">
              <div>
                <h3>{{ selectedTicket.title }}</h3>
                <p>{{ selectedTicket.description }}</p>
              </div>
              <div class="detail-tags">
                <NTag :type="statusTagType(selectedTicket.status)">{{ statusLabel(selectedTicket.status) }}</NTag>
                <NTag :type="priorityTagType(selectedTicket.priority)">{{ priorityLabel(selectedTicket.priority) }}</NTag>
                <NTag>{{ categoryLabel(selectedTicket.category) }}</NTag>
              </div>
            </div>
            <div class="detail-meta">
              <span>提交人：{{ selectedTicket.reporter?.nickname || selectedTicket.reporter?.username }}</span>
              <span>最近更新：{{ formatDateTime(selectedTicket.updatedAt) }}</span>
              <span>当前处理人：{{ selectedTicket.adminAssignee || "未指派" }}</span>
            </div>
          </n-card>

          <n-card v-if="canManage" class="detail-card" size="small">
            <div class="admin-grid">
              <n-select v-model:value="manageForm.status" :options="statusOptions"></n-select>
              <n-select v-model:value="manageForm.priority" :options="priorityOptions"></n-select>
              <n-input placeholder="处理人，例如：admin" v-model:value="manageForm.adminAssignee"></n-input>
              <NButton type="primary" :loading="savingTicket" @click="submitUpdate">保存处理状态</NButton>
            </div>
          </n-card>

          <n-card class="detail-card" size="small">
            <template #header>沟通记录</template>
            <div class="message-list">
              <div v-for="item in ticketMessages" :key="item.id" class="message-item" :class="item.authorRole">
                <div class="message-meta">
                  <strong>{{ item.authorName }}</strong>
                  <span>{{ item.authorRole === "admin" ? "管理员" : "用户" }}</span>
                  <span>{{ formatDateTime(item.createdAt) }}</span>
                  <NTag v-if="item.internalOnly" size="small" type="warning">内部备注</NTag>
                </div>
                <div class="message-body">{{ item.message }}</div>
              </div>
            </div>
          </n-card>

          <n-card class="detail-card" size="small">
            <template #header>{{ canManage ? "回复或补充说明" : "继续补充问题" }}</template>
            <n-form label-placement="top">
              <n-form-item label="回复内容">
                <n-input
                  placeholder="输入你要发送给对方的说明。"
                  type="textarea"
                  v-model:value="replyForm.message"
                  :autosize="{ minRows: 4, maxRows: 7 }"
                ></n-input>
              </n-form-item>
              <n-checkbox v-if="canManage" v-model:checked="replyForm.internalOnly">
                仅管理员可见（内部备注）
              </n-checkbox>
              <div class="modal-actions">
                <NButton @click="showDetailDrawer = false">关闭</NButton>
                <NButton type="primary" :loading="sendingReply" @click="submitReply">发送回复</NButton>
              </div>
            </n-form>
          </n-card>
        </template>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<script setup>
import { NButton, NTag, useMessage } from "naive-ui";
import { computed, h, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import {
  createSupportTicket,
  getSupportTicketDetail,
  listSupportTickets,
  replySupportTicket,
  updateSupportTicket,
} from "@/api/support";
import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const router = useRouter();
const message = useMessage();
const authStore = useAuthStore();

const loading = ref(false);
const submittingCreate = ref(false);
const savingTicket = ref(false);
const sendingReply = ref(false);
const showCreateModal = ref(false);
const showDetailDrawer = ref(false);

const tickets = ref([]);
const stats = ref({ total: 0, active: 0, resolved: 0, closed: 0 });
const selectedTicket = ref(null);
const ticketMessages = ref([]);

const filters = reactive({
  status: null,
  category: null,
  keyword: "",
});

const createForm = reactive({
  title: "",
  category: "general",
  priority: "normal",
  description: "",
});

const manageForm = reactive({
  status: "open",
  priority: "normal",
  adminAssignee: "",
});

const replyForm = reactive({
  message: "",
  internalOnly: false,
});

const isStandalonePortal = computed(() => route.path.startsWith("/support"));
const canCreate = computed(() => authStore.hasPermission("support:ticket:create"));
const canManage = computed(() => authStore.hasPermission("support:ticket:manage"));

const categoryOptions = [
  { label: "一般问题", value: "general" },
  { label: "Bug 报错", value: "bug" },
  { label: "账号问题", value: "account" },
  { label: "支付问题", value: "payment" },
  { label: "功能建议", value: "suggestion" },
  { label: "卡片倒卖", value: "cardflip" },
];

const priorityOptions = [
  { label: "低", value: "low" },
  { label: "普通", value: "normal" },
  { label: "高", value: "high" },
  { label: "紧急", value: "urgent" },
];

const statusOptions = [
  { label: "待处理", value: "open" },
  { label: "处理中", value: "in_progress" },
  { label: "等待用户", value: "waiting_user" },
  { label: "已解决", value: "resolved" },
  { label: "已关闭", value: "closed" },
];

const summaryCards = computed(() => [
  {
    key: "total",
    label: "全部工单",
    value: stats.value.total,
    help: canManage.value ? "管理员可查看全部记录" : "你提交过的全部问题",
  },
  {
    key: "active",
    label: "处理中",
    value: stats.value.active,
    help: "包含待处理、处理中、等待用户",
  },
  {
    key: "resolved",
    label: "已解决",
    value: stats.value.resolved,
    help: "已经给出处理结果的工单",
  },
  {
    key: "closed",
    label: "已关闭",
    value: stats.value.closed,
    help: "已经归档，不再继续跟进",
  },
]);

const statusLabel = (value) => statusOptions.find((item) => item.value === value)?.label || value || "-";
const priorityLabel = (value) => priorityOptions.find((item) => item.value === value)?.label || value || "-";
const categoryLabel = (value) => categoryOptions.find((item) => item.value === value)?.label || value || "-";

const statusTagType = (status) => {
  if (status === "resolved" || status === "closed")
    return "success";
  if (status === "in_progress")
    return "info";
  if (status === "waiting_user")
    return "warning";
  return "default";
};

const priorityTagType = (priority) => {
  if (priority === "urgent")
    return "error";
  if (priority === "high")
    return "warning";
  if (priority === "low")
    return "success";
  return "default";
};

const formatDateTime = (value) => {
  if (!value)
    return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime()))
    return value;
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
};

const openDetail = async (row) => {
  try {
    const data = await getSupportTicketDetail(row.id, authStore.token);
    selectedTicket.value = data.ticket;
    ticketMessages.value = data.messages || [];
    manageForm.status = data.ticket.status;
    manageForm.priority = data.ticket.priority;
    manageForm.adminAssignee = data.ticket.adminAssignee || "";
    replyForm.message = "";
    replyForm.internalOnly = false;
    showDetailDrawer.value = true;
  } catch (error) {
    message.error(error instanceof Error ? error.message : "工单详情加载失败");
  }
};

const columns = computed(() => {
  const base = [
    { title: "工单号", key: "ticketNo", width: 150 },
    { title: "标题", key: "title", ellipsis: { tooltip: true }, minWidth: 220 },
    {
      title: "状态",
      key: "status",
      width: 120,
      render: (row) => h(NTag, { type: statusTagType(row.status) }, { default: () => statusLabel(row.status) }),
    },
    {
      title: "紧急程度",
      key: "priority",
      width: 100,
      render: (row) => h(NTag, { type: priorityTagType(row.priority) }, { default: () => priorityLabel(row.priority) }),
    },
    {
      title: "分类",
      key: "category",
      width: 120,
      render: (row) => categoryLabel(row.category),
    },
  ];

  if (canManage.value) {
    base.push({
      title: "提交人",
      key: "reporter",
      width: 140,
      render: (row) => row.reporter?.nickname || row.reporter?.username || "-",
    });
  }

  base.push(
    {
      title: "最近更新",
      key: "updatedAt",
      width: 170,
      render: (row) => formatDateTime(row.updatedAt),
    },
    {
      title: "操作",
      key: "actions",
      width: 120,
      render: (row) =>
        h(
          NButton,
          {
            size: "small",
            type: "primary",
            tertiary: true,
            onClick: () => openDetail(row),
          },
          { default: () => (canManage.value ? "处理" : "查看") },
        ),
    },
  );

  return base;
});

const loadTickets = async () => {
  loading.value = true;
  try {
    const data = await listSupportTickets({
      token: authStore.token,
      status: filters.status,
      category: filters.category,
      keyword: filters.keyword,
      limit: 100,
    });
    tickets.value = data.items || [];
    stats.value = data.stats || { total: 0, active: 0, resolved: 0, closed: 0 };
  } catch (error) {
    message.error(error instanceof Error ? error.message : "工单列表加载失败");
  } finally {
    loading.value = false;
  }
};

const resetCreateForm = () => {
  createForm.title = "";
  createForm.category = "general";
  createForm.priority = "normal";
  createForm.description = "";
};

const submitCreate = async () => {
  submittingCreate.value = true;
  try {
    await createSupportTicket({
      token: authStore.token,
      title: createForm.title,
      category: createForm.category,
      priority: createForm.priority,
      description: createForm.description,
    });
    message.success("工单已提交");
    showCreateModal.value = false;
    resetCreateForm();
    await loadTickets();
  } catch (error) {
    message.error(error instanceof Error ? error.message : "提交工单失败");
  } finally {
    submittingCreate.value = false;
  }
};

const submitReply = async () => {
  if (!selectedTicket.value)
    return;
  sendingReply.value = true;
  try {
    const data = await replySupportTicket(
      selectedTicket.value.id,
      {
        message: replyForm.message,
        internalOnly: replyForm.internalOnly,
      },
      authStore.token,
    );
    selectedTicket.value = data.ticket;
    ticketMessages.value = data.messages || [];
    replyForm.message = "";
    replyForm.internalOnly = false;
    message.success("回复已发送");
    await loadTickets();
  } catch (error) {
    message.error(error instanceof Error ? error.message : "发送回复失败");
  } finally {
    sendingReply.value = false;
  }
};

const submitUpdate = async () => {
  if (!selectedTicket.value)
    return;
  savingTicket.value = true;
  try {
    const data = await updateSupportTicket(
      selectedTicket.value.id,
      {
        status: manageForm.status,
        priority: manageForm.priority,
        adminAssignee: manageForm.adminAssignee,
      },
      authStore.token,
    );
    selectedTicket.value = data.ticket;
    ticketMessages.value = data.messages || [];
    message.success("工单状态已更新");
    await loadTickets();
  } catch (error) {
    message.error(error instanceof Error ? error.message : "保存失败");
  } finally {
    savingTicket.value = false;
  }
};

const logoutAndBack = async () => {
  await authStore.logout();
  router.push("/login");
};

onMounted(async () => {
  await authStore.initAuth();
  if (!authStore.isAuthenticated) {
    router.push("/login");
    return;
  }
  await loadTickets();
});
</script>

<style scoped lang="scss">
.support-ticket-page {
  padding: 24px;

  &.standalone {
    min-height: 100dvh;
    background:
      radial-gradient(circle at top left, rgba(59, 130, 246, 0.08), transparent 22rem),
      linear-gradient(180deg, #f7f9fc 0%, #eef3f9 100%);
  }
}

.portal-hero {
  max-width: 1200px;
  margin: 0 auto 24px;
  padding: 28px 32px;
  border-radius: 24px;
  background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%);
  color: #fff;
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: center;

  h1 {
    margin: 10px 0 12px;
    font-size: 32px;
    line-height: 1.2;
  }
}

.portal-eyebrow {
  margin: 0;
  font-size: 13px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  opacity: 0.78;
}

.portal-copy {
  max-width: 680px;
  margin: 0;
  color: rgba(255, 255, 255, 0.82);
  line-height: 1.7;
}

.portal-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.support-content {
  max-width: 1200px;
  margin: 0 auto;
  display: grid;
  gap: 20px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.stat-card {
  border-radius: 18px;
}

.stat-label {
  color: #64748b;
  font-size: 13px;
}

.stat-value {
  margin-top: 10px;
  font-size: 30px;
  font-weight: 700;
  color: #0f172a;
}

.stat-help {
  margin-top: 8px;
  color: #94a3b8;
  font-size: 12px;
  line-height: 1.6;
}

.toolbar-card,
.table-card,
.detail-card {
  border-radius: 20px;
}

.toolbar-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.toolbar-copy h2 {
  margin: 0;
  font-size: 22px;
}

.toolbar-copy p {
  margin: 8px 0 0;
  color: #64748b;
}

.toolbar-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-grid {
  margin-top: 18px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.empty-state {
  padding: 28px 0 10px;
}

.ticket-modal {
  max-width: 760px;
}

.modal-grid,
.admin-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.admin-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  align-items: center;
}

.modal-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.detail-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.detail-head h3 {
  margin: 0 0 8px;
}

.detail-head p {
  margin: 0;
  color: #475569;
  line-height: 1.7;
}

.detail-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.detail-meta {
  margin-top: 14px;
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  color: #64748b;
  font-size: 13px;
}

.message-list {
  display: grid;
  gap: 14px;
}

.message-item {
  padding: 14px 16px;
  border-radius: 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;

  &.admin {
    background: #eff6ff;
    border-color: #bfdbfe;
  }
}

.message-meta {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  color: #64748b;
  font-size: 12px;
}

.message-body {
  margin-top: 10px;
  line-height: 1.75;
  color: #0f172a;
  white-space: pre-wrap;
}

@media (max-width: 960px) {
  .stats-grid,
  .filter-grid,
  .admin-grid {
    grid-template-columns: 1fr 1fr;
  }

  .portal-hero,
  .toolbar-row,
  .detail-head {
    flex-direction: column;
  }
}

@media (max-width: 640px) {
  .support-ticket-page {
    padding: 14px;
  }

  .portal-hero {
    padding: 22px 20px;

    h1 {
      font-size: 26px;
    }
  }

  .stats-grid,
  .filter-grid,
  .modal-grid,
  .admin-grid {
    grid-template-columns: 1fr;
  }
}
</style>
