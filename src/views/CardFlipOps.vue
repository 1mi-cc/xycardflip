<template>
  <div class="card-flip-page">
    <section class="hero">
      <div>
        <h1>卡片倒卖助手</h1>
        <p>机会扫描、人工审批、交易流转全流程</p>
      </div>
      <n-space>
        <n-input-number v-model:value="scanLimit" :min="1" :max="500" />
        <n-button type="primary" :loading="scanLoading" @click="runScan">
          扫描机会
        </n-button>
        <n-select
          v-model:value="pricingMode"
          :options="pricingModeOptions"
          style="width: 160px"
        />
        <n-button :loading="batchPricingLoading" @click="previewBatchReprice">
          批量预览定价
        </n-button>
        <n-button type="warning" :loading="batchPricingLoading" @click="applyBatchReprice">
          批量应用定价
        </n-button>
        <n-button :loading="loading" @click="loadData">刷新</n-button>
      </n-space>
    </section>

    <section class="stats">
      <div class="stat-card">
        <div class="label">待审核</div>
        <div class="value">{{ metrics.pending_review_count }}</div>
      </div>
      <div class="stat-card">
        <div class="label">进行中交易</div>
        <div class="value">{{ metrics.active_trades_count }}</div>
      </div>
      <div class="stat-card">
        <div class="label">已卖出</div>
        <div class="value">{{ metrics.sold_count }}</div>
      </div>
      <div class="stat-card warning">
        <div class="label">风控拦截</div>
        <div class="value">{{ blockedOpportunities.length }}</div>
      </div>
      <div class="stat-card profit">
        <div class="label">累计毛利</div>
        <div class="value">¥{{ toMoney(metrics.gross_profit) }}</div>
      </div>
    </section>

    <n-tabs type="line" animated>
      <n-tab-pane name="opportunities" tab="待审核机会">
        <n-card :bordered="false" class="table-card">
          <n-spin :show="loading">
            <div v-if="opportunities.length === 0" class="empty-wrap">
              <n-empty description="暂无待审核机会" />
            </div>
            <n-table v-else striped>
              <thead>
                <tr>
                  <th>标题</th>
                  <th>当前价</th>
                  <th>预估售价</th>
                  <th>预估利润</th>
                  <th>ROI</th>
                  <th>评分</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in opportunities" :key="item.opportunity_id">
                  <td class="title-cell">{{ item.title }}</td>
                  <td>¥{{ toMoney(item.list_price) }}</td>
                  <td>¥{{ toMoney(item.expected_sale_price) }}</td>
                  <td :class="{ good: item.expected_profit > 0 }">
                    ¥{{ toMoney(item.expected_profit) }}
                  </td>
                  <td :class="{ good: item.roi > 0 }">{{ toPercent(item.roi) }}</td>
                  <td>{{ item.score }}</td>
                  <td>
                    <n-space>
                      <n-button size="small" @click="openListing(item)">
                        查看商品
                      </n-button>
                      <n-button size="small" type="primary" @click="openApprove(item)">
                        审批买入
                      </n-button>
                      <n-button
                        size="small"
                        tertiary
                        type="error"
                        @click="reject(item)"
                      >
                        忽略
                      </n-button>
                    </n-space>
                  </td>
                </tr>
              </tbody>
            </n-table>
          </n-spin>
        </n-card>
      </n-tab-pane>

      <n-tab-pane name="blockedRisk" tab="风控拦截">
        <n-card :bordered="false" class="table-card">
          <n-spin :show="loading">
            <n-space style="margin-bottom: 12px">
              <n-input-number
                v-model:value="blockedRiskThreshold"
                :min="0"
                :max="100"
                :step="1"
                style="width: 180px"
                placeholder="风险分阈值"
              />
              <n-button
                type="primary"
                :loading="blockedBatchLoading"
                :disabled="blockedOpportunities.length === 0"
                @click="sendBlockedBatchToReview"
              >
                风险分<=阈值批量复核
              </n-button>
            </n-space>
            <div v-if="blockedOpportunities.length === 0" class="empty-wrap">
              <n-empty description="暂无风控拦截机会" />
            </div>
            <n-table v-else striped>
              <thead>
                <tr>
                  <th>标题</th>
                  <th>当前价</th>
                  <th>预估售价</th>
                  <th>评分</th>
                  <th>风险分</th>
                  <th>风险等级</th>
                  <th>风险原因</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in blockedOpportunities" :key="item.opportunity_id">
                  <td class="title-cell">{{ item.title }}</td>
                  <td>¥{{ toMoney(item.list_price) }}</td>
                  <td>¥{{ toMoney(item.expected_sale_price) }}</td>
                  <td>{{ item.score }}</td>
                  <td>{{ item.risk.score ?? "-" }}</td>
                  <td>
                    <n-tag size="small" :type="getRiskLevelType(item.risk.level)">
                      {{ getRiskLevelText(item.risk.level) }}
                    </n-tag>
                  </td>
                  <td>
                    <n-space v-if="item.risk.reasons.length > 0" size="small">
                      <n-tag
                        v-for="reason in item.risk.reasons"
                        :key="`${item.opportunity_id}-${reason}`"
                        size="small"
                        type="warning"
                      >
                        {{ getRiskReasonText(reason) }}
                      </n-tag>
                    </n-space>
                    <span v-else>-</span>
                  </td>
                  <td>
                    <n-space>
                      <n-button size="small" @click="openListing(item)">
                        查看商品
                      </n-button>
                      <n-button size="small" type="primary" @click="sendToReview(item)">
                        申请复核
                      </n-button>
                      <n-button size="small" tertiary type="error" @click="reject(item)">
                        忽略
                      </n-button>
                    </n-space>
                  </td>
                </tr>
              </tbody>
            </n-table>
          </n-spin>
        </n-card>
      </n-tab-pane>

      <n-tab-pane name="activeTrades" tab="进行中交易">
        <n-card :bordered="false" class="table-card">
          <n-spin :show="loading">
            <div v-if="activeTrades.length === 0" class="empty-wrap">
              <n-empty description="暂无进行中交易" />
            </div>
            <n-table v-else striped>
              <thead>
                <tr>
                  <th>标题</th>
                  <th>买入价</th>
                  <th>目标卖价</th>
                  <th>状态</th>
                  <th>上架链接</th>
                  <th>智能定价</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="trade in activeTrades" :key="trade.trade_id">
                  <td class="title-cell">{{ trade.title }}</td>
                  <td>¥{{ toMoney(trade.approved_buy_price) }}</td>
                  <td>¥{{ toMoney(trade.target_sell_price) }}</td>
                  <td>{{ trade.status }}</td>
                  <td class="title-cell">
                    {{ trade.listing_url || "-" }}
                  </td>
                  <td>
                    <div v-if="getPricingPreview(trade.trade_id)" class="pricing-preview">
                      <div class="pricing-main">
                        ¥{{ toMoney(getPricingPreview(trade.trade_id).recommended_price) }}
                        <n-tag size="small" :type="getActionType(getPricingPreview(trade.trade_id).action)">
                          {{ getActionText(getPricingPreview(trade.trade_id).action) }}
                        </n-tag>
                      </div>
                      <div class="pricing-sub">
                        紧急度:
                        <n-tag size="small" :type="getUrgencyType(getPricingPreview(trade.trade_id).urgency)">
                          {{ getUrgencyText(getPricingPreview(trade.trade_id).urgency) }}
                        </n-tag>
                      </div>
                    </div>
                    <span v-else>-</span>
                  </td>
                  <td>
                    <n-space vertical size="small">
                      <n-space>
                        <n-button
                          v-if="trade.status === 'approved_for_buy'"
                          size="small"
                          type="primary"
                          @click="openMarkListed(trade)"
                        >
                          标记已挂售
                        </n-button>
                        <n-button
                          size="small"
                          :type="trade.status === 'approved_for_buy' ? 'default' : 'success'"
                          @click="openMarkSold(trade)"
                        >
                          标记已卖出
                        </n-button>
                      </n-space>
                      <n-space>
                        <n-button
                          size="small"
                          tertiary
                          :loading="pricingLoadingTradeId === trade.trade_id && pricingAction === 'preview'"
                          @click="previewTradePricing(trade)"
                        >
                          预览定价
                        </n-button>
                        <n-button
                          size="small"
                          type="warning"
                          :loading="pricingLoadingTradeId === trade.trade_id && pricingAction === 'apply'"
                          @click="applyTradePricing(trade)"
                        >
                          应用建议价
                        </n-button>
                      </n-space>
                    </n-space>
                  </td>
                </tr>
              </tbody>
            </n-table>
          </n-spin>
        </n-card>
      </n-tab-pane>

      <n-tab-pane name="soldTrades" tab="已卖出记录">
        <n-card :bordered="false" class="table-card">
          <n-spin :show="loading">
            <div v-if="soldTrades.length === 0" class="empty-wrap">
              <n-empty description="暂无已卖出记录" />
            </div>
            <n-table v-else striped>
              <thead>
                <tr>
                  <th>标题</th>
                  <th>买入价</th>
                  <th>卖出价</th>
                  <th>毛利</th>
                  <th>更新时间</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="trade in soldTrades" :key="trade.trade_id">
                  <td class="title-cell">{{ trade.title }}</td>
                  <td>¥{{ toMoney(trade.approved_buy_price) }}</td>
                  <td>¥{{ toMoney(trade.sold_price) }}</td>
                  <td :class="{ good: (trade.sold_price || 0) > (trade.approved_buy_price || 0) }">
                    ¥{{ toMoney((trade.sold_price || 0) - (trade.approved_buy_price || 0)) }}
                  </td>
                  <td>{{ trade.updated_at }}</td>
                </tr>
              </tbody>
            </n-table>
          </n-spin>
        </n-card>
      </n-tab-pane>
    </n-tabs>

    <n-modal
      v-model:show="approveModalVisible"
      preset="dialog"
      title="审批买入"
      positive-text="确认审批"
      negative-text="取消"
      :positive-button-props="{ loading: approving }"
      @positive-click="submitApprove"
    >
      <n-form label-placement="left" :label-width="90">
        <n-form-item label="机会ID">
          <n-input :value="String(approveForm.opportunity_id || '')" disabled />
        </n-form-item>
        <n-form-item label="审批买入价">
          <n-input-number
            v-model:value="approveForm.approved_buy_price"
            :min="0.01"
            :precision="2"
            style="width: 100%"
          />
        </n-form-item>
        <n-form-item label="审批人">
          <n-input v-model:value="approveForm.approved_by" />
        </n-form-item>
        <n-form-item label="备注">
          <n-input v-model:value="approveForm.note" type="textarea" />
        </n-form-item>
      </n-form>
    </n-modal>

    <n-modal
      v-model:show="markListedModalVisible"
      preset="dialog"
      title="标记已挂售"
      positive-text="确认"
      negative-text="取消"
      :positive-button-props="{ loading: markListedLoading }"
      @positive-click="submitMarkListed"
    >
      <n-form label-placement="left" :label-width="90">
        <n-form-item label="交易ID">
          <n-input :value="String(markListedForm.trade_id || '')" disabled />
        </n-form-item>
        <n-form-item label="挂售链接">
          <n-input v-model:value="markListedForm.listing_url" placeholder="https://..." />
        </n-form-item>
        <n-form-item label="备注">
          <n-input v-model:value="markListedForm.note" type="textarea" />
        </n-form-item>
      </n-form>
    </n-modal>

    <n-modal
      v-model:show="markSoldModalVisible"
      preset="dialog"
      title="标记已卖出"
      positive-text="确认"
      negative-text="取消"
      :positive-button-props="{ loading: markSoldLoading }"
      @positive-click="submitMarkSold"
    >
      <n-form label-placement="left" :label-width="90">
        <n-form-item label="交易ID">
          <n-input :value="String(markSoldForm.trade_id || '')" disabled />
        </n-form-item>
        <n-form-item label="卖出价格">
          <n-input-number
            v-model:value="markSoldForm.sold_price"
            :min="0.01"
            :precision="2"
            style="width: 100%"
          />
        </n-form-item>
        <n-form-item label="备注">
          <n-input v-model:value="markSoldForm.note" type="textarea" />
        </n-form-item>
      </n-form>
    </n-modal>

    <n-modal
      v-model:show="pricingPlanModalVisible"
      preset="card"
      title="智能定价建议"
      style="width: 90%; max-width: 760px"
    >
      <div v-if="pricingPlanPayload">
        <n-descriptions bordered :column="2" label-placement="left">
          <n-descriptions-item label="交易ID">
            {{ pricingPlanPayload.trade_id }}
          </n-descriptions-item>
          <n-descriptions-item label="模式">
            {{ getModeText(pricingPlanPayload.mode) }}
          </n-descriptions-item>
          <n-descriptions-item label="当前目标卖价">
            ¥{{ toMoney(pricingPlanPayload.plan.current_target_price) }}
          </n-descriptions-item>
          <n-descriptions-item label="建议卖价">
            ¥{{ toMoney(pricingPlanPayload.plan.recommended_price) }}
          </n-descriptions-item>
          <n-descriptions-item label="建议动作">
            <n-tag :type="getActionType(pricingPlanPayload.plan.action)">
              {{ getActionText(pricingPlanPayload.plan.action) }}
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="紧急度">
            <n-tag :type="getUrgencyType(pricingPlanPayload.plan.urgency)">
              {{ getUrgencyText(pricingPlanPayload.plan.urgency) }}
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="持仓天数">
            {{ pricingPlanPayload.plan.holding_days }}
          </n-descriptions-item>
          <n-descriptions-item label="参考成交数">
            {{ pricingPlanPayload.plan.similar_sales_count }}
          </n-descriptions-item>
          <n-descriptions-item label="价格下限">
            ¥{{ toMoney(pricingPlanPayload.plan.price_floor) }}
          </n-descriptions-item>
          <n-descriptions-item label="价格上限">
            ¥{{ toMoney(pricingPlanPayload.plan.price_ceiling) }}
          </n-descriptions-item>
        </n-descriptions>
        <div class="pricing-reasons">
          <div class="pricing-title">策略解释</div>
          <n-space>
            <n-tag
              v-for="reason in pricingPlanPayload.plan.reasons"
              :key="reason"
              size="small"
              type="info"
            >
              {{ reason }}
            </n-tag>
          </n-space>
        </div>
      </div>
    </n-modal>

    <n-modal
      v-model:show="batchPricingModalVisible"
      preset="card"
      title="批量重定价预览"
      style="width: 95%; max-width: 960px"
    >
      <n-space vertical>
        <div class="batch-summary" v-if="batchPricingResult">
          模式: {{ getModeText(batchPricingResult.mode) }} |
          已处理: {{ batchPricingResult.processed }} |
          已更新: {{ batchPricingResult.updated }} |
          当前为{{ batchPricingResult.apply ? "应用结果" : "预览结果" }}
        </div>
        <n-table
          v-if="batchPricingResult && batchPricingResult.items && batchPricingResult.items.length > 0"
          striped
          size="small"
        >
          <thead>
            <tr>
              <th>交易ID</th>
              <th>标题</th>
              <th>当前价</th>
              <th>建议价</th>
              <th>动作</th>
              <th>紧急度</th>
              <th>持仓天数</th>
              <th>是否已应用</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in batchPricingResult.items" :key="item.trade_id">
              <td>{{ item.trade_id }}</td>
              <td class="title-cell">{{ item.title }}</td>
              <td>¥{{ toMoney(item.current_target_price) }}</td>
              <td>¥{{ toMoney(item.recommended_price) }}</td>
              <td>
                <n-tag size="small" :type="getActionType(item.action)">
                  {{ getActionText(item.action) }}
                </n-tag>
              </td>
              <td>
                <n-tag size="small" :type="getUrgencyType(item.urgency)">
                  {{ getUrgencyText(item.urgency) }}
                </n-tag>
              </td>
              <td>{{ item.holding_days }}</td>
              <td>{{ item.applied ? "是" : "否" }}</td>
            </tr>
          </tbody>
        </n-table>
        <n-empty v-else description="暂无重定价结果" />
      </n-space>
    </n-modal>

    <n-modal
      v-model:show="listingModalVisible"
      preset="card"
      title="商品信息"
      style="width: 90%; max-width: 760px"
    >
      <n-spin :show="listingLoading">
        <div v-if="listingPayload">
          <n-descriptions bordered :column="2" label-placement="left">
            <n-descriptions-item label="标题">
              {{ listingPayload.title }}
            </n-descriptions-item>
            <n-descriptions-item label="当前价">
              楼{{ toMoney(listingPayload.list_price) }}
            </n-descriptions-item>
            <n-descriptions-item label="来源">
              {{ listingPayload.source || "-" }}
            </n-descriptions-item>
            <n-descriptions-item label="状态">
              {{ listingPayload.status || "-" }}
            </n-descriptions-item>
            <n-descriptions-item label="卖家ID">
              {{ listingPayload.seller_id || "-" }}
            </n-descriptions-item>
            <n-descriptions-item label="上架时间">
              {{ listingPayload.listed_at || "-" }}
            </n-descriptions-item>
            <n-descriptions-item label="商品ID">
              {{ listingPayload.listing_id || "-" }}
            </n-descriptions-item>
            <n-descriptions-item label="链接">
              <span v-if="listingPayload.listing_url">
                <a :href="listingPayload.listing_url" target="_blank" rel="noreferrer">打开链接</a>
              </span>
              <span v-else>-</span>
            </n-descriptions-item>
          </n-descriptions>
          <div class="listing-description">
            <div class="listing-label">描述</div>
            <div class="listing-text">
              {{ listingPayload.description || "-" }}
            </div>
          </div>
          <div class="listing-raw" v-if="rawListingJson">
            <div class="listing-label">原始数据</div>
            <pre>{{ rawListingJson }}</pre>
          </div>
        </div>
      </n-spin>
    </n-modal>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useMessage } from "naive-ui";
