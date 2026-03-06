<template>
  <div class="dashboard-page">
    <section class="overview-hero">
      <div class="hero-copy">
        <div class="hero-kicker">Workbench</div>
        <h1>欢迎回来，{{ tokenStore.selectedToken?.name || "游戏玩家" }}</h1>
        <p>
          今天是 {{ currentDate }}。这里集中展示账户状态、卡片倒卖入口和最近动作，
          方便你像标准后台一样快速切换工作。
        </p>
        <div class="hero-tags">
          <n-tag size="small" round type="info">
            当前 Token：{{ tokenStore.selectedToken?.name || "未选择" }}
          </n-tag>
          <n-tag size="small" round type="success">
            已导入 {{ tokenStore.gameTokens.length }} 个 Token
          </n-tag>
          <n-tag size="small" round :type="tokenStore.hasTokens ? 'warning' : 'error'">
            {{ tokenStore.hasTokens ? "已准备进入后台" : "请先导入 Token" }}
          </n-tag>
        </div>
      </div>

      <div class="hero-actions">
        <n-button type="primary" size="large" @click="router.push('/admin/card-flip-ops')">
          进入卡片倒卖操作台
        </n-button>
        <n-button size="large" @click="handleManageTokens">管理 Token</n-button>
        <n-button quaternary size="large" @click="router.push('/admin/card-flip/docs')">
          查看使用文档
        </n-button>
      </div>
    </section>

    <section class="summary-grid">
      <article v-for="stat in statistics" :key="stat.id" class="summary-card">
        <div class="summary-icon" :style="{ color: stat.color, background: stat.bg }">
          <component :is="stat.icon" />
        </div>
        <div class="summary-body">
          <span class="summary-label">{{ stat.label }}</span>
          <strong class="summary-value">{{ stat.value }}</strong>
          <span class="summary-foot" :class="stat.changeType">{{ stat.change }}</span>
        </div>
      </article>
    </section>

    <section class="dashboard-grid">
      <article class="panel-card">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">Quick Access</span>
            <h2>高频入口</h2>
          </div>
        </div>
        <div class="quick-grid">
          <button
            v-for="action in quickActions"
            :key="action.id"
            type="button"
            class="quick-card"
            @click="handleQuickAction(action)"
          >
            <div class="quick-icon">
              <component :is="action.icon" />
            </div>
            <div class="quick-copy">
              <h3>{{ action.title }}</h3>
              <p>{{ action.description }}</p>
            </div>
          </button>
        </div>
      </article>

      <article class="panel-card compact-panel">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">Guidance</span>
            <h2>今日建议</h2>
          </div>
        </div>
        <div class="tips-list">
          <div class="tip-item">
            <strong>1.</strong>
            <span>先看模拟盘，再切到操作台调参，最后才考虑实战盘。</span>
          </div>
          <div class="tip-item">
            <strong>2.</strong>
            <span>实战前先确认 Token、代理、自动化开关和风险分阈值都正常。</span>
          </div>
          <div class="tip-item">
            <strong>3.</strong>
            <span>如果你是第一次用这套系统，优先打开“使用文档”按步骤照做。</span>
          </div>
        </div>
      </article>
    </section>

    <section class="panel-card">
      <div class="panel-head">
        <div>
          <span class="panel-kicker">Recent Activity</span>
          <h2>最近活动</h2>
        </div>
        <n-button text type="primary" @click="refreshActivity">刷新</n-button>
      </div>

      <div v-if="recentActivities.length" class="activity-list">
        <div
          v-for="activity in recentActivities"
          :key="activity.id"
          class="activity-item"
        >
          <div class="activity-icon" :class="activity.type">
            <component :is="getActivityIcon(activity.type)" />
          </div>
          <div class="activity-copy">
            <div class="activity-text">{{ activity.message }}</div>
            <div class="activity-time">{{ formatTime(activity.timestamp) }}</div>
          </div>
        </div>
      </div>

      <div v-else class="activity-empty">
        <n-empty description="最近还没有新的后台记录" />
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useMessage } from "naive-ui";
import { useTokenStore } from "@/stores/tokenStore";
import {
  Add,
  CheckmarkCircle,
  Cloud,
  Cube,
  DocumentText,
  Home,
  PersonCircle,
  Settings,
  Time,
  TrendingUp,
} from "@vicons/ionicons5";

