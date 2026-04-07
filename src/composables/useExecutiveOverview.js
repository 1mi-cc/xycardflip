import { computed, onMounted, onUnmounted, ref, watch } from "vue";

import cardFlipApi from "@/api/cardFlip";
import { useAuthStore } from "@/stores/auth";

const ALERT_TEXT_MAP = new Map([
  ["autotrade disabled", "自动审批已关闭"],
  ["automatic approvals are turned off.", "现在没有开启自动审批。"],
  ["monitor stopped", "市场监听已停止"],
  ["execution retry stopped", "执行重试已停止"],
  ["no recent signal", "最近没有新的信号。"],
  ["operating state in recovery", "系统正在恢复模式"],
  ["the system is running in recovery mode and expects operator attention.", "系统处在恢复期，建议先盯紧风险和执行情况。"],
  ["execution webhook not ready", "执行通道还没准备好"],
  ["live execution is configured but the webhook provider is not ready.", "已经配置实盘执行，但执行通道当前不可用。"],
  ["portfolio capital exhausted", "可用资金已经打满"],
  ["no remaining capital is available for new approvals.", "当前没有多余资金给新的审批机会。"],
]);

const BASELINE_RECOMMENDATION_PATTERNS = [
  {
    test: /keep the account in observation mode until more sold evidence accumulates/i,
    text: "先继续观察，等成交样本再多一点，再决定要不要放量。",
  },
  {
    test: /increase validation sample size/i,
    text: "验证样本还不够，先把样本做厚一点。",
  },
  {
    test: /maintain current strategy/i,
    text: "先别改策略，按现在的节奏继续观察。",
  },
];

const SIGNAL_LABEL_MAP = {
  closed_validation_batches: "已完成验证批次",
  latest_closed_batch_sample: "最近一批样本数",
  previous_closed_batch_sample: "上一批样本数",
  recent_sold_count: "最近卖出数",
  profit_hit_rate: "利润命中率",
  avg_realized_roi: "平均 ROI",
  latest_closed_batch_hit_rate: "最近一批命中率",
  latest_closed_batch_avg_roi: "最近一批平均 ROI",
  latest_closed_batch_holding_days: "最近一批持有天数",
  latest_closed_batch_net_profit: "最近一批净利润",
  operating_state: "运行状态",
  active_freezes: "冻结数量",
  execution_business_bans: "业务封禁次数",
};

const MODE_LABEL_MAP = new Map([
  ["single-account-local", "单账号观察"],
  ["standard", "标准模式"],
  ["single account local", "单账号观察"],
  ["standard mode", "标准模式"],
  ["single account local mode", "单账号观察"],
  ["single account local", "单账号观察"],
  ["standard", "标准模式"],
  ["Single Account Local", "单账号观察"],
  ["Standard", "标准模式"],
]);

const BASELINE_STATUS_MAP = new Map([
  ["ready", "已就绪"],
  ["observe", "观察中"],
  ["blocked", "已拦截"],
  ["build", "积累样本中"],
  ["已就绪", "已就绪"],
  ["观察中", "观察中"],
]);

const DIRECTION_TEXT_MAP = new Map([
  ["up", "向上"],
  ["down", "转弱"],
  ["flat", "平稳"],
  ["stable", "平稳"],
  ["improving", "向好"],
  ["weakening", "转弱"],
]);

const SERVICE_LABEL_MAP = {
  monitor: "市场监听",
  autotrade: "自动审批",
  execution_retry: "执行重试",
};

const formatTime = (value) => {
  const text = String(value || "").trim();
  if (!text)
    return "暂无";
  const parsed = new Date(text);
  return Number.isNaN(parsed.getTime())
    ? text
    : parsed.toLocaleString("zh-CN", { hour12: false });
};

const translateText = (value) => {
  const text = String(value || "").trim();
  if (!text)
    return "";
  const direct = ALERT_TEXT_MAP.get(text.toLowerCase());
  if (direct)
    return direct;
  return text;
};

const translateRecommendation = (value) => {
  const text = String(value || "").trim();
  if (!text)
    return "继续观察";
  for (const rule of BASELINE_RECOMMENDATION_PATTERNS) {
    if (rule.test.test(text))
      return rule.text;
  }
  return text;
};

const translateModeLabel = (value) => {
  const text = String(value || "").trim();
  if (!text)
    return "标准模式";
  return MODE_LABEL_MAP.get(text) || MODE_LABEL_MAP.get(text.toLowerCase()) || text;
};

const translateBaselineStatus = (value) => {
  const text = String(value || "").trim();
  if (!text)
    return "观察中";
  return BASELINE_STATUS_MAP.get(text) || BASELINE_STATUS_MAP.get(text.toLowerCase()) || text;
};

