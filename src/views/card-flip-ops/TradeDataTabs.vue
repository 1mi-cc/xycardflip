<template>
  <n-tabs
    :value="activeTab"
    type="line"
    animated
    @update:value="value => $emit('update:activeTab', value)"
  >
    <n-tab-pane name="opportunities" tab="待审核机会">
      <n-card :bordered="false" class="table-card">
        <div class="tab-panel-head">
          <div>
            <div class="section-title">待审核机会</div>
            <div class="section-subtitle">
              这里保留人工审批与忽略入口，先看标的，再决定是否入场。
            </div>
          </div>
          <n-tag size="small" type="info">{{ opportunities.length }} 条</n-tag>
        </div>

        <n-spin :show="loading || listsLoading">
          <div v-if="opportunities.length === 0" class="empty-wrap">
            <n-empty description="暂无待审核机会" />
          </div>

          <n-table v-else striped class="ops-table">
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
                <td>￥{{ toMoney(item.list_price) }}</td>
                <td>￥{{ toMoney(item.expected_sale_price) }}</td>
                <td :class="{ good: item.expected_profit > 0 }">
                  ￥{{ toMoney(item.expected_profit) }}
                </td>
                <td :class="{ good: item.roi > 0 }">{{ toPercent(item.roi) }}</td>
                <td>{{ item.score }}</td>
                <td>
                  <n-space>
                    <n-button size="small" @click="$emit('openListing', item)">
                      查看商品
                    </n-button>
                    <n-button
                      size="small"
                      type="primary"
                      @click="$emit('openApprove', item)"
                    >
                      审批买入
                    </n-button>
                    <n-button
                      size="small"
                      tertiary
                      type="error"
                      @click="$emit('reject', item)"
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
        <div class="tab-panel-head">
          <div>
            <div class="section-title">风控拦截</div>
            <div class="section-subtitle">
              支持阈值复核或一键忽略，用来清理风险可控的候选机会。
            </div>
          </div>
          <n-tag size="small" type="warning">{{ blockedOpportunities.length }} 条</n-tag>
        </div>

        <n-spin :show="loading || listsLoading">
          <div class="table-toolbar">
            <n-input-number
              :value="blockedRiskThreshold"
              :min="0"
              :max="100"
              :step="1"
              style="width: 180px"
              placeholder="复核风险阈值"
              @update:value="value => $emit('update:blockedRiskThreshold', value)"
            />
            <n-button
              type="primary"
              :loading="blockedBatchLoading"
              :disabled="blockedOpportunities.length === 0"
              @click="$emit('sendBlockedBatchToReview')"
            >
              阈值内批量复核
            </n-button>
            <n-button
              type="error"
              tertiary
              :loading="blockedRejectBatchLoading"
              :disabled="blockedOpportunities.length === 0"
              @click="$emit('rejectBlockedBatch')"
            >
              一键忽略
            </n-button>
          </div>

          <div v-if="blockedOpportunities.length === 0" class="empty-wrap">
            <n-empty description="暂无风控拦截机会" />
          </div>

          <n-table v-else striped class="ops-table">
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
                <td>￥{{ toMoney(item.list_price) }}</td>
                <td>￥{{ toMoney(item.expected_sale_price) }}</td>
                <td>{{ item.score }}</td>
                <td>{{ item.risk.score ?? "-" }}</td>
                <td>
                  <n-tag size="small" :type="getRiskLevelType(item.risk.level)">
                    {{ getRiskLevelText(item.risk.level) }}
                  </n-tag>
                </td>
                <td>
                  <n-space
                    v-if="item.risk.reasons.length > 0"
                    class="risk-reason-list"
                    size="small"
                    wrap
                  >
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
                    <n-button size="small" @click="$emit('openListing', item)">
                      查看商品
                    </n-button>
                    <n-button
                      size="small"
                      type="primary"
                      @click="$emit('sendToReview', item)"
                    >
                      申请复核
                    </n-button>
                    <n-button
                      size="small"
                      tertiary
                      type="error"
                      @click="$emit('reject', item)"
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

    <n-tab-pane name="activeTrades" tab="进行中交易">
      <n-card :bordered="false" class="table-card">
        <div class="tab-panel-head">
          <div>
            <div class="section-title">进行中交易</div>
            <div class="section-subtitle">
              集中处理买入、上架、卖出和智能定价，不再把动作散落在主面板。
            </div>
          </div>
          <n-tag size="small" type="success">{{ activeTrades.length }} 条</n-tag>
        </div>

        <n-spin :show="loading || listsLoading">
          <div v-if="activeTrades.length === 0" class="empty-wrap">
            <n-empty description="暂无进行中交易" />
          </div>

          <n-table v-else striped class="ops-table">
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
                <td>￥{{ toMoney(trade.approved_buy_price) }}</td>
                <td>￥{{ toMoney(trade.target_sell_price) }}</td>
                <td>
                  <n-tag size="small" :type="trade.status === 'listed_for_sale' ? 'success' : 'info'">
                    {{ getTradeStatusText(trade.status) }}
                  </n-tag>
                </td>
                <td class="title-cell">{{ trade.listing_url || "-" }}</td>
                <td>
                  <div v-if="getPricingPreview(trade.trade_id)" class="pricing-preview">
                    <div class="pricing-main">
                      ￥{{ toMoney(getPricingPreview(trade.trade_id).recommended_price) }}
                      <n-tag
                        size="small"
                        :type="getActionType(getPricingPreview(trade.trade_id).action)"
                      >
                        {{ getActionText(getPricingPreview(trade.trade_id).action) }}
                      </n-tag>
                    </div>
                    <div class="pricing-sub">
                      紧急度：
                      <n-tag
                        size="small"
                        :type="getUrgencyType(getPricingPreview(trade.trade_id).urgency)"
                      >
                        {{ getUrgencyText(getPricingPreview(trade.trade_id).urgency) }}
                      </n-tag>
                    </div>
                  </div>
                  <span v-else>-</span>
                </td>
                <td>
                  <n-space vertical size="small">
                    <n-space wrap>
                      <n-button
                        v-if="trade.status === 'approved_for_buy'"
                        size="small"
                        type="primary"
                        @click="$emit('openMarkListed', trade)"
                      >
                        标记已挂售
                      </n-button>
                      <n-button
                        size="small"
                        :type="trade.status === 'approved_for_buy' ? 'default' : 'success'"
                        @click="$emit('openMarkSold', trade)"
                      >
                        标记已卖出
                      </n-button>
                    </n-space>

                    <n-space wrap>
                      <n-button
                        v-if="trade.status === 'approved_for_buy'"
                        size="small"
                        :loading="executionLoadingTradeId === trade.trade_id && executionAction === 'buy_dry_run'"
                        @click="$emit('executeTradeBuy', trade, true)"
                      >
                        模拟买入
                      </n-button>
                      <n-button
                        v-if="trade.status === 'approved_for_buy'"
                        size="small"
                        type="error"
                        :loading="executionLoadingTradeId === trade.trade_id && executionAction === 'buy_live'"
                        @click="$emit('executeTradeBuy', trade, false)"
                      >
                        实盘买入
                      </n-button>
                      <n-button
                        v-if="trade.status === 'approved_for_buy'"
                        size="small"
                        :loading="executionLoadingTradeId === trade.trade_id && executionAction === 'list_dry_run'"
                        @click="$emit('executeTradeList', trade, true)"
                      >
                        模拟上架
                      </n-button>
                      <n-button
                        v-if="trade.status === 'approved_for_buy'"
                        size="small"
                        type="error"
                        :loading="executionLoadingTradeId === trade.trade_id && executionAction === 'list_live'"
                        @click="$emit('executeTradeList', trade, false)"
                      >
                        实盘上架
                      </n-button>
                      <n-button
                        v-if="trade.status === 'listed_for_sale'"
                        size="small"
                        :loading="executionLoadingTradeId === trade.trade_id && executionAction === 'sell_dry_run'"
                        @click="$emit('executeTradeSell', trade, true)"
                      >
                        模拟卖出
                      </n-button>
                      <n-button
                        v-if="trade.status === 'listed_for_sale'"
                        size="small"
                        type="error"
                        :loading="executionLoadingTradeId === trade.trade_id && executionAction === 'sell_live'"
                        @click="$emit('executeTradeSell', trade, false)"
                      >
                        实盘卖出
                      </n-button>
                      <n-button
                        size="small"
                        tertiary
                        :loading="pricingLoadingTradeId === trade.trade_id && pricingAction === 'preview'"
                        @click="$emit('previewTradePricing', trade)"
                      >
                        预览定价
                      </n-button>
                      <n-button
                        size="small"
                        type="warning"
                        :loading="pricingLoadingTradeId === trade.trade_id && pricingAction === 'apply'"
                        @click="$emit('applyTradePricing', trade)"
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
        <div class="tab-panel-head">
          <div>
            <div class="section-title">已卖出记录</div>
            <div class="section-subtitle">快速回看成交表现和已落袋利润。</div>
          </div>
          <n-tag size="small">{{ soldTrades.length }} 条</n-tag>
        </div>

        <n-spin :show="loading || listsLoading">
          <div v-if="soldTrades.length === 0" class="empty-wrap">
            <n-empty description="暂无已卖出记录" />
          </div>

          <n-table v-else striped class="ops-table">
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
                <td>￥{{ toMoney(trade.approved_buy_price) }}</td>
                <td>￥{{ toMoney(trade.sold_price) }}</td>
                <td
                  :class="{
                    good: (trade.sold_price || 0) > (trade.approved_buy_price || 0),
                  }"
                >
                  ￥{{ toMoney((trade.sold_price || 0) - (trade.approved_buy_price || 0)) }}
                </td>
                <td>{{ trade.updated_at }}</td>
              </tr>
            </tbody>
          </n-table>
        </n-spin>
      </n-card>
    </n-tab-pane>

    <n-tab-pane name="executionLogs" tab="执行日志">
      <n-card :bordered="false" class="table-card">
        <div class="tab-panel-head">
          <div>
            <div class="section-title">执行日志</div>
            <div class="section-subtitle">仅在切到这个页签后加载，适合排查执行失败与补跑。</div>
          </div>
          <n-tag size="small" type="warning">{{ executionLogs.length }} 条</n-tag>
        </div>

        <n-spin :show="loading || executionLogsLoading">
          <div class="table-toolbar">
            <n-input
              :value="executionLogFilters.trade_id"
              clearable
              placeholder="交易 ID"
              style="width: 120px"
              @update:value="value => updateLogFilter('trade_id', value)"
            />
            <n-select
              :value="executionLogFilters.action"
              :options="executionActionOptions"
              style="width: 140px"
              @update:value="value => updateLogFilter('action', value)"
            />
            <n-select
              :value="executionLogFilters.provider"
              :options="executionProviderOptions"
              style="width: 140px"
              @update:value="value => updateLogFilter('provider', value)"
            />
            <n-select
              :value="executionLogFilters.mode"
              :options="executionModeOptions"
              style="width: 140px"
              @update:value="value => updateLogFilter('mode', value)"
            />
            <n-select
              :value="executionLogFilters.result"
              :options="executionResultOptions"
              style="width: 140px"
              @update:value="value => updateLogFilter('result', value)"
            />
            <n-button
              size="small"
              type="primary"
              :loading="executionLogsLoading"
              @click="$emit('loadExecutionLogs')"
            >
              刷新日志
            </n-button>
            <n-button size="small" tertiary @click="$emit('resetExecutionLogFilters')">
              重置筛选
            </n-button>

            <n-select
              :value="executionRetryAction"
              :options="executionRetryActionOptions"
              style="width: 140px"
              @update:value="value => $emit('update:executionRetryAction', value)"
            />
            <n-input-number
              :value="executionRetryLimit"
              :min="1"
              :max="200"
              style="width: 120px"
              @update:value="value => $emit('update:executionRetryLimit', value)"
            />
            <n-switch
              :value="executionRetryDryRun"
              @update:value="value => $emit('update:executionRetryDryRun', value)"
            >
              <template #checked>retry dry-run</template>
              <template #unchecked>retry live</template>
            </n-switch>
            <n-switch
              :value="executionRetryForce"
              @update:value="value => $emit('update:executionRetryForce', value)"
            >
              <template #checked>强制</template>
              <template #unchecked>严格</template>
            </n-switch>
            <n-button
              size="small"
              type="warning"
              :loading="executionRetryLoading"
              @click="$emit('retryFailedExecutions')"
            >
              重试失败记录
            </n-button>
          </div>

          <div v-if="executionLogs.length === 0" class="empty-wrap">
            <n-empty description="暂无执行日志" />
          </div>

          <n-table v-else striped size="small" class="ops-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>交易 ID</th>
                <th>动作</th>
                <th>通道</th>
                <th>模式</th>
                <th>结果</th>
                <th>错误</th>
                <th>请求</th>
                <th>响应</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in executionLogs" :key="row.id">
                <td>{{ row.created_at }}</td>
                <td>{{ row.trade_id }}</td>
                <td>{{ getExecutionActionText(row.action) }}</td>
                <td>{{ row.provider }}</td>
                <td>
                  <n-tag size="small" :type="row.dry_run ? 'warning' : 'success'">
                    {{ row.dry_run ? "dry-run" : "live" }}
                  </n-tag>
                </td>
                <td>
                  <n-tag size="small" :type="row.success ? 'success' : 'error'">
                    {{ row.success ? "成功" : "失败" }}
                  </n-tag>
                </td>
                <td class="title-cell">{{ shortText(row.error || "-", 80) }}</td>
                <td class="title-cell">{{ compactJson(row.request_json) }}</td>
                <td class="title-cell">{{ compactJson(row.response_json) }}</td>
              </tr>
            </tbody>
          </n-table>
        </n-spin>
      </n-card>
    </n-tab-pane>
  </n-tabs>
