<template>
  <div class="dashboard-page">
    <section class="hero-row">
      <div>
        <h1>Dashboard Overview</h1>
        <p>Real-time performance and service health monitoring.</p>
      </div>

      <div class="hero-actions">
        <button
          v-for="item in rangeTabs"
          :key="item.value"
          class="hero-chip"
          :class="{ active: activeRange === item.value }"
          type="button"
          @click="activeRange = item.value"
        >
          {{ item.label }}
        </button>
        <n-button type="primary" :loading="refreshing" @click="openTradingWorkspace">Open Trading</n-button>
      </div>
    </section>

    <n-alert v-if="error" type="error" :show-icon="false">{{ error }}</n-alert>

    <section class="metrics-grid">
      <article v-for="item in metricCards" :key="item.label" class="metric-card">
        <p>{{ item.label }}</p>
        <div class="metric-value-row">
          <span class="metric-value" :class="item.tone">{{ item.value }}</span>
          <span v-if="item.trailing" class="metric-trailing">{{ item.trailing }}</span>
        </div>
      </article>
    </section>

    <section class="analytics-grid">
      <article class="panel chart-panel">
        <div class="panel-head">
          <div>
            <h3>Trading Profit Trend</h3>
            <p>Daily performance over the last {{ selectedRangeDays }} days</p>
          </div>
          <div class="panel-tag">{{ activeRangeLabel }}</div>
        </div>

        <div class="chart-shell">
          <div class="chart-grid"></div>
          <svg v-if="priceChart.points.length" class="chart-svg" viewBox="0 0 1000 220" preserveAspectRatio="none">
            <defs>
              <linearGradient id="priceChartFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stop-color="#0071e3" stop-opacity="0.28"></stop>
                <stop offset="100%" stop-color="#0071e3" stop-opacity="0"></stop>
              </linearGradient>
            </defs>
            <path :d="priceChart.areaPath" fill="url(#priceChartFill)"></path>
            <path :d="priceChart.linePath" fill="none" stroke="#0071e3" stroke-width="3" stroke-linecap="round"></path>
            <circle
              v-if="priceChart.lastPoint"
              :cx="priceChart.lastPoint.x"
              :cy="priceChart.lastPoint.y"
              r="5"
              fill="#0071e3"
            ></circle>
          </svg>
          <div v-else class="chart-empty">No sales history available.</div>
          <div class="chart-corner">{{ priceChart.maxLabel }}</div>
          <div class="chart-axis">
            <span v-for="item in chartAxisLabels" :key="item.label">{{ item.label }}</span>
          </div>
        </div>
      </article>

      <article class="panel donut-panel">
        <div class="panel-head">
          <div>
            <h3>Asset Distribution</h3>
            <p>Volume by product category</p>
          </div>
        </div>

        <div class="donut-wrap">
          <div class="donut-chart" :style="{ background: donutGradient }">
            <div class="donut-hole">
              <strong>{{ donutTotalLabel }}</strong>
              <span>Allocated</span>
            </div>
          </div>
        </div>

        <div class="legend-list">
          <div v-for="item in donutSlices" :key="item.label" class="legend-row">
            <div class="legend-left">
              <span class="legend-dot" :style="{ backgroundColor: item.color }"></span>
              <span>{{ item.label }}</span>
            </div>
            <strong>{{ item.percentText }}</strong>
          </div>
        </div>
      </article>
    </section>

    <section class="arbitrage-panel panel">
      <div class="panel-head">
        <div>
          <h3>Cross-Platform Spread Watch</h3>
          <p>Read-only arbitrage scan across active listing sources. Buy on the cheapest source, sell on the highest.</p>
        </div>
        <div class="panel-actions">
          <div class="panel-tag">{{ arbitrageDataModeLabel }}</div>
          <n-button secondary @click="openMarketplaceDrawer">Marketplace Intake</n-button>
        </div>
      </div>

      <div class="arbitrage-meta">
        <div class="arbitrage-stat">
          <span>Scanned Listings</span>
          <strong>{{ formatInteger(arbitrageSummary.scanned_listing_count || 0) }}</strong>
        </div>
        <div class="arbitrage-stat">
          <span>Source Count</span>
          <strong>{{ formatInteger(arbitrageSummary.source_count || 0) }}</strong>
        </div>
        <div class="arbitrage-stat">
          <span>Live Opportunities</span>
          <strong>{{ formatInteger(arbitrageSummary.opportunity_count || 0) }}</strong>
        </div>
        <div class="arbitrage-stat">
          <span>Best Net Spread</span>
          <strong>{{ formatMoney(arbitrageSummary.best_estimated_net_profit || 0) }}</strong>
        </div>
      </div>

      <div v-if="arbitrageRows.length" class="arbitrage-list">
        <article v-for="item in arbitrageRows" :key="item.arbitrage_key" class="arbitrage-row">
          <div class="arbitrage-main">
            <h4>{{ item.reference_title }}</h4>
            <p>{{ item.sources.join(' -> ') }}</p>
          </div>
          <div class="arbitrage-side">
            <div class="arbitrage-price-line">
              <span>Buy {{ item.buy.source }}</span>
              <strong>{{ formatMoney(item.buy.list_price) }}</strong>
            </div>
            <div class="arbitrage-price-line">
              <span>Sell {{ item.sell.source }}</span>
              <strong>{{ formatMoney(item.sell.list_price) }}</strong>
            </div>
            <div class="arbitrage-price-line emphasis">
              <span>Est. Net / ROI</span>
              <strong>{{ formatMoney(item.estimated_net_profit) }} / {{ formatPercent(item.estimated_roi) }}</strong>
            </div>
          </div>
        </article>
      </div>
      <div v-else class="arbitrage-empty">
        <strong>No cross-platform spread yet.</strong>
        <span>Current live data only contains one source. Add Taobao, JD, or Pinduoduo listings to start seeing spread candidates.</span>
      </div>

      <div class="drawer-panel">
        <strong>Matching Preview</strong>
        <p>See which offers were grouped together and why they are or are not creating arbitrage candidates.</p>
      </div>
      <div v-if="arbitrageMatchingRows.length" class="arbitrage-list">
        <article v-for="item in arbitrageMatchingRows" :key="`match-${item.arbitrage_key}`" class="arbitrage-row">
          <div class="arbitrage-main">
            <h4>{{ item.reference_title }}</h4>
            <p>{{ item.reason }}</p>
          </div>
          <div class="arbitrage-side">
            <div class="arbitrage-price-line">
              <span>Status</span>
              <strong>{{ item.status }}</strong>
            </div>
            <div class="arbitrage-price-line">
              <span>Platforms</span>
              <strong>{{ item.sources.join(" / ") || "--" }}</strong>
            </div>
            <div class="arbitrage-price-line emphasis">
              <span>Net / ROI</span>
              <strong>{{ formatMoney(item.estimated_net_profit || 0) }} / {{ formatPercent(item.estimated_roi || 0) }}</strong>
            </div>
          </div>
        </article>
      </div>
    </section>

    <section class="services-section">
      <div class="services-toolbar">
        <div class="services-title">
          <h2>Services</h2>
          <span>/ Backend Services</span>
        </div>

        <div class="services-controls">
          <div class="segmented-control">
            <button
              v-for="item in serviceFilters"
              :key="item.value"
              class="segmented-button"
              :class="{ active: activeServiceFilter === item.value }"
              type="button"
              @click="activeServiceFilter = item.value"
            >
              {{ item.label }}
            </button>
          </div>

          <div class="sort-shell">
            <span>Sort:</span>
            <n-select
              v-model:value="serviceSort"
              size="small"
              :options="serviceSortOptions"
            ></n-select>
          </div>
        </div>
      </div>

      <div class="service-stack">
        <article v-for="item in filteredServiceRows" :key="item.id" class="service-row-card">
          <div class="service-main">
            <div class="service-header">
              <div>
                <div class="service-title-line">
                  <h3>{{ item.title }}</h3>
                  <span class="service-badge" :class="item.tone">{{ item.badge }}</span>
                </div>
                <div class="service-status-line">
                  <span class="service-dot" :class="item.tone"></span>
                  <span>Status: {{ item.statusText }}</span>
                </div>
              </div>

              <button class="service-round-button" type="button" @click="openServiceDrawer(item.id)">
                <n-icon size="18"><PlayOutline></PlayOutline></n-icon>
              </button>
            </div>

            <div v-if="item.layout === 'metrics'" class="service-mini-grid">
              <div v-for="metric in item.metrics" :key="`${item.id}-${metric.label}`" class="mini-metric">
                <p>{{ metric.label }}</p>
                <strong>{{ metric.value }}</strong>
              </div>
            </div>

            <div v-else class="service-placeholder-row">
              <span>{{ item.placeholder }}</span>
            </div>
          </div>

          <div class="service-side">
            <div class="side-icon-shell">
              <n-icon size="26"><component :is="item.sideIcon"></component></n-icon>
            </div>
            <div class="side-label">{{ item.sideTitle }}</div>
            <div class="side-value">{{ item.sideValue }}</div>
            <button class="side-link" type="button" @click="openServiceDrawer(item.id)">{{ item.actionLabel }}</button>
          </div>
        </article>
      </div>
    </section>

    <section class="network-panel">
      <div class="network-overlay"></div>
      <div class="network-content">
        <div>
          <h2>Global Trading Network</h2>
          <p>Active nodes across Asian market clusters.</p>
        </div>

        <div class="network-stats">
          <div v-for="item in networkStatCards" :key="item.label" class="network-stat">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </div>
    </section>

    <n-drawer v-model:show="showServiceDrawer" placement="right" :width="420">
      <n-drawer-content :title="selectedServiceRow?.title || 'Service Details'" closable>
        <div v-if="selectedServiceRow" class="drawer-stack">
          <div class="drawer-hero">
            <div class="drawer-status">
              <span class="drawer-status-dot" :class="selectedServiceRow.tone"></span>
              <strong>{{ selectedServiceRow.badge }}</strong>
            </div>
            <p>{{ selectedServiceRow.drawerDescription }}</p>
          </div>
          <div class="drawer-list">
            <div v-for="item in selectedServiceRow.drawerItems" :key="`${selectedServiceRow.id}-${item.label}`" class="drawer-row">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
          <div v-if="selectedServiceRow.controlActions?.length" class="drawer-actions">
            <n-button
              v-for="item in selectedServiceRow.controlActions"
              :key="`${selectedServiceRow.id}-${item.key}`"
              :type="item.primary ? 'primary' : 'default'"
              :disabled="!canOperate"
              :loading="actionLoading === item.key"
              @click="runDashboardAction(item.key)"
            >
              {{ item.label }}
            </n-button>
          </div>
          <div class="drawer-actions">
            <n-button type="primary" @click="handleRefresh">Refresh Data</n-button>
            <n-button secondary @click="showServiceDrawer = false">Close</n-button>
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>

    <n-drawer v-model:show="showMarketplaceDrawer" placement="right" :width="520">
      <n-drawer-content title="Marketplace Offers Intake" closable>
        <div class="drawer-stack">
          <div class="drawer-hero">
            <div class="drawer-status">
              <span class="drawer-status-dot neutral"></span>
              <strong>Read-Only Offers</strong>
            </div>
            <p>Import normalized Taobao, JD, or Pinduoduo offers into the dedicated marketplace layer. These rows do not enter the card-flip review flow.</p>
          </div>
          <n-select v-model:value="marketplacePlatform" :options="marketplacePlatformOptions"></n-select>
          <n-input
            v-model:value="marketplaceOffersJson"
            type="textarea"
            :autosize="{ minRows: 10, maxRows: 20 }"
            placeholder="Paste a JSON array of marketplace offers."
          ></n-input>
          <n-input
            v-model:value="taobaoSnapshotJson"
            type="textarea"
            :autosize="{ minRows: 8, maxRows: 16 }"
            placeholder="Paste a raw Taobao snapshot JSON object."
          ></n-input>
          <n-input
            v-model:value="pinduoduoSnapshotJson"
            type="textarea"
            :autosize="{ minRows: 8, maxRows: 16 }"
            placeholder="Paste a raw Pinduoduo snapshot JSON object."
          ></n-input>
          <n-input
            v-model:value="pinduoduoSnapshotBridgeUrl"
            placeholder="Optional Pinduoduo snapshot bridge URL for cookie-mode sync-once"
          ></n-input>
          <n-input
            v-model:value="jdSnapshotJson"
            type="textarea"
            :autosize="{ minRows: 8, maxRows: 16 }"
            placeholder="Paste a raw JD snapshot JSON object."
          ></n-input>
          <n-input
            v-model:value="jdSnapshotBridgeUrl"
            placeholder="Optional JD snapshot bridge URL for cookie-mode sync-once"
          ></n-input>
          <div class="drawer-actions">
            <n-button secondary @click="taobaoSnapshotJson = TAOBAO_SNAPSHOT_EXAMPLE">Load Taobao Example</n-button>
            <n-button secondary @click="pinduoduoSnapshotJson = PINDUODUO_SNAPSHOT_EXAMPLE">Load Pinduoduo Example</n-button>
            <n-button secondary @click="jdSnapshotJson = JD_SNAPSHOT_EXAMPLE">Load JD Example</n-button>
          </div>
          <div class="drawer-actions">
            <n-button type="primary" :loading="marketplaceImportLoading" @click="importMarketplaceOffers">Import Offers</n-button>
            <n-button secondary :loading="taobaoSnapshotLoading" @click="importTaobaoSnapshot">Import Taobao Snapshot</n-button>
            <n-button secondary :loading="taobaoSyncLoading" @click="syncTaobaoOnce">Sync Taobao API</n-button>
            <n-button secondary :loading="pinduoduoSnapshotLoading" @click="importPinduoduoSnapshot">Import Pinduoduo Snapshot</n-button>
            <n-button secondary :loading="pinduoduoSyncLoading" @click="syncPinduoduoOnce">Sync Pinduoduo API</n-button>
            <n-button secondary :loading="jdSnapshotLoading" @click="importJdSnapshot">Import JD Snapshot</n-button>
            <n-button secondary :loading="jdSyncLoading" @click="syncJdOnce">Sync JD API</n-button>
            <n-button secondary :loading="marketplaceBackfillLoading" @click="backfillMarketplaceOffers">Backfill Xianyu</n-button>
            <n-button secondary @click="refreshMarketplaceLayer">Refresh Layer</n-button>
          </div>
          <div v-if="marketplaceImportResult" class="drawer-panel">
            <strong>Last Import</strong>
            <p>{{ marketplaceImportResult }}</p>
          </div>
          <div class="drawer-panel">
            <strong>Platform Health</strong>
            <p>{{ marketplaceHealthSummary }}</p>
          </div>
          <div class="drawer-list">
            <div v-for="item in marketplaceHealthRows" :key="item.source" class="drawer-row">
              <span>{{ item.source }}</span>
              <strong>{{ formatInteger(item.listing_count) }} offers</strong>
            </div>
          </div>
          <div class="drawer-panel">
            <strong>Provider Readiness</strong>
            <p>{{ marketplaceReadinessSummary }}</p>
          </div>
          <div class="drawer-panel">
            <strong>Shadow Automation</strong>
            <p>{{ marketplaceShadowSummary }}</p>
          </div>
          <div class="drawer-actions">
            <n-button secondary :loading="marketplaceShadowLoading" @click="runMarketplaceShadowOnce">Run Shadow Once</n-button>
          </div>
          <div class="drawer-panel">
            <strong>Taobao API Status</strong>
            <p>{{ taobaoStatusSummary }}</p>
          </div>
          <div class="drawer-panel">
            <strong>Pinduoduo API Status</strong>
            <p>{{ pinduoduoStatusSummary }}</p>
          </div>
          <div class="drawer-panel">
            <strong>JD API Status</strong>
            <p>{{ jdStatusSummary }}</p>
          </div>
          <div class="drawer-list">
            <div v-for="item in marketplaceProviderRows" :key="item.provider" class="drawer-row">
              <span>{{ item.provider }}</span>
              <strong>{{ formatInteger(item.offer_count) }} offers / {{ formatInteger(item.legacy_open_listing_count) }} legacy</strong>
            </div>
          </div>
          <div class="drawer-panel">
            <strong>Recent Shadow Intents</strong>
            <p>Dry-run decisions only. No real trade execution is triggered.</p>
          </div>
          <div class="drawer-list">
            <div v-for="item in marketplaceShadowIntents" :key="item.id" class="drawer-row">
              <span>{{ item.reference_title || item.intent_key }}</span>
              <strong>{{ item.decision_status }} / {{ item.blocked_reason || 'accepted' }}</strong>
            </div>
          </div>
          <div class="drawer-panel">
            <strong>Recent Shadow Runs</strong>
            <p>Latest dry-run batches with accepted and blocked counts.</p>
          </div>
          <div class="drawer-list">
            <div v-for="item in marketplaceShadowRuns" :key="item.id" class="drawer-row">
              <span>{{ compactTime(item.created_at) }}</span>
              <strong>{{ formatInteger(item.accepted_count) }} accepted / {{ formatInteger(item.blocked_count) }} blocked</strong>
            </div>
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<script setup>
import {
  InformationCircleOutline,
  PlayOutline,
  PulseOutline,
  ServerOutline,
} from "@vicons/ionicons5";
import { useMessage } from "naive-ui";
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import cardFlipApi from "@/api/cardFlip";
import useExecutiveOverview from "@/composables/useExecutiveOverview";
import { useAuthStore } from "@/stores/auth";

