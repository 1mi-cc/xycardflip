<template>
  <div class="mode-page">
    <section class="mode-hero" :class="{ live: isLiveMode }">
      <div class="hero-main">
        <h1>{{ modeTitle }}</h1>
        <p>{{ modeDescription }}</p>
        <div class="hero-tags">
          <n-tag size="small" :type="isLiveMode ? 'error' : 'info'">
            {{ isLiveMode ? "实战执行链路" : "模拟执行链路" }}
          </n-tag>
          <n-tag
            size="small"
            :type="autotradeStatus.running ? 'success' : 'default'"
          >
            {{ autotradeStatus.running ? "审批引擎运行中" : "审批引擎已停止" }}
          </n-tag>
          <n-tag size="small" type="warning">
            数据窗口：最近 {{ windowDays }} 天
          </n-tag>
        </div>
      </div>

      <div class="hero-actions">
        <n-button type="primary" @click="goToOps"> 进入操作台 </n-button>
        <n-button :loading="loading" @click="loadData"> 刷新看板 </n-button>
      </div>
    </section>

    <n-spin :show="loading">
      <section class="filter-panel">
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
          <div class="kpi-label">执行总次数</div>
          <div class="kpi-value">{{ executionSummary.total }}</div>
        </article>
        <article class="kpi-card">
          <div class="kpi-label">成功率</div>
          <div class="kpi-value">{{ executionSummary.successRate }}%</div>
        </article>
        <article class="kpi-card">
          <div class="kpi-label">
            {{ isLiveMode ? "实战买入" : "模拟买入" }}
          </div>
          <div class="kpi-value">{{ executionSummary.buyCount }}</div>
        </article>
        <article class="kpi-card">
          <div class="kpi-label">
            {{ isLiveMode ? "实战卖出" : "模拟卖出" }}
          </div>
          <div class="kpi-value">{{ executionSummary.sellCount }}</div>
        </article>
        <article class="kpi-card">
          <div class="kpi-label">待审核机会</div>
          <div class="kpi-value">{{ metrics.pending_review_count || 0 }}</div>
        </article>
        <article class="kpi-card">
          <div class="kpi-label">累计审批</div>
          <div class="kpi-value">{{ autotradeStatus.total_approved || 0 }}</div>
        </article>
      </section>

      <section class="trend-grid">
        <article
          v-for="chart in visibleChartCards"
          :key="chart.key"
          class="trend-card"
        >
          <header class="trend-head">
            <h3>{{ chart.title }}</h3>
            <span>{{ chart.latest }}{{ chart.unit }}</span>
          </header>
          <div class="trend-body" @mouseleave="clearActivePoint(chart.key)">
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
                    stop-opacity="0.42"
                  />
                  <stop
                    offset="100%"
                    :stop-color="chart.gradientEnd"
                    stop-opacity="0.06"
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
                r="1.5"
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
              :style="{
                left: tooltipLeftStyle(activePointForChart(chart.key).x),
              }"
            >
              <div class="tooltip-date">
                {{ activePointForChart(chart.key).label }}
              </div>
              <div class="tooltip-value">
                {{ activePointForChart(chart.key).value }}{{ chart.unit }}
              </div>
            </div>
          </div>
          <footer class="trend-foot">
            <span>{{ trendLabels[0] || "-" }}</span>
            <span>{{ trendLabels[trendLabels.length - 1] || "-" }}</span>
          </footer>
        </article>
      </section>

      <section v-if="loadError" class="error-box">
        {{ loadError }}
      </section>
    </n-spin>
  </div>
</template>

<script setup>
import cardFlipApi from "@/api/cardFlip";
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

const props = defineProps({
  mode: {
    type: String,
    default: "simulation",
  },
});

const router = useRouter();
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
    ? "聚焦实战执行链路，观察真实执行成功率、买卖曲线与审批节奏。"
    : "聚焦模拟执行链路，先在 dry-run 环境验证策略与参数变化。",
);

