<template>
  <div class="mode-page">
    <section class="mode-hero" :class="{ live: isLiveMode }">
      <div class="hero-main">
        <div class="hero-copy">
          <span class="hero-kicker">{{ isLiveMode ? "Live Board" : "Simulation Board" }}</span>
          <h1>{{ modeTitle }}</h1>
          <p>{{ modeDescription }}</p>
        </div>

        <div class="hero-tags">
          <n-tag size="small" round :type="isLiveMode ? 'error' : 'info'">
            {{ isLiveMode ? "实战执行链路" : "模拟执行链路" }}
          </n-tag>
          <n-tag
            size="small"
            round
            :type="autotradeStatus.running ? 'success' : 'default'"
          >
            {{ autotradeStatus.running ? "审批引擎运行中" : "审批引擎已停止" }}
          </n-tag>
          <n-tag size="small" round type="warning">
            数据窗口：最近 {{ windowDays }} 天
          </n-tag>
        </div>
      </div>

      <div class="hero-actions">
        <n-button type="primary" @click="goToOps">进入操作台</n-button>
        <n-button secondary @click="goToDocs">查看文档</n-button>
        <n-button tertiary :loading="loading" @click="loadData">刷新看板</n-button>
      </div>
    </section>

    <n-alert
      v-if="loadError"
      type="error"
      :show-icon="false"
      class="error-alert"
    >
      {{ loadError }}
    </n-alert>

    <n-spin :show="loading">
      <section class="filter-panel">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">Filters</span>
            <h2>时间窗口与趋势指标</h2>
          </div>
        </div>

        <div class="filter-row">
          <span class="filter-label">时间窗口</span>
          <n-radio-group v-model:value="windowDays" size="small">
            <n-radio-button
              v-for="option in windowOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </n-radio-button>
          </n-radio-group>
        </div>

        <div class="filter-row">
          <span class="filter-label">趋势指标</span>
          <n-checkbox-group v-model:value="selectedMetricKeys">
            <n-space size="small" wrap>
              <n-checkbox
                v-for="option in metricOptions"
                :key="option.key"
                :value="option.key"
              >
                {{ option.label }}
              </n-checkbox>
            </n-space>
          </n-checkbox-group>
        </div>
      </section>

      <section class="kpi-grid">
        <article class="kpi-card">
          <span class="kpi-label">执行总次数</span>
          <strong class="kpi-value">{{ executionSummary.total }}</strong>
        </article>
        <article class="kpi-card">
          <span class="kpi-label">成功率</span>
          <strong class="kpi-value">{{ executionSummary.successRate }}%</strong>
        </article>
        <article class="kpi-card">
          <span class="kpi-label">{{ isLiveMode ? "买入次数" : "模拟买入次数" }}</span>
          <strong class="kpi-value">{{ executionSummary.buyCount }}</strong>
        </article>
        <article class="kpi-card">
          <span class="kpi-label">{{ isLiveMode ? "卖出次数" : "模拟卖出次数" }}</span>
          <strong class="kpi-value">{{ executionSummary.sellCount }}</strong>
        </article>
        <article class="kpi-card">
          <span class="kpi-label">待审核机会</span>
          <strong class="kpi-value">{{ metrics.pending_review_count || 0 }}</strong>
        </article>
        <article class="kpi-card">
          <span class="kpi-label">累计审批</span>
          <strong class="kpi-value">{{ autotradeStatus.total_approved || 0 }}</strong>
        </article>
      </section>

      <section class="trend-grid">
        <article
          v-for="chart in visibleChartCards"
          :key="chart.key"
          class="trend-card"
        >
          <header class="trend-head">
            <div>
              <h3>{{ chart.title }}</h3>
              <p>{{ chart.description }}</p>
            </div>
            <span class="trend-latest">{{ chart.latest }}{{ chart.unit }}</span>
          </header>

          <div
            v-if="chart.hasData"
            class="trend-body"
            @mouseleave="clearActivePoint(chart.key)"
          >
            <svg
              viewBox="0 0 100 36"
              preserveAspectRatio="none"
              class="trend-svg"
            >
              <defs>
                <linearGradient
                  :id="`area-${chart.key}`"
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop
                    offset="0%"
                    :stop-color="chart.gradientStart"
                    stop-opacity="0.35"
                  />
                  <stop
                    offset="100%"
                    :stop-color="chart.gradientEnd"
                    stop-opacity="0.04"
                  />
                </linearGradient>
              </defs>

              <line
                v-for="lineY in [8, 18, 28]"
                :key="`line-${chart.key}-${lineY}`"
                x1="0"
                :y1="lineY"
                x2="100"
                :y2="lineY"
                class="trend-grid-line"
              />

              <polygon
                :points="chart.areaPoints"
                :fill="`url(#area-${chart.key})`"
                class="trend-area"
              />
              <polyline
                :points="chart.linePoints"
                :stroke="chart.color"
                class="trend-line"
              />

              <line
                v-if="activePointForChart(chart.key)"
                :x1="activePointForChart(chart.key).x"
                y1="4"
                :x2="activePointForChart(chart.key).x"
                y2="34"
                class="trend-cursor"
              />
              <circle
                v-if="activePointForChart(chart.key)"
                :cx="activePointForChart(chart.key).x"
                :cy="activePointForChart(chart.key).y"
                r="1.6"
                :fill="chart.color"
                class="trend-point"
              />

              <circle
                v-for="point in chart.points"
                :key="`${chart.key}-${point.index}`"
                :cx="point.x"
                :cy="point.y"
                r="2.8"
                class="trend-hit"
                @mouseenter="setActivePoint(chart.key, point.index)"
              />
            </svg>

            <div
              v-if="activePointForChart(chart.key)"
              class="trend-tooltip"
              :style="{ left: tooltipLeftStyle(activePointForChart(chart.key).x) }"
            >
              <div class="tooltip-date">{{ activePointForChart(chart.key).label }}</div>
              <div class="tooltip-value">
                {{ activePointForChart(chart.key).value }}{{ chart.unit }}
              </div>
            </div>
          </div>

          <div v-else class="trend-empty">
            <n-empty size="small" :description="emptyChartDescription" />
          </div>

          <footer class="trend-foot">
            <span>{{ trendLabels[0] || "-" }}</span>
            <span>{{ trendLabels[trendLabels.length - 1] || "-" }}</span>
          </footer>
        </article>
      </section>
    </n-spin>
  </div>