const {
  error,
  loadOverview,
  loading,
  profitCockpit,
  profitability,
  runtime,
} = useExecutiveOverview();
const router = useRouter();
const authStore = useAuthStore();
const message = useMessage();

const activeRange = ref("30d");
const activeServiceFilter = ref("all");
const serviceSort = ref("load");
const priceHistory = ref([]);
const priceHistoryLoading = ref(false);
const showServiceDrawer = ref(false);
const selectedServiceId = ref("");
const reportSummary = ref({});
const reportLoading = ref(false);
const actionLoading = ref("");
const arbitrageSummary = ref({});
const arbitrageRows = ref([]);
const arbitrageMatchingRows = ref([]);
const arbitrageLoading = ref(false);
const arbitrageAssumptionsState = ref({});
const showMarketplaceDrawer = ref(false);
const marketplacePlatform = ref("taobao");
const marketplaceOffersJson = ref("");
const taobaoSnapshotJson = ref("");
const pinduoduoSnapshotJson = ref("");
const pinduoduoSnapshotBridgeUrl = ref("");
const jdSnapshotJson = ref("");
const jdSnapshotBridgeUrl = ref("");
const marketplaceImportLoading = ref(false);
const taobaoSnapshotLoading = ref(false);
const taobaoSyncLoading = ref(false);
const pinduoduoSnapshotLoading = ref(false);
const pinduoduoSyncLoading = ref(false);
const jdSnapshotLoading = ref(false);
const jdSyncLoading = ref(false);
const marketplaceImportResult = ref("");
const marketplaceHealthRows = ref([]);
const marketplaceProviderRows = ref([]);
const marketplaceBackfillLoading = ref(false);
const marketplaceShadowStatus = ref({});
const marketplaceShadowIntents = ref([]);
const marketplaceShadowRuns = ref([]);
const marketplaceShadowLoading = ref(false);
const taobaoProviderStatus = ref({});
const pinduoduoProviderStatus = ref({});
const jdProviderStatus = ref({});