const dryRunFilter = computed(() => !isLiveMode.value);
const windowOptions = [
  { value: 7, label: "最近 7 天" },
  { value: 14, label: "最近 14 天" },
  { value: 30, label: "最近 30 天" },
];
const metricOptions = [
  { key: "exec-total", label: "执行次数" },
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

const formatDayLabel = (key) => key.slice(5);

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
    days.map((day) => [
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
  const success = items.filter((item) => item.success).length;
  const buyCount = items.filter((item) => item.action === "buy").length;
  const sellCount = items.filter((item) => item.action === "sell").length;
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
    };
  }
  const safeValues = values.map((value) =>
    Number.isFinite(value) ? value : 0,
  );
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

  const linePoints = points.map((point) => `${point.x},${point.y}`).join(" ");
  const areaPoints = `${linePoints} ${points[points.length - 1].x},34 ${points[0].x},34`;
  return {
    points,
    linePoints,
    areaPoints,
  };
};

const chartCards = computed(() => {
  const source = trendSource.value;
  const latest = (values) => (values.length ? values[values.length - 1] : 0);
  const cards = [
    {
      key: "exec-total",
      title: "执行次数曲线",
      values: source.total,
      latest: latest(source.total),
      unit: "次",
      color: "#3b82f6",
      gradientStart: "#60a5fa",
      gradientEnd: "#1d4ed8",
    },
    {
      key: "exec-success-rate",
      title: "执行成功率曲线",
      values: source.successRate,
      latest: latest(source.successRate),
      unit: "%",
      color: "#16a34a",
      gradientStart: "#4ade80",
      gradientEnd: "#15803d",
    },
    {
      key: "exec-buy",
      title: isLiveMode.value ? "实战买入次数曲线" : "模拟买入次数曲线",
      values: source.buy,
      latest: latest(source.buy),
      unit: "次",
      color: "#f59e0b",
      gradientStart: "#fbbf24",
      gradientEnd: "#b45309",
    },
    {
      key: "exec-sell",
      title: isLiveMode.value ? "实战卖出次数曲线" : "模拟卖出次数曲线",
      values: source.sell,
      latest: latest(source.sell),
      unit: "次",
      color: "#ef4444",
      gradientStart: "#f87171",
      gradientEnd: "#b91c1c",
    },
  ];
  return cards.map((card) => {
    const geometry = buildChartGeometry(card.values, source.labels);
    return {
      ...card,
      ...geometry,
    };
  });
});

const visibleChartCards = computed(() => {
  const selected = selectedMetricKeys.value.length
    ? new Set(selectedMetricKeys.value)
    : new Set(metricOptions.map((option) => option.key));
  return chartCards.value.filter((chart) => selected.has(chart.key));
});

