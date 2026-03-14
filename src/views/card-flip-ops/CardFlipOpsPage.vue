<template>
  <div class="card-flip-page">
    <OpsOverviewHeader
      :batch-pricing-loading="batchPricingLoading"
      :blocked-count="blockedOpportunities.length"
      :can-batch-apply-pricing="canBatchApplyPricing"
      :can-maintain="canMaintain"
      :can-operate="canOperate"
      :cookie-refresh-loading="cookieRefreshLoading"
      :data-integrity-alert="dataIntegrityAlert"
      :guard-alert="guardAlert"
      :is-viewer="isViewer"
      :loading="loading"
      :metrics="metrics"
      :pricing-mode="pricingMode"
      :pricing-mode-options="pricingModeOptions"
      :role-tag-text="roleTagText"
      :role-tag-type="roleTagType"
      :scan-limit="scanLimit"
      :scan-loading="scanLoading"
      :simulation-training-loading="simulationTrainingLoading"
      :to-money="toMoney"
      @apply-batch-reprice="applyBatchReprice"
      @preview-batch-reprice="previewBatchReprice"
      @refresh="loadData"
      @refresh-cookie="refreshCookie"
      @run-scan="runScan"
      @run-simulation-training="runSimulationTraining"
      @update:pricing-mode="pricingMode = $event"
      @update:scan-limit="scanLimit = $event"
    ></OpsOverviewHeader>

    <AutomationControlPanel
      :automation-action-loading="automationActionLoading"
      :automation-autotrade-limit="automationAutotradeLimit"
      :automation-execution-retry-limit="automationExecutionRetryLimit"
      :automation-force="automationForce"
      :automation-include-autotrade="automationIncludeAutotrade"
      :automation-include-execution-retry="automationIncludeExecutionRetry"
      :automation-include-monitor="automationIncludeMonitor"
      :automation-include-scan="automationIncludeScan"
      :automation-scan-limit="automationScanLimit"
      :automation-status="automationStatus"
      :automation-status-loading="automationStatusLoading"
      :can-maintain="canMaintain"
      :can-operate="canOperate"
      :monitor-action-loading="monitorActionLoading"
      :monitor-cookie-status-hint="monitorCookieStatusHint"
      :monitor-stop-reason="monitorStopReason"
      @load-automation-status="loadAutomationStatus"
      @reset-monitor-circuit="resetMonitorCircuit"
      @restart-monitor="restartMonitorFromAutomation"
      @run-automation-once="runAutomationOnce"
      @start-automation="startAutomation"
      @stop-automation="stopAutomation"
      @update:automation-autotrade-limit="automationAutotradeLimit = $event"
      @update:automation-execution-retry-limit="
        automationExecutionRetryLimit = $event
      "
      @update:automation-force="automationForce = $event"
      @update:automation-include-autotrade="automationIncludeAutotrade = $event"
      @update:automation-include-execution-retry="
        automationIncludeExecutionRetry = $event
      "
      @update:automation-include-monitor="automationIncludeMonitor = $event"
      @update:automation-include-scan="automationIncludeScan = $event"
      @update:automation-scan-limit="automationScanLimit = $event"
    ></AutomationControlPanel>

    <AutotradePanel
      :autotrade-action-loading="autotradeActionLoading"
      :autotrade-config-loading="autotradeConfigLoading"
      :autotrade-run-force="autotradeRunForce"
      :autotrade-run-limit="autotradeRunLimit"
      :autotrade-status="autotradeStatus"
      :autotrade-status-loading="autotradeStatusLoading"
      :can-operate="canOperate"
      :execution-config-loading="executionConfigLoading"
      :execution-live-confirm-token="executionLiveConfirmToken"
      :execution-status="executionStatus"
      :to-money="toMoney"
      :to-percent="toPercent"
      @adjust-autotrade-number="adjustAutotradeNumber"
      @adjust-autotrade-roi="adjustAutotradeRoi"
      @adjust-execution-number="adjustExecutionNumber"
      @load-autotrade-status="loadAutotradeStatus"
      @run-autotrade-once="runAutotradeOnce"
      @set-execution-provider="setExecutionProvider"
      @start-autotrade="startAutotrade"
      @stop-autotrade="stopAutotrade"
      @toggle-autotrade-flag="toggleAutotradeFlag"
      @toggle-execution-flag="toggleExecutionFlag"
      @update:autotrade-run-force="autotradeRunForce = $event"
      @update:autotrade-run-limit="autotradeRunLimit = $event"
      @update:execution-live-confirm-token="executionLiveConfirmToken = $event"
    ></AutotradePanel>

    <ExecutionRetryPanel
      :can-operate="canOperate"
      :execution-retry-action-options="executionRetryActionOptions"
      :execution-retry-config-loading="executionRetryConfigLoading"
      :execution-retry-service-action="executionRetryServiceAction"
      :execution-retry-service-action-loading="
        executionRetryServiceActionLoading
      "
      :execution-retry-service-dry-run="executionRetryServiceDryRun"
      :execution-retry-service-execution-force="
        executionRetryServiceExecutionForce
      "
      :execution-retry-service-run-force="executionRetryServiceRunForce"
      :execution-retry-service-run-limit="executionRetryServiceRunLimit"
      :execution-retry-service-status="executionRetryServiceStatus"
      :execution-retry-service-status-loading="
        executionRetryServiceStatusLoading
      "
      @adjust-execution-retry-number="adjustExecutionRetryNumber"
      @load-execution-retry-service-status="loadExecutionRetryServiceStatus"
      @run-execution-retry-service-once="runExecutionRetryServiceOnce"
      @set-execution-retry-default-action="setExecutionRetryDefaultAction"
      @start-execution-retry-service="startExecutionRetryService"
      @stop-execution-retry-service="stopExecutionRetryService"
      @toggle-execution-retry-flag="toggleExecutionRetryFlag"
      @update:execution-retry-service-action="
        executionRetryServiceAction = $event
      "
      @update:execution-retry-service-dry-run="
        executionRetryServiceDryRun = $event
      "
      @update:execution-retry-service-execution-force="
        executionRetryServiceExecutionForce = $event
      "
      @update:execution-retry-service-run-force="
        executionRetryServiceRunForce = $event
      "
      @update:execution-retry-service-run-limit="
        executionRetryServiceRunLimit = $event
      "
    ></ExecutionRetryPanel>

    <TradeDataTabs
      :active-tab="activeTab"
      :active-trades="activeTrades"
      :blocked-batch-loading="blockedBatchLoading"
      :blocked-opportunities="blockedOpportunities"
      :blocked-reject-batch-loading="blockedRejectBatchLoading"
      :blocked-risk-threshold="blockedRiskThreshold"
      :execution-action="executionAction"
      :execution-action-options="executionActionOptions"
      :execution-loading-trade-id="executionLoadingTradeId"
      :execution-log-filters="executionLogFilters"
      :execution-logs="executionLogs"
      :execution-logs-loading="executionLogsLoading"
      :execution-mode-options="executionModeOptions"
      :execution-provider-options="executionProviderOptions"
      :execution-result-options="executionResultOptions"
      :compact-json="compactJson"
      :execution-retry-action="executionRetryAction"
      :execution-retry-action-options="executionRetryActionOptions"
      :execution-retry-dry-run="executionRetryDryRun"
      :execution-retry-force="executionRetryForce"
      :execution-retry-limit="executionRetryLimit"
      :execution-retry-loading="executionRetryLoading"
      :get-action-text="getActionText"
      :get-action-type="getActionType"
      :get-pricing-preview="getPricingPreview"
      :get-urgency-text="getUrgencyText"
      :get-urgency-type="getUrgencyType"
      :get-risk-level-type="getRiskLevelType"
      :lists-loading="listsLoading"
      :get-risk-level-text="getRiskLevelText"
      :loading="loading"
      :get-risk-reason-text="getRiskReasonText"
      :opportunities="opportunities"
      :pricing-action="pricingAction"
      :pricing-loading-trade-id="pricingLoadingTradeId"
      :short-text="shortText"
      :sold-trades="soldTrades"
      :to-money="toMoney"
      :to-percent="toPercent"
      @execute-trade-buy="executeTradeBuy"
      @execute-trade-list="executeTradeList"
      @execute-trade-sell="executeTradeSell"
      @open-approve="openApprove"
      @apply-trade-pricing="applyTradePricing"
      @open-listing="openListing"
      @load-execution-logs="loadExecutionLogs"
      @open-mark-listed="openMarkListed"
      @open-mark-sold="openMarkSold"
      @preview-trade-pricing="previewTradePricing"
      @reject="reject"
      @reject-blocked-batch="rejectBlockedBatch"
      @reset-execution-log-filters="resetExecutionLogFilters"
      @retry-failed-executions="retryFailedExecutions"
      @send-blocked-batch-to-review="sendBlockedBatchToReview"
      @send-to-review="sendToReview"
      @update:active-tab="activeTab = $event"
      @update:blocked-risk-threshold="blockedRiskThreshold = $event"
      @update:execution-log-filters="executionLogFilters = $event"
      @update:execution-retry-action="executionRetryAction = $event"
      @update:execution-retry-dry-run="executionRetryDryRun = $event"
      @update:execution-retry-force="executionRetryForce = $event"
      @update:execution-retry-limit="executionRetryLimit = $event"
    ></TradeDataTabs>

    <n-modal
      negative-text="取消"
      positive-text="确认审批"
      preset="dialog"
      title="审批买入"
      v-model:show="approveModalVisible"
      :positive-button-props="{ loading: approving }"
      @positive-click="submitApprove"
    >
      <n-form label-placement="left" :label-width="90">
        <n-form-item label="机会ID">
          <n-input disabled :value="String(approveForm.opportunity_id || '')"></n-input>
        </n-form-item>
        <n-form-item label="审批买入价">
          <n-input-number
            style="width: 100%"
            v-model:value="approveForm.approved_buy_price"
            :min="0.01"
            :precision="2"
          ></n-input-number>
        </n-form-item>
        <n-form-item label="审批人">
          <n-input v-model:value="approveForm.approved_by"></n-input>
        </n-form-item>
        <n-form-item label="备注">
          <n-input type="textarea" v-model:value="approveForm.note"></n-input>
        </n-form-item>
      </n-form>
    </n-modal>

    <n-modal
      negative-text="取消"
      positive-text="确认"
      preset="dialog"
      title="标记已挂售"
      v-model:show="markListedModalVisible"
      :positive-button-props="{ loading: markListedLoading }"
      @positive-click="submitMarkListed"
    >
      <n-form label-placement="left" :label-width="90">
        <n-form-item label="交易ID">
          <n-input disabled :value="String(markListedForm.trade_id || '')"></n-input>
        </n-form-item>
        <n-form-item label="挂售链接">
          <n-input
            placeholder="https://..."
            v-model:value="markListedForm.listing_url"
          ></n-input>
        </n-form-item>
        <n-form-item label="备注">
          <n-input type="textarea" v-model:value="markListedForm.note"></n-input>
        </n-form-item>
      </n-form>
    </n-modal>

    <n-modal
      negative-text="取消"
      positive-text="确认"
      preset="dialog"
      title="标记已卖出"
      v-model:show="markSoldModalVisible"
      :positive-button-props="{ loading: markSoldLoading }"
      @positive-click="submitMarkSold"
    >
      <n-form label-placement="left" :label-width="90">
        <n-form-item label="交易ID">
          <n-input disabled :value="String(markSoldForm.trade_id || '')"></n-input>
        </n-form-item>
        <n-form-item label="卖出价格">
          <n-input-number
            style="width: 100%"
            v-model:value="markSoldForm.sold_price"
            :min="0.01"
            :precision="2"
          ></n-input-number>
        </n-form-item>
        <n-form-item label="备注">
          <n-input type="textarea" v-model:value="markSoldForm.note"></n-input>
        </n-form-item>
      </n-form>
    </n-modal>

    <n-modal
      preset="card"
      style="width: 90%; max-width: 760px"
      title="智能定价建议"
      v-model:show="pricingPlanModalVisible"
    >
      <div v-if="pricingPlanPayload">
        <n-descriptions bordered label-placement="left" :column="2">
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
      preset="card"
      style="width: 95%; max-width: 960px"
      title="批量重定价预览"
      v-model:show="batchPricingModalVisible"
    >
      <n-space vertical>
        <div v-if="batchPricingResult" class="batch-summary">
          模式: {{ getModeText(batchPricingResult.mode) }} | 已处理
          {{ batchPricingResult.processed }} | 已更新
          {{ batchPricingResult.updated }} | 当前为
          {{ batchPricingResult.apply ? "应用结果" : "预览结果" }}
        </div>
        <n-table
          v-if="
            batchPricingResult
              && batchPricingResult.items
              && batchPricingResult.items.length > 0
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
        <n-empty v-else description="暂无重定价结果"></n-empty>
      </n-space>
    </n-modal>

    <n-modal
      preset="card"
      style="width: 90%; max-width: 760px"
      title="商品信息"
      v-model:show="listingModalVisible"
    >
      <n-spin :show="listingLoading">
        <div v-if="listingPayload">
          <n-descriptions bordered label-placement="left" :column="2">
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
                  rel="noreferrer"
                  target="_blank"
                  :href="listingPayload.listing_url"
                >打开链接</a>
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
          <div v-if="rawListingJson" class="listing-raw">
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
