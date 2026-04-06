<template>
  <div class="executive-page">
    <section class="hero">
      <div class="hero-copy">
        <div class="hero-kicker">只读数据视图</div>
        <h1>卡片倒卖总览</h1>
        <p>
          只展示经营结果、风险状态、服务透明度和观测基线。执行参数、调参控件、预设动作和手工处置入口
          已全部收回后台。
        </p>
        <div class="hero-tags">
          <n-tag size="small" :type="roleTagType">{{ roleLabel }}</n-tag>
          <n-tag size="small" :type="cockpitReadyTagType">{{ cockpitReadyLabel }}</n-tag>
          <n-tag size="small" :type="executionLiveTagType">{{ executionLiveLabel }}</n-tag>
          <n-tag size="small" :type="baselineTagType">{{ baselineLabel }}</n-tag>
        </div>
      </div>
      <div class="hero-side">
        <div class="hero-time">最近刷新</div>
        <div class="hero-stamp">{{ generatedAtLabel }}</div>
        <n-button type="primary" :loading="loading" @click="loadData">刷新数据</n-button>
      </div>
    </section>

    <section v-if="headlineAlerts.length" class="headline-list">
      <n-alert
        v-for="item in headlineAlerts"
        :key="item.title"
        :type="item.type"
        :bordered="false"
        show-icon
      >
        <template #header>
          {{ item.title }}
        </template>
        {{ item.message }}
      </n-alert>
    </section>

    <n-alert v-if="errorText" type="error" :show-icon="false" class="error-banner">
      {{ errorText }}
    </n-alert>

    <section class="summary-grid">
      <article v-for="card in summaryCards" :key="card.id" class="summary-card">
        <div class="summary-label">{{ card.label }}</div>
        <div class="summary-value">{{ card.value }}</div>
        <div class="summary-note" :class="card.tone">{{ card.note }}</div>
      </article>
    </section>

    <section class="content-grid">
      <article class="panel">
        <div class="panel-head">
          <div>
            <div class="panel-kicker">经营结果</div>
            <h2>收益与库存</h2>
          </div>
        </div>

        <div class="metric-list">
          <div v-for="item in profitabilityRows" :key="item.label" class="metric-row">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>

        <div class="sub-grid">
          <div class="subpanel">
            <div class="subpanel-title">近 7 天来源贡献</div>
            <div v-if="sourceLeaders.length" class="mini-list">
              <div v-for="item in sourceLeaders" :key="item.name" class="metric-row compact">
                <span>{{ item.name }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>
            <n-empty v-else size="small" description="暂无来源贡献数据"></n-empty>
          </div>
          <div class="subpanel">
            <div class="subpanel-title">近 7 天卖家贡献</div>
            <div v-if="sellerLeaders.length" class="mini-list">
              <div v-for="item in sellerLeaders" :key="item.name" class="metric-row compact">
                <span>{{ item.name }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>
            <n-empty v-else size="small" description="暂无卖家贡献数据"></n-empty>
          </div>
        </div>
      </article>

      <article class="panel">
        <div class="panel-head">
          <div>
            <div class="panel-kicker">服务透明度</div>
            <h2>后台服务状态</h2>
          </div>
        </div>

        <div class="service-list">
          <div v-for="item in serviceRows" :key="item.id" class="service-row">
            <div>
              <strong>{{ item.label }}</strong>
              <div class="muted">{{ item.note }}</div>
            </div>
            <div class="service-side">
              <n-tag size="small" :type="item.type">{{ item.value }}</n-tag>
              <span class="muted">{{ item.time }}</span>
            </div>
          </div>
        </div>

        <div v-if="runtimeReasons.length" class="reason-wrap">
          <span v-for="reason in runtimeReasons" :key="reason" class="reason-pill">{{ reason }}</span>
        </div>
      </article>
    </section>

    <section class="content-grid">
      <article class="panel">
        <div class="panel-head">
          <div>
            <div class="panel-kicker">风险状态</div>
            <h2>当前告警与阻塞</h2>
          </div>
          <span class="muted">{{ alertItems.length }} 条</span>
        </div>

        <div v-if="alertItems.length" class="alert-list">
          <div v-for="item in alertItems" :key="item.alert_key || item.code" class="alert-row">
            <div class="alert-top">
              <strong>{{ item.title || item.code || "未知告警" }}</strong>
              <n-tag size="small" :type="severityTagType(item.effective_severity || item.severity)">
                {{ severityText(item.effective_severity || item.severity) }}
              </n-tag>
            </div>
            <div class="muted">{{ item.target || item.message || "-" }}</div>
            <div class="alert-meta">
              <span>优先级：{{ item.incident_priority || "-" }}</span>
              <span>责任人：{{ item.incident_owner || "-" }}</span>
              <span>通道：{{ item.delivery_lane || "-" }}</span>
              <span>
                SLA：{{ item.sla_breached ? "已超时" : `${item.sla_remaining_minutes || 0} 分钟` }}
              </span>
            </div>
          </div>
        </div>
        <n-empty v-else description="当前没有活动告警"></n-empty>

        <div v-if="blockingReasons.length" class="reason-wrap">
          <span v-for="reason in blockingReasons" :key="reason" class="reason-pill">{{ reason }}</span>
        </div>
      </article>

      <article class="panel">
        <div class="panel-head">
          <div>
            <div class="panel-kicker">观测期</div>
            <h2>验证基线</h2>
          </div>
        </div>

        <div class="metric-list">
          <div class="metric-row">
            <span>基线状态</span>
            <strong>{{ baselineSummary.status }}</strong>
          </div>
          <div class="metric-row">
            <span>可调参</span>
            <strong>{{ baselineSummary.readyForTune }}</strong>
          </div>
          <div class="metric-row">
            <span>可扩量</span>
            <strong>{{ baselineSummary.readyForScale }}</strong>
          </div>
          <div class="metric-row">
            <span>方向</span>
            <strong>{{ baselineSummary.direction }}</strong>
          </div>
          <div class="metric-row">
            <span>最近建议</span>
            <strong>{{ baselineSummary.recommendation }}</strong>
          </div>
        </div>

        <div class="sub-grid">
          <div class="subpanel">
            <div class="subpanel-title">最近验证批次</div>
            <div v-if="recentBatches.length" class="mini-list">
              <div v-for="batch in recentBatches" :key="batch.id" class="metric-row compact">
                <span>{{ batch.name || `批次 #${batch.id}` }}</span>
                <strong>{{ batch.status || "-" }}</strong>
              </div>
            </div>
            <n-empty v-else size="small" description="暂无前向验证批次"></n-empty>
          </div>
          <div class="subpanel">
            <div class="subpanel-title">基线阻塞项</div>
            <div v-if="baselineBlockingCodes.length" class="reason-wrap compact-wrap">
              <span v-for="code in baselineBlockingCodes" :key="code" class="reason-pill">{{ code }}</span>
            </div>
            <n-empty v-else size="small" description="暂无阻塞项"></n-empty>
          </div>
        </div>
      </article>
    </section>

    <section class="content-grid">
      <article class="panel">
        <div class="panel-head">
          <div>
            <div class="panel-kicker">质量信号</div>
            <h2>数据完整性与启动检查</h2>
          </div>
        </div>

        <div class="metric-list">
          <div class="metric-row">
            <span>数据完整性</span>
            <strong>{{ integrityStatusText }}</strong>
          </div>
          <div class="metric-row">
            <span>唯一索引</span>
            <strong>{{ uniqueIndexText }}</strong>
          </div>
          <div class="metric-row">
            <span>重复机会单</span>
            <strong>{{ duplicateTradeText }}</strong>
          </div>
          <div class="metric-row">
            <span>启动检查</span>
            <strong>{{ startupStatusText }}</strong>
          </div>
        </div>

        <div v-if="startupCheckCodes.length" class="reason-wrap">
          <span v-for="item in startupCheckCodes" :key="item" class="reason-pill">{{ item }}</span>
        </div>
      </article>

      <article class="panel">
        <div class="panel-head">
          <div>
            <div class="panel-kicker">策略护栏</div>
            <h2>单账号保守模式</h2>
          </div>
        </div>

        <div class="metric-list">
          <div class="metric-row">
            <span>运行模式</span>
            <strong>{{ operatingModeText }}</strong>
          </div>
          <div class="metric-row">
            <span>策略档位</span>
            <strong>{{ strategyProfileText }}</strong>
          </div>
          <div class="metric-row">
            <span>护栏对齐</span>
            <strong>{{ guardrailAlignedText }}</strong>
          </div>
          <div class="metric-row">
            <span>利润保护</span>
            <strong>{{ profitProtectionText }}</strong>
          </div>
        </div>

        <div v-if="guardrailCodes.length" class="reason-wrap">
          <span v-for="item in guardrailCodes" :key="item" class="reason-pill">{{ item }}</span>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import { computed } from "vue";

import useCardFlipOpsPage from "@/views/card-flip-ops/useCardFlipOpsPage";

const page = useCardFlipOpsPage();

const {
  currentRoleKey,
  loading,
  loadData,
  metrics,
  blockedOpportunities,
  healthStatus,
  automationStatus,
  autotradeStatus,
  autotradeCockpit,
  executionStatus,
  executionRetryServiceStatus,
  startupCheckAlert,
  geminiAlert,
  profitProtectionAlert,
  dataIntegrityAlert,
  guardAlert,
  tuningBroadcast,
  toMoney,
  toPercent,
  shardErrors,
} = page;

const roleTagType = computed(() => {
  if (currentRoleKey.value === "viewer")
    return "warning";
  if (currentRoleKey.value === "ops")
    return "info";
  return "success";
});

const roleLabel = computed(() => {
  if (currentRoleKey.value === "viewer")
    return "只读模式";
  if (currentRoleKey.value === "ops")
    return "运营模式";
  return "管理模式";
});

const formatMoney = (value) => `¥${toMoney(value)}`;
const emptyText = (value, fallback = "-") => {
  const text = String(value || "").trim();
  return text || fallback;
};
const formatTime = (value) => {
  const text = String(value || "").trim();
  if (!text)
    return "暂无记录";
  const parsed = new Date(text);
  return Number.isNaN(parsed.getTime()) ? text : parsed.toLocaleString("zh-CN", { hour12: false });
};

const cockpit = computed(() => autotradeCockpit.value || {});
const profit = computed(() => metrics.value?.profit_cockpit || {});
const today = computed(() => profit.value.today || {});
const last7d = computed(() => profit.value.last_7d || {});
const inventory = computed(() => profit.value.inventory || {});
const validationBaseline = computed(() => autotradeStatus.value?.validation_baseline || {});
const recentBatches = computed(() => {
  const recent = metrics.value?.forward_validation?.recent_batches;
  return Array.isArray(recent) ? recent.slice(0, 5) : [];
});
const alertItems = computed(() => (Array.isArray(cockpit.value.alerts) ? cockpit.value.alerts.slice(0, 8) : []));

const summaryCards = computed(() => [
  {
    id: "pending",
    label: "待审机会",
    value: String(metrics.value?.pending_review_count || 0),
    note: `${metrics.value?.total_trade_count || 0} 笔累计交易`,
    tone: "neutral",
  },
  {
    id: "active",
    label: "进行中交易",
    value: String(metrics.value?.active_trades_count || 0),
    note: `${inventory.value?.listed_trade_count || 0} 笔已挂售`,
    tone: "neutral",
  },
  {
    id: "sold",
    label: "已卖出记录",
    value: String(metrics.value?.sold_count || 0),
    note: `利润命中率 ${toPercent(metrics.value?.profit_hit_rate || 0)}`,
    tone: "positive",
  },
  {
    id: "blocked",
    label: "风控拦截",
    value: String(blockedOpportunities.value?.length || 0),
    note: "等待后台自动处置",
    tone: blockedOpportunities.value?.length ? "warning" : "neutral",
  },
  {
    id: "gross",
    label: "累计毛利",
    value: formatMoney(metrics.value?.gross_profit || 0),
    note: `近 7 天净利 ${formatMoney(last7d.value?.realized_net_profit || 0)}`,
    tone: Number(metrics.value?.gross_profit || 0) > 0 ? "positive" : "neutral",
  },
  {
    id: "capital",
    label: "在途资金",
    value: formatMoney(inventory.value?.deployed_capital || 0),
    note: `预期价差 ${formatMoney(inventory.value?.expected_exit_spread || 0)}`,
    tone: "neutral",
  },
  {
    id: "server",
    label: "服务器状态",
    value: cockpit.value?.ready ? "就绪" : "受限",
    note: `${alertItems.value.length} 条活动告警`,
    tone: cockpit.value?.ready ? "positive" : "warning",
  },
  {
    id: "baseline",
    label: "观测基线",
    value: emptyText(validationBaseline.value?.status, "观察中"),
    note: emptyText(validationBaseline.value?.direction, "暂无方向"),
    tone: validationBaseline.value?.ready ? "positive" : "warning",
  },
]);

const profitabilityRows = computed(() => [
  { label: "今日净利", value: formatMoney(today.value?.realized_net_profit || 0) },
  { label: "近 7 天净利", value: formatMoney(last7d.value?.realized_net_profit || 0) },
  { label: "平均已实现 ROI", value: toPercent(metrics.value?.avg_realized_roi || 0) },
  { label: "平均持有天数", value: `${Number(metrics.value?.avg_holding_days || 0).toFixed(1)} 天` },
  { label: "中位持有天数", value: `${Number(metrics.value?.median_holding_days || 0).toFixed(1)} 天` },
  { label: "目标退出价值", value: formatMoney(inventory.value?.target_exit_value || 0) },
]);

const sourceLeaders = computed(() =>
  (Array.isArray(profit.value?.source_leaderboard_7d) ? profit.value.source_leaderboard_7d : [])
    .slice(0, 5)
    .map(item => ({
      name: emptyText(item?.source, "未知来源"),
      value: formatMoney(item?.realized_net_profit || 0),
    })),
);

const sellerLeaders = computed(() =>
  (Array.isArray(profit.value?.seller_leaderboard_7d) ? profit.value.seller_leaderboard_7d : [])
    .slice(0, 5)
    .map(item => ({
      name: emptyText(item?.seller_id, "未知卖家"),
      value: formatMoney(item?.realized_net_profit || 0),
    })),
);

const serviceRows = computed(() => {
  const automation = automationStatus.value || {};
  const monitor = automation.monitor || {};
  const autoTrade = autotradeStatus.value || {};
  const retry = executionRetryServiceStatus.value || {};
  const live = executionStatus.value || {};
  return [
    {
      id: "monitor",
      label: "市场监听",
      value: monitor.is_running ? "运行中" : "已停止",
      note: monitor.circuit_open ? `熔断：${emptyText(monitor.circuit_reason)}` : "后台采集服务",
      time: formatTime(monitor.last_run_at),
      type: monitor.is_running ? "success" : "default",
    },
    {
      id: "autotrade",
      label: "自动交易审批",
      value: autoTrade.running ? "运行中" : "已停止",
      note: `累计审批 ${autoTrade.total_approved || 0} 笔`,
      time: formatTime(autoTrade.last_run_at),
      type: autoTrade.running ? "success" : "default",
    },
    {
      id: "retry",
      label: "执行重试",
      value: retry.running ? "运行中" : "已停止",
      note: `累计重试 ${retry.total_retried || 0} 笔`,
      time: formatTime(retry.last_run_at),
      type: retry.running ? "success" : "default",
    },
    {
      id: "execution",
      label: "实盘执行",
      value: live.live_enabled ? "已启用" : "未启用",
      note: `提供方 ${emptyText(live.provider, "mock")}`,
      time: "后台控制",
      type: live.live_enabled ? "warning" : "default",
    },
  ];
});

const cockpitReadyTagType = computed(() => (cockpit.value?.ready ? "success" : "warning"));
const cockpitReadyLabel = computed(() => (cockpit.value?.ready ? "后台就绪" : "后台受限"));
const executionLiveTagType = computed(() => (executionStatus.value?.live_enabled ? "warning" : "default"));
const executionLiveLabel = computed(() => (executionStatus.value?.live_enabled ? "实盘已启用" : "实盘未启用"));
const baselineTagType = computed(() => (validationBaseline.value?.ready ? "success" : "warning"));
const baselineLabel = computed(() => `基线：${emptyText(validationBaseline.value?.status, "观察中")}`);
const generatedAtLabel = computed(() => formatTime(cockpit.value?.generated_at || autotradeStatus.value?.last_run_at));

const runtimeReasons = computed(() => {
  const reasons = [];
  if (Array.isArray(cockpit.value?.blocking_reasons))
    reasons.push(...cockpit.value.blocking_reasons.filter(Boolean));
  const healthReasons = healthStatus.value?.runtime?.health_reasons || healthStatus.value?.health_reasons;
  if (Array.isArray(healthReasons))
    reasons.push(...healthReasons.filter(Boolean));
  return [...new Set(reasons)].slice(0, 8);
});

const blockingReasons = computed(() => {
  const reasons = [];
  if (Array.isArray(validationBaseline.value?.blocking_codes))
    reasons.push(...validationBaseline.value.blocking_codes);
  if (Array.isArray(validationBaseline.value?.tune_blocking_codes))
    reasons.push(...validationBaseline.value.tune_blocking_codes);
  return [...new Set(reasons)].filter(Boolean).slice(0, 8);
});

const baselineSummary = computed(() => ({
  status: emptyText(validationBaseline.value?.status, "观察中"),
  readyForTune: validationBaseline.value?.ready_for_tune ? "是" : "否",
  readyForScale: validationBaseline.value?.ready_for_scale ? "是" : "否",
  direction: emptyText(validationBaseline.value?.direction, "暂无方向"),
  recommendation: emptyText(validationBaseline.value?.recommendation, "继续观察"),
}));

const integrity = computed(() => healthStatus.value?.data_integrity || {});
const integrityStatusText = computed(() => (integrity.value?.ok ? "正常" : "异常"));
const uniqueIndexText = computed(() => (integrity.value?.trade_opportunity_unique_index ? "已建立" : "缺失"));
const duplicateTradeText = computed(() => `${integrity.value?.duplicate_trade_opportunity_count || 0} 条`);
const startupChecks = computed(() => healthStatus.value?.startup_checks || {});
const startupStatusText = computed(() => emptyText(startupChecks.value?.status, "未知"));
const startupCheckCodes = computed(() =>
  (Array.isArray(startupChecks.value?.items) ? startupChecks.value.items : [])
    .slice(0, 8)
    .map(item => emptyText(item?.code))
    .filter(Boolean),
);

const operatingModeText = computed(() => emptyText(cockpit.value?.operating_state?.state, "标准"));
const strategyProfileText = computed(() => emptyText(autotradeStatus.value?.strategy_profile, "balanced"));
const guardrailAlignedText = computed(() => {
  const profile = healthStatus.value?.operating_state?.operating_profile || {};
  if (profile.aligned === true)
    return "已对齐";
  if (profile.aligned === false)
    return "存在漂移";
  return "未知";
});
const guardrailCodes = computed(() => {
  const profile = healthStatus.value?.operating_state?.operating_profile || {};
  return Array.isArray(profile?.failing_codes) ? profile.failing_codes.slice(0, 8) : [];
});
const profitProtectionText = computed(() => {
  const guard = autotradeStatus.value?.profit_guard || {};
  if (!guard.enabled)
    return "未启用";
  if (guard.blocked)
    return "已拦截";
  return "保护中";
});

const headlineAlerts = computed(() => {
  const items = [];
  if (dataIntegrityAlert.value) {
    items.push({ title: "数据完整性", message: dataIntegrityAlert.value, type: "error" });
  }
  if (guardAlert.value) {
    items.push({ title: "自动化护栏", message: guardAlert.value, type: "warning" });
  }
  if (profitProtectionAlert.value) {
    items.push({ title: "利润保护", message: profitProtectionAlert.value, type: "warning" });
  }
  if (startupCheckAlert.value) {
    items.push({ title: "启动检查", message: startupCheckAlert.value, type: "warning" });
  }
  if (geminiAlert.value) {
    items.push({ title: "AI 能力状态", message: "Gemini 不可用或退化，当前已回退到非 AI 逻辑。", type: "warning" });
  }
  if (tuningBroadcast.value?.content) {
    items.push({
      title: emptyText(tuningBroadcast.value?.title, "策略更新"),
      message: tuningBroadcast.value.content,
      type: tuningBroadcast.value.type || "info",
    });
  }
  return items.slice(0, 3);
});

const errorText = computed(() => {
  return Object.values(shardErrors || {}).find(Boolean) || "";
});

const severityText = (severity) => {
  const text = String(severity || "").toLowerCase();
  if (text === "error")
    return "错误";
  if (text === "warning")
    return "警告";
  if (text === "info")
    return "提示";
  return emptyText(severity, "未知");
};

const severityTagType = (severity) => {
  const text = String(severity || "").toLowerCase();
  if (text === "error")
    return "error";
  if (text === "warning")
    return "warning";
  return "info";
};
</script>

<style scoped lang="scss">
.executive-page {
  display: grid;
  gap: 20px;
  padding: 4px;
}

.hero,
.panel,
.summary-card,
.error-banner {
  border-radius: 18px;
  border: 1px solid var(--border-light);
  background: var(--panel-bg);
  box-shadow: var(--shadow-light);
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) 280px;
  gap: 20px;
  padding: 28px 30px;
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
}

.hero h1,
.panel h2 {
  margin: 14px 0 10px;
  color: #0f172a;
  line-height: 1.1;
}

.hero h1 {
  font-size: clamp(28px, 3vw, 40px);
}

.hero p,
.muted,
.summary-note,
.alert-meta,
.hero-time {
  color: #475569;
}

.hero p {
  max-width: 760px;
  line-height: 1.8;
}

.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}

