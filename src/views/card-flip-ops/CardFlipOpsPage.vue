<template>
  <div class="card-flip-page">
    <OpsOverviewHeader
      :role-tag-text="roleTagText"
      :role-tag-type="roleTagType"
      :is-viewer="isViewer"
      :can-operate="canOperate"
      :can-maintain="canMaintain"
      :can-batch-apply-pricing="canBatchApplyPricing"
      :scan-limit="scanLimit"
      :pricing-mode="pricingMode"
      :pricing-mode-options="pricingModeOptions"
      :scan-loading="scanLoading"
      :simulation-training-loading="simulationTrainingLoading"
      :cookie-refresh-loading="cookieRefreshLoading"
      :batch-pricing-loading="batchPricingLoading"
      :loading="loading"
      :data-integrity-alert="dataIntegrityAlert"
      :guard-alert="guardAlert"
      :metrics="metrics"
      :blocked-count="blockedOpportunities.length"
      :to-money="toMoney"
      @update:scan-limit="scanLimit = $event"
      @update:pricing-mode="pricingMode = $event"
      @run-scan="runScan"
      @run-simulation-training="runSimulationTraining"
      @refresh-cookie="refreshCookie"
      @preview-batch-reprice="previewBatchReprice"
      @apply-batch-reprice="applyBatchReprice"
      @refresh="loadData"
    />

    <AutomationControlPanel
      :automation-status="automationStatus"
      :automation-status-loading="automationStatusLoading"
      :automation-action-loading="automationActionLoading"
      :monitor-action-loading="monitorActionLoading"
      :can-operate="canOperate"
      :can-maintain="canMaintain"
      :automation-include-monitor="automationIncludeMonitor"
      :automation-include-scan="automationIncludeScan"
      :automation-include-autotrade="automationIncludeAutotrade"
      :automation-include-execution-retry="automationIncludeExecutionRetry"
      :automation-force="automationForce"
      :automation-scan-limit="automationScanLimit"
      :automation-autotrade-limit="automationAutotradeLimit"
      :automation-execution-retry-limit="automationExecutionRetryLimit"
      :monitor-stop-reason="monitorStopReason"
      :monitor-cookie-status-hint="monitorCookieStatusHint"
      @update:automation-include-monitor="automationIncludeMonitor = $event"
      @update:automation-include-scan="automationIncludeScan = $event"
      @update:automation-include-autotrade="automationIncludeAutotrade = $event"
      @update:automation-include-execution-retry="
        automationIncludeExecutionRetry = $event
      "
      @update:automation-force="automationForce = $event"
      @update:automation-scan-limit="automationScanLimit = $event"
      @update:automation-autotrade-limit="automationAutotradeLimit = $event"
      @update:automation-execution-retry-limit="
        automationExecutionRetryLimit = $event
      "
      @start-automation="startAutomation"
      @stop-automation="stopAutomation"
      @load-automation-status="loadAutomationStatus"
      @run-automation-once="runAutomationOnce"
      @restart-monitor="restartMonitorFromAutomation"
      @reset-monitor-circuit="resetMonitorCircuit"
    />

    <AutotradePanel
      :autotrade-status="autotradeStatus"
      :execution-status="executionStatus"
      :autotrade-status-loading="autotradeStatusLoading"
      :autotrade-action-loading="autotradeActionLoading"
      :autotrade-config-loading="autotradeConfigLoading"
      :execution-config-loading="executionConfigLoading"
      :can-operate="canOperate"
      :autotrade-run-limit="autotradeRunLimit"
      :autotrade-run-force="autotradeRunForce"
      :execution-live-confirm-token="executionLiveConfirmToken"
      :to-money="toMoney"
      :to-percent="toPercent"
      @load-autotrade-status="loadAutotradeStatus"
      @start-autotrade="startAutotrade"
      @stop-autotrade="stopAutotrade"
      @set-execution-provider="setExecutionProvider"
      @toggle-execution-flag="toggleExecutionFlag"
      @adjust-execution-number="adjustExecutionNumber"
      @adjust-autotrade-number="adjustAutotradeNumber"
      @adjust-autotrade-roi="adjustAutotradeRoi"
      @toggle-autotrade-flag="toggleAutotradeFlag"
      @update:execution-live-confirm-token="executionLiveConfirmToken = $event"
      @update:autotrade-run-limit="autotradeRunLimit = $event"
      @update:autotrade-run-force="autotradeRunForce = $event"
      @run-autotrade-once="runAutotradeOnce"
    />

    <ExecutionRetryPanel
      :execution-retry-service-status="executionRetryServiceStatus"
      :execution-retry-service-status-loading="
        executionRetryServiceStatusLoading
      "
      :execution-retry-service-action-loading="
        executionRetryServiceActionLoading
      "
      :execution-retry-config-loading="executionRetryConfigLoading"
      :can-operate="canOperate"
      :execution-retry-service-action="executionRetryServiceAction"
      :execution-retry-service-run-limit="executionRetryServiceRunLimit"
      :execution-retry-service-run-force="executionRetryServiceRunForce"
      :execution-retry-service-dry-run="executionRetryServiceDryRun"
      :execution-retry-service-execution-force="
        executionRetryServiceExecutionForce
      "
      :execution-retry-action-options="executionRetryActionOptions"
      @load-execution-retry-service-status="loadExecutionRetryServiceStatus"
      @start-execution-retry-service="startExecutionRetryService"
      @stop-execution-retry-service="stopExecutionRetryService"
      @adjust-execution-retry-number="adjustExecutionRetryNumber"
      @set-execution-retry-default-action="setExecutionRetryDefaultAction"
      @toggle-execution-retry-flag="toggleExecutionRetryFlag"
      @update:execution-retry-service-action="
        executionRetryServiceAction = $event
      "
      @update:execution-retry-service-run-limit="
        executionRetryServiceRunLimit = $event
      "
      @update:execution-retry-service-run-force="
        executionRetryServiceRunForce = $event
      "
      @update:execution-retry-service-dry-run="
        executionRetryServiceDryRun = $event
      "
      @update:execution-retry-service-execution-force="
        executionRetryServiceExecutionForce = $event
      "
      @run-execution-retry-service-once="runExecutionRetryServiceOnce"
    />

    <TradeDataTabs
      :active-tab="activeTab"
      :loading="loading"
      :lists-loading="listsLoading"
      :execution-logs-loading="executionLogsLoading"
      :execution-retry-loading="executionRetryLoading"
      :blocked-batch-loading="blockedBatchLoading"
      :blocked-reject-batch-loading="blockedRejectBatchLoading"
      :pricing-loading-trade-id="pricingLoadingTradeId"
      :pricing-action="pricingAction"
      :execution-loading-trade-id="executionLoadingTradeId"
      :execution-action="executionAction"
      :opportunities="opportunities"
      :blocked-opportunities="blockedOpportunities"
      :active-trades="activeTrades"
      :sold-trades="soldTrades"
      :execution-logs="executionLogs"
      :blocked-risk-threshold="blockedRiskThreshold"
      :execution-log-filters="executionLogFilters"
      :execution-action-options="executionActionOptions"
      :execution-provider-options="executionProviderOptions"
      :execution-mode-options="executionModeOptions"
      :execution-result-options="executionResultOptions"
      :execution-retry-action="executionRetryAction"
      :execution-retry-limit="executionRetryLimit"
      :execution-retry-dry-run="executionRetryDryRun"
      :execution-retry-force="executionRetryForce"
      :execution-retry-action-options="executionRetryActionOptions"
      :to-money="toMoney"
      :to-percent="toPercent"
      :short-text="shortText"
      :compact-json="compactJson"
      :get-pricing-preview="getPricingPreview"
      :get-action-text="getActionText"
      :get-action-type="getActionType"
      :get-urgency-text="getUrgencyText"
      :get-urgency-type="getUrgencyType"
      :get-risk-level-type="getRiskLevelType"
      :get-risk-level-text="getRiskLevelText"
      :get-risk-reason-text="getRiskReasonText"
      @update:active-tab="activeTab = $event"
      @update:blocked-risk-threshold="blockedRiskThreshold = $event"
      @update:execution-log-filters="executionLogFilters = $event"
      @update:execution-retry-action="executionRetryAction = $event"
      @update:execution-retry-limit="executionRetryLimit = $event"
      @update:execution-retry-dry-run="executionRetryDryRun = $event"
      @update:execution-retry-force="executionRetryForce = $event"
      @open-listing="openListing"
      @open-approve="openApprove"
      @reject="reject"
      @send-to-review="sendToReview"
      @send-blocked-batch-to-review="sendBlockedBatchToReview"
      @reject-blocked-batch="rejectBlockedBatch"
      @open-mark-listed="openMarkListed"
      @open-mark-sold="openMarkSold"
      @execute-trade-buy="executeTradeBuy"
      @execute-trade-list="executeTradeList"
      @execute-trade-sell="executeTradeSell"
      @preview-trade-pricing="previewTradePricing"
      @apply-trade-pricing="applyTradePricing"
      @load-execution-logs="loadExecutionLogs"
      @reset-execution-log-filters="resetExecutionLogFilters"
      @retry-failed-executions="retryFailedExecutions"
    />

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
          <n-input
            v-model:value="markListedForm.listing_url"
            placeholder="https://..."
          />
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
            ￥{{ toMoney(pricingPlanPayload.plan.current_target_price) }}
          </n-descriptions-item>
          <n-descriptions-item label="建议卖价">
            ￥{{ toMoney(pricingPlanPayload.plan.recommended_price) }}
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
            ￥{{ toMoney(pricingPlanPayload.plan.price_floor) }}
          </n-descriptions-item>
          <n-descriptions-item label="价格上限">
            ￥{{ toMoney(pricingPlanPayload.plan.price_ceiling) }}
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
          模式: {{ getModeText(batchPricingResult.mode) }} | 已处理
          {{ batchPricingResult.processed }} | 已更新
          {{ batchPricingResult.updated }} | 当前为
          {{ batchPricingResult.apply ? "应用结果" : "预览结果" }}
        </div>
        <n-table
          v-if="
            batchPricingResult &&
            batchPricingResult.items &&
            batchPricingResult.items.length > 0
          "
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
              <td>￥{{ toMoney(item.current_target_price) }}</td>
              <td>￥{{ toMoney(item.recommended_price) }}</td>
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
              CNY {{ toMoney(listingPayload.list_price) }}
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
                <a
                  :href="listingPayload.listing_url"
                  target="_blank"
                  rel="noreferrer"
                  >打开链接</a
                >
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

<script>
import { defineComponent } from "vue";
import "@/views/card-flip-ops/cardFlipOps.scss";
import AutomationControlPanel from "@/views/card-flip-ops/AutomationControlPanel.vue";
import AutotradePanel from "@/views/card-flip-ops/AutotradePanel.vue";
import ExecutionRetryPanel from "@/views/card-flip-ops/ExecutionRetryPanel.vue";
import OpsOverviewHeader from "@/views/card-flip-ops/OpsOverviewHeader.vue";
import TradeDataTabs from "@/views/card-flip-ops/TradeDataTabs.vue";
import useCardFlipOpsPage from "@/views/card-flip-ops/useCardFlipOpsPage";

export default defineComponent({
  name: "CardFlipOpsPage",
  components: {
    AutomationControlPanel,
    AutotradePanel,
    ExecutionRetryPanel,
    OpsOverviewHeader,
    TradeDataTabs,
  },
  setup() {
    return useCardFlipOpsPage();
  },
});
</script>
