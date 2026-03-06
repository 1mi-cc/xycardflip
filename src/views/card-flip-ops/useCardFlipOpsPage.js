import { computed, onMounted, reactive, ref, watch } from "vue";
import { useMessage } from "naive-ui";
import cardFlipApi from "@/api/cardFlip";
import { useAuthStore } from "@/stores/auth";
import useCardFlipOpsData from "@/views/card-flip-ops/useCardFlipOpsData";

export function useCardFlipOpsPage() {
  const message = useMessage();
  const authStore = useAuthStore();
  const recentMessages = new Map();
  const { nextRequestId, isLatestRequest, isBusyError, getErrorMessage } =
    useCardFlipOpsData();

  const notifyDedup = (type, text, dedupMs = 2200) => {
    const key = `${type}:${text}`;
    const now = Date.now();
    const last = recentMessages.get(key) || 0;
    if (now - last < dedupMs) return;
    recentMessages.set(key, now);
    if (type === "success") message.success(text);
    else if (type === "warning") message.warning(text);
    else if (type === "info") message.info(text);
    else message.error(text);
  };

  const currentRoleKey = computed(() => {
    const info = authStore.userInfo || {};
    const roleKeys = Array.isArray(info.roleKeys) ? info.roleKeys : [];
    if (roleKeys.length > 0) {
      return String(roleKeys[0] || "").toLowerCase() || "admin";
    }
    const roles = Array.isArray(info.roles) ? info.roles : [];
    if (roles.length > 0) {
      const firstRole = roles[0];
      if (typeof firstRole === "string") return firstRole.toLowerCase();
      if (firstRole && typeof firstRole === "object") {
        const text = String(firstRole.key || firstRole.name || "")
          .toLowerCase()
          .trim();
        if (text) return text;
      }
    }
    return "admin";
  });

  const isViewer = computed(() => currentRoleKey.value === "viewer");
  const canOperate = computed(() => !isViewer.value);
  const canMaintain = computed(() => currentRoleKey.value === "admin");
  const canBatchApplyPricing = computed(
    () => currentRoleKey.value === "admin" || currentRoleKey.value === "ops",
  );
  const roleTagType = computed(() =>
    isViewer.value
      ? "warning"
      : currentRoleKey.value === "ops"
        ? "info"
        : "success",
  );
  const roleTagText = computed(() => {
    if (currentRoleKey.value === "viewer") return "viewer 只读模式";
    if (currentRoleKey.value === "ops") return "ops 运营模式";
    return "admin 管理模式";
  });
  const isSimulationMode = computed(() => {
    const provider = String(
      executionStatus.value?.provider || "",
    ).toLowerCase();
    const liveEnabled = Boolean(executionStatus.value?.live_enabled);
    return provider === "mock" && !liveEnabled;
  });

  const loading = ref(false);
  const healthLoading = ref(false);
  const overviewLoading = ref(false);
  const listsLoading = ref(false);
  const scanLoading = ref(false);
  const cookieRefreshLoading = ref(false);
  const approving = ref(false);
  const markListedLoading = ref(false);
  const markSoldLoading = ref(false);
  const batchPricingLoading = ref(false);
  const blockedBatchLoading = ref(false);
  const blockedRejectBatchLoading = ref(false);
  const pricingLoadingTradeId = ref(null);
  const pricingAction = ref("");
  const executionLoadingTradeId = ref(null);
  const executionAction = ref("");
  const executionLogsLoading = ref(false);
  const executionRetryLoading = ref(false);
  const autotradeStatusLoading = ref(false);
  const autotradeActionLoading = ref("");
  const autotradeConfigLoading = ref(false);
  const executionConfigLoading = ref(false);
  const automationStatusLoading = ref(false);
  const automationActionLoading = ref("");
  const monitorActionLoading = ref(false);
  const executionRetryServiceStatusLoading = ref(false);
  const executionRetryServiceActionLoading = ref("");
  const executionRetryConfigLoading = ref(false);
  const simulationTrainingLoading = ref(false);
  const activeTab = ref("opportunities");
  const executionLogsInitialized = ref(false);
  const shardErrors = reactive({
    health: "",
    overview: "",
    automation: "",
    autotrade: "",
    executionRetry: "",
    lists: "",
    executionLogs: "",
  });

  const scanLimit = ref(100);
  const blockedRiskThreshold = ref(45);
  const pricingMode = ref("balanced");
  const autotradeRunLimit = ref(0);
  const autotradeRunForce = ref(false);
  const executionLiveConfirmToken = ref("");
  const executionRetryAction = ref("buy");
  const executionRetryLimit = ref(20);
  const executionRetryDryRun = ref(true);
  const executionRetryForce = ref(false);
  const executionRetryServiceRunLimit = ref(0);
  const executionRetryServiceRunForce = ref(false);
  const executionRetryServiceAction = ref("all");
  const executionRetryServiceDryRun = ref(true);
  const executionRetryServiceExecutionForce = ref(false);
  const executionRetryServiceControlInitialized = ref(false);
  const automationIncludeMonitor = ref(true);
  const automationIncludeScan = ref(true);
  const automationIncludeAutotrade = ref(true);
  const automationIncludeExecutionRetry = ref(true);
  const automationForce = ref(false);
  const automationScanLimit = ref(0);
  const automationAutotradeLimit = ref(0);
  const automationExecutionRetryLimit = ref(0);
  const defaultExecutionLogFilters = {
    trade_id: "",
    action: "all",
    provider: "all",
    mode: "all",
    result: "all",
    limit: 200,
  };
  const executionLogFilters = ref({ ...defaultExecutionLogFilters });
  const pricingModeOptions = [
    { label: "平衡模式", value: "balanced" },
    { label: "快速出货", value: "fast_exit" },
    { label: "利润优先", value: "profit_max" },
  ];
  const executionActionOptions = [
    { label: "全部动作", value: "all" },
    { label: "买入", value: "buy" },
    { label: "上架", value: "list" },
    { label: "卖出", value: "sell" },
  ];
  const executionModeOptions = [
    { label: "全部模式", value: "all" },
    { label: "dry-run", value: "dry" },
    { label: "live", value: "live" },
  ];
  const executionResultOptions = [
    { label: "全部结果", value: "all" },
    { label: "成功", value: "success" },
    { label: "失败", value: "failed" },
  ];
  const executionRetryActionOptions = [
    { label: "重试买入", value: "buy" },
    { label: "重试上架", value: "list" },
    { label: "重试卖出", value: "sell" },
    { label: "重试全部", value: "all" },
  ];
  const autotradeStatus = ref({
    enabled: false,
    running: false,
    interval_sec: 0,
    batch_size: 0,
    min_score: 0,
    min_roi: 0,
    max_risk_score: 0,
    total_runs: 0,
    total_approved: 0,
    auto_execute_buy_on_approve: false,
    auto_execute_buy_dry_run: true,
    auto_execute_list_on_buy_success: false,
    auto_execute_list_dry_run: true,
    last_run_at: "",
  });
  const executionStatus = ref({
    provider: "mock",
    live_enabled: false,
    live_confirm_required: false,
    live_max_buy_price: 0,
    live_min_list_profit_ratio: 0,
    live_min_sell_profit_ratio: 0,
  });
  const automationStatus = ref({
    monitor: { is_running: false },
    autotrade: { running: false },
    execution_retry: { running: false },
    all_running: false,
    default_include_monitor: true,
    default_include_scan: true,
    default_include_autotrade: true,
    default_include_execution_retry: true,
    default_scan_limit: 120,
    auto_start_monitor: false,
    auto_start_autotrade: false,
    auto_start_execution_retry: false,
    last_run_at: "",
    last_run_result: {},
  });
  const healthStatus = ref({
    status: "unknown",
    data_integrity: {
      ok: true,
      message: "",
      trade_opportunity_unique_index: false,
      has_duplicate_trade_opportunities: false,
      duplicate_trade_opportunity_count: 0,
      duplicate_trade_opportunity_ids: [],
    },
    automation_guards: {
      automation: { busy: false },
      autotrade: { busy: false },
      execution_retry: { busy: false },
      execution_retry_replay: { busy: false },
    },
  });
  const executionRetryServiceStatus = ref({
    enabled: false,
    running: false,
    interval_sec: 45,
    batch_size: 20,
    action: "all",
    dry_run: true,
    force: false,
    confirm_token_configured: false,
    last_run_at: "",
    last_error: "",
    total_runs: 0,
    total_retried: 0,
    total_succeeded: 0,
    total_failed: 0,
  });

  const opportunities = ref([]);
  const blockedOpportunities = ref([]);
  const activeTrades = ref([]);
  const soldTrades = ref([]);
  const executionLogs = ref([]);
  const metrics = ref({
    pending_review_count: 0,
    active_trades_count: 0,
    sold_count: 0,
    gross_profit: 0,
  });

  const approveModalVisible = ref(false);
  const approveForm = ref({
    opportunity_id: null,
    approved_buy_price: 0,
    approved_by: "owner",
    note: "",
  });

  const markListedModalVisible = ref(false);
  const markListedForm = ref({
    trade_id: null,
    listing_url: "",
    note: "",
  });

  const markSoldModalVisible = ref(false);
  const markSoldForm = ref({
    trade_id: null,
    sold_price: 0,
    note: "",
  });

  const pricingPlanModalVisible = ref(false);
  const pricingPlanPayload = ref(null);
  const batchPricingModalVisible = ref(false);
  const batchPricingResult = ref(null);
  const pricingPreviewMap = ref({});
  const listingModalVisible = ref(false);
  const listingPayload = ref(null);
  const listingLoading = ref(false);

  const toMoney = (value) => Number(value || 0).toFixed(2);
  const toPercent = (value) => `${(Number(value || 0) * 100).toFixed(2)}%`;
  const shortText = (value, max = 90) => {
    const text = String(value || "");
    if (!text) return "-";
    if (text.length <= max) return text;
    return `${text.slice(0, max)}...`;
  };
  const compactJson = (value) => {
    if (value == null || value === "") return "-";
    try {
      if (typeof value === "string") {
        const parsed = JSON.parse(value);
        return shortText(JSON.stringify(parsed), 120);
      }
      return shortText(JSON.stringify(value), 120);
    } catch {
      return shortText(String(value), 120);
    }
  };
  const getModeText = (mode) =>
    ({
      balanced: "平衡模式",
      fast_exit: "快速出货",
      profit_max: "利润优先",
    })[mode] || mode;
  const getActionText = (action) =>
    ({
      set: "设置",
      raise: "上调",
      lower: "下调",
      keep: "保持",
    })[action] || action;
  const getActionType = (action) =>
    ({
      set: "info",
      raise: "success",
      lower: "warning",
      keep: "default",
    })[action] || "default";
  const getUrgencyText = (urgency) =>
    ({
      high: "高",
      medium: "中",
      low: "低",
    })[urgency] || urgency;
  const getUrgencyType = (urgency) =>
    ({
      high: "error",
      medium: "warning",
      low: "success",
    })[urgency] || "default";
  const getPricingPreview = (tradeId) =>
    pricingPreviewMap.value[tradeId] || null;
  const getRiskLevelType = (level) =>
    ({
      high: "error",
      medium: "warning",
      low: "success",
    })[level] || "default";
  const getRiskLevelText = (level) =>
    ({
      high: "高风险",
      medium: "中风险",
      low: "低风险",
    })[level] || "未知";
  const riskReasonTextMap = {
    list_price_above_buy_limit: "当前价格高于买入上限",
    buy_limit_non_positive: "买入上限异常",
    too_few_comparables: "可比成交样本不足",
    low_model_confidence: "模型置信度偏低",
    wide_price_interval: "估价区间过宽",
    insufficient_margin_safety: "安全边际不足",
    seller_listing_concentration: "卖家在架集中",
    suspicious_listing_keywords: "命中可疑关键词",
  };
  const getRiskReasonText = (reason) => riskReasonTextMap[reason] || reason;
  const rawListingJson = computed(() => {
    if (!listingPayload.value) return "";
    const raw = listingPayload.value.raw_json;
    if (raw == null) return "";
    if (typeof raw === "string") return raw;
    try {
      return JSON.stringify(raw, null, 2);
    } catch {
      return String(raw);
    }
  });
  const monitorStopReason = computed(() => {
    const monitor = automationStatus.value?.monitor || {};
    if (monitor.is_running) return "";
    if (monitor.circuit_open && monitor.circuit_reason) {
      return `熔断中：${monitor.circuit_reason}`;
    }
    if (monitor.last_error) {
      return `最近错误：${shortText(monitor.last_error, 120)}`;
    }
    return "未运行（可能未启动或启动被拒绝）";
  });
  const monitorCookieStatusHint = computed(() => {
    const monitor = automationStatus.value?.monitor || {};
    const cookieMeta = monitor.cookie_meta || {};
    const ttl = Number(cookieMeta?.m_h5_tk_ttl_sec);
    if (!Number.isFinite(ttl)) return "";
    const expireAt = String(cookieMeta?.m_h5_tk_expire_at || "");
    const expired = Boolean(cookieMeta?.m_h5_tk_expired);
    if (expired || ttl <= 0) {
      return "Cookie token 已过期，建议先刷新 Cookie，再启动 Monitor。";
    }
    if (ttl <= 3600) {
      const mins = Math.max(1, Math.floor(ttl / 60));
      return `Cookie token 将在约 ${mins} 分钟后过期（UTC ${expireAt || "-"}），建议提前刷新。`;
    }
    return "";
  });
  const dataIntegrityAlert = computed(() => {
    const integrity = healthStatus.value?.data_integrity || {};
    if (integrity.ok) return "";
    const duplicateCount = Number(
      integrity.duplicate_trade_opportunity_count || 0,
    );
    if (duplicateCount > 0) {
      return `检测到 ${duplicateCount} 组重复 trade opportunity，启动时已跳过唯一索引创建，请尽快处理历史重复数据。`;
    }
    return String(integrity.message || "数据一致性存在风险");
  });
  const guardAlert = computed(() => {
    const guards = healthStatus.value?.automation_guards || {};
    const items = Object.values(guards).filter((item) => item && item.busy);
    if (!items.length) return "";
    return "有自动化任务正在执行，重复触发会立即返回 busy。";
  });
  const cachePricingItems = (items = []) => {
    const merged = { ...pricingPreviewMap.value };
    for (const item of items) {
      merged[item.trade_id] = item;
    }
    pricingPreviewMap.value = merged;
  };

  const syncExecutionRetryServiceControls = (status) => {
    if (!status || executionRetryServiceControlInitialized.value) return;
    executionRetryServiceAction.value = status.action || "all";
    executionRetryServiceDryRun.value = Boolean(status.dry_run);
    executionRetryServiceExecutionForce.value = Boolean(status.force);
    executionRetryServiceControlInitialized.value = true;
  };

  const syncAutomationDefaults = (status) => {
    if (!status) return;
    // In mock/dry-run mode, monitor is usually unnecessary and can trigger cooldown warnings.
    automationIncludeMonitor.value = isSimulationMode.value
      ? false
      : Boolean(status.default_include_monitor);
    automationIncludeScan.value = Boolean(status.default_include_scan);
    automationIncludeAutotrade.value = Boolean(
      status.default_include_autotrade,
    );
    automationIncludeExecutionRetry.value = Boolean(
      status.default_include_execution_retry,
    );
    automationScanLimit.value = Number(status.default_scan_limit || 0);
  };

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  const updateAutotradeConfig = async (payload, successText = "") => {
    autotradeConfigLoading.value = true;
    try {
      const status = await cardFlipApi.updateAutotradeConfig(payload);
      autotradeStatus.value = status || autotradeStatus.value;
      if (successText) message.success(successText);
    } catch (error) {
      showActionError("更新 AutoTrade 参数失败", error);
    } finally {
      autotradeConfigLoading.value = false;
    }
  };

  const adjustAutotradeNumber = async (key, delta, min, max) => {
    const current = Number(autotradeStatus.value?.[key] ?? 0);
    const next = clamp(Number((current + delta).toFixed(4)), min, max);
    if (next === current) return;
    await updateAutotradeConfig({ [key]: next });
  };

  const adjustAutotradeRoi = async (delta) => {
    const current = Number(autotradeStatus.value?.min_roi ?? 0);
    const next = clamp(Number((current + delta).toFixed(4)), 0, 3);
    if (next === current) return;
    await updateAutotradeConfig({ min_roi: next });
  };

  const toggleAutotradeFlag = async (key) => {
    await updateAutotradeConfig({
      [key]: !Boolean(autotradeStatus.value?.[key]),
    });
  };

  const updateExecutionConfig = async (payload, successText = "") => {
    executionConfigLoading.value = true;
    try {
      const status = await cardFlipApi.updateExecutionConfig(payload);
      executionStatus.value = status || executionStatus.value;
      if (successText) message.success(successText);
    } catch (error) {
      showActionError("更新执行参数失败", error);
    } finally {
      executionConfigLoading.value = false;
    }
  };

  const setExecutionProvider = async (provider) => {
    if (executionStatus.value?.provider === provider) return;
    await updateExecutionConfig({ provider });
  };

  const toggleExecutionFlag = async (key) => {
    await updateExecutionConfig({
      [key]: !Boolean(executionStatus.value?.[key]),
    });
  };

  const adjustExecutionNumber = async (key, delta, min, max) => {
    const current = Number(executionStatus.value?.[key] ?? 0);
    const next = clamp(Number((current + delta).toFixed(4)), min, max);
    if (next === current) return;
    await updateExecutionConfig({ [key]: next });
  };

  const updateExecutionRetryConfig = async (payload, successText = "") => {
    executionRetryConfigLoading.value = true;
    try {
      const status = await cardFlipApi.updateExecutionRetryConfig(payload);
      executionRetryServiceStatus.value =
        status || executionRetryServiceStatus.value;
      syncExecutionRetryServiceControls(status);
      if (successText) message.success(successText);
    } catch (error) {
      showActionError("更新 ExecutionRetry 参数失败", error);
    } finally {
      executionRetryConfigLoading.value = false;
    }
  };

  const adjustExecutionRetryNumber = async (key, delta, min, max) => {
    const current = Number(executionRetryServiceStatus.value?.[key] ?? 0);
    const next = clamp(Number((current + delta).toFixed(4)), min, max);
    if (next === current) return;
    await updateExecutionRetryConfig({ [key]: next });
  };

  const toggleExecutionRetryFlag = async (key) => {
    await updateExecutionRetryConfig({
      [key]: !Boolean(executionRetryServiceStatus.value?.[key]),
    });
  };

  const setExecutionRetryDefaultAction = async (action) => {
    if (executionRetryServiceStatus.value?.action === action) return;
    await updateExecutionRetryConfig({ action });
  };

  const parseRiskNote = (note) => {
    const parsed = {
      score: null,
      level: "unknown",
      reasons: [],
    };
    if (!note || typeof note !== "string") {
      return parsed;
    }
    const segments = note
      .split(";")
      .map((seg) => seg.trim())
      .filter(Boolean);
    for (const segment of segments) {
      const [rawKey, rawValue] = segment.split("=");
      const key = (rawKey || "").trim();
      const value = (rawValue || "").trim();
      if (key === "risk_score") {
        const num = Number(value);
        parsed.score = Number.isFinite(num) ? num : null;
      } else if (key === "risk_level") {
        parsed.level = value || "unknown";
      } else if (key === "reasons") {
        parsed.reasons =
          value && value !== "none"
            ? value
                .split(",")
                .map((v) => v.trim())
                .filter(Boolean)
            : [];
      }
    }
    return parsed;
  };

  const executionProviderOptions = computed(() => {
    const options = [{ label: "全部通道", value: "all" }];
    const providers = new Set();
    if (executionStatus.value.provider)
      providers.add(String(executionStatus.value.provider));
    for (const row of executionLogs.value) {
      if (row?.provider) providers.add(String(row.provider));
    }
    return options.concat(
      Array.from(providers)
        .sort()
        .map((provider) => ({ label: provider, value: provider })),
    );
  });

  const buildExecutionLogParams = () => {
    const filters = executionLogFilters.value;
    const params = {
      limit: Number(filters.limit) > 0 ? Number(filters.limit) : 200,
    };

    const tradeId = Number(filters.trade_id);
    if (Number.isInteger(tradeId) && tradeId > 0) params.trade_id = tradeId;
    if (filters.action && filters.action !== "all")
      params.action = filters.action;
    if (filters.provider && filters.provider !== "all")
      params.provider = filters.provider;
    if (filters.mode === "dry") params.dry_run = true;
    else if (filters.mode === "live") params.dry_run = false;
    if (filters.result === "success") params.success = true;
    else if (filters.result === "failed") params.success = false;

    return params;
  };

  const showActionError = (prefix, error) => {
    const text = getErrorMessage(error);
    if (isBusyError(error)) {
      message.warning(text);
      return;
    }
    message.error(`${prefix}: ${text}`);
  };

  const loadHealth = async (silent = false) => {
    const requestId = nextRequestId("health");
    if (!silent) healthLoading.value = true;
    try {
      const status = await cardFlipApi.getHealth();
      if (!isLatestRequest("health", requestId)) return status;
      healthStatus.value = status || healthStatus.value;
      shardErrors.health = "";
      return status;
    } catch (error) {
      if (!isLatestRequest("health", requestId)) return null;
      shardErrors.health = getErrorMessage(error);
      if (!silent) showActionError("加载健康状态失败", error);
      return null;
    } finally {
      if (!silent && isLatestRequest("health", requestId)) {
        healthLoading.value = false;
      }
    }
  };
  const loadOverview = async (silent = false) => {
    const requestId = nextRequestId("overview");
    if (!silent) overviewLoading.value = true;
    try {
      const [metricsRes, executionRes] = await Promise.all([
        cardFlipApi.getMetrics(),
        cardFlipApi.getExecutionStatus(),
      ]);
      if (!isLatestRequest("overview", requestId)) {
        return { metricsRes, executionRes };
      }
      metrics.value = metricsRes || metrics.value;
      executionStatus.value = executionRes || executionStatus.value;
      shardErrors.overview = "";
      return { metricsRes, executionRes };
    } catch (error) {
      if (!isLatestRequest("overview", requestId)) return null;
      shardErrors.overview = getErrorMessage(error);
      if (!silent) showActionError("加载总览失败", error);
      return null;
    } finally {
      if (!silent && isLatestRequest("overview", requestId)) {
        overviewLoading.value = false;
      }
    }
  };
  const loadAutomationStatus = async (silent = false) => {
    const requestId = nextRequestId("automation");
    if (!silent) automationStatusLoading.value = true;
    try {
      const status = await cardFlipApi.getAutomationStatus();
      if (!isLatestRequest("automation", requestId)) return status;
      automationStatus.value = status || automationStatus.value;
      syncAutomationDefaults(status);
      shardErrors.automation = "";
      return status;
    } catch (error) {
      if (!isLatestRequest("automation", requestId)) return null;
      shardErrors.automation = getErrorMessage(error);
      if (!silent) showActionError("加载 Automation 状态失败", error);
      return null;
    } finally {
      if (!silent && isLatestRequest("automation", requestId)) {
        automationStatusLoading.value = false;
      }
    }
  };
  const loadAutotradeStatus = async (silent = false) => {
    const requestId = nextRequestId("autotrade");
    if (!silent) autotradeStatusLoading.value = true;
    try {
      const status = await cardFlipApi.getAutotradeStatus();
      if (!isLatestRequest("autotrade", requestId)) return status;
      autotradeStatus.value = status || autotradeStatus.value;
      shardErrors.autotrade = "";
      return status;
    } catch (error) {
      if (!isLatestRequest("autotrade", requestId)) return null;
      shardErrors.autotrade = getErrorMessage(error);
      if (!silent) showActionError("加载 AutoTrade 状态失败", error);
      return null;
    } finally {
      if (!silent && isLatestRequest("autotrade", requestId)) {
        autotradeStatusLoading.value = false;
      }
    }
  };
  const loadExecutionRetryServiceStatus = async (silent = false) => {
    const requestId = nextRequestId("executionRetry");
    if (!silent) executionRetryServiceStatusLoading.value = true;
    try {
      const status = await cardFlipApi.getExecutionRetryStatus();
      if (!isLatestRequest("executionRetry", requestId)) return status;
      executionRetryServiceStatus.value =
        status || executionRetryServiceStatus.value;
      syncExecutionRetryServiceControls(status);
      shardErrors.executionRetry = "";
      return status;
    } catch (error) {
      if (!isLatestRequest("executionRetry", requestId)) return null;
      shardErrors.executionRetry = getErrorMessage(error);
      if (!silent) showActionError("加载 ExecutionRetry 状态失败", error);
      return null;
    } finally {
      if (!silent && isLatestRequest("executionRetry", requestId)) {
        executionRetryServiceStatusLoading.value = false;
      }
    }
  };
  const loadLists = async (silent = false) => {
    const requestId = nextRequestId("lists");
    if (!silent) listsLoading.value = true;
    try {
      const [oppsRes, blockedRes, activeRes, listedRes, soldRes] =
        await Promise.all([
          cardFlipApi.listOpportunities("pending_review", 200),
          cardFlipApi.listOpportunities("blocked_risk", 200),
          cardFlipApi.listTrades("approved_for_buy", 200),
          cardFlipApi.listTrades("listed_for_sale", 200),
          cardFlipApi.listTrades("sold", 200),
        ]);
      if (!isLatestRequest("lists", requestId)) return null;
      opportunities.value = oppsRes.items || [];
      blockedOpportunities.value = (blockedRes.items || []).map((item) => ({
        ...item,
        risk: parseRiskNote(item.risk_note),
      }));
      activeTrades.value = [
        ...(activeRes.items || []),
        ...(listedRes.items || []),
      ];
      soldTrades.value = soldRes.items || [];
      shardErrors.lists = "";
      return {
        oppsRes,
        blockedRes,
        activeRes,
        listedRes,
        soldRes,
      };
    } catch (error) {
      if (!isLatestRequest("lists", requestId)) return null;
      shardErrors.lists = getErrorMessage(error);
      if (!silent) showActionError("加载列表失败", error);
      return null;
    } finally {
      if (!silent && isLatestRequest("lists", requestId)) {
        listsLoading.value = false;
      }
    }
  };
  const loadExecutionLogs = async (silent = false, force = false) => {
    if (
      !force &&
      activeTab.value !== "executionLogs" &&
      !executionLogsInitialized.value
    ) {
      return null;
    }
    const requestId = nextRequestId("executionLogs");
    if (!silent) executionLogsLoading.value = true;
    try {
      const logsRes = await cardFlipApi.listExecutionLogs(
        buildExecutionLogParams(),
      );
      if (!isLatestRequest("executionLogs", requestId)) return logsRes;
      executionLogs.value = logsRes.items || [];
      executionLogsInitialized.value = true;
      shardErrors.executionLogs = "";
      return logsRes;
    } catch (error) {
      if (!isLatestRequest("executionLogs", requestId)) return null;
      shardErrors.executionLogs = getErrorMessage(error);
      if (!silent) showActionError("加载执行日志失败", error);
      return null;
    } finally {
      if (!silent && isLatestRequest("executionLogs", requestId)) {
        executionLogsLoading.value = false;
      }
    }
  };
  const resetExecutionLogFilters = async () => {
    executionLogFilters.value = { ...defaultExecutionLogFilters };
    await loadExecutionLogs(false, true);
  };

  const retryFailedExecutions = async () => {
    if (!executionRetryDryRun.value) {
      if (
        executionStatus.value.live_confirm_required &&
        !executionLiveConfirmToken.value.trim()
      ) {
        message.warning("请先输入实盘确认口令");
        return;
      }
      if (!window.confirm("确认执行失败记录重试（live）？")) return;
    }
    executionRetryLoading.value = true;
    try {
      const action =
        executionRetryAction.value === "all"
          ? null
          : executionRetryAction.value;
      const res = await cardFlipApi.retryFailedExecution(
        action,
        executionRetryLimit.value || 20,
        executionRetryDryRun.value,
        executionRetryForce.value,
        executionLiveConfirmToken.value.trim(),
      );
      message.success(
        `重试完成: ${res.retried || 0} 条, 成功 ${res.succeeded || 0}, 失败 ${res.failed || 0}`,
      );
      await Promise.allSettled([
        loadOverview(true),
        loadExecutionRetryServiceStatus(true),
        loadLists(true),
        loadExecutionLogs(true, true),
      ]);
    } catch (error) {
      showActionError("重试失败记录失败", error);
    } finally {
      executionRetryLoading.value = false;
    }
  };

  const restartMonitorFromAutomation = async () => {
    monitorActionLoading.value = true;
    try {
      const res = await cardFlipApi.startMonitor();
      if (res.started) {
        message.success("Monitor 已启动");
      } else {
        message.warning(`Monitor 未启动: ${res.reason || "unknown"}`);
      }
      await refreshAutomationPanels({ includeLists: false });
    } catch (error) {
      showActionError("Monitor 启动失败", error);
    } finally {
      monitorActionLoading.value = false;
    }
  };

  const resetMonitorCircuit = async () => {
    monitorActionLoading.value = true;
    try {
      const res = await cardFlipApi.resetMonitorCircuit("manual reset from ui");
      if (res.ok) {
        message.success("熔断状态已清空，可重新启动 Monitor");
      } else {
        message.warning("熔断状态清空未生效");
      }
      await refreshAutomationPanels({ includeLists: false });
    } catch (error) {
      showActionError("解熔断失败", error);
    } finally {
      monitorActionLoading.value = false;
    }
  };

  const startAutomation = async () => {
    automationActionLoading.value = "start";
    try {
      const res = await cardFlipApi.startAutomation(
        automationIncludeMonitor.value,
        automationIncludeAutotrade.value,
        automationIncludeExecutionRetry.value,
      );
      const stageReasons = [];
      if (
        automationIncludeMonitor.value &&
        res.monitor?.reason &&
        res.monitor?.reason !== "already running"
      )
        stageReasons.push(`Monitor: ${res.monitor.reason}`);
      if (
        automationIncludeAutotrade.value &&
        res.autotrade?.reason &&
        res.autotrade?.reason !== "already running"
      )
        stageReasons.push(`AutoTrade: ${res.autotrade.reason}`);
      if (
        automationIncludeExecutionRetry.value &&
        res.execution_retry?.reason &&
        res.execution_retry?.reason !== "already running"
      )
        stageReasons.push(`ExecRetry: ${res.execution_retry.reason}`);
      const allAlreadyRunning = Boolean(
        (automationIncludeMonitor.value
          ? res.monitor?.reason === "already running"
          : true) &&
        (automationIncludeAutotrade.value
          ? res.autotrade?.reason === "already running"
          : true) &&
        (automationIncludeExecutionRetry.value
          ? res.execution_retry?.reason === "already running"
          : true),
      );
      if (res.started_any) {
        if (stageReasons.length > 0) {
          message.warning(`Automation 已部分启动: ${stageReasons.join(" | ")}`);
        } else {
          message.success("Automation 一键启动已触发");
        }
      } else if (allAlreadyRunning) {
        message.info("Automation 已在运行");
      } else {
        message.warning(
          stageReasons.length > 0
            ? `Automation 启动未执行: ${stageReasons.join(" | ")}`
            : "Automation 启动未执行，请检查各子模块启用开关",
        );
      }
      await refreshAutomationPanels({ includeLists: false });
    } catch (error) {
      showActionError("Automation 启动失败", error);
    } finally {
      automationActionLoading.value = "";
    }
  };

  const stopAutomation = async () => {
    automationActionLoading.value = "stop";
    try {
      const res = await cardFlipApi.stopAutomation(
        automationIncludeMonitor.value,
        automationIncludeAutotrade.value,
        automationIncludeExecutionRetry.value,
      );
      if (res.stopped_any) {
        message.success("Automation 一键停止已触发");
      } else {
        message.warning("Automation 停止未执行");
      }
      await refreshAutomationPanels({ includeLists: false });
    } catch (error) {
      showActionError("Automation 停止失败", error);
    } finally {
      automationActionLoading.value = "";
    }
  };

  const runAutomationOnce = async () => {
    if (
      automationIncludeExecutionRetry.value &&
      executionStatus.value.live_confirm_required &&
      !executionRetryServiceStatus.value.confirm_token_configured &&
      !executionLiveConfirmToken.value.trim()
    ) {
      message.warning(
        "ExecutionRetry 可能需要实盘确认口令，请先填写口令或配置环境变量",
      );
      return;
    }
    automationActionLoading.value = "run_once";
    try {
      const res = await cardFlipApi.runAutomationOnce({
        includeMonitor: automationIncludeMonitor.value,
        includeScan: automationIncludeScan.value,
        includeAutotrade: automationIncludeAutotrade.value,
        includeExecutionRetry: automationIncludeExecutionRetry.value,
        scanLimit: automationScanLimit.value || 0,
        autotradeLimit: automationAutotradeLimit.value || 0,
        executionRetryLimit: automationExecutionRetryLimit.value || 0,
        force: automationForce.value,
        confirmToken: executionLiveConfirmToken.value.trim(),
      });
      const scanProcessed = Number(res?.scan?.processed || 0);
      const approved = Number(res?.autotrade?.approved || 0);
      const retried = Number(res?.execution_retry?.retried || 0);
      const busyStages = [
        "monitor",
        "scan",
        "autotrade",
        "execution_retry",
        "supabase_sync",
      ].filter((key) => Boolean(res?.[key]?.busy));
      if (busyStages.length) {
        message.warning(
          `Automation 单次完成（部分 busy）: 扫描 ${scanProcessed} 条, 审批 ${approved} 条, 重试 ${retried} 条, busy=${busyStages.join("/")}`,
        );
      } else {
        message.success(
          `Automation 单次完成: 扫描 ${scanProcessed} 条, 审批 ${approved} 条, 重试 ${retried} 条`,
        );
      }
      await refreshAutomationPanels({ includeLists: true, includeLogs: true });
    } catch (error) {
      showActionError("Automation 单次执行失败", error);
    } finally {
      automationActionLoading.value = "";
    }
  };

  const runSimulationTraining = async () => {
    if (!canOperate.value) {
      message.warning("当前角色是只读模式，无法执行模拟训练");
      return;
    }

    simulationTrainingLoading.value = true;
    try {
      await cardFlipApi.updateExecutionConfig({
        provider: "mock",
        live_enabled: false,
        live_confirm_required: false,
      });
      await cardFlipApi.updateAutotradeConfig({
        auto_execute_buy_on_approve: true,
        auto_execute_buy_dry_run: true,
        auto_execute_list_on_buy_success: true,
        auto_execute_list_dry_run: true,
      });
      await cardFlipApi.updateExecutionRetryConfig({
        dry_run: true,
        force: false,
      });
      const seedRes = await cardFlipApi.bootstrapSimulationData(8);
      automationIncludeMonitor.value = false;
      automationIncludeScan.value = false;
      automationIncludeAutotrade.value = true;
      automationIncludeExecutionRetry.value = false;

      const res = await cardFlipApi.runAutomationOnce({
        includeMonitor: false,
        includeScan: false,
        includeAutotrade: true,
        includeExecutionRetry: false,
        autotradeLimit: Math.max(
          1,
          Number(automationAutotradeLimit.value || 30),
        ),
        force: true,
      });

      const approved = Number(res?.autotrade?.approved || 0);
      const considered = Number(res?.autotrade?.considered || 0);
      const buyAttempted = Number(res?.autotrade?.buy_exec_attempted || 0);
      const buySucceeded = Number(res?.autotrade?.buy_exec_succeeded || 0);
      const listAttempted = Number(res?.autotrade?.list_exec_attempted || 0);
      const listSucceeded = Number(res?.autotrade?.list_exec_succeeded || 0);

      if (considered === 0) {
        message.warning(
          `模拟训练未命中候选：待审核 0 条（本次已补样本 ${Number(seedRes?.seeded || 0)} 条），请点击“刷新”后再试`,
        );
      } else {
        message.success(
          `模拟训练完成: 审批 ${approved}/${considered}, 模拟买入 ${buySucceeded}/${buyAttempted}, 模拟上架 ${listSucceeded}/${listAttempted}（补样本 ${Number(seedRes?.seeded || 0)} 条）`,
        );
      }

      await refreshAutomationPanels({ includeLists: true, includeLogs: true });
    } catch (error) {
      showActionError("模拟训练失败", error);
    } finally {
      simulationTrainingLoading.value = false;
    }
  };

  const startExecutionRetryService = async () => {
    executionRetryServiceActionLoading.value = "start";
    try {
      const res = await cardFlipApi.startExecutionRetry();
      if (res.started) {
        message.success("ExecutionRetry 已启动");
      } else {
        message.warning(`ExecutionRetry 未启动: ${res.reason || "unknown"}`);
      }
      await refreshAutomationPanels({ includeLists: false });
    } catch (error) {
      showActionError("启动 ExecutionRetry 失败", error);
    } finally {
      executionRetryServiceActionLoading.value = "";
    }
  };

  const stopExecutionRetryService = async () => {
    executionRetryServiceActionLoading.value = "stop";
    try {
      const res = await cardFlipApi.stopExecutionRetry();
      if (res.stopped) {
        message.success("ExecutionRetry 已停止");
      } else {
        message.warning(`ExecutionRetry 未停止: ${res.reason || "unknown"}`);
      }
      await refreshAutomationPanels({ includeLists: false });
    } catch (error) {
      showActionError("停止 ExecutionRetry 失败", error);
    } finally {
      executionRetryServiceActionLoading.value = "";
    }
  };

  const runExecutionRetryServiceOnce = async () => {
    if (!executionRetryServiceDryRun.value) {
      if (
        executionStatus.value.live_confirm_required &&
        !executionRetryServiceStatus.value.confirm_token_configured &&
        !executionLiveConfirmToken.value.trim()
      ) {
        message.warning(
          "请先输入实盘确认口令，或在环境中配置 EXECUTION_RETRY_CONFIRM_TOKEN",
        );
        return;
      }
      if (!window.confirm("确认执行 ExecutionRetry 单次 live 重试？")) return;
    }
    executionRetryServiceActionLoading.value = "run_once";
    try {
      const res = await cardFlipApi.runExecutionRetryOnce(
        executionRetryServiceRunLimit.value || 0,
        executionRetryServiceRunForce.value,
        executionRetryServiceAction.value,
        executionRetryServiceDryRun.value,
        executionRetryServiceExecutionForce.value,
        executionLiveConfirmToken.value.trim(),
      );
      message.success(
        `ExecutionRetry 单次完成: 重试 ${res.retried || 0} 条, 成功 ${res.succeeded || 0}, 失败 ${res.failed || 0}`,
      );
      await refreshAutomationPanels({ includeLists: true, includeLogs: true });
    } catch (error) {
      showActionError("ExecutionRetry 单次执行失败", error);
    } finally {
      executionRetryServiceActionLoading.value = "";
    }
  };

  const loadData = async () => {
    loading.value = true;
    try {
      await Promise.allSettled([
        loadHealth(true),
        loadOverview(true),
        loadAutomationStatus(true),
        loadAutotradeStatus(true),
        loadExecutionRetryServiceStatus(true),
        loadLists(true),
      ]);
    } catch (error) {
      showActionError("加载失败", error);
    } finally {
      loading.value = false;
    }
  };

  const refreshOverviewAndLists = async ({ includeLogs = false } = {}) => {
    const tasks = [loadOverview(true), loadLists(true)];
    if (
      includeLogs &&
      (activeTab.value === "executionLogs" || executionLogsInitialized.value)
    )
      tasks.push(loadExecutionLogs(true, true));
    await Promise.allSettled(tasks);
  };

  const refreshAutomationPanels = async ({
    includeLists = false,
    includeLogs = false,
  } = {}) => {
    const tasks = [
      loadHealth(true),
      loadAutomationStatus(true),
      loadAutotradeStatus(true),
      loadExecutionRetryServiceStatus(true),
    ];
    if (includeLists) tasks.push(loadOverview(true), loadLists(true));
    if (
      includeLogs &&
      (activeTab.value === "executionLogs" || executionLogsInitialized.value)
    )
      tasks.push(loadExecutionLogs(true, true));
    await Promise.allSettled(tasks);
  };

  const startAutotrade = async () => {
    autotradeActionLoading.value = "start";
    try {
      const res = await cardFlipApi.startAutotrade();
      if (res.started) {
        message.success("AutoTrade 已启动");
      } else {
        message.warning(`启动未执行: ${res.reason || "unknown"}`);
      }
      await refreshAutomationPanels({ includeLists: false });
    } catch (error) {
      showActionError("启动 AutoTrade 失败", error);
    } finally {
      autotradeActionLoading.value = "";
    }
  };

  const stopAutotrade = async () => {
    autotradeActionLoading.value = "stop";
    try {
      const res = await cardFlipApi.stopAutotrade();
      if (res.stopped) {
        message.success("AutoTrade 已停止");
      } else {
        message.warning(`停止未执行 ${res.reason || "unknown"}`);
      }
      await refreshAutomationPanels({ includeLists: false });
    } catch (error) {
      showActionError("停止 AutoTrade 失败", error);
    } finally {
      autotradeActionLoading.value = "";
    }
  };

  const runAutotradeOnce = async () => {
    autotradeActionLoading.value = "run_once";
    try {
      const res = await cardFlipApi.runAutotradeOnce(
        autotradeRunLimit.value || 0,
        autotradeRunForce.value,
      );
      const listExecSummary = res.list_exec_attempted
        ? `, 自动上架 ${res.list_exec_succeeded || 0}/${res.list_exec_attempted || 0}`
        : "";
      const idempotentSummary = res.idempotent_hits
        ? `, 幂等命中 ${res.idempotent_hits} 条`
        : "";
      message.success(
        `AutoTrade 单次执行完成: 审批 ${res.approved || 0} 条, 扫描 ${res.considered || 0} 条${listExecSummary}${idempotentSummary}`,
      );
      await refreshAutomationPanels({ includeLists: true, includeLogs: true });
    } catch (error) {
      showActionError("AutoTrade 单次执行失败", error);
    } finally {
      autotradeActionLoading.value = "";
    }
  };

  const executeTradeBuy = async (trade, dryRun = true) => {
    if (!dryRun) {
      if (
        executionStatus.value.live_confirm_required &&
        !executionLiveConfirmToken.value.trim()
      ) {
        message.warning("请先输入实盘确认口令");
        return;
      }
      if (!window.confirm(`确认对交易 #${trade.trade_id} 触发实盘买入？`))
        return;
    }
    executionLoadingTradeId.value = trade.trade_id;
    executionAction.value = dryRun ? "buy_dry_run" : "buy_live";
    try {
      const res = await cardFlipApi.executeBuy(
        trade.trade_id,
        dryRun,
        false,
        executionLiveConfirmToken.value.trim(),
      );
      if (res.blocked) {
        message.warning(
          `${dryRun ? "模拟买入" : "实盘买入"}被拦截: ${res.error || "blocked by guard"}`,
        );
      } else if (res.success) {
        message.success(
          `${dryRun ? "模拟买入" : "实盘买入"}触发成功: log=${res.log_id}${res.external_id ? `, external=${res.external_id}` : ""}`,
        );
      } else {
        message.error(
          `${dryRun ? "模拟买入" : "实盘买入"}触发失败: ${res.error || "execution failed"}`,
        );
      }
      await refreshOverviewAndLists({ includeLogs: true });
    } catch (error) {
      showActionError("买入执行失败", error);
    } finally {
      executionLoadingTradeId.value = null;
      executionAction.value = "";
    }
  };

  const executeTradeList = async (trade, dryRun = true) => {
    if (!dryRun) {
      if (
        executionStatus.value.live_confirm_required &&
        !executionLiveConfirmToken.value.trim()
      ) {
        message.warning("请先输入实盘确认口令");
        return;
      }
      if (!window.confirm(`确认对交易 #${trade.trade_id} 触发实盘上架？`))
        return;
    }
    executionLoadingTradeId.value = trade.trade_id;
    executionAction.value = dryRun ? "list_dry_run" : "list_live";
    try {
      const res = await cardFlipApi.executeList(
        trade.trade_id,
        dryRun,
        false,
        executionLiveConfirmToken.value.trim(),
        trade.listing_url || "",
        true,
        "ui execution list",
      );
      if (res.blocked) {
        message.warning(
          `${dryRun ? "模拟上架" : "实盘上架"}被拦截: ${res.error || "blocked by guard"}`,
        );
      } else if (res.success) {
        message.success(
          `${dryRun ? "模拟上架" : "实盘上架"}触发成功: log=${res.log_id}${res.external_id ? `, external=${res.external_id}` : ""}`,
        );
      } else {
        message.error(
          `${dryRun ? "模拟上架" : "实盘上架"}触发失败: ${res.error || "execution failed"}`,
        );
      }
      await refreshOverviewAndLists({ includeLogs: true });
    } catch (error) {
      showActionError("上架执行失败", error);
    } finally {
      executionLoadingTradeId.value = null;
      executionAction.value = "";
    }
  };

  const executeTradeSell = async (trade, dryRun = true) => {
    if (!dryRun) {
      if (
        executionStatus.value.live_confirm_required &&
        !executionLiveConfirmToken.value.trim()
      ) {
        message.warning("请先输入实盘确认口令");
        return;
      }
      if (!window.confirm(`确认对交易 #${trade.trade_id} 触发实盘卖出？`))
        return;
    }
    executionLoadingTradeId.value = trade.trade_id;
    executionAction.value = dryRun ? "sell_dry_run" : "sell_live";
    try {
      const res = await cardFlipApi.executeSell(
        trade.trade_id,
        dryRun,
        false,
        executionLiveConfirmToken.value.trim(),
        null,
        true,
        "ui execution sell",
      );
      if (res.blocked) {
        message.warning(
          `${dryRun ? "模拟卖出" : "实盘卖出"}被拦截: ${res.error || "blocked by guard"}`,
        );
      } else if (res.success) {
        message.success(
          `${dryRun ? "模拟卖出" : "实盘卖出"}触发成功: log=${res.log_id}${res.external_id ? `, external=${res.external_id}` : ""}`,
        );
      } else {
        message.error(
          `${dryRun ? "模拟卖出" : "实盘卖出"}触发失败: ${res.error || "execution failed"}`,
        );
      }
      await refreshOverviewAndLists({ includeLogs: true });
    } catch (error) {
      showActionError("卖出执行失败", error);
    } finally {
      executionLoadingTradeId.value = null;
      executionAction.value = "";
    }
  };

  const runScan = async () => {
    scanLoading.value = true;
    try {
      const res = await cardFlipApi.scanOpportunities(scanLimit.value);
      notifyDedup(
        "success",
        `扫描完成: 处理 ${res.processed} 条, 待审核 ${res.pending_review} 条, 风控拦截 ${res.blocked_risk || 0} 条`,
      );
      await refreshOverviewAndLists();
    } catch (error) {
      showActionError("扫描失败", error);
    } finally {
      scanLoading.value = false;
    }
  };

  const refreshCookie = async () => {
    if (
      !window.confirm("将刷新闲鱼 Cookie，过程中会关闭 Chrome/Edge。确认继续？")
    )
      return;
    cookieRefreshLoading.value = true;
    try {
      const res = await cardFlipApi.refreshMonitorCookie(true);
      if (res.success) {
        message.success(
          `Cookie 刷新成功: 长度 ${res.cookie_len || 0}, _m_h5_tk=${res.has_m_h5_tk ? "ok" : "missing"}, _m_h5_tk_enc=${res.has_m_h5_tk_enc ? "ok" : "missing"}`,
        );
        await refreshAutomationPanels({ includeLists: false });
        return;
      }
      message.error(`Cookie 刷新失败: ${res.error || res.stderr || "unknown"}`);
    } catch (error) {
      showActionError("Cookie 刷新失败", error);
    } finally {
      cookieRefreshLoading.value = false;
    }
  };

  const openApprove = (item) => {
    approveForm.value = {
      opportunity_id: item.opportunity_id,
      approved_buy_price: Number(item.list_price || 0),
      approved_by: "owner",
      note: "",
    };
    approveModalVisible.value = true;
  };

  const submitApprove = async () => {
    if (
      !approveForm.value.opportunity_id ||
      approveForm.value.approved_buy_price <= 0
    ) {
      message.warning("请填写有效的审批价格");
      return false;
    }
    approving.value = true;
    try {
      const res = await cardFlipApi.approveTrade(approveForm.value);
      if (res.idempotent) {
        message.warning(
          `机会已存在交易 #${res.existing_trade_id || res.trade_id}，未重复创建`,
        );
      } else {
        message.success(
          `审批成功，交易ID: ${res.trade_id}，建议挂牌价: ￥${toMoney(res.target_sell_price)}`,
        );
      }
      approveModalVisible.value = false;
      await refreshOverviewAndLists();
      return true;
    } catch (error) {
      showActionError("审批失败", error);
      return false;
    } finally {
      approving.value = false;
    }
  };

  const reject = async (item) => {
    try {
      const res = await cardFlipApi.rejectOpportunity(item.opportunity_id);
      const logSuffix = res?.reject_log_id ? `，日志#${res.reject_log_id}` : "";
      message.success(`已忽略机会 #${item.opportunity_id}${logSuffix}`);
      await refreshOverviewAndLists();
    } catch (error) {
      showActionError("忽略失败", error);
    }
  };

  const sendToReview = async (item) => {
    try {
      await cardFlipApi.sendOpportunityToReview(
        item.opportunity_id,
        "manual review from blocked list",
      );
      message.success(`机会 #${item.opportunity_id} 已移入待审核`);
      await refreshOverviewAndLists();
    } catch (error) {
      showActionError("申请复核失败", error);
    }
  };

  const openListing = async (item) => {
    listingLoading.value = true;
    listingModalVisible.value = true;
    try {
      listingPayload.value = await cardFlipApi.getListing(item.listing_row_id);
    } catch (error) {
      showActionError("获取商品信息失败", error);
      listingModalVisible.value = false;
    } finally {
      listingLoading.value = false;
    }
  };

  const sendBlockedBatchToReview = async () => {
    if (!blockedOpportunities.value.length) {
      message.info("当前没有可复核的风控拦截机会");
      return;
    }
    if (
      !window.confirm(
        `确认将风险分 <= ${blockedRiskThreshold.value} 的拦截机会批量移入待审核？`,
      )
    ) {
      return;
    }
    blockedBatchLoading.value = true;
    try {
      const res = await cardFlipApi.sendBlockedToReviewBatch(
        blockedRiskThreshold.value,
        200,
        "manual batch review from blocked list",
      );
      message.success(
        `批量复核完成: 扫描 ${res.scanned} 条, 符合 ${res.eligible} 条, 已移入待审核 ${res.moved} 条`,
      );
      await refreshOverviewAndLists();
    } catch (error) {
      showActionError("批量复核失败", error);
    } finally {
      blockedBatchLoading.value = false;
    }
  };

  const rejectBlockedBatch = async () => {
    if (!blockedOpportunities.value.length) {
      message.info("当前没有可忽略的风控拦截机会");
      return;
    }
    if (
      !window.confirm(
        `确认批量忽略当前 ${blockedOpportunities.value.length} 条风控拦截机会？`,
      )
    ) {
      return;
    }
    blockedRejectBatchLoading.value = true;
    try {
      let totalScanned = 0;
      let totalRejected = 0;
      let totalLogged = 0;
      // Clear in chunks to avoid only rejecting the first page and causing visible backflow.
      for (let i = 0; i < 10; i += 1) {
        const res = await cardFlipApi.rejectBlockedBatch(
          1000,
          "manual batch reject from blocked list",
        );
        totalScanned += Number(res.scanned || 0);
        totalRejected += Number(res.rejected || 0);
        totalLogged += Number(res.logged || 0);
        if (Number(res.rejected || 0) === 0) break;
      }
      message.success(
        `批量忽略完成: 扫描 ${totalScanned} 条, 已忽略 ${totalRejected} 条, 已入库 ${totalLogged} 条`,
      );
      await refreshOverviewAndLists();
    } catch (error) {
      showActionError("批量忽略失败", error);
    } finally {
      blockedRejectBatchLoading.value = false;
    }
  };

  const openMarkListed = (trade) => {
    markListedForm.value = {
      trade_id: trade.trade_id,
      listing_url: trade.listing_url || "",
      note: "",
    };
    markListedModalVisible.value = true;
  };

  const submitMarkListed = async () => {
    if (!markListedForm.value.trade_id || !markListedForm.value.listing_url) {
      message.warning("请填写挂售链接");
      return false;
    }
    markListedLoading.value = true;
    try {
      await cardFlipApi.markTradeListed(markListedForm.value.trade_id, {
        listing_url: markListedForm.value.listing_url,
        note: markListedForm.value.note,
      });
      message.success("已标记为挂售中");
      markListedModalVisible.value = false;
      await refreshOverviewAndLists();
      return true;
    } catch (error) {
      showActionError("更新失败", error);
      return false;
    } finally {
      markListedLoading.value = false;
    }
  };

  const openMarkSold = (trade) => {
    markSoldForm.value = {
      trade_id: trade.trade_id,
      sold_price: Number(trade.target_sell_price || 0),
      note: "",
    };
    markSoldModalVisible.value = true;
  };

  const submitMarkSold = async () => {
    if (!markSoldForm.value.trade_id || markSoldForm.value.sold_price <= 0) {
      message.warning("请填写有效卖出价");
      return false;
    }
    markSoldLoading.value = true;
    try {
      await cardFlipApi.markTradeSold(markSoldForm.value.trade_id, {
        sold_price: markSoldForm.value.sold_price,
        note: markSoldForm.value.note,
      });
      message.success("已标记为卖出");
      markSoldModalVisible.value = false;
      await refreshOverviewAndLists();
      return true;
    } catch (error) {
      showActionError("更新失败", error);
      return false;
    } finally {
      markSoldLoading.value = false;
    }
  };

  const previewTradePricing = async (trade) => {
    pricingLoadingTradeId.value = trade.trade_id;
    pricingAction.value = "preview";
    try {
      const payload = await cardFlipApi.getTradePricingPlan(
        trade.trade_id,
        pricingMode.value,
      );
      pricingPlanPayload.value = payload;
      pricingPlanModalVisible.value = true;
      cachePricingItems([
        {
          trade_id: trade.trade_id,
          title: trade.title,
          mode: payload.mode,
          action: payload.plan.action,
          urgency: payload.plan.urgency,
          current_target_price: payload.plan.current_target_price,
          recommended_price: payload.plan.recommended_price,
          price_floor: payload.plan.price_floor,
          price_ceiling: payload.plan.price_ceiling,
          holding_days: payload.plan.holding_days,
          similar_sales_count: payload.plan.similar_sales_count,
          applied: false,
        },
      ]);
    } catch (error) {
      showActionError("获取定价建议失败", error);
    } finally {
      pricingLoadingTradeId.value = null;
      pricingAction.value = "";
    }
  };

  const applyTradePricing = async (trade) => {
    pricingLoadingTradeId.value = trade.trade_id;
    pricingAction.value = "apply";
    try {
      const res = await cardFlipApi.applyTradePricingPlan(
        trade.trade_id,
        pricingMode.value,
        "ui single apply",
      );
      if (res.applied) {
        message.success(
          `交易 #${trade.trade_id} 已应用建议价 ￥${toMoney(res.recommended_price)}`,
        );
      } else {
        message.info(`交易 #${trade.trade_id} 当前价格已接近建议价，保持不变`);
      }
      await refreshOverviewAndLists();
    } catch (error) {
      showActionError("应用建议价失败", error);
    } finally {
      pricingLoadingTradeId.value = null;
      pricingAction.value = "";
    }
  };

  const previewBatchReprice = async () => {
    batchPricingLoading.value = true;
    try {
      const res = await cardFlipApi.repriceOpenTrades(
        pricingMode.value,
        200,
        false,
        "ui batch preview",
      );
      batchPricingResult.value = res;
      batchPricingModalVisible.value = true;
      cachePricingItems(res.items || []);
      message.success(
        `预览完成: 处理 ${res.processed} 条, 建议调整 ${res.items?.filter((v) => v.action !== "keep").length || 0} 条`,
      );
    } catch (error) {
      showActionError("批量预览失败", error);
    } finally {
      batchPricingLoading.value = false;
    }
  };

  const applyBatchReprice = async () => {
    if (
      !window.confirm(
        "确认按当前模式批量应用建议价格？该操作会更新进行中交易的目标卖价。",
      )
    ) {
      return;
    }
    batchPricingLoading.value = true;
    try {
      const res = await cardFlipApi.repriceOpenTrades(
        pricingMode.value,
        200,
        true,
        "ui batch apply",
      );
      batchPricingResult.value = res;
      batchPricingModalVisible.value = true;
      cachePricingItems(res.items || []);
      message.success(
        `批量应用完成: 处理 ${res.processed} 条, 更新 ${res.updated} 条`,
      );
      await refreshOverviewAndLists();
    } catch (error) {
      showActionError("批量应用失败", error);
    } finally {
      batchPricingLoading.value = false;
    }
  };

  watch(activeTab, async (tab) => {
    if (tab === "executionLogs" && !executionLogsInitialized.value) {
      await loadExecutionLogs(false, true);
    }
  });

  onMounted(loadData);

  return {
    currentRoleKey,
    isViewer,
    canOperate,
    canMaintain,
    canBatchApplyPricing,
    roleTagType,
    roleTagText,
    isSimulationMode,
    loading,
    healthLoading,
    overviewLoading,
    listsLoading,
    scanLoading,
    cookieRefreshLoading,
    approving,
    markListedLoading,
    markSoldLoading,
    batchPricingLoading,
    blockedBatchLoading,
    blockedRejectBatchLoading,
    pricingLoadingTradeId,
    pricingAction,
    executionLoadingTradeId,
    executionAction,
    executionLogsLoading,
    executionRetryLoading,
    autotradeStatusLoading,
    autotradeActionLoading,
    autotradeConfigLoading,
    executionConfigLoading,
    automationStatusLoading,
    automationActionLoading,
    monitorActionLoading,
    executionRetryServiceStatusLoading,
    executionRetryServiceActionLoading,
    executionRetryConfigLoading,
    simulationTrainingLoading,
    activeTab,
    executionLogsInitialized,
    shardErrors,
    scanLimit,
    blockedRiskThreshold,
    pricingMode,
    autotradeRunLimit,
    autotradeRunForce,
    executionLiveConfirmToken,
    executionRetryAction,
    executionRetryLimit,
    executionRetryDryRun,
    executionRetryForce,
    executionRetryServiceRunLimit,
    executionRetryServiceRunForce,
    executionRetryServiceAction,
    executionRetryServiceDryRun,
    executionRetryServiceExecutionForce,
    executionRetryServiceControlInitialized,
    automationIncludeMonitor,
    automationIncludeScan,
    automationIncludeAutotrade,
    automationIncludeExecutionRetry,
    automationForce,
    automationScanLimit,
    automationAutotradeLimit,
    automationExecutionRetryLimit,
    defaultExecutionLogFilters,
    executionLogFilters,
    pricingModeOptions,
    executionActionOptions,
    executionModeOptions,
    executionResultOptions,
    executionRetryActionOptions,
    autotradeStatus,
    executionStatus,
    automationStatus,
    healthStatus,
    executionRetryServiceStatus,
    opportunities,
    blockedOpportunities,
    activeTrades,
    soldTrades,
    executionLogs,
    metrics,
    approveModalVisible,
    approveForm,
    markListedModalVisible,
    markListedForm,
    markSoldModalVisible,
    markSoldForm,
    pricingPlanModalVisible,
    pricingPlanPayload,
    batchPricingModalVisible,
    batchPricingResult,
    pricingPreviewMap,
    listingModalVisible,
    listingPayload,
    listingLoading,
    toMoney,
    toPercent,
    shortText,
    compactJson,
    getModeText,
    getActionText,
    getActionType,
    getUrgencyText,
    getUrgencyType,
    getPricingPreview,
    getRiskLevelType,
    getRiskLevelText,
    riskReasonTextMap,
    getRiskReasonText,
    rawListingJson,
    monitorStopReason,
    monitorCookieStatusHint,
    dataIntegrityAlert,
    guardAlert,
    executionProviderOptions,
    loadHealth,
    loadOverview,
    loadAutomationStatus,
    loadAutotradeStatus,
    loadExecutionRetryServiceStatus,
    loadLists,
    loadExecutionLogs,
    resetExecutionLogFilters,
    retryFailedExecutions,
    restartMonitorFromAutomation,
    resetMonitorCircuit,
    startAutomation,
    stopAutomation,
    runAutomationOnce,
    runSimulationTraining,
    startExecutionRetryService,
    stopExecutionRetryService,
    runExecutionRetryServiceOnce,
    loadData,
    refreshOverviewAndLists,
    refreshAutomationPanels,
    startAutotrade,
    stopAutotrade,
    runAutotradeOnce,
    executeTradeBuy,
    executeTradeList,
    executeTradeSell,
    runScan,
    refreshCookie,
    openApprove,
    submitApprove,
    reject,
    sendToReview,
    openListing,
    sendBlockedBatchToReview,
    rejectBlockedBatch,
    openMarkListed,
    submitMarkListed,
    openMarkSold,
    submitMarkSold,
    previewTradePricing,
    applyTradePricing,
    previewBatchReprice,
    applyBatchReprice,
    adjustAutotradeNumber,
    adjustAutotradeRoi,
    toggleAutotradeFlag,
    setExecutionProvider,
    toggleExecutionFlag,
    adjustExecutionNumber,
    adjustExecutionRetryNumber,
    setExecutionRetryDefaultAction,
    toggleExecutionRetryFlag,
  };
}

export default useCardFlipOpsPage;