const translateDirection = (value) => {
  const text = String(value || "").trim();
  if (!text)
    return "暂无";
  return DIRECTION_TEXT_MAP.get(text) || DIRECTION_TEXT_MAP.get(text.toLowerCase()) || text;
};

const humanizeSignal = code =>
  SIGNAL_LABEL_MAP[String(code || "").trim()] || String(code || "").trim();

export function useExecutiveOverview(options = {}) {
  const { autoRefreshMs = 30000 } = options;
  const authStore = useAuthStore();

  const loading = ref(false);
  const error = ref("");
  const overview = ref(null);
  const lastLoadedAt = ref("");
  let timerId = 0;

  const isAdmin = computed(() => Boolean(authStore.userInfo?.isAdmin));
  const runtime = computed(() => overview.value?.runtime || {});
  const profitability = computed(() => overview.value?.profitability || {});
  const profitCockpit = computed(() => profitability.value?.profit_cockpit || {});
  const deploymentReadiness = computed(() => overview.value?.deployment_readiness || {});
  const validationBaseline = computed(
    () => deploymentReadiness.value?.validation_baseline || {},
  );
  const alerts = computed(() => overview.value?.alerts || {});

  const alertItems = computed(() =>
    (Array.isArray(alerts.value?.items) ? alerts.value.items : []).map(item => ({
      ...item,
      title: translateText(item.title || item.code || "系统提示"),
      message: translateText(item.message || item.target || ""),
    })),
  );

  const baselineRecommendation = computed(() =>
    translateRecommendation(validationBaseline.value?.recommendation),
  );

  const baselineStatusText = computed(() =>
    translateBaselineStatus(validationBaseline.value?.status),
  );

  const baselineDirectionText = computed(() =>
    translateDirection(validationBaseline.value?.direction),
  );

  const operatingModeText = computed(() =>
    translateModeLabel(deploymentReadiness.value?.operating_profile?.mode_label),
  );

  const baselineSignals = computed(() => {
    const rawCodes = [
      ...(Array.isArray(validationBaseline.value?.blocking_codes)
        ? validationBaseline.value.blocking_codes
        : []),
      ...(Array.isArray(validationBaseline.value?.tune_blocking_codes)
        ? validationBaseline.value.tune_blocking_codes
        : []),
    ];

    return [...new Set(rawCodes.filter(Boolean))].map(code => ({
      code,
      label: humanizeSignal(code),
    }));
  });

  const serviceSnapshot = computed(() => {
    const services = runtime.value?.services || {};
    return [
      {
        key: "monitor",
        label: SERVICE_LABEL_MAP.monitor,
        running: Boolean(services.monitor?.is_running),
        note: services.monitor?.circuit_open ? "当前已熔断" : "监听状态正常",
      },
      {
        key: "autotrade",
        label: SERVICE_LABEL_MAP.autotrade,
        running: Boolean(services.autotrade?.running),
        note: `累计通过 ${Number(services.autotrade?.total_approved || 0)} 笔`,
      },
      {
        key: "execution_retry",
        label: SERVICE_LABEL_MAP.execution_retry,
        running: Boolean(services.execution_retry?.running),
        note: `累计重试 ${Number(services.execution_retry?.total_retried || 0)} 次`,
      },
    ];
  });

  const loadOverview = async () => {
    if (!isAdmin.value)
      return;
    loading.value = true;
    try {
      overview.value = await cardFlipApi.getAdminTransparencyOverview();
      error.value = "";
      lastLoadedAt.value = formatTime(new Date().toISOString());
    } catch (requestError) {
      error.value = requestError instanceof Error ? requestError.message : "加载总览失败";
    } finally {
      loading.value = false;
    }
  };

  const stopAutoRefresh = () => {
    if (timerId) {
      window.clearInterval(timerId);
      timerId = 0;
    }
  };

  const startAutoRefresh = () => {
    stopAutoRefresh();
    if (!isAdmin.value || autoRefreshMs <= 0)
      return;
    timerId = window.setInterval(() => {
      void loadOverview();
    }, autoRefreshMs);
  };

  onMounted(() => {
    if (isAdmin.value) {
      void loadOverview();
      startAutoRefresh();
    }
  });

  onUnmounted(() => {
    stopAutoRefresh();
  });

  watch(isAdmin, (nextValue) => {
    if (nextValue) {
      void loadOverview();
      startAutoRefresh();
      return;
    }
    stopAutoRefresh();
  });

  return {
    alertItems,
    alerts,
    baselineDirectionText,
    baselineRecommendation,
    baselineSignals,
    baselineStatusText,
    deploymentReadiness,
    error,
    formatTime,
    isAdmin,
    lastLoadedAt,
    loadOverview,
    loading,
    overview,
    operatingModeText,
    profitCockpit,
    profitability,
    runtime,
    serviceSnapshot,
    validationBaseline,
  };
}

export default useExecutiveOverview;