import cardFlipApi from "@/api/cardFlip";

const message = useMessage();

const loading = ref(false);
const scanLoading = ref(false);
const approving = ref(false);
const markListedLoading = ref(false);
const markSoldLoading = ref(false);
const batchPricingLoading = ref(false);
const blockedBatchLoading = ref(false);
const pricingLoadingTradeId = ref(null);
const pricingAction = ref("");

const scanLimit = ref(100);
const blockedRiskThreshold = ref(45);
const pricingMode = ref("balanced");
const pricingModeOptions = [
  { label: "平衡模式", value: "balanced" },
  { label: "快速出货", value: "fast_exit" },
  { label: "利润优先", value: "profit_max" },
];

const opportunities = ref([]);
const blockedOpportunities = ref([]);
const activeTrades = ref([]);
const soldTrades = ref([]);
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
const getModeText = (mode) => ({
  balanced: "平衡模式",
  fast_exit: "快速出货",
  profit_max: "利润优先",
}[mode] || mode);
const getActionText = (action) => ({
  set: "设置",
  raise: "上调",
  lower: "下调",
  keep: "保持",
}[action] || action);
const getActionType = (action) => ({
  set: "info",
  raise: "success",
  lower: "warning",
  keep: "default",
}[action] || "default");
const getUrgencyText = (urgency) => ({
  high: "高",
  medium: "中",
  low: "低",
}[urgency] || urgency);
const getUrgencyType = (urgency) => ({
  high: "error",
  medium: "warning",
  low: "success",
}[urgency] || "default");
const getPricingPreview = (tradeId) => pricingPreviewMap.value[tradeId] || null;
const getRiskLevelType = (level) => ({
  high: "error",
  medium: "warning",
  low: "success",
}[level] || "default");
const getRiskLevelText = (level) => ({
  high: "高风险",
  medium: "中风险",
  low: "低风险",
}[level] || "未知");
const riskReasonTextMap = {
  list_price_above_buy_limit: "当前价高于买入上限",
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
  if (!listingPayload.value)
    return "";
  const raw = listingPayload.value.raw_json;
  if (raw == null)
    return "";
  if (typeof raw === "string")
    return raw;
  try {
    return JSON.stringify(raw, null, 2);
  } catch {
    return String(raw);
  }
});