const rangeTabs = [
  { label: "Last 7 Days", value: "7d" },
  { label: "Last 30 Days", value: "30d" },
  { label: "Last 90 Days", value: "90d" },
];

const serviceFilters = [
  { label: "All", value: "all" },
  { label: "Running", value: "running" },
  { label: "Stopped", value: "stopped" },
];
const serviceSortOptions = [
  { label: "Highest Load", value: "load" },
  { label: "Uptime", value: "uptime" },
  { label: "Name (A-Z)", value: "name" },
];

const inventory = computed(() => profitCockpit.value?.inventory || {});
const sourceLeaders = computed(() =>
  (Array.isArray(profitCockpit.value?.source_leaderboard_7d) ? profitCockpit.value.source_leaderboard_7d : [])
    .slice(0, 3)
    .map(item => ({
      label: String(item.source || "Unknown"),
      value: Math.max(Number(item.realized_net_profit || 0), 0),
    })),
);
const selectedRangeDays = computed(() => {
  if (activeRange.value === "7d")
    return 7;
  if (activeRange.value === "90d")
    return 90;
  return 30;
});
const activeRangeLabel = computed(() => {
  const matched = rangeTabs.find(item => item.value === activeRange.value);
  return matched?.label || "Last 30 Days";
});
const refreshing = computed(() => loading.value || priceHistoryLoading.value || reportLoading.value);
const marketSnapshot = computed(() => reportSummary.value?.data_layer?.market_snapshot || {});
const canOperate = computed(() => {
  if (authStore.userInfo?.isAdmin)
    return true;
  const roles = Array.isArray(authStore.userInfo?.roleKeys) ? authStore.userInfo.roleKeys : [];
  return roles.map(item => String(item || "").toLowerCase()).includes("ops");
});

const metricCards = computed(() => [
  {
    label: "Profit Margin",
    value: formatPercent(profitability.value?.avg_realized_roi || 0),
    trailing: "vs realized trades",
    tone: "accent",
  },
  {
    label: "Avg Holding Days",
    value: formatNumber(profitability.value?.avg_holding_days || 0, 1),
    trailing: "days",
    tone: "",
  },
  {
    label: "Target Exit Value",
    value: formatMoney(inventory.value?.target_exit_value || 0),
    trailing: "",
    tone: "",
  },
  {
    label: "Expected Exit Spread",
    value: formatMoney(inventory.value?.expected_exit_spread || 0),
    trailing: "",
    tone: "",
  },
]);

const donutSlices = computed(() => {
  const fallback = [
    { label: "Sports Cards", value: 1 },
    { label: "TCG Items", value: 1 },
    { label: "Collectibles", value: 1 },
  ];
  const rows = sourceLeaders.value.length ? sourceLeaders.value : fallback;
  const colors = ["#0071e3", "#abc7ff", "#ffffff"];
  const total = rows.reduce((sum, item) => sum + item.value, 0) || 1;

  return rows.map((item, index) => {
    const percent = (item.value / total) * 100;
    return {
      ...item,
      color: colors[index % colors.length],
      percent,
      percentText: `${percent.toFixed(0)}%`,
    };
  });
});

const donutGradient = computed(() => {
  let cursor = 0;
  return `conic-gradient(${donutSlices.value.map((item) => {
    const start = cursor;
    const end = cursor + item.percent;
    cursor = end;
    return `${item.color} ${start}% ${end}%`;
  }).join(", ")})`;
});