.hero-side {
  display: grid;
  align-content: start;
  gap: 12px;
  justify-items: end;
}

.hero-stamp {
  color: #0f172a;
  font-size: 18px;
  font-weight: 700;
}

.headline-list {
  display: grid;
  gap: 12px;
}

.error-banner {
  padding: 16px 18px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.summary-card {
  padding: 20px;
  display: grid;
  gap: 8px;
}

.summary-label {
  color: #64748b;
  font-size: 13px;
}

.summary-value {
  color: #0f172a;
  font-size: 32px;
  font-weight: 800;
  line-height: 1;
}

.summary-note.warning {
  color: #c2410c;
}

.summary-note.positive {
  color: #15803d;
}

.content-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.panel {
  padding: 22px 24px;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 18px;
}

.metric-list,
.service-list,
.alert-list,
.mini-list {
  display: grid;
  gap: 12px;
}

.metric-row,
.service-row,
.alert-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #0f172a;
}

.metric-row strong,
.service-row strong,
.alert-row strong {
  color: #0f172a;
}

.metric-row.compact,
.service-row,
.alert-row {
  display: grid;
}

.service-side {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.sub-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
}

.subpanel {
  padding: 16px;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
}

.subpanel-title {
  margin-bottom: 12px;
  color: #0f172a;
  font-size: 14px;
  font-weight: 700;
}

.alert-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.alert-meta,
.reason-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
  font-size: 12px;
}

.reason-pill {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(191, 219, 254, 0.45);
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 600;
}

.compact-wrap {
  margin-top: 0;
}

@media (max-width: 1280px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 980px) {
  .hero,
  .content-grid,
  .sub-grid {
    grid-template-columns: 1fr;
  }

  .hero-side {
    justify-items: start;
  }
}

@media (max-width: 640px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .hero,
  .panel,
  .summary-card {
    padding: 18px;
  }
}
</style>