</template>

<script setup>
import cardFlipApi from "@/api/cardFlip";
import useCardFlipOpsData from "@/views/card-flip-ops/useCardFlipOpsData";
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

const props = defineProps({
  mode: {
    type: String,
    default: "simulation",
  },
});

const router = useRouter();
const { getErrorMessage } = useCardFlipOpsData();
const DASHBOARD_LOG_LIMIT = 500;

const loading = ref(false);
const loadError = ref("");
const executionLogs = ref([]);
const metrics = ref({
  pending_review_count: 0,
});
const autotradeStatus = ref({
  running: false,
  total_approved: 0,
});
const hoverState = ref({
  chartKey: "",
  pointIndex: -1,
});
const windowDays = ref(14);
const selectedMetricKeys = ref([
  "exec-total",
  "exec-success-rate",
  "exec-buy",
  "exec-sell",
]);

const isLiveMode = computed(() => props.mode === "live");
const modeTitle = computed(() =>
  isLiveMode.value ? "卡片倒卖 · 实战盘看板" : "卡片倒卖 · 模拟盘看板",
);
const modeDescription = computed(() =>
  isLiveMode.value
    ? "观察真实执行链路的结果，重点看买入、卖出、审批和成功率是否稳定。"
    : "先在 dry-run 环境里验证策略、节奏和参数，再决定是否切换到实战盘。",
);
const emptyChartDescription = computed(() =>
  isLiveMode.value ? "最近窗口暂无实战执行数据" : "最近窗口暂无模拟执行数据",
);

const dryRunFilter = computed(() => !isLiveMode.value);
const windowOptions = [
  { value: 7, label: "最近 7 天" },
  { value: 14, label: "最近 14 天" },
  { value: 30, label: "最近 30 天" },
];
const metricOptions = [
  { key: "exec-total", label: "执行总次数" },
  { key: "exec-success-rate", label: "成功率" },
  { key: "exec-buy", label: "买入次数" },
  { key: "exec-sell", label: "卖出次数" },
];

