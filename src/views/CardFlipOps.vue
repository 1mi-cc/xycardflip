<template>
  <div class="card-flip-page">
    <section class="hero">
      <div>
        <h1>卡片倒卖助手</h1>
        <p>机会扫描、人工审核、交易流转全流程</p>
      </div>
      <n-space>
        <n-input-number v-model:value="scanLimit" :min="1" :max="500" />
        <n-button type="primary" :loading="scanLoading" @click="runScan">
          扫描机会
        </n-button>
        <n-button :loading="cookieRefreshLoading" @click="refreshCookie">
          刷新Cookie
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

    <section class="autotrade-panel">
      <div class="autotrade-head">
        <div class="autotrade-title-wrap">
          <h3>Automation 全自动总控</h3>
          <div class="autotrade-tags">
            <n-tag :type="automationStatus.all_running ? 'success' : 'warning'" size="small">
              {{ automationStatus.all_running ? "全链路运行中" : "部分或全部未运行" }}
            </n-tag>
            <n-tag :type="automationStatus.monitor.is_running ? 'success' : 'default'" size="small">
              {{ automationStatus.monitor.is_running ? "Monitor 运行中" : "Monitor 已停止" }}
            </n-tag>
            <n-tag :type="automationStatus.autotrade.running ? 'success' : 'default'" size="small">
              {{ automationStatus.autotrade.running ? "AutoTrade 运行中" : "AutoTrade 已停止" }}
            </n-tag>
            <n-tag :type="automationStatus.execution_retry.running ? 'success' : 'default'" size="small">
              {{ automationStatus.execution_retry.running ? "ExecRetry 运行中" : "ExecRetry 已停止" }}
            </n-tag>
          </div>
        </div>
        <n-space>
          <n-button
            size="small"
            type="primary"
            :loading="automationActionLoading === 'start'"
            @click="startAutomation"
          >
            一键启动
          </n-button>
          <n-button
            size="small"
            :loading="automationActionLoading === 'stop'"
            @click="stopAutomation"
          >
            一键停止
          </n-button>
          <n-button
            size="small"
            tertiary
            :loading="automationStatusLoading"
            @click="loadAutomationStatus"
          >
            刷新状态
          </n-button>
        </n-space>
      </div>
      <div class="autotrade-metrics">
        <span>默认链路: monitor={{ automationStatus.default_include_monitor ? "on" : "off" }}, scan={{ automationStatus.default_include_scan ? "on" : "off" }}, autotrade={{ automationStatus.default_include_autotrade ? "on" : "off" }}, retry={{ automationStatus.default_include_execution_retry ? "on" : "off" }}</span>
        <span>默认扫描上限: {{ automationStatus.default_scan_limit ?? "-" }}</span>
        <span>启动自拉起: monitor={{ automationStatus.auto_start_monitor ? "on" : "off" }}, autotrade={{ automationStatus.auto_start_autotrade ? "on" : "off" }}, retry={{ automationStatus.auto_start_execution_retry ? "on" : "off" }}</span>
        <span>最近编排执行: {{ automationStatus.last_run_at || "-" }}</span>
      </div>
      <div class="autotrade-once">
        <n-space>
          <n-switch v-model:value="automationIncludeMonitor">
            <template #checked>monitor</template>
            <template #unchecked>no monitor</template>
          </n-switch>
          <n-switch v-model:value="automationIncludeScan">
            <template #checked>scan</template>
            <template #unchecked>no scan</template>
          </n-switch>
          <n-switch v-model:value="automationIncludeAutotrade">
            <template #checked>autotrade</template>
            <template #unchecked>no autotrade</template>
          </n-switch>
          <n-switch v-model:value="automationIncludeExecutionRetry">
            <template #checked>retry</template>
            <template #unchecked>no retry</template>
          </n-switch>
          <n-switch v-model:value="automationForce">
            <template #checked>force</template>
            <template #unchecked>strict</template>
          </n-switch>
          <n-input-number
            v-model:value="automationScanLimit"
            :min="0"
            :max="500"
            style="width: 140px"
            placeholder="scan limit"
          />
          <n-input-number
            v-model:value="automationAutotradeLimit"
            :min="0"
            :max="500"
            style="width: 150px"
            placeholder="autotrade limit"
          />
          <n-input-number
            v-model:value="automationExecutionRetryLimit"
            :min="0"
            :max="200"
            style="width: 140px"
            placeholder="retry limit"
          />
          <n-button
            type="warning"
            :loading="automationActionLoading === 'run_once'"
            @click="runAutomationOnce"
          >
            链路运行一次
          </n-button>
        </n-space>
      </div>
    </section>

    <section class="autotrade-panel">
      <div class="autotrade-head">
        <div class="autotrade-title-wrap">
          <h3>AutoTrade 审批引擎</h3>
          <div class="autotrade-tags">
            <n-tag :type="autotradeStatus.running ? 'success' : 'default'" size="small">
              {{ autotradeStatus.running ? "运行中" : "已停止" }}
            </n-tag>
            <n-tag :type="autotradeStatus.enabled ? 'info' : 'warning'" size="small">
              {{ autotradeStatus.enabled ? "已启用" : "环境未启用" }}
            </n-tag>
          </div>
        </div>
        <n-space>
          <n-button
            size="small"
            type="primary"
            :loading="autotradeActionLoading === 'start'"
            @click="startAutotrade"
          >
            启动
          </n-button>
          <n-button
            size="small"
            :loading="autotradeActionLoading === 'stop'"
            @click="stopAutotrade"
          >
            停止
          </n-button>
          <n-button
            size="small"
            tertiary
            :loading="autotradeStatusLoading"
            @click="loadAutotradeStatus"
          >
            刷新状态          </n-button>
        </n-space>
      </div>
      <div class="autotrade-metrics">
        <span>执行通道: {{ executionStatus.provider || "-" }}</span>
        <span>实盘开关 {{ executionStatus.live_enabled ? "开启" : "关闭" }}</span>
        <span>实盘二次确认: {{ executionStatus.live_confirm_required ? "已启用" : "未启用" }}</span>
        <span>
          实盘价格上限:
          {{ executionStatus.live_max_buy_price > 0 ? `CNY ${toMoney(executionStatus.live_max_buy_price)}` : "不限" }}
        </span>
        <span>实盘上架最小利润率: {{ toPercent(executionStatus.live_min_list_profit_ratio || 0) }}</span>
        <span>实盘卖出最小利润率: {{ toPercent(executionStatus.live_min_sell_profit_ratio || 0) }}</span>
        <span>循环间隔: {{ autotradeStatus.interval_sec ?? "-" }}s</span>
        <span>批量上限: {{ autotradeStatus.batch_size ?? "-" }}</span>
        <span>最小评分 {{ autotradeStatus.min_score ?? "-" }}</span>
        <span>最小ROI: {{ toPercent(autotradeStatus.min_roi || 0) }}</span>
        <span>最大风险分: {{ autotradeStatus.max_risk_score ?? "-" }}</span>
      </div>
      <div class="autotrade-metrics">
        <span>累计执行: {{ autotradeStatus.total_runs ?? 0 }}</span>
        <span>累计审批: {{ autotradeStatus.total_approved ?? 0 }}</span>
        <span>审批后自动买入 {{ autotradeStatus.auto_execute_buy_on_approve ? "开启" : "关闭" }}</span>
        <span>自动买入模式: {{ autotradeStatus.auto_execute_buy_dry_run ? "dry-run" : "live" }}</span>
        <span>买入后自动上架 {{ autotradeStatus.auto_execute_list_on_buy_success ? "开启" : "关闭" }}</span>
        <span>自动上架模式: {{ autotradeStatus.auto_execute_list_dry_run ? "dry-run" : "live" }}</span>
        <span>最近运行 {{ autotradeStatus.last_run_at || "-" }}</span>
      </div>
      <div class="autotrade-once">
        <n-space style="margin-bottom: 8px">
          <n-input
            v-model:value="executionLiveConfirmToken"
            type="password"
            show-password-on="click"
            placeholder="实盘确认口令（EXECUTION_LIVE_CONFIRM_TOKEN）"
            style="width: 320px"
            :disabled="!executionStatus.live_confirm_required"
          />
        </n-space>
        <n-space>
          <n-input-number
            v-model:value="autotradeRunLimit"
            :min="0"
            :max="500"
            style="width: 160px"
            placeholder="单次处理数(0=默认)"
          />
          <n-switch v-model:value="autotradeRunForce">
            <template #checked>强制执行</template>
            <template #unchecked>遵循环境开关</template>
          </n-switch>
          <n-button
            type="warning"
            :loading="autotradeActionLoading === 'run_once'"
            @click="runAutotradeOnce"
          >
            运行一次          </n-button>
        </n-space>
      </div>
    </section>

    <section class="autotrade-panel">
      <div class="autotrade-head">
        <div class="autotrade-title-wrap">
          <h3>ExecutionRetry 失败重试引擎</h3>
          <div class="autotrade-tags">
            <n-tag :type="executionRetryServiceStatus.running ? 'success' : 'default'" size="small">
              {{ executionRetryServiceStatus.running ? "运行中" : "已停止" }}
            </n-tag>
            <n-tag :type="executionRetryServiceStatus.enabled ? 'info' : 'warning'" size="small">
              {{ executionRetryServiceStatus.enabled ? "已启用" : "环境未启用" }}
            </n-tag>
          </div>
        </div>
        <n-space>
          <n-button
            size="small"
            type="primary"
            :loading="executionRetryServiceActionLoading === 'start'"
            @click="startExecutionRetryService"
          >
            启动
          </n-button>
          <n-button
            size="small"
            :loading="executionRetryServiceActionLoading === 'stop'"
            @click="stopExecutionRetryService"
          >
            停止
          </n-button>
          <n-button
            size="small"
            tertiary
            :loading="executionRetryServiceStatusLoading"
            @click="loadExecutionRetryServiceStatus"
          >
            刷新状态
          </n-button>
        </n-space>
      </div>
      <div class="autotrade-metrics">
        <span>循环间隔: {{ executionRetryServiceStatus.interval_sec ?? "-" }}s</span>
        <span>批量上限: {{ executionRetryServiceStatus.batch_size ?? "-" }}</span>
        <span>默认动作: {{ executionRetryServiceStatus.action || "all" }}</span>
        <span>默认模式: {{ executionRetryServiceStatus.dry_run ? "dry-run" : "live" }}</span>
        <span>默认强制: {{ executionRetryServiceStatus.force ? "开启" : "关闭" }}</span>
        <span>确认口令: {{ executionRetryServiceStatus.confirm_token_configured ? "已配置" : "未配置" }}</span>
        <span>最近运行: {{ executionRetryServiceStatus.last_run_at || "-" }}</span>
      </div>
      <div class="autotrade-metrics">
        <span>累计轮次: {{ executionRetryServiceStatus.total_runs ?? 0 }}</span>
        <span>累计重试: {{ executionRetryServiceStatus.total_retried ?? 0 }}</span>
        <span>累计成功: {{ executionRetryServiceStatus.total_succeeded ?? 0 }}</span>
        <span>累计失败: {{ executionRetryServiceStatus.total_failed ?? 0 }}</span>
        <span>最近错误: {{ executionRetryServiceStatus.last_error || "-" }}</span>
      </div>
      <div class="autotrade-once">
        <n-space>
          <n-select
            v-model:value="executionRetryServiceAction"
            :options="executionRetryActionOptions"
            style="width: 140px"
          />
          <n-input-number
            v-model:value="executionRetryServiceRunLimit"
            :min="0"
            :max="200"
            style="width: 130px"
            placeholder="单次条数(0=默认)"
          />
          <n-switch v-model:value="executionRetryServiceDryRun">
            <template #checked>dry-run</template>
            <template #unchecked>live</template>
          </n-switch>
          <n-switch v-model:value="executionRetryServiceExecutionForce">
            <template #checked>force</template>
            <template #unchecked>strict</template>
          </n-switch>
          <n-switch v-model:value="executionRetryServiceRunForce">
            <template #checked>忽略启用开关</template>
            <template #unchecked>遵循启用开关</template>
          </n-switch>
          <n-button
            type="warning"
            :loading="executionRetryServiceActionLoading === 'run_once'"
            @click="runExecutionRetryServiceOnce"
          >
            运行一次
          </n-button>
        </n-space>
      </div>
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
        <div class="value">￥{{ toMoney(metrics.gross_profit) }}</div>
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
                  <td>￥{{ toMoney(item.list_price) }}</td>
                  <td>￥{{ toMoney(item.expected_sale_price) }}</td>
                  <td :class="{ good: item.expected_profit > 0 }">
                    ￥{{ toMoney(item.expected_profit) }}
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
                placeholder="风险分阈值" />
              <n-button
                type="primary"
                :loading="blockedBatchLoading"
                :disabled="blockedOpportunities.length === 0"
                @click="sendBlockedBatchToReview"
              >
                风险分<=阈值批量复核              </n-button>
              <n-button
                type="error"
                tertiary
                :loading="blockedRejectBatchLoading"
                :disabled="blockedOpportunities.length === 0"
                @click="rejectBlockedBatch"
              >
                一键忽略拦截
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
                  <td>￥{{ toMoney(trade.approved_buy_price) }}</td>
                  <td>￥{{ toMoney(trade.target_sell_price) }}</td>
                  <td>{{ trade.status }}</td>
                  <td class="title-cell">
                    {{ trade.listing_url || "-" }}
                  </td>
                  <td>
                    <div v-if="getPricingPreview(trade.trade_id)" class="pricing-preview">
                      <div class="pricing-main">
                        ￥{{ toMoney(getPricingPreview(trade.trade_id).recommended_price) }}
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
                          标记已挂售                        </n-button>
                        <n-button
                          size="small"
                          :type="trade.status === 'approved_for_buy' ? 'default' : 'success'"
                          @click="openMarkSold(trade)"
                        >
                          标记已卖出                        </n-button>
                      </n-space>
                      <n-space>
                        <n-button
                          v-if="trade.status === 'approved_for_buy'"
                          size="small"
                          :loading="executionLoadingTradeId === trade.trade_id && executionAction === 'buy_dry_run'"
                          @click="executeTradeBuy(trade, true)"
                        >
                          模拟买入
                        </n-button>
                        <n-button
                          v-if="trade.status === 'approved_for_buy'"
                          size="small"
                          type="error"
                          :loading="executionLoadingTradeId === trade.trade_id && executionAction === 'buy_live'"
                          @click="executeTradeBuy(trade, false)"
                        >
                          实盘买入
                        </n-button>
                        <n-button
                          v-if="trade.status === 'approved_for_buy'"
                          size="small"
                          :loading="executionLoadingTradeId === trade.trade_id && executionAction === 'list_dry_run'"
                          @click="executeTradeList(trade, true)"
                        >
                          模拟上架
                        </n-button>
                        <n-button
                          v-if="trade.status === 'approved_for_buy'"
                          size="small"
                          type="error"
                          :loading="executionLoadingTradeId === trade.trade_id && executionAction === 'list_live'"
                          @click="executeTradeList(trade, false)"
                        >
                          实盘上架
                        </n-button>
                        <n-button
                          v-if="trade.status === 'listed_for_sale'"
                          size="small"
                          :loading="executionLoadingTradeId === trade.trade_id && executionAction === 'sell_dry_run'"
                          @click="executeTradeSell(trade, true)"
                        >
                          模拟卖出
                        </n-button>
                        <n-button
                          v-if="trade.status === 'listed_for_sale'"
                          size="small"
                          type="error"
                          :loading="executionLoadingTradeId === trade.trade_id && executionAction === 'sell_live'"
                          @click="executeTradeSell(trade, false)"
                        >
                          实盘卖出
                        </n-button>
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
                          应用建议价                        </n-button>
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
                  <td>￥{{ toMoney(trade.approved_buy_price) }}</td>
                  <td>￥{{ toMoney(trade.sold_price) }}</td>
                  <td :class="{ good: (trade.sold_price || 0) > (trade.approved_buy_price || 0) }">
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
          <n-spin :show="loading || executionLogsLoading">
            <n-space style="margin-bottom: 12px" wrap>
              <n-input
                v-model:value="executionLogFilters.trade_id"
                clearable
                placeholder="交易ID"
                style="width: 120px"
              />
              <n-select
                v-model:value="executionLogFilters.action"
                :options="executionActionOptions"
                style="width: 140px"
              />
              <n-select
                v-model:value="executionLogFilters.provider"
                :options="executionProviderOptions"
                style="width: 140px"
              />
              <n-select
                v-model:value="executionLogFilters.mode"
                :options="executionModeOptions"
                style="width: 140px"
              />
              <n-select
                v-model:value="executionLogFilters.result"
                :options="executionResultOptions"
                style="width: 140px"
              />
              <n-button size="small" type="primary" :loading="executionLogsLoading" @click="loadExecutionLogs">
                刷新日志
              </n-button>
              <n-button size="small" tertiary @click="resetExecutionLogFilters">
                重置筛选              </n-button>
              <n-select
                v-model:value="executionRetryAction"
                :options="executionRetryActionOptions"
                style="width: 140px"
              />
              <n-input-number
                v-model:value="executionRetryLimit"
                :min="1"
                :max="200"
                style="width: 120px"
              />
              <n-switch v-model:value="executionRetryDryRun">
                <template #checked>retry dry-run</template>
                <template #unchecked>retry live</template>
              </n-switch>
              <n-switch v-model:value="executionRetryForce">
                <template #checked>force</template>
                <template #unchecked>strict</template>
              </n-switch>
              <n-button
                size="small"
                type="warning"
                :loading="executionRetryLoading"
                @click="retryFailedExecutions"
              >
                重试失败
              </n-button>
            </n-space>
            <div v-if="executionLogs.length === 0" class="empty-wrap">
              <n-empty description="暂无执行日志" />
            </div>
            <n-table v-else striped size="small">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>交易ID</th>
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
                  <td>{{ row.action }}</td>
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
          模式: {{ getModeText(batchPricingResult.mode) }} |
          已处理 {{ batchPricingResult.processed }} |
          已更新 {{ batchPricingResult.updated }} |
          当前为 {{ batchPricingResult.apply ? "应用结果" : "预览结果" }}
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
const automationStatusLoading = ref(false);
const automationActionLoading = ref("");
const executionRetryServiceStatusLoading = ref(false);
const executionRetryServiceActionLoading = ref("");

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
  if (!text)
    return "-";
  if (text.length <= max)
    return text;
  return `${text.slice(0, max)}...`;
};
const compactJson = (value) => {
  if (value == null || value === "")
    return "-";
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

const syncExecutionRetryServiceControls = (status) => {
  if (!status || executionRetryServiceControlInitialized.value)
    return;
  executionRetryServiceAction.value = status.action || "all";
  executionRetryServiceDryRun.value = Boolean(status.dry_run);
  executionRetryServiceExecutionForce.value = Boolean(status.force);
  executionRetryServiceControlInitialized.value = true;
};

const syncAutomationDefaults = (status) => {
  if (!status)
    return;
  automationIncludeMonitor.value = Boolean(status.default_include_monitor);
  automationIncludeScan.value = Boolean(status.default_include_scan);
  automationIncludeAutotrade.value = Boolean(status.default_include_autotrade);
  automationIncludeExecutionRetry.value = Boolean(status.default_include_execution_retry);
  automationScanLimit.value = Number(status.default_scan_limit || 0);
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

const executionProviderOptions = computed(() => {
  const options = [{ label: "鍏ㄩ儴通道", value: "all" }];
  const providers = new Set();
  if (executionStatus.value.provider)
    providers.add(String(executionStatus.value.provider));
  for (const row of executionLogs.value) {
    if (row?.provider)
      providers.add(String(row.provider));
  }
  return options.concat(
    Array.from(providers).sort().map((provider) => ({ label: provider, value: provider })),
  );
});

const buildExecutionLogParams = () => {
  const filters = executionLogFilters.value;
  const params = {
    limit: Number(filters.limit) > 0 ? Number(filters.limit) : 200,
  };

  const tradeId = Number(filters.trade_id);
  if (Number.isInteger(tradeId) && tradeId > 0)
    params.trade_id = tradeId;
  if (filters.action && filters.action !== "all")
    params.action = filters.action;
  if (filters.provider && filters.provider !== "all")
    params.provider = filters.provider;
  if (filters.mode === "dry")
    params.dry_run = true;
  else if (filters.mode === "live")
    params.dry_run = false;
  if (filters.result === "success")
    params.success = true;
  else if (filters.result === "failed")
    params.success = false;

  return params;
};

const loadExecutionLogs = async (silent = false) => {
  if (!silent)
    executionLogsLoading.value = true;
  try {
    const logsRes = await cardFlipApi.listExecutionLogs(buildExecutionLogParams());
    executionLogs.value = logsRes.items || [];
  } catch (error) {
    if (!silent)
      message.error(`鍔犺浇执行日志失败: ${error.message}`);
  } finally {
    if (!silent)
      executionLogsLoading.value = false;
  }
};

const resetExecutionLogFilters = async () => {
  executionLogFilters.value = { ...defaultExecutionLogFilters };
  await loadExecutionLogs();
};

const retryFailedExecutions = async () => {
  if (!executionRetryDryRun.value) {
    if (executionStatus.value.live_confirm_required && !executionLiveConfirmToken.value.trim()) {
      message.warning("请先输入实盘确认口令");
      return;
    }
    if (!window.confirm("确认执行失败记录重试（live）？"))
      return;
  }
  executionRetryLoading.value = true;
  try {
    const action = executionRetryAction.value === "all" ? null : executionRetryAction.value;
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
    await loadData();
  } catch (error) {
    message.error(`重试失败记录失败: ${error.message}`);
  } finally {
    executionRetryLoading.value = false;
  }
};

const loadAutomationStatus = async (silent = false) => {
  if (!silent)
    automationStatusLoading.value = true;
  try {
    const status = await cardFlipApi.getAutomationStatus();
    automationStatus.value = status || automationStatus.value;
    syncAutomationDefaults(status);
  } catch (error) {
    if (!silent)
      message.error(`加载 Automation 状态失败: ${error.message}`);
  } finally {
    if (!silent)
      automationStatusLoading.value = false;
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
    if (automationIncludeMonitor.value)
      stageReasons.push(res.monitor?.reason || "");
    if (automationIncludeAutotrade.value)
      stageReasons.push(res.autotrade?.reason || "");
    if (automationIncludeExecutionRetry.value)
      stageReasons.push(res.execution_retry?.reason || "");
    const allAlreadyRunning = stageReasons.length > 0 && stageReasons.every((reason) => reason === "already running");
    if (res.started_any) {
      message.success("Automation 一键启动已触发");
    } else if (allAlreadyRunning) {
      message.info("Automation 已在运行");
    } else {
      message.warning("Automation 启动未执行，请检查各子模块启用开关");
    }
    await loadData();
  } catch (error) {
    message.error(`Automation 启动失败: ${error.message}`);
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
    await loadData();
  } catch (error) {
    message.error(`Automation 停止失败: ${error.message}`);
  } finally {
    automationActionLoading.value = "";
  }
};

const runAutomationOnce = async () => {
  if (
    automationIncludeExecutionRetry.value
    && executionStatus.value.live_confirm_required
    && !executionRetryServiceStatus.value.confirm_token_configured
    && !executionLiveConfirmToken.value.trim()
  ) {
    message.warning("ExecutionRetry 可能需要实盘确认口令，请先填写口令或配置环境变量");
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
    message.success(
      `Automation 单次完成: 扫描 ${scanProcessed} 条, 审批 ${approved} 条, 重试 ${retried} 条`,
    );
    await loadData();
  } catch (error) {
    message.error(`Automation 单次执行失败: ${error.message}`);
  } finally {
    automationActionLoading.value = "";
  }
};

const loadAutotradeStatus = async (silent = false) => {
  if (!silent)
    autotradeStatusLoading.value = true;
  try {
    autotradeStatus.value = await cardFlipApi.getAutotradeStatus();
  } catch (error) {
    if (!silent)
      message.error(`鍔犺浇 AutoTrade 状态佸け璐? ${error.message}`);
  } finally {
    if (!silent)
      autotradeStatusLoading.value = false;
  }
};

const loadExecutionRetryServiceStatus = async (silent = false) => {
  if (!silent)
    executionRetryServiceStatusLoading.value = true;
  try {
    const status = await cardFlipApi.getExecutionRetryStatus();
    executionRetryServiceStatus.value = status || executionRetryServiceStatus.value;
    syncExecutionRetryServiceControls(status);
  } catch (error) {
    if (!silent)
      message.error(`加载 ExecutionRetry 状态失败: ${error.message}`);
  } finally {
    if (!silent)
      executionRetryServiceStatusLoading.value = false;
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
    await loadExecutionRetryServiceStatus(true);
  } catch (error) {
    message.error(`启动 ExecutionRetry 失败: ${error.message}`);
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
    await loadExecutionRetryServiceStatus(true);
  } catch (error) {
    message.error(`停止 ExecutionRetry 失败: ${error.message}`);
  } finally {
    executionRetryServiceActionLoading.value = "";
  }
};

const runExecutionRetryServiceOnce = async () => {
  if (!executionRetryServiceDryRun.value) {
    if (
      executionStatus.value.live_confirm_required
      && !executionRetryServiceStatus.value.confirm_token_configured
      && !executionLiveConfirmToken.value.trim()
    ) {
      message.warning("请先输入实盘确认口令，或在环境中配置 EXECUTION_RETRY_CONFIRM_TOKEN");
      return;
    }
    if (!window.confirm("确认执行 ExecutionRetry 单次 live 重试？"))
      return;
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
    await loadData();
  } catch (error) {
    message.error(`ExecutionRetry 单次执行失败: ${error.message}`);
  } finally {
    executionRetryServiceActionLoading.value = "";
  }
};

const loadData = async () => {
  loading.value = true;
  try {
    const [
      oppsRes,
      blockedRes,
      activeRes,
      listedRes,
      soldRes,
      metricsRes,
      autotradeRes,
      executionRes,
      executionRetryServiceRes,
      automationRes,
    ] = await Promise.all([
      cardFlipApi.listOpportunities("pending_review", 200),
      cardFlipApi.listOpportunities("blocked_risk", 200),
      cardFlipApi.listTrades("approved_for_buy", 200),
      cardFlipApi.listTrades("listed_for_sale", 200),
      cardFlipApi.listTrades("sold", 200),
      cardFlipApi.getMetrics(),
      cardFlipApi.getAutotradeStatus(),
      cardFlipApi.getExecutionStatus(),
      cardFlipApi.getExecutionRetryStatus(),
      cardFlipApi.getAutomationStatus(),
    ]);

    opportunities.value = oppsRes.items || [];
    blockedOpportunities.value = (blockedRes.items || []).map((item) => ({
      ...item,
      risk: parseRiskNote(item.risk_note),
    }));
    activeTrades.value = [...(activeRes.items || []), ...(listedRes.items || [])];
    soldTrades.value = soldRes.items || [];
    metrics.value = metricsRes;
    autotradeStatus.value = autotradeRes || autotradeStatus.value;
    executionStatus.value = executionRes || executionStatus.value;
    executionRetryServiceStatus.value = executionRetryServiceRes || executionRetryServiceStatus.value;
    automationStatus.value = automationRes || automationStatus.value;
    syncExecutionRetryServiceControls(executionRetryServiceRes);
    syncAutomationDefaults(automationRes);
    await loadExecutionLogs(true);
  } catch (error) {
    message.error(`加载失败: ${error.message}`);
  } finally {
    loading.value = false;
  }
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
    await loadAutotradeStatus(true);
  } catch (error) {
    message.error(`启动 AutoTrade 失败: ${error.message}`);
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
    await loadAutotradeStatus(true);
  } catch (error) {
    message.error(`停止 AutoTrade 失败: ${error.message}`);
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
    message.success(
      `AutoTrade 单次执行完成: 审批 ${res.approved || 0} 条, 扫描 ${res.considered || 0} 条${listExecSummary}`,
    );
    await loadData();
  } catch (error) {
    message.error(`AutoTrade 单次执行失败: ${error.message}`);
  } finally {
    autotradeActionLoading.value = "";
  }
};

const executeTradeBuy = async (trade, dryRun = true) => {
  if (!dryRun) {
    if (executionStatus.value.live_confirm_required && !executionLiveConfirmToken.value.trim()) {
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
    await loadExecutionLogs(true);
  } catch (error) {
    message.error(`买入执行失败: ${error.message}`);
  } finally {
    executionLoadingTradeId.value = null;
    executionAction.value = "";
  }
};

const executeTradeList = async (trade, dryRun = true) => {
  if (!dryRun) {
    if (executionStatus.value.live_confirm_required && !executionLiveConfirmToken.value.trim()) {
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
    await loadData();
  } catch (error) {
    message.error(`上架执行失败: ${error.message}`);
  } finally {
    executionLoadingTradeId.value = null;
    executionAction.value = "";
  }
};

const executeTradeSell = async (trade, dryRun = true) => {
  if (!dryRun) {
    if (executionStatus.value.live_confirm_required && !executionLiveConfirmToken.value.trim()) {
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
    await loadData();
  } catch (error) {
    message.error(`卖出执行失败: ${error.message}`);
  } finally {
    executionLoadingTradeId.value = null;
    executionAction.value = "";
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

const refreshCookie = async () => {
  if (!window.confirm("将刷新闲鱼 Cookie，过程中会关闭 Chrome/Edge。确认继续？"))
    return;
  cookieRefreshLoading.value = true;
  try {
    const res = await cardFlipApi.refreshMonitorCookie(true);
    if (res.success) {
      message.success(
        `Cookie 刷新成功: 长度 ${res.cookie_len || 0}, _m_h5_tk=${res.has_m_h5_tk ? "ok" : "missing"}, _m_h5_tk_enc=${res.has_m_h5_tk_enc ? "ok" : "missing"}`,
      );
      await loadData();
      return;
    }
    message.error(`Cookie 刷新失败: ${res.error || res.stderr || "unknown"}`);
  } catch (error) {
    message.error(`Cookie 刷新失败: ${error.message}`);
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
  if (!approveForm.value.opportunity_id || approveForm.value.approved_buy_price <= 0) {
    message.warning("请填写有效的审批价格");
    return false;
  }
  approving.value = true;
  try {
    const res = await cardFlipApi.approveTrade(approveForm.value);
    message.success(
      `审批成功，交易ID: ${res.trade_id}，建议挂牌价: ￥${toMoney(res.target_sell_price)}`,
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
    const res = await cardFlipApi.rejectOpportunity(item.opportunity_id);
    const logSuffix = res?.reject_log_id ? `，日志#${res.reject_log_id}` : "";
    message.success(`已忽略机会 #${item.opportunity_id}${logSuffix}`);
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

const rejectBlockedBatch = async () => {
  if (!blockedOpportunities.value.length) {
    message.info("当前没有可忽略的风控拦截机会");
    return;
  }
  if (!window.confirm(`确认批量忽略当前 ${blockedOpportunities.value.length} 条风控拦截机会？`)) {
    return;
  }
  blockedRejectBatchLoading.value = true;
  try {
    const res = await cardFlipApi.rejectBlockedBatch(
      200,
      "manual batch reject from blocked list",
    );
    message.success(
      `批量忽略完成: 扫描 ${res.scanned || 0} 条, 已忽略 ${res.rejected || 0} 条, 已入库 ${res.logged || 0} 条`,
    );
    await loadData();
  } catch (error) {
    message.error(`批量忽略失败: ${error.message}`);
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
      message.success(`交易 #${trade.trade_id} 已应用建议价 ￥${toMoney(res.recommended_price)}`);
    } else {
      message.info(`交易 #${trade.trade_id} 当前价格已接近建议价，保持不变`);
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
    message.success(`预览完成: 处理 ${res.processed} 条, 建议调整 ${res.items?.filter((v) => v.action !== "keep").length || 0} 条`);
  } catch (error) {
    message.error(`批量预览失败: ${error.message}`);
  } finally {
    batchPricingLoading.value = false;
  }
};

const applyBatchReprice = async () => {
  if (!window.confirm("确认按当前模式批量应用建议价格？该操作会更新进行中交易的目标卖价。")) {
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
    message.success(`批量应用完成: 处理 ${res.processed} 条, 更新 ${res.updated} 条`);
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

.autotrade-panel {
  margin-bottom: var(--spacing-lg);
  padding: var(--spacing-md);
  border-radius: var(--border-radius-large);
  background: var(--bg-primary);
  box-shadow: var(--shadow-light);
}

.autotrade-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--spacing-md);
}

.autotrade-title-wrap h3 {
  margin: 0;
}

.autotrade-tags {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.autotrade-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 10px;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}

.autotrade-once {
  margin-top: 12px;
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

  .autotrade-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>