const cachePricingItems = (items = []) => {
  const merged = { ...pricingPreviewMap.value };
  for (const item of items) {
    merged[item.trade_id] = item;
  }
  pricingPreviewMap.value = merged;
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
  const segments = note.split(";").map((seg) => seg.trim()).filter(Boolean);
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
      parsed.reasons = value && value !== "none"
        ? value.split(",").map((v) => v.trim()).filter(Boolean)
        : [];
    }
  }
  return parsed;
};

const loadData = async () => {
  loading.value = true;
  try {
    const [oppsRes, blockedRes, activeRes, listedRes, soldRes, metricsRes] = await Promise.all([
      cardFlipApi.listOpportunities("pending_review", 200),
      cardFlipApi.listOpportunities("blocked_risk", 200),
      cardFlipApi.listTrades("approved_for_buy", 200),
      cardFlipApi.listTrades("listed_for_sale", 200),
      cardFlipApi.listTrades("sold", 200),
      cardFlipApi.getMetrics(),
    ]);

    opportunities.value = oppsRes.items || [];
    blockedOpportunities.value = (blockedRes.items || []).map((item) => ({
      ...item,
      risk: parseRiskNote(item.risk_note),
    }));
    activeTrades.value = [...(activeRes.items || []), ...(listedRes.items || [])];
    soldTrades.value = soldRes.items || [];
    metrics.value = metricsRes;
  } catch (error) {
    message.error(`加载失败: ${error.message}`);
  } finally {
    loading.value = false;
  }
};