const formatDayKey = (date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const formatDayLabel = key => key.slice(5);

const trendDayKeys = computed(() => {
  const days = [];
  const today = new Date();
  for (let index = windowDays.value - 1; index >= 0; index -= 1) {
    const day = new Date(today);
    day.setDate(today.getDate() - index);
    days.push(formatDayKey(day));
  }
  return days;
});

const trendDayKeySet = computed(() => new Set(trendDayKeys.value));

const modeWindowLogs = computed(() => {
  const keySet = trendDayKeySet.value;
  const expectedDryRun = dryRunFilter.value;
  const result = [];
  for (const item of executionLogs.value) {
    if (Boolean(item?.dry_run) !== expectedDryRun) continue;
    const parsedDate = new Date(item?.created_at || "");
    if (Number.isNaN(parsedDate.getTime())) continue;
    const dayKey = formatDayKey(parsedDate);
    if (!keySet.has(dayKey)) continue;
    result.push({
      action: item?.action,
      success: Boolean(item?.success),
      dayKey,
    });
  }
  return result;
});

const trendSource = computed(() => {
  const days = trendDayKeys.value;
  const bucket = new Map(
    days.map(day => [
      day,
      {
        total: 0,
        success: 0,
        buy: 0,
        sell: 0,
      },
    ]),
  );

  for (const item of modeWindowLogs.value) {
    if (!bucket.has(item.dayKey)) continue;
    const row = bucket.get(item.dayKey);
    row.total += 1;
    if (item.success) row.success += 1;
    if (item.action === "buy") row.buy += 1;
    if (item.action === "sell") row.sell += 1;
  }

  const labels = days.map(formatDayLabel);
  const total = [];
  const successRate = [];
  const buy = [];
  const sell = [];

  for (const day of days) {
    const row = bucket.get(day);
    total.push(row.total);
    successRate.push(
      row.total > 0 ? Number(((row.success / row.total) * 100).toFixed(1)) : 0,
    );
    buy.push(row.buy);
    sell.push(row.sell);
  }

  return { labels, total, successRate, buy, sell };
});

const trendLabels = computed(() => trendSource.value.labels);

const executionSummary = computed(() => {
  const items = modeWindowLogs.value;
  const total = items.length;
  const success = items.filter(item => item.success).length;
  const buyCount = items.filter(item => item.action === "buy").length;
  const sellCount = items.filter(item => item.action === "sell").length;
  return {
    total,
    successRate: total > 0 ? Number(((success / total) * 100).toFixed(1)) : 0,
    buyCount,
    sellCount,
  };
});

const buildChartGeometry = (values, labels) => {
  if (!Array.isArray(values) || values.length === 0) {
    return {
      points: [],
      linePoints: "",
      areaPoints: "",
      hasData: false,
    };
  }

  const safeValues = values.map(value => (Number.isFinite(value) ? Number(value) : 0));
  const hasData = safeValues.some(value => value > 0);
  if (!hasData) {
    return {
      points: safeValues.map((value, index) => ({
        index,
        x:
          values.length > 1
            ? Number((index * (100 / (values.length - 1))).toFixed(2))
            : 50,
        y: 30,
        value,
        label: labels[index] || "-",
      })),
      linePoints: "",
      areaPoints: "",
      hasData: false,
    };
  }

  const maxValue = Math.max(1, ...safeValues);
  const xStep = safeValues.length > 1 ? 100 / (safeValues.length - 1) : 0;
  const points = safeValues.map((value, index) => {
    const x = Number((index * xStep).toFixed(2));
    const y = Number((34 - (value / maxValue) * 28).toFixed(2));
    return {
      index,
      x,
      y,
      value,
      label: labels[index] || "-",
    };
  });

  const linePoints = points.map(point => `${point.x},${point.y}`).join(" ");
  const areaPoints = `${linePoints} ${points[points.length - 1].x},34 ${points[0].x},34`;
  return {
    points,
    linePoints,
    areaPoints,
    hasData: true,
  };
};

const chartCards = computed(() => {
  const source = trendSource.value;
  const latest = values => (values.length ? values[values.length - 1] : 0);
  const cards = [
    {
      key: "exec-total",
      title: "执行总次数",
      description: "观察最近窗口内动作密度是否持续。",
      values: source.total,
      latest: latest(source.total),
      unit: "次",
      color: "#409eff",
      gradientStart: "#8cc5ff",
      gradientEnd: "#337ecc",
    },
    {
      key: "exec-success-rate",
      title: "成功率",
      description: "观察执行链路在当前窗口内是否稳定。",
      values: source.successRate,
      latest: latest(source.successRate),
      unit: "%",
      color: "#67c23a",
      gradientStart: "#95d475",
      gradientEnd: "#529b2e",
    },
    {
      key: "exec-buy",
      title: isLiveMode.value ? "买入次数" : "模拟买入次数",
      description: "观察买入动作是否持续触发。",
      values: source.buy,
      latest: latest(source.buy),
      unit: "次",
      color: "#e6a23c",
      gradientStart: "#f3c980",
      gradientEnd: "#b88230",
    },
    {
      key: "exec-sell",
      title: isLiveMode.value ? "卖出次数" : "模拟卖出次数",
      description: "观察卖出动作是否形成闭环。",
      values: source.sell,
      latest: latest(source.sell),
      unit: "次",
      color: "#f56c6c",
      gradientStart: "#f89f9f",
      gradientEnd: "#dd6161",
    },
  ];

  return cards.map(card => ({
    ...card,
    ...buildChartGeometry(card.values, source.labels),
  }));
});

const visibleChartCards = computed(() => {
  const selected = selectedMetricKeys.value.length
    ? new Set(selectedMetricKeys.value)
    : new Set(metricOptions.map(option => option.key));
  return chartCards.value.filter(chart => selected.has(chart.key));
});

const activePointMap = computed(() => {
  const result = {};
  if (!hoverState.value.chartKey || hoverState.value.pointIndex < 0) {
    return result;
  }
  const chart = visibleChartCards.value.find(item => item.key === hoverState.value.chartKey);
  if (!chart) return result;
  const point = chart.points[hoverState.value.pointIndex];
  if (point) result[chart.key] = point;
  return result;
});

const setActivePoint = (chartKey, pointIndex) => {
  hoverState.value = { chartKey, pointIndex };
};

const clearActivePoint = (chartKey = "") => {
  if (!chartKey || hoverState.value.chartKey === chartKey) {
    hoverState.value = {
      chartKey: "",
      pointIndex: -1,
    };
  }
};

const activePointForChart = chartKey => activePointMap.value[chartKey] || null;

const tooltipLeftStyle = (x) => {
  const safeX = Number.isFinite(x) ? x : 50;
  const clamped = Math.min(90, Math.max(10, safeX));
  return `${clamped}%`;
};

watch(windowDays, () => {
  clearActivePoint();
});

watch(
  selectedMetricKeys,
  (next) => {
    if (!next.length) selectedMetricKeys.value = [metricOptions[0].key];
    clearActivePoint();
  },
  { deep: true },
);

watch(
  () => props.mode,
  () => {
    void loadData();
  },
);

const loadData = async () => {
  loading.value = true;
  loadError.value = "";
  clearActivePoint();
  try {
    const [metricsRes, autotradeRes, logsRes] = await Promise.all([
      cardFlipApi.getMetrics(),
      cardFlipApi.getAutotradeStatus(),
      cardFlipApi.listExecutionLogs({
        limit: DASHBOARD_LOG_LIMIT,
        dry_run: dryRunFilter.value,
      }),
    ]);
    metrics.value = metricsRes || metrics.value;
    autotradeStatus.value = autotradeRes || autotradeStatus.value;
    executionLogs.value = Array.isArray(logsRes?.items) ? logsRes.items : [];
  } catch (error) {
    loadError.value = `看板数据加载失败：${getErrorMessage(error, "请稍后重试")}`;
  } finally {
    loading.value = false;
  }
};

const goToOps = () => {
  router.push("/admin/card-flip-ops");
};

const goToDocs = () => {
  router.push("/admin/card-flip/docs");
};

onMounted(() => {
  void loadData();
});
</script>

<style scoped lang="scss">
.mode-page {
  display: grid;
  gap: 18px;
  min-height: 100%;
}

.mode-hero,
.filter-panel,
.kpi-card,
.trend-card {
  border: 1px solid var(--border-light);
  background: var(--panel-bg);
  box-shadow: var(--shadow-light);
}

.mode-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 28px 30px;
  border-radius: 18px;
}