const router = useRouter();
const message = useMessage();
const tokenStore = useTokenStore();

const recentActivities = ref([]);

const currentDate = computed(() =>
  new Date().toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  }),
);

const statistics = computed(() => [
  {
    id: 1,
    icon: PersonCircle,
    label: "已导入 Token",
    value: tokenStore.gameTokens.length,
    change: tokenStore.hasTokens ? "账户池已可用" : "等待导入",
    changeType: tokenStore.hasTokens ? "positive" : "warning",
    color: "#409eff",
    bg: "rgba(64, 158, 255, 0.12)",
  },
  {
    id: 2,
    icon: CheckmarkCircle,
    label: "默认工作流",
    value: tokenStore.selectedToken?.name ? "已选定" : "未选择",
    change: tokenStore.selectedToken?.name || "请先指定一个默认 Token",
    changeType: tokenStore.selectedToken?.name ? "positive" : "warning",
    color: "#67c23a",
    bg: "rgba(103, 194, 58, 0.12)",
  },
  {
    id: 3,
    icon: Time,
    label: "模拟优先",
    value: "Dry-Run",
    change: "先验证，再放量",
    changeType: "positive",
    color: "#e6a23c",
    bg: "rgba(230, 162, 60, 0.12)",
  },
  {
    id: 4,
    icon: TrendingUp,
    label: "推荐入口",
    value: "操作台",
    change: "适合集中调参和执行",
    changeType: "positive",
    color: "#f56c6c",
    bg: "rgba(245, 108, 108, 0.12)",
  },
]);

const quickActions = ref([
  {
    id: 1,
    icon: TrendingUp,
    title: "模拟盘",
    description: "先观察最近趋势、执行次数和成功率，不直接上实盘。",
    action: "/admin/card-flip/sim",
  },
  {
    id: 2,
    icon: Cube,
    title: "操作台",
    description: "集中管理 Automation、AutoTrade、ExecutionRetry 和执行日志。",
    action: "/admin/card-flip-ops",
  },
  {
    id: 3,
    icon: DocumentText,
    title: "使用文档",
    description: "给第一次使用的人看的图文说明和从零演示。",
    action: "/admin/card-flip/docs",
  },
  {
    id: 4,
    icon: Add,
    title: "新增 Token",
    description: "打开 Token 管理页，继续导入新的游戏账户。",
    action: "/tokens",
  },
  {
    id: 5,
    icon: Cloud,
    title: "消息与连接测试",
    description: "排查 WebSocket 和测试消息是否正常送达。",
    action: "/admin/message-test",
  },
  {
    id: 6,
    icon: Settings,
    title: "个人设置",
    description: "管理个人资料、权限来源和基础配置。",
    action: "/admin/profile",
  },
]);

const handleManageTokens = () => {
  try {
    router.push("/tokens");
  } catch (error) {
    console.error("导航到 Token 管理失败:", error);
    message.error("打开 Token 管理页失败");
  }
};

const handleQuickAction = action => router.push(action.action);

const refreshActivity = () => {
  recentActivities.value = [
    {
      id: 1,
      type: "success",
      message: "卡片倒卖操作台已就绪，可以继续查看模拟盘和参数设置。",
      timestamp: Date.now() - 20 * 60 * 1000,
    },
    {
      id: 2,
      type: "info",
      message: `当前已导入 ${tokenStore.gameTokens.length} 个 Token，可切换不同账户进入后台。`,
      timestamp: Date.now() - 90 * 60 * 1000,
    },
    {
      id: 3,
      type: "warning",
      message: "若要切到实战盘，先确认 dry-run 相关开关和风险参数已经复核。",
      timestamp: Date.now() - 3 * 60 * 60 * 1000,
    },
  ];
  message.success("活动面板已刷新");
};

const getActivityIcon = (type) => {
  if (type === "success") return CheckmarkCircle;
  if (type === "warning") return Time;
  return Home;
};

const formatTime = (timestamp) => {
  const diff = Date.now() - timestamp;
  const minutes = Math.floor(diff / (1000 * 60));
  const hours = Math.floor(diff / (1000 * 60 * 60));
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));

  if (days > 0) return `${days} 天前`;
  if (hours > 0) return `${hours} 小时前`;
  if (minutes > 0) return `${minutes} 分钟前`;
  return "刚刚";
};

