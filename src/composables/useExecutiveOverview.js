import { computed, onMounted, onUnmounted, ref, watch } from "vue";

import cardFlipApi from "@/api/cardFlip";
import { useAuthStore } from "@/stores/auth";

const formatTime = (value) => {
  const text = String(value || "").trim();
  if (!text)
    return "暂无";
  const parsed = new Date(text);
  return Number.isNaN(parsed.getTime())
    ? text
    : parsed.toLocaleString("zh-CN", { hour12: false });
};

export function useExecutiveOverview(options = {}) {
  const { autoRefreshMs = 30000 } = options;
  const authStore = useAuthStore();

  const loading = ref(false);
  const error = ref("");
  const overview = ref(null);
  const lastLoadedAt = ref("");
  let timerId = 0;

  const isAdmin = computed(() => Boolean(authStore.userInfo?.isAdmin));
  const currentRoleKey = computed(() => {
    const roleKeys = Array.isArray(authStore.userInfo?.roleKeys)
      ? authStore.userInfo.roleKeys
      : [];
    return String(roleKeys[0] || "viewer").toLowerCase() || "viewer";
  });

  const runtime = computed(() => overview.value?.runtime || {});
  const profitability = computed(() => overview.value?.profitability || {});
  const profitCockpit = computed(() => profitability.value?.profit_cockpit || {});
  const deploymentReadiness = computed(() => overview.value?.deployment_readiness || {});
  const validationBaseline = computed(() =>
    deploymentReadiness.value?.validation_baseline || {},
  );
  const alerts = computed(() => overview.value?.alerts || {});

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
    loading,
    error,
    overview,
    lastLoadedAt,
    isAdmin,
    currentRoleKey,
    runtime,
    profitability,
    profitCockpit,
    deploymentReadiness,
    validationBaseline,
    alerts,
    loadOverview,
    formatTime,
  };
}

export default useExecutiveOverview;