const runScan = async () => {
  scanLoading.value = true;
  try {
    const res = await cardFlipApi.scanOpportunities(scanLimit.value);
    message.success(
      `扫描完成: 处理 ${res.processed} 条, 待审核 ${res.pending_review} 条, 风控拦截 ${res.blocked_risk || 0} 条`,
    );
    await loadData();
  } catch (error) {
    message.error(`扫描失败: ${error.message}`);
  } finally {
    scanLoading.value = false;
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
  if (!approveForm.value.opportunity_id || approveForm.value.approved_buy_price <= 0) {
    message.warning("请填写有效的审批价格");
    return false;
  }
  approving.value = true;
  try {
    const res = await cardFlipApi.approveTrade(approveForm.value);
    message.success(
      `审批成功，交易ID: ${res.trade_id}，建议挂价: ¥${toMoney(res.target_sell_price)}`,
    );
    approveModalVisible.value = false;
    await loadData();
    return true;
  } catch (error) {
    message.error(`审批失败: ${error.message}`);
    return false;
  } finally {
    approving.value = false;
  }
};

const reject = async (item) => {
  try {
    await cardFlipApi.rejectOpportunity(item.opportunity_id);
    message.success(`已忽略机会 #${item.opportunity_id}`);
    await loadData();
  } catch (error) {
    message.error(`忽略失败: ${error.message}`);
  }
};

const sendToReview = async (item) => {
  try {
    await cardFlipApi.sendOpportunityToReview(
      item.opportunity_id,
      "manual review from blocked list",
    );
    message.success(`机会 #${item.opportunity_id} 已移入待审核`);
    await loadData();
  } catch (error) {
    message.error(`申请复核失败: ${error.message}`);
  }
};

const openListing = async (item) => {
  listingLoading.value = true;
  listingModalVisible.value = true;
  try {
    listingPayload.value = await cardFlipApi.getListing(item.listing_row_id);
  } catch (error) {
    message.error(`获取商品信息失败: ${error.message}`);
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
  if (!window.confirm(`确认将风险分 <= ${blockedRiskThreshold.value} 的拦截机会批量移入待审核？`)) {
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
    await loadData();
  } catch (error) {
    message.error(`批量复核失败: ${error.message}`);
  } finally {
    blockedBatchLoading.value = false;
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
    await loadData();
    return true;
  } catch (error) {
    message.error(`更新失败: ${error.message}`);
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
    await loadData();
    return true;
  } catch (error) {
    message.error(`更新失败: ${error.message}`);
    return false;
  } finally {
    markSoldLoading.value = false;
  }
};

const previewTradePricing = async (trade) => {
  pricingLoadingTradeId.value = trade.trade_id;
  pricingAction.value = "preview";
  try {
    const payload = await cardFlipApi.getTradePricingPlan(trade.trade_id, pricingMode.value);
    pricingPlanPayload.value = payload;
    pricingPlanModalVisible.value = true;
    cachePricingItems([{
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
    }]);
  } catch (error) {
    message.error(`获取定价建议失败: ${error.message}`);
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
      message.success(`交易 #${trade.trade_id} 已应用建议价 ¥${toMoney(res.recommended_price)}`);
    } else {
      message.info(`交易 #${trade.trade_id} 当前价已接近建议价，保持不变`);
    }
    await loadData();
  } catch (error) {
    message.error(`应用建议价失败: ${error.message}`);
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
    message.success(`预览完成: 处理 ${res.processed} 条，建议调整 ${res.items?.filter((v) => v.action !== "keep").length || 0} 条`);
  } catch (error) {
    message.error(`批量预览失败: ${error.message}`);
  } finally {
    batchPricingLoading.value = false;
  }
};

const applyBatchReprice = async () => {
  if (!window.confirm("确认按当前模式批量应用建议价？该操作会更新进行中交易的目标卖价。")) {
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
    message.success(`批量应用完成: 处理 ${res.processed} 条，更新 ${res.updated} 条`);
    await loadData();
  } catch (error) {
    message.error(`批量应用失败: ${error.message}`);
  } finally {
    batchPricingLoading.value = false;
  }
};

onMounted(loadData);
</script>

<style scoped lang="scss">
.card-flip-page {
  padding: var(--spacing-xl);
  background: var(--bg-secondary);
  min-height: calc(100vh - 64px);
}

.hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
  padding: var(--spacing-lg);
  border-radius: var(--border-radius-large);
  background: linear-gradient(120deg, #0b6d5d 0%, #2f8f80 45%, #71bda8 100%);
  color: #fff;
}

.hero h1 {
  margin: 0 0 8px;
  font-size: 28px;
}

.hero p {
  margin: 0;
  opacity: 0.95;
}

.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

.stat-card {
  background: var(--bg-primary);
  border-radius: var(--border-radius-large);
  padding: var(--spacing-md);
  box-shadow: var(--shadow-light);
}

.stat-card .label {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}

.stat-card .value {
  margin-top: 8px;
  color: var(--text-primary);
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
}

.stat-card.profit .value {
  color: #0e8d67;
}

.stat-card.warning .value {
  color: #d46b08;
}

.table-card {
  border-radius: var(--border-radius-large);
}

.empty-wrap {
  padding: 20px 0;
}

.title-cell {
  max-width: 360px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pricing-preview {
  min-width: 170px;
}

.pricing-main {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.pricing-sub {
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
}

.pricing-reasons {
  margin-top: 12px;
}

.pricing-title {
  margin-bottom: 8px;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}

.listing-description,
.listing-raw {
  margin-top: 16px;
}

.listing-label {
  margin-bottom: 6px;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}

.listing-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
}

.listing-raw pre {
  max-height: 280px;
  overflow: auto;
  padding: 12px;
  border-radius: 8px;
  background: #f7f7f9;
  font-size: 12px;
  line-height: 1.5;
}

.batch-summary {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}

.good {
  color: #0e8d67;
  font-weight: 600;
}

@media (max-width: 768px) {
  .card-flip-page {
    padding: var(--spacing-md);
  }

  .hero {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