const donutTotalLabel = computed(() => {
  const total = donutSlices.value.reduce((sum, item) => sum + item.percent, 0);
  return `${Math.round(total)}%`;
});

const sampledPriceHistory = computed(() => {
  const sorted = [...priceHistory.value]
    .map(item => ({
      ...item,
      atValue: new Date(String(item.at || "")).getTime(),
      price: Number(item.price || 0),
    }))
    .filter(item => Number.isFinite(item.atValue) && item.price > 0)
    .sort((a, b) => a.atValue - b.atValue);

  if (sorted.length <= 20)
    return sorted;

  const step = (sorted.length - 1) / 19;
  return Array.from({ length: 20 }, (_value, index) => sorted[Math.round(step * index)]);
});

const priceChart = computed(() => {
  const rows = sampledPriceHistory.value;
  if (!rows.length) {
    return {
      points: [],
      linePath: "",
      areaPath: "",
      lastPoint: null,
      maxLabel: "--",
    };
  }

  const width = 1000;
  const height = 220;
  const values = rows.map(item => item.price);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const valueRange = Math.max(maxValue - minValue, 1);

  const points = rows.map((item, index) => {
    const x = rows.length === 1 ? width / 2 : (index / (rows.length - 1)) * width;
    const y = height - (((item.price - minValue) / valueRange) * 170 + 20);
    return {
      x: Number(x.toFixed(2)),
      y: Number(y.toFixed(2)),
      price: item.price,
      label: item.at,
    };
  });

  const linePath = points
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x},${point.y}`)
    .join(" ");
  const areaPath = `${linePath} L${points[points.length - 1].x},${height} L${points[0].x},${height} Z`;

  return {
    points,
    linePath,
    areaPath,
    lastPoint: points[points.length - 1],
    maxLabel: formatMoney(maxValue),
  };
});

const chartAxisLabels = computed(() => {
  const rows = sampledPriceHistory.value;
  if (!rows.length)
    return [{ label: "Start" }, { label: "Mid" }, { label: "Now" }];

  const indexes = [0, Math.max(Math.floor((rows.length - 1) / 2), 0), rows.length - 1];
  return [...new Set(indexes)].map((index) => ({
    label: formatAxisDate(rows[index]?.at),
  }));
});

const serviceRows = computed(() => {
  const services = runtime.value?.services || {};
  const automation = runtime.value?.automation || {};
  const executionReadiness = runtime.value?.execution_readiness || {};
  const autotradeRunning = Boolean(services.autotrade?.running);
  const retryRunning = Boolean(services.execution_retry?.running);
  const monitorRunning = Boolean(services.monitor?.is_running);
  const anyAutomationRunning = autotradeRunning || retryRunning;

  const automationBadge = autotradeRunning && retryRunning
    ? "Running"
    : anyAutomationRunning ? "Partial Running" : "Idle";

  const automationLoad = (autotradeRunning ? 2 : 0) + (retryRunning ? 1 : 0);
  const monitorLoad = (monitorRunning ? 0 : 2) + (services.monitor?.circuit_open ? 2 : 0);

  return [
    {
      id: "automation",
      title: "Automation Console",
      badge: automationBadge,
      statusText: anyAutomationRunning ? "Automation loops active" : "Idle",
      tone: anyAutomationRunning ? "warning" : "neutral",
      running: anyAutomationRunning,
      loadRank: automationLoad,
      uptimeRank: new Date(String(automation.last_run_at || "")).getTime() || 0,
      layout: "metrics",
      metrics: [
        { label: "Auto Approvals", value: formatInteger(services.autotrade?.total_approved || 0) },
        { label: "Retries", value: formatInteger(services.execution_retry?.total_retried || 0) },
        { label: "Last Run", value: compactTime(automation.last_run_at) },
      ],
      sideTitle: "Details",
      sideValue: executionReadiness.live_ready ? "Webhook Ready" : "None",
      sideIcon: InformationCircleOutline,
      actionLabel: "Configure Service",
      drawerDescription: "Inspect automation readiness, current runtime flags, and webhook state before changing the service posture.",
      drawerItems: [
        { label: "Auto trade running", value: autotradeRunning ? "Yes" : "No" },
        { label: "Retry worker running", value: retryRunning ? "Yes" : "No" },
        { label: "Last automation run", value: compactTime(automation.last_run_at) },
        { label: "Webhook ready", value: executionReadiness.live_ready ? "Ready" : "Not ready" },
      ],
      controlActions: [
        { key: "automation-start", label: "Start", primary: !anyAutomationRunning },
        { key: "automation-stop", label: "Stop", primary: false },
        { key: "automation-run", label: "Run Once", primary: false },
      ],
    },
    {
      id: "monitor",
      title: "Market Monitoring",
      badge: monitorRunning ? "Running" : "Stopped / Idle",
      statusText: services.monitor?.circuit_open ? "Recovery mode" : monitorRunning ? "Normal" : "Stopped",
      tone: monitorRunning ? "positive" : "neutral",
      running: monitorRunning,
      loadRank: monitorLoad,
      uptimeRank: new Date(String(services.monitor?.last_run_at || "")).getTime() || 0,
      layout: "metrics",
      metrics: [
        { label: "Health", value: compactHealth(services.monitor?.health) },
        { label: "Circuit", value: services.monitor?.circuit_open ? "Open" : "Normal" },
        { label: "Last Run", value: compactTime(services.monitor?.last_run_at) },
      ],
      sideTitle: "Metrics",
      sideValue: compactHealth(services.monitor?.health),
      sideIcon: PulseOutline,
      actionLabel: monitorRunning ? "View Metrics" : "Start Monitor",
      drawerDescription: "Review monitor runtime, health state, and last execution details before restarting or observing the listener.",
      drawerItems: [
        { label: "Health", value: compactHealth(services.monitor?.health) },
        { label: "Circuit", value: services.monitor?.circuit_open ? "Open" : "Normal" },
        { label: "Runs", value: formatInteger(services.monitor?.runs || 0) },
        { label: "Last run", value: compactTime(services.monitor?.last_run_at) },
      ],
      controlActions: [
        { key: "monitor-start", label: "Start", primary: !monitorRunning },
        { key: "monitor-stop", label: "Stop", primary: false },
        { key: "monitor-run", label: "Run Once", primary: false },
      ],
    },
  ];
});
const selectedServiceRow = computed(() => serviceRows.value.find(item => item.id === selectedServiceId.value) || null);
const networkStatCards = computed(() => [
  {
    label: "Open Listings",
    value: formatInteger(marketSnapshot.value?.open_listing_count || 0),
  },
  {
    label: "Tradable Markets",
    value: formatInteger(marketSnapshot.value?.tradable_market_count || marketSnapshot.value?.strategy_market_count || 0),
  },
]);

const arbitrageAssumptions = computed(() => ({
  limit: 5,
  window_hours: 72,
  min_platforms: 2,
}));
const arbitrageDataModeLabel = computed(() =>
  arbitrageAssumptionsState.value?.data_mode === "marketplace_offers"
    ? "Offers Layer"
    : "Read Only",
);
const marketplacePlatformOptions = [
  { label: "Taobao", value: "taobao" },
  { label: "JD", value: "jd" },
  { label: "Pinduoduo", value: "pinduoduo" },
];
const TAOBAO_SNAPSHOT_EXAMPLE = JSON.stringify({
  items: [
    {
      num_iid: "tb-example-1",
      title: "Pokemon Card Charizard PSA 10",
      seller_id: "tb-seller",
      price: 2388.0,
      item_url: "https://example.com/tb-example-1",
      listed_at: new Date().toISOString(),
    },
  ],
}, null, 2);
const PINDUODUO_SNAPSHOT_EXAMPLE = JSON.stringify({
  goods_search_response: {
    goods_list: [
      {
        goods_id: "pdd-example-1",
        goods_name: "Pokemon Card Charizard PSA 10",
        mall_id: "pdd-mall",
        min_group_price: 228800,
        goods_link: "https://example.com/pdd-example-1",
        listed_at: new Date().toISOString(),
      },
    ],
  },
}, null, 2);
const JD_SNAPSHOT_EXAMPLE = JSON.stringify({
  jd_union_open_goods_query_response: {
    queryResult: {
      goodsList: [
        {
          skuId: "jd-example-1",
          skuName: "Pokemon Card Charizard PSA 10",
          owner: "jd-shop",
          price: 2499.0,
          materialUrl: "https://example.com/jd-example-1",
          listed_at: new Date().toISOString(),
        },
      ],
    },
  },
}, null, 2);
const marketplaceHealthSummary = computed(() => {
  const sourceCount = marketplaceHealthRows.value.length;
  const offerCount = marketplaceHealthRows.value.reduce((sum, item) => sum + Number(item.listing_count || 0), 0);
  return `${formatInteger(sourceCount)} platforms, ${formatInteger(offerCount)} active offers in the dedicated marketplace layer.`;
});
const marketplaceReadinessSummary = computed(() => {
  const readyCount = marketplaceProviderRows.value.filter(item => item.backfill_ready || Number(item.offer_count || 0) > 0).length;
  return `${formatInteger(readyCount)} providers have either imported offers or legacy data ready for backfill.`;
});
const marketplaceShadowSummary = computed(() => {
  const status = marketplaceShadowStatus.value || {};
  const lastRun = status.last_run || {};
  if (!Object.keys(status).length)
    return "Shadow automation status not loaded yet.";
  if (!Object.keys(lastRun).length)
    return `Dry-run only. Thresholds: ${formatMoney(status.min_net_profit || 0)} / ${formatPercent(status.min_roi || 0)} / confidence ${formatPercent(status.min_confidence || 0)}.`;
  return `Last run accepted ${formatInteger(lastRun.accepted_count || 0)} of ${formatInteger(lastRun.candidate_count || 0)} candidates. Cooldown ${formatInteger(status.cooldown_minutes || 0)} minutes.`;
});
const taobaoStatusSummary = computed(() => {
  if (!Object.keys(taobaoProviderStatus.value || {}).length)
    return "Status not loaded yet.";
  if (taobaoProviderStatus.value.configured)
    return `Configured via ${taobaoProviderStatus.value.method || "TOP API"} on ${taobaoProviderStatus.value.gateway_url || "gateway"}.`;
  return "Taobao TOP config missing. Set app key, secret, and query_string before sync.";
});
const pinduoduoStatusSummary = computed(() => {
  if (!Object.keys(pinduoduoProviderStatus.value || {}).length)
    return "Status not loaded yet.";
  if (pinduoduoProviderStatus.value.active_mode === "cookie")
    return "Cookie mode active. High-risk and unstable. Fill the snapshot bridge URL below, then run Sync Pinduoduo API.";
  if (pinduoduoProviderStatus.value.configured)
    return `Configured via ${pinduoduoProviderStatus.value.type || "DDK API"} on ${pinduoduoProviderStatus.value.api_url || "gateway"}.`;
  return "Pinduoduo API config missing. Set client_id, client_secret, and params_json before sync.";
});
const jdStatusSummary = computed(() => {
  if (!Object.keys(jdProviderStatus.value || {}).length)
    return "Status not loaded yet.";
  if (jdProviderStatus.value.active_mode === "cookie")
    return "Cookie mode active. High-risk and unstable. Fill the snapshot bridge URL below, then run Sync JD API.";
  if (jdProviderStatus.value.configured)
    return `Configured via ${jdProviderStatus.value.method || "JD API"} on ${jdProviderStatus.value.api_url || "gateway"}.`;
  return "JD API config missing. Set app key, secret, and param_json before sync.";
});

const filteredServiceRows = computed(() => {
  const rows = serviceRows.value.filter((item) => {
    if (activeServiceFilter.value === "running")
      return item.running;
    if (activeServiceFilter.value === "stopped")
      return !item.running;
    return true;
  });

  const sorted = [...rows];
  if (serviceSort.value === "name") {
    sorted.sort((a, b) => a.title.localeCompare(b.title));
    return sorted;
  }
  if (serviceSort.value === "uptime") {
    sorted.sort((a, b) => b.uptimeRank - a.uptimeRank);
    return sorted;
  }
  sorted.sort((a, b) => b.loadRank - a.loadRank);
  return sorted;
});

const loadPriceHistory = async () => {
  priceHistoryLoading.value = true;
  try {
    const response = await cardFlipApi.getPriceHistory({ limit: selectedRangeDays.value });
    priceHistory.value = Array.isArray(response?.items) ? response.items : [];
  } catch {
    priceHistory.value = [];
  } finally {
    priceHistoryLoading.value = false;
  }
};

const loadReportData = async () => {
  reportLoading.value = true;
  try {
    reportSummary.value = await cardFlipApi.getAnalysisReport({ limit: 50 });
  } catch {
    reportSummary.value = {};
  } finally {
    reportLoading.value = false;
  }
};

const loadArbitrageData = async () => {
  arbitrageLoading.value = true;
  try {
    const [response, matchingResponse] = await Promise.all([
      cardFlipApi.getArbitrageOpportunities(arbitrageAssumptions.value),
      cardFlipApi.getArbitrageMatchingPreview({ ...arbitrageAssumptions.value, limit: 6 }),
    ]);
    arbitrageSummary.value = response?.summary || {};
    arbitrageRows.value = Array.isArray(response?.items) ? response.items : [];
    arbitrageAssumptionsState.value = response?.assumptions || {};
    arbitrageMatchingRows.value = Array.isArray(matchingResponse?.items) ? matchingResponse.items : [];
  } catch {
    arbitrageSummary.value = {};
    arbitrageRows.value = [];
    arbitrageAssumptionsState.value = {};
    arbitrageMatchingRows.value = [];
  } finally {
    arbitrageLoading.value = false;
  }
};

const loadMarketplaceHealth = async () => {
  try {
    const response = await cardFlipApi.getMarketplacePlatformHealth({ listing_hours: 72 });
    marketplaceHealthRows.value = Array.isArray(response?.items) ? response.items : [];
  } catch {
    marketplaceHealthRows.value = [];
  }
};

const loadMarketplaceProviderStatus = async () => {
  try {
    const response = await cardFlipApi.getMarketplaceProviderStatus({ listing_hours: 72 });
    marketplaceProviderRows.value = Array.isArray(response?.items) ? response.items : [];
  } catch {
    marketplaceProviderRows.value = [];
  }
};

const loadMarketplaceShadow = async () => {
  try {
    const [status, intents, runs] = await Promise.all([
      cardFlipApi.getMarketplaceShadowStatus(),
      cardFlipApi.listMarketplaceShadowIntents({ limit: 6 }),
      cardFlipApi.listMarketplaceShadowRuns({ limit: 6 }),
    ]);
    marketplaceShadowStatus.value = status || {};
    marketplaceShadowIntents.value = Array.isArray(intents?.items) ? intents.items : [];
    marketplaceShadowRuns.value = Array.isArray(runs?.items) ? runs.items : [];
  } catch {
    marketplaceShadowStatus.value = {};
    marketplaceShadowIntents.value = [];
    marketplaceShadowRuns.value = [];
  }
};

const loadTaobaoProviderStatus = async () => {
  try {
    taobaoProviderStatus.value = await cardFlipApi.getTaobaoProviderStatus();
  } catch {
    taobaoProviderStatus.value = {};
  }
};

const loadPinduoduoProviderStatus = async () => {
  try {
    pinduoduoProviderStatus.value = await cardFlipApi.getPinduoduoProviderStatus();
    if (!pinduoduoSnapshotBridgeUrl.value && pinduoduoProviderStatus.value?.snapshot_provider_url_configured) {
      pinduoduoSnapshotBridgeUrl.value = pinduoduoProviderStatus.value.snapshot_provider_url || "";
    }
  } catch {
    pinduoduoProviderStatus.value = {};
  }
};

const loadJdProviderStatus = async () => {
  try {
    jdProviderStatus.value = await cardFlipApi.getJdProviderStatus();
    if (!jdSnapshotBridgeUrl.value && jdProviderStatus.value?.snapshot_provider_url_configured) {
      jdSnapshotBridgeUrl.value = jdProviderStatus.value.snapshot_provider_url || "";
    }
  } catch {
    jdProviderStatus.value = {};
  }
};

const refreshMarketplaceLayer = async () => {
  await Promise.all([
    loadMarketplaceHealth(),
    loadMarketplaceProviderStatus(),
    loadMarketplaceShadow(),
    loadTaobaoProviderStatus(),
    loadPinduoduoProviderStatus(),
    loadJdProviderStatus(),
    loadArbitrageData(),
  ]);
};

const openMarketplaceDrawer = async () => {
  showMarketplaceDrawer.value = true;
  await refreshMarketplaceLayer();
};

const importMarketplaceOffers = async () => {
  marketplaceImportLoading.value = true;
  marketplaceImportResult.value = "";
  try {
    const parsed = JSON.parse(marketplaceOffersJson.value || "[]");
    if (!Array.isArray(parsed) || !parsed.length)
      throw new Error("Paste a non-empty JSON array of marketplace offers.");

    const normalized = parsed.map((item, index) => ({
      platform: String(item?.platform || marketplacePlatform.value),
      offer_id: item?.offer_id ? String(item.offer_id) : `${marketplacePlatform.value}-${Date.now()}-${index}`,
      seller_id: item?.seller_id ? String(item.seller_id) : null,
      title: String(item?.title || "").trim(),
      canonical_key: String(item?.canonical_key || item?.title || "").trim(),
      item_type: String(item?.item_type || "generic"),
      list_price: Number(item?.list_price || 0),
      shipping_cost: Number(item?.shipping_cost || 0),
      fee_rate: Number(item?.fee_rate || 0),
      currency: String(item?.currency || "CNY"),
      listed_at: String(item?.listed_at || new Date().toISOString()),
      status: String(item?.status || "open"),
      listing_url: String(item?.listing_url || ""),
      raw: item?.raw && typeof item.raw === "object" ? item.raw : item,
    }));

    if (normalized.some(item => !item.title || !Number.isFinite(item.list_price) || item.list_price <= 0))
      throw new Error("Each marketplace offer must include a title and positive list_price.");

    const result = await cardFlipApi.ingestMarketplaceOffers(normalized);
    marketplaceImportResult.value = `Imported ${formatInteger(result?.inserted || 0)} marketplace offers.`;
    await Promise.all([refreshMarketplaceLayer(), loadReportData()]);
    message.success(marketplaceImportResult.value);
  } catch (requestError) {
    const text = requestError instanceof Error ? requestError.message : "Marketplace import failed.";
    marketplaceImportResult.value = text;
    message.error(text);
  } finally {
    marketplaceImportLoading.value = false;
  }
};

const importTaobaoSnapshot = async () => {
  taobaoSnapshotLoading.value = true;
  marketplaceImportResult.value = "";
  try {
    const parsed = JSON.parse(taobaoSnapshotJson.value || "{}");
    const result = await cardFlipApi.ingestTaobaoSnapshot(parsed);
    marketplaceImportResult.value = `Imported ${formatInteger(result?.inserted || 0)} taobao offers from snapshot.`;
    await Promise.all([refreshMarketplaceLayer(), loadReportData()]);
    message.success(marketplaceImportResult.value);
  } catch (requestError) {
    const text = requestError instanceof Error ? requestError.message : "Taobao snapshot import failed.";
    marketplaceImportResult.value = text;
    message.error(text);
  } finally {
    taobaoSnapshotLoading.value = false;
  }
};

const syncTaobaoOnce = async () => {
  taobaoSyncLoading.value = true;
  marketplaceImportResult.value = "";
  try {
    const result = await cardFlipApi.syncTaobaoOnce();
    marketplaceImportResult.value = `Synced ${formatInteger(result?.inserted || 0)} taobao offers via TOP gateway.`;
    await Promise.all([refreshMarketplaceLayer(), loadReportData()]);
    message.success(marketplaceImportResult.value);
  } catch (requestError) {
    const text = requestError instanceof Error ? requestError.message : "Taobao sync failed.";
    marketplaceImportResult.value = text;
    message.error(text);
  } finally {
    taobaoSyncLoading.value = false;
  }
};

const importPinduoduoSnapshot = async () => {
  pinduoduoSnapshotLoading.value = true;
  marketplaceImportResult.value = "";
  try {
    const parsed = JSON.parse(pinduoduoSnapshotJson.value || "{}");
    const result = await cardFlipApi.ingestPinduoduoSnapshot(parsed);
    marketplaceImportResult.value = `Imported ${formatInteger(result?.inserted || 0)} pinduoduo offers from snapshot.`;
    await Promise.all([refreshMarketplaceLayer(), loadReportData()]);
    message.success(marketplaceImportResult.value);
  } catch (requestError) {
    const text = requestError instanceof Error ? requestError.message : "Pinduoduo snapshot import failed.";
    marketplaceImportResult.value = text;
    message.error(text);
  } finally {
    pinduoduoSnapshotLoading.value = false;
  }
};

const syncPinduoduoOnce = async () => {
  pinduoduoSyncLoading.value = true;
  marketplaceImportResult.value = "";
  try {
    const result = await cardFlipApi.syncPinduoduoOnce({
      snapshot_url: pinduoduoSnapshotBridgeUrl.value || undefined,
    });
    marketplaceImportResult.value = `Synced ${formatInteger(result?.inserted || 0)} pinduoduo offers via open API.`;
    await Promise.all([refreshMarketplaceLayer(), loadReportData()]);
    message.success(marketplaceImportResult.value);
  } catch (requestError) {
    const text = requestError instanceof Error ? requestError.message : "Pinduoduo sync failed.";
    marketplaceImportResult.value = text;
    message.error(text);
  } finally {
    pinduoduoSyncLoading.value = false;
  }
};

const importJdSnapshot = async () => {
  jdSnapshotLoading.value = true;
  marketplaceImportResult.value = "";
  try {
    const parsed = JSON.parse(jdSnapshotJson.value || "{}");
    const result = await cardFlipApi.ingestJdSnapshot(parsed);
    marketplaceImportResult.value = `Imported ${formatInteger(result?.inserted || 0)} jd offers from snapshot.`;
    await Promise.all([refreshMarketplaceLayer(), loadReportData()]);
    message.success(marketplaceImportResult.value);
  } catch (requestError) {
    const text = requestError instanceof Error ? requestError.message : "JD snapshot import failed.";
    marketplaceImportResult.value = text;
    message.error(text);
  } finally {
    jdSnapshotLoading.value = false;
  }
};

const syncJdOnce = async () => {
  jdSyncLoading.value = true;
  marketplaceImportResult.value = "";
  try {
    const result = await cardFlipApi.syncJdOnce({
      snapshot_url: jdSnapshotBridgeUrl.value || undefined,
    });
    marketplaceImportResult.value = `Synced ${formatInteger(result?.inserted || 0)} jd offers via open API.`;
    await Promise.all([refreshMarketplaceLayer(), loadReportData()]);
    message.success(marketplaceImportResult.value);
  } catch (requestError) {
    const text = requestError instanceof Error ? requestError.message : "JD sync failed.";
    marketplaceImportResult.value = text;
    message.error(text);
  } finally {
    jdSyncLoading.value = false;
  }
};

const backfillMarketplaceOffers = async () => {
  marketplaceBackfillLoading.value = true;
  marketplaceImportResult.value = "";
  try {
    const result = await cardFlipApi.backfillMarketplaceOffers({
      sources: "xianyu_monitor",
      limit: 500,
      listing_hours: 24 * 30,
    });
    marketplaceImportResult.value = `Backfilled ${formatInteger(result?.inserted || 0)} xianyu offers into marketplace_offers.`;
    await Promise.all([refreshMarketplaceLayer(), loadReportData()]);
    message.success(marketplaceImportResult.value);
  } catch (requestError) {
    const text = requestError instanceof Error ? requestError.message : "Marketplace backfill failed.";
    marketplaceImportResult.value = text;
    message.error(text);
  } finally {
    marketplaceBackfillLoading.value = false;
  }
};

const runMarketplaceShadowOnce = async () => {
  marketplaceShadowLoading.value = true;
  marketplaceImportResult.value = "";
  try {
    const result = await cardFlipApi.runMarketplaceShadowOnce();
    marketplaceImportResult.value = `Shadow run accepted ${formatInteger(result?.accepted_count || 0)} of ${formatInteger(result?.candidate_count || 0)} candidates.`;
    await refreshMarketplaceLayer();
    message.success(marketplaceImportResult.value);
  } catch (requestError) {
    const text = requestError instanceof Error ? requestError.message : "Marketplace shadow run failed.";
    marketplaceImportResult.value = text;
    message.error(text);
  } finally {
    marketplaceShadowLoading.value = false;
  }
};

const handleRefresh = async () => {
  await Promise.all([
    loadOverview(),
    loadPriceHistory(),
    loadReportData(),
    loadArbitrageData(),
  ]);
};

const openTradingWorkspace = () => {
  router.push("/admin/card-flip-ops");
};

const openServiceDrawer = (serviceId) => {
  selectedServiceId.value = serviceId;
  showServiceDrawer.value = true;
};

const runDashboardAction = async (action) => {
  if (!canOperate.value) {
    message.warning("Current account cannot operate services.");
    return;
  }

  actionLoading.value = action;
  try {
    if (action === "automation-start")
      await cardFlipApi.startAutomation();
    else if (action === "automation-stop")
      await cardFlipApi.stopAutomation();
    else if (action === "automation-run")
      await cardFlipApi.runAutomationOnce();
    else if (action === "monitor-start")
      await cardFlipApi.startMonitor();
    else if (action === "monitor-stop")
      await cardFlipApi.stopMonitor();
    else if (action === "monitor-run")
      await cardFlipApi.runMonitorOnce();

    await handleRefresh();
    message.success("Dashboard service action completed.");
  } catch (requestError) {
    message.error(requestError instanceof Error ? requestError.message : "Dashboard service action failed.");
  } finally {
    actionLoading.value = "";
  }
};

watch(activeRange, () => {
  void loadPriceHistory();
});

onMounted(() => {
  void loadPriceHistory();
  void loadReportData();
  void loadArbitrageData();
  void loadMarketplaceHealth();
  void loadMarketplaceProviderStatus();
  void loadMarketplaceShadow();
  void loadTaobaoProviderStatus();
  void loadPinduoduoProviderStatus();
  void loadJdProviderStatus();
});

function formatMoney(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

function formatInteger(value) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(Number(value || 0));
}

function formatPercent(value) {
  return `${new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(Number(value || 0) * 100)}%`;
}

function formatNumber(value, digits = 1) {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(Number(value || 0));
}

function formatAxisDate(value) {
  const parsed = new Date(String(value || ""));
  if (Number.isNaN(parsed.getTime()))
    return "Now";
  return parsed.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function compactTime(value) {
  const text = String(value || "").trim();
  if (!text)
    return "--";
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime()))
    return text;
  return parsed.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function compactHealth(value) {
  if (!value)
    return "None";
  if (typeof value === "string")
    return value;
  if (typeof value === "object") {
    const first = Object.entries(value).find(([_key, item]) => item !== null && item !== undefined);
    if (!first)
      return "None";
    return `${first[0]}:${first[1]}`;
  }
  return String(value);
}
</script>

<style scoped lang="scss">
.dashboard-page {
  display: grid;
  gap: 28px;
}

.hero-row {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 20px;
}

.hero-row h1 {
  color: var(--text-primary);
  font-size: 40px;
  font-weight: 800;
  letter-spacing: -0.05em;
}

.hero-row p {
  margin-top: 8px;
  color: var(--text-muted);
  font-size: 17px;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.hero-chip {
  height: 40px;
  padding: 0 16px;
  border-radius: var(--radius-full);
  border: 1px solid var(--surface-line);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.hero-chip.active {
  color: #fff;
  background: rgba(255, 255, 255, 0.1);
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 20px;
}

.metric-card,
.panel,
.service-row-card,
.network-panel,
.services-toolbar {
  border-radius: var(--radius-lg);
  background: var(--surface-card);
  border: 1px solid var(--surface-line);
  box-shadow: var(--shadow-medium);
}

.metric-card,
.panel,
.services-toolbar {
  padding: 24px;
}

.metric-card p {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.metric-value-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-top: 12px;
}

.metric-value {
  color: var(--text-primary);
  font-size: 36px;
  font-weight: 800;
  letter-spacing: -0.05em;
}

.metric-value.accent {
  color: #5eb2ff;
}

.metric-trailing {
  color: rgba(171, 199, 255, 0.55);
  font-size: 12px;
  font-weight: 700;
}

.analytics-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr);
  gap: 20px;
}

.arbitrage-panel {
  display: grid;
  gap: 18px;
}

.arbitrage-meta {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.arbitrage-stat,
.arbitrage-row {
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.arbitrage-stat {
  padding: 16px 18px;
}

.arbitrage-stat span {
  display: block;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.arbitrage-stat strong {
  display: block;
  margin-top: 8px;
  color: var(--text-primary);
  font-size: 24px;
  font-weight: 800;
}

.arbitrage-list {
  display: grid;
  gap: 14px;
}

.arbitrage-row {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(280px, 1fr);
  gap: 20px;
  padding: 18px 20px;
}

.arbitrage-main h4 {
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 700;
}

.arbitrage-main p {
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 13px;
}

.arbitrage-side {
  display: grid;
  gap: 10px;
}

.arbitrage-price-line {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--text-secondary);
  font-size: 13px;
}

.arbitrage-price-line strong {
  color: var(--text-primary);
  font-size: 14px;
}

.arbitrage-price-line.emphasis strong {
  color: #5eb2ff;
}

.arbitrage-empty {
  display: grid;
  gap: 8px;
  padding: 20px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px dashed rgba(255, 255, 255, 0.1);
}

.arbitrage-empty strong {
  color: var(--text-primary);
  font-size: 16px;
}

.arbitrage-empty span {
  color: var(--text-muted);
  line-height: 1.7;
}

.panel-head {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 16px;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.panel-head h3 {
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 700;
}

.panel-head p {
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 12px;
}

.panel-tag {
  padding: 6px 10px;
  border-radius: var(--radius-full);
  color: #5eb2ff;
  background: rgba(0, 113, 227, 0.12);
  border: 1px solid rgba(0, 113, 227, 0.22);
  font-size: 11px;
  font-weight: 700;
}

.chart-shell {
  position: relative;
  height: 280px;
  margin-top: 24px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  overflow: hidden;
}

.chart-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(to right, rgba(255, 255, 255, 0.04) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
  background-size: 72px 56px;
}

.chart-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.chart-empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: var(--text-muted);
  font-size: 14px;
}

.chart-corner {
  position: absolute;
  top: 14px;
  left: 14px;
  color: rgba(245, 247, 251, 0.55);
  font-size: 11px;
  font-weight: 700;
}

.chart-axis {
  position: absolute;
  left: 18px;
  right: 18px;
  bottom: 14px;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: rgba(245, 247, 251, 0.22);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.donut-wrap {
  display: flex;
  justify-content: center;
  margin: 28px 0;
}

.donut-chart {
  width: 180px;
  height: 180px;
  padding: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.donut-hole {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  text-align: center;
  border-radius: 50%;
  background: #161719;
}

.donut-hole strong {
  color: var(--text-primary);
  font-size: 20px;
  font-weight: 800;
}

.donut-hole span {
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.legend-list {
  display: grid;
  gap: 12px;
}

.legend-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--text-secondary);
  font-size: 12px;
}

.legend-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.legend-row strong {
  color: var(--text-primary);
  font-weight: 700;
}

.services-section {
  display: grid;
  gap: 20px;
}

.services-toolbar {
  position: sticky;
  top: 80px;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  background: rgba(27, 27, 27, 0.92);
  backdrop-filter: blur(16px);
}

.services-title {
  display: flex;
  align-items: end;
  gap: 10px;
}

.services-title h2 {
  color: var(--text-primary);
  font-size: 28px;
  font-weight: 700;
}

.services-title span {
  color: var(--text-muted);
  font-size: 17px;
  margin-bottom: 2px;
}

.services-controls {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.segmented-control {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.segmented-button {
  height: 34px;
  padding: 0 14px;
  border-radius: var(--radius-full);
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 600;
}

.segmented-button.active {
  color: #fff;
  background: rgba(255, 255, 255, 0.08);
}

.sort-shell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 200px;
  padding: 6px 14px;
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.05);
  color: var(--text-muted);
  font-size: 12px;
}

.sort-shell :deep(.n-base-selection) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}

.sort-shell :deep(.n-base-selection-label) {
  color: rgba(245, 247, 251, 0.82) !important;
}

.sort-shell :deep(.n-base-selection-placeholder) {
  color: rgba(245, 247, 251, 0.42) !important;
}

.service-stack {
  display: grid;
  gap: 20px;
}

.service-row-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  overflow: hidden;
}

.service-main {
  padding: 28px;
  border-right: 1px solid var(--surface-line);
}

.service-header {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 16px;
}

.service-title-line {
  display: flex;
  align-items: center;
  gap: 10px;
}

.service-title-line h3 {
  color: var(--text-primary);
  font-size: 22px;
  font-weight: 700;
}

.service-badge {
  padding: 4px 8px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.service-badge.positive {
  color: var(--success-color);
  background: rgba(52, 211, 153, 0.12);
}

.service-badge.warning {
  color: var(--warning-color);
  background: rgba(245, 158, 11, 0.12);
}

.service-badge.neutral {
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.08);
}

.service-status-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 14px;
}

.service-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.service-dot.positive {
  background: var(--success-color);
}

.service-dot.warning {
  background: var(--warning-color);
}

.service-dot.neutral {
  background: rgba(255, 255, 255, 0.2);
}

.service-round-button {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.service-mini-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 24px;
}

.mini-metric {
  padding: 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.04);
}

.mini-metric p {
  color: rgba(245, 247, 251, 0.3);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.mini-metric strong {
  display: block;
  margin-top: 10px;
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 700;
}

.service-placeholder-row {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 64px;
  margin-top: 24px;
  border-radius: 18px;
  border: 1px dashed rgba(255, 255, 255, 0.08);
  color: rgba(245, 247, 251, 0.24);
  font-size: 12px;
  font-style: italic;
}

.service-side {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding: 28px;
  text-align: center;
  background: rgba(0, 0, 0, 0.18);
}

.side-icon-shell {
  width: 60px;
  height: 60px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: rgba(245, 247, 251, 0.2);
  background: rgba(255, 255, 255, 0.04);
  border: 1px dashed rgba(255, 255, 255, 0.12);
}

.side-label {
  color: rgba(245, 247, 251, 0.58);
  font-size: 14px;
  font-weight: 600;
}

.side-value {
  color: rgba(245, 247, 251, 0.22);
  font-size: 12px;
}

.side-link {
  color: #5eb2ff;
  font-size: 14px;
  font-weight: 600;
}

.network-panel {
  position: relative;
  overflow: hidden;
  min-height: 380px;
  padding: 32px;
  background: linear-gradient(180deg, rgba(8, 9, 11, 0.88), rgba(10, 11, 14, 0.98));
}

.network-overlay {
  position: absolute;
  inset: 0;
  opacity: 0.34;
  background:
    radial-gradient(circle at 30% 60%, rgba(0, 113, 227, 0.22), transparent 35%),
    repeating-linear-gradient(
      165deg,
      transparent 0 18px,
      rgba(0, 113, 227, 0.09) 18px 20px,
      transparent 20px 42px
    );
  transform: scale(1.05);
}

.network-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;
}

.network-content h2 {
  color: var(--text-primary);
  font-size: 22px;
  font-weight: 700;
}

.network-content p {
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 14px;
}

.network-stats {
  display: flex;
  gap: 32px;
  margin-top: 220px;
}

.network-stat {
  display: flex;
  align-items: center;
  gap: 14px;
}

.network-stat::before {
  content: "";
  width: 4px;
  height: 32px;
  border-radius: 999px;
  background: linear-gradient(180deg, #0071e3, #34d399);
}

.network-stat span {
  display: block;
  color: rgba(245, 247, 251, 0.36);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.network-stat strong {
  display: block;
  margin-top: 4px;
  color: var(--text-primary);
  font-size: 20px;
  font-weight: 700;
}

.drawer-stack {
  display: grid;
  gap: 18px;
}

.drawer-hero {
  padding: 18px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.04);
}

.drawer-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.drawer-status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.drawer-status-dot.positive {
  background: var(--success-color);
}

.drawer-status-dot.warning {
  background: var(--warning-color);
}

.drawer-status-dot.neutral {
  background: rgba(255, 255, 255, 0.28);
}

.drawer-hero p {
  margin-top: 12px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.drawer-list {
  display: grid;
  gap: 10px;
}

.drawer-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.04);
}

.drawer-row span {
  color: var(--text-secondary);
}

.drawer-row strong {
  color: var(--text-primary);
}

.drawer-actions {
  display: flex;
  gap: 10px;
}

@media (max-width: 1200px) {
  .metrics-grid,
  .analytics-grid {
    grid-template-columns: 1fr;
  }

  .service-row-card {
    grid-template-columns: 1fr;
  }

  .service-main {
    border-right: none;
    border-bottom: 1px solid var(--surface-line);
  }
}

@media (max-width: 900px) {
  .hero-row,
  .services-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .metrics-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .arbitrage-meta {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .arbitrage-row {
    grid-template-columns: 1fr;
  }

  .service-mini-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .hero-row h1 {
    font-size: 32px;
  }

  .metrics-grid {
    grid-template-columns: 1fr;
  }

  .services-title {
    flex-direction: column;
    align-items: flex-start;
  }

  .network-stats {
    flex-direction: column;
    gap: 16px;
    margin-top: 180px;
  }
}
</style>