</template>

<script setup>
const props = defineProps({
  activeTab: { type: String, default: "opportunities" },
  loading: { type: Boolean, default: false },
  listsLoading: { type: Boolean, default: false },
  executionLogsLoading: { type: Boolean, default: false },
  executionRetryLoading: { type: Boolean, default: false },
  blockedBatchLoading: { type: Boolean, default: false },
  blockedRejectBatchLoading: { type: Boolean, default: false },
  pricingLoadingTradeId: { type: [Number, String], default: null },
  pricingAction: { type: String, default: "" },
  executionLoadingTradeId: { type: [Number, String], default: null },
  executionAction: { type: String, default: "" },
  opportunities: { type: Array, default: () => [] },
  blockedOpportunities: { type: Array, default: () => [] },
  activeTrades: { type: Array, default: () => [] },
  soldTrades: { type: Array, default: () => [] },
  executionLogs: { type: Array, default: () => [] },
  blockedRiskThreshold: { type: Number, default: 45 },
  executionLogFilters: { type: Object, default: () => ({}) },
  executionActionOptions: { type: Array, default: () => [] },
  executionProviderOptions: { type: Array, default: () => [] },
  executionModeOptions: { type: Array, default: () => [] },
  executionResultOptions: { type: Array, default: () => [] },
  executionRetryAction: { type: String, default: "buy" },
  executionRetryLimit: { type: Number, default: 20 },
  executionRetryDryRun: { type: Boolean, default: true },
  executionRetryForce: { type: Boolean, default: false },
  executionRetryActionOptions: { type: Array, default: () => [] },
  toMoney: { type: Function, required: true },
  toPercent: { type: Function, required: true },
  shortText: { type: Function, required: true },
  compactJson: { type: Function, required: true },
  getPricingPreview: { type: Function, required: true },
  getActionText: { type: Function, required: true },
  getActionType: { type: Function, required: true },
  getUrgencyText: { type: Function, required: true },
  getUrgencyType: { type: Function, required: true },
  getRiskLevelType: { type: Function, required: true },
  getRiskLevelText: { type: Function, required: true },
  getRiskReasonText: { type: Function, required: true },
});

const emit = defineEmits([
  "update:activeTab",
  "update:blockedRiskThreshold",
  "update:executionLogFilters",
  "update:executionRetryAction",
  "update:executionRetryLimit",
  "update:executionRetryDryRun",
  "update:executionRetryForce",
  "openListing",
  "openApprove",
  "reject",
  "sendToReview",
  "sendBlockedBatchToReview",
  "rejectBlockedBatch",
  "openMarkListed",
  "openMarkSold",
  "executeTradeBuy",
  "executeTradeList",
  "executeTradeSell",
  "previewTradePricing",
  "applyTradePricing",
  "loadExecutionLogs",
  "resetExecutionLogFilters",
  "retryFailedExecutions",
]);

const updateLogFilter = (key, value) => {
  emit("update:executionLogFilters", {
    ...props.executionLogFilters,
    [key]: value,
  });
};

const getTradeStatusText = (status) =>
  ({
    approved_for_buy: "待买入",
    listed_for_sale: "已上架",
    sold: "已卖出",
  })[status] || status;

const getExecutionActionText = (action) =>
  ({
    buy: "买入",
    list: "上架",
    sell: "卖出",
  })[action] || action;
</script>