const activePointMap = computed(() => {
  const result = {};
  if (!hoverState.value.chartKey || hoverState.value.pointIndex < 0)
    return result;
  const chart = visibleChartCards.value.find(
    (item) => item.key === hoverState.value.chartKey,
  );
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

const activePointForChart = (chartKey) =>
  activePointMap.value[chartKey] || null;

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

const loadData = async () => {
  loading.value = true;
  loadError.value = "";
  clearActivePoint();
  try {
    const [metricsRes, autotradeRes, logsRes] = await Promise.all([
      cardFlipApi.getMetrics(),
      cardFlipApi.getAutotradeStatus(),
      cardFlipApi.listExecutionLogs({
        limit: 2000,
        dry_run: dryRunFilter.value,
      }),
    ]);
    metrics.value = metricsRes || metrics.value;
    autotradeStatus.value = autotradeRes || autotradeStatus.value;
    executionLogs.value = Array.isArray(logsRes?.items) ? logsRes.items : [];
  } catch (error) {
    loadError.value = `看板数据加载失败: ${error.message}`;
  } finally {
    loading.value = false;
  }
};

const goToOps = () => {
  router.push("/admin/card-flip-ops");
};

onMounted(() => {
  void loadData();
});
</script>

<style scoped lang="scss">
.mode-page {
  display: grid;
  gap: 18px;
  padding: 20px;
  min-height: calc(100vh - 64px);
  background:
    radial-gradient(
      circle at top right,
      rgba(245, 158, 11, 0.08),
      transparent 26%
    ),
    radial-gradient(
      circle at top left,
      rgba(15, 118, 110, 0.08),
      transparent 28%
    ),
    var(--bg-secondary);
}

.mode-hero {
  border-radius: 22px;
  padding: 28px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  background: linear-gradient(
    135deg,
    rgba(255, 248, 235, 0.97) 0%,
    rgba(241, 247, 243, 0.97) 100%
  );
  border: 1px solid rgba(15, 118, 110, 0.12);
  box-shadow: var(--shadow-medium);
  color: var(--text-primary);
}

.mode-hero.live {
  background: linear-gradient(
    135deg,
    rgba(255, 243, 234, 0.98) 0%,
    rgba(252, 237, 231, 0.98) 100%
  );
  border-color: rgba(180, 83, 9, 0.18);
}

.hero-main {
  max-width: 720px;
}

.hero-main h1 {
  margin: 0;
  font-size: 30px;
}

.hero-main p {
  margin: 10px 0 12px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.hero-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.hero-actions {
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.filter-panel {
  display: grid;
  gap: 12px;
  padding: 18px 20px;
  border: 1px solid var(--border-light);
  border-radius: 18px;
  background: rgba(255, 253, 248, 0.94);
  box-shadow: var(--shadow-light);
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
  gap: 12px;
}

.kpi-card,
.trend-card {
  background: rgba(255, 253, 248, 0.95);
  border-radius: 18px;
  border: 1px solid var(--border-light);
  box-shadow: var(--shadow-light);
}

.kpi-card {
  padding: 18px;
}

.kpi-label {
  color: var(--text-secondary);
  font-size: 13px;
}

.kpi-value {
  margin-top: 8px;
  color: var(--text-primary);
  font-size: 28px;
  font-weight: 700;
  line-height: 1.1;
}

.trend-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.trend-card {
  padding: 16px 18px;
}

.trend-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.trend-head h3 {
  margin: 0;
  font-size: 15px;
  color: var(--text-primary);
}

.trend-head span {
  color: var(--text-secondary);
  font-size: 13px;
}

.trend-body {
  position: relative;
  height: 182px;
  border-radius: 14px;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
  border: 1px solid #edf2f7;
  overflow: hidden;
}

.trend-svg {
  width: 100%;
  height: 100%;
}

.trend-grid-line {
  stroke: #dbe3ef;
  stroke-width: 0.5;
  opacity: 0.85;
}

.trend-area {
  pointer-events: none;
}

.trend-line {
  fill: none;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
  filter: drop-shadow(0 2px 3px rgba(15, 23, 42, 0.15));
}

.trend-cursor {
  stroke: #94a3b8;
  stroke-width: 0.7;
  stroke-dasharray: 1.8 1.4;
}

.trend-point {
  stroke: #ffffff;
  stroke-width: 0.8;
}

.trend-hit {
  fill: rgba(59, 130, 246, 0);
  cursor: crosshair;
}

.trend-tooltip {
  position: absolute;
  top: 10px;
  transform: translateX(-50%);
  min-width: 90px;
  padding: 6px 8px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.9);
  color: #f8fafc;
  pointer-events: none;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.2);
}

.tooltip-date {
  font-size: 11px;
  color: #cbd5e1;
  line-height: 1.2;
}

.tooltip-value {
  margin-top: 2px;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.25;
}

.trend-foot {
  display: flex;
  justify-content: space-between;
  color: var(--text-secondary);
  font-size: 12px;
}

.error-box {
  border: 1px solid #fecaca;
  background: #fff1f2;
  color: #b91c1c;
  border-radius: 14px;
  padding: 12px;
}

@media (max-width: 1200px) {
  .kpi-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 860px) {
  .mode-page {
    padding: 14px;
  }

  .mode-hero {
    padding: 22px;
    flex-direction: column;
  }

  .hero-main {
    max-width: none;
  }

  .hero-actions {
    width: 100%;
    justify-content: flex-start;
    align-items: center;
  }

  .filter-row {
    align-items: flex-start;
    flex-direction: column;
    gap: 6px;
  }

  .trend-grid {
    grid-template-columns: 1fr;
  }

  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 540px) {
  .kpi-grid {
    grid-template-columns: 1fr;
  }

  .kpi-value {
    font-size: 24px;
  }
}
</style>