.mode-hero.live {
  border-color: rgba(245, 108, 108, 0.22);
}

.hero-main {
  display: grid;
  gap: 14px;
  max-width: 760px;
}

.hero-kicker,
.panel-kicker {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--primary-color-light);
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.hero-copy h1,
.panel-head h2 {
  margin: 0;
  color: var(--text-primary);
}

.hero-copy h1 {
  font-size: clamp(28px, 2.8vw, 38px);
  line-height: 1.08;
}

.hero-copy p {
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

.hero-actions {
  justify-content: flex-end;
}

.error-alert {
  border-radius: 14px;
}

.filter-panel {
  display: grid;
  gap: 14px;
  padding: 22px 24px;
  border-radius: 16px;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 14px;
}

.panel-head h2 {
  margin-top: 10px;
  font-size: 22px;
  line-height: 1.12;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-label {
  min-width: 72px;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 14px;
}

.kpi-card {
  display: grid;
  gap: 10px;
  padding: 18px;
  border-radius: 16px;
}

.kpi-label {
  color: var(--text-tertiary);
  font-size: 13px;
  font-weight: 600;
}

.kpi-value {
  color: var(--text-primary);
  font-size: 28px;
  line-height: 1.1;
}

.trend-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.trend-card {
  padding: 18px 20px;
  border-radius: 16px;
}

.trend-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.trend-head h3 {
  margin: 0;
  font-size: 18px;
  color: var(--text-primary);
}

.trend-head p {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.trend-latest {
  color: var(--text-primary);
  font-size: 22px;
  font-weight: 700;
  white-space: nowrap;
}

.trend-body {
  position: relative;
  margin-top: 16px;
  height: 220px;
  padding: 16px 16px 12px;
  border-radius: 16px;
  border: 1px solid var(--border-light);
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
}

.trend-empty {
  display: grid;
  place-items: center;
  margin-top: 16px;
  height: 220px;
  border-radius: 16px;
  border: 1px dashed var(--border-medium);
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
}

.trend-svg {
  width: 100%;
  height: 100%;
}

.trend-grid-line {
  stroke: rgba(144, 147, 153, 0.22);
  stroke-width: 0.35;
}

.trend-line {
  fill: none;
  stroke-width: 1.15;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.trend-cursor {
  stroke: rgba(48, 49, 51, 0.18);
  stroke-dasharray: 1.6 1.2;
  stroke-width: 0.35;
}

.trend-point {
  filter: drop-shadow(0 0 6px rgba(15, 23, 42, 0.12));
}

.trend-hit {
  fill: transparent;
  cursor: pointer;
}

.trend-tooltip {
  position: absolute;
  bottom: 10px;
  transform: translateX(-50%);
  min-width: 94px;
  padding: 8px 10px;
  border-radius: 12px;
  background: rgba(48, 49, 51, 0.92);
  color: #fff;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.18);
  pointer-events: none;
}

.tooltip-date {
  font-size: 12px;
  opacity: 0.78;
}

.tooltip-value {
  margin-top: 4px;
  font-size: 15px;
  font-weight: 700;
}

.trend-foot {
  display: flex;
  justify-content: space-between;
  margin-top: 10px;
  color: var(--text-muted);
  font-size: 12px;
}

@media (max-width: 1280px) {
  .kpi-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .mode-hero {
    flex-direction: column;
    padding: 22px;
  }

  .hero-actions {
    justify-content: flex-start;
  }

  .trend-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .trend-head {
    flex-direction: column;
  }

  .trend-body,
  .trend-empty {
    height: 190px;
  }
}

@media (max-width: 520px) {
  .mode-hero,
  .filter-panel,
  .kpi-card,
  .trend-card {
    border-radius: 14px;
  }

  .hero-copy h1 {
    font-size: 24px;
  }

  .kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