onMounted(() => {
  if (!tokenStore.hasTokens) {
    router.push("/tokens");
    return;
  }
  tokenStore.initTokenStore();
  refreshActivity();
});
</script>

<style scoped lang="scss">
.dashboard-page {
  display: grid;
  gap: 20px;
  min-height: 100%;
  padding: 4px;
}

.overview-hero,
.panel-card,
.summary-card {
  border: 1px solid var(--border-light);
  background: var(--panel-bg);
  box-shadow: var(--shadow-light);
}

.overview-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.8fr);
  gap: 20px;
  padding: 28px 32px;
  border-radius: 18px;
}

.hero-kicker,
.panel-kicker {
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

.hero-copy h1 {
  margin: 16px 0 10px;
  font-size: clamp(28px, 3vw, 40px);
  line-height: 1.08;
  color: var(--text-primary);
}

.hero-copy p {
  max-width: 760px;
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.8;
}

.hero-tags,
.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.hero-tags {
  margin-top: 18px;
}

.hero-actions {
  align-content: start;
  justify-content: flex-end;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.summary-card {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  padding: 20px;
  border-radius: 14px;
}

.summary-icon {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex: 0 0 auto;
}

.summary-body {
  display: grid;
  gap: 6px;
}

.summary-label {
  color: var(--text-tertiary);
  font-size: 13px;
}

.summary-value {
  color: var(--text-primary);
  font-size: 24px;
  line-height: 1.1;
}

.summary-foot {
  color: var(--text-secondary);
  font-size: 13px;
}

.summary-foot.warning {
  color: var(--warning-color);
}

.summary-foot.positive {
  color: var(--success-color);
}

.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.65fr);
  gap: 20px;
}

.panel-card {
  padding: 22px 24px;
  border-radius: 16px;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 18px;
}

.panel-head h2 {
  margin: 10px 0 0;
  color: var(--text-primary);
  font-size: 24px;
  line-height: 1.1;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.quick-card {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding: 16px;
  border: 1px solid var(--border-light);
  border-radius: 14px;
  background: linear-gradient(180deg, #fff 0%, #f9fbff 100%);
  text-align: left;
  transition:
    transform var(--transition-fast),
    box-shadow var(--transition-fast),
    border-color var(--transition-fast);

  &:hover {
    transform: translateY(-2px);
    border-color: rgba(64, 158, 255, 0.35);
    box-shadow: var(--shadow-light);
  }
}

.quick-icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(64, 158, 255, 0.12);
  color: var(--primary-color);
  font-size: 20px;
  flex: 0 0 auto;
}

.quick-copy h3 {
  margin: 0 0 8px;
  color: var(--text-primary);
  font-size: 16px;
}

.quick-copy p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.compact-panel {
  align-self: start;
}

.tips-list {
  display: grid;
  gap: 12px;
}

.tip-item {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 12px;
  padding: 14px 16px;
  border-radius: 14px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  line-height: 1.75;
}

.tip-item strong {
  color: var(--primary-color);
}

.activity-list {
  display: grid;
  gap: 12px;
}

.activity-item {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding: 16px 14px;
  border-radius: 14px;
  background: #fafcff;
  border: 1px solid var(--border-light);
}

.activity-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex: 0 0 auto;
}

.activity-icon.success {
  background: rgba(103, 194, 58, 0.12);
  color: var(--success-color);
}

.activity-icon.warning {
  background: rgba(230, 162, 60, 0.14);
  color: var(--warning-color);
}

.activity-icon.info {
  background: rgba(64, 158, 255, 0.12);
  color: var(--primary-color);
}

.activity-copy {
  display: grid;
  gap: 6px;
}

.activity-text {
  color: var(--text-primary);
  line-height: 1.7;
}

.activity-time {
  color: var(--text-tertiary);
  font-size: 12px;
}

.activity-empty {
  padding: 12px 0;
}

@media (max-width: 1180px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dashboard-grid,
  .overview-hero {
    grid-template-columns: 1fr;
  }

  .hero-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 720px) {
  .quick-grid,
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .overview-hero,
  .panel-card {
    padding: 20px;
  }

  .hero-copy h1 {
    font-size: 28px;
  }
}
</style>
