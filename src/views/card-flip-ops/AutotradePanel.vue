<template>
  <section class="service-panel autotrade-panel">
    <div class="service-head">
      <div class="service-copy">
        <div class="service-kicker">AutoTrade</div>
        <h3>Approval Engine</h3>
        <p>Handles automated approval, buy execution, and listing flow. This is the main execution panel for card flip operations.</p>
        <div class="service-tags">
          <n-tag size="small" :type="autotradeStatus.running ? 'success' : 'default'">
            {{ autotradeStatus.running ? "Running" : "Stopped" }}
          </n-tag>
          <n-tag size="small" :type="autotradeStatus.enabled ? 'info' : 'warning'">
            {{ autotradeStatus.enabled ? "Enabled" : "Disabled" }}
          </n-tag>
          <n-tag size="small" :type="executionStatus.live_enabled ? 'error' : 'warning'">
            {{ executionStatus.live_enabled ? "Live lane" : "Dry-run lane" }}
          </n-tag>
        </div>
      </div>

      <n-space>
        <n-button
          size="small"
          type="primary"
          :disabled="!canOperate"
          :loading="autotradeActionLoading === 'start'"
          @click="$emit('startAutotrade')"
        >
          Start
        </n-button>
        <n-button
          size="small"
          :disabled="!canOperate"
          :loading="autotradeActionLoading === 'stop'"
          @click="$emit('stopAutotrade')"
        >
          Stop
        </n-button>
        <n-button
          tertiary
          size="small"
          :loading="autotradeStatusLoading"
          @click="$emit('loadAutotradeStatus')"
        >
          Refresh Status
        </n-button>
      </n-space>
    </div>

    <div class="service-summary-grid">
      <div class="summary-chip">
        <span class="summary-label">Execution Lane</span>
        <strong class="summary-value">{{ executionStatus.provider || "-" }}</strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">Loop Interval</span>
        <strong class="summary-value">{{ autotradeStatus.interval_sec ?? "-" }}s</strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">Batch Limit</span>
        <strong class="summary-value">{{ autotradeStatus.batch_size ?? "-" }}</strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">Min Score</span>
        <strong class="summary-value">{{ autotradeStatus.min_score ?? "-" }}</strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">Min ROI</span>
        <strong class="summary-value">{{ toPercent(autotradeStatus.min_roi || 0) }}</strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">Risk Ceiling</span>
        <strong class="summary-value">{{ autotradeStatus.max_risk_score ?? "-" }}</strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">Loss Guard</span>
        <strong class="summary-value">
          {{
            autotradeStatus.loss_recovery_state?.active
              ? "Recovery"
              : autotradeStatus.profit_guard?.blocked
                ? "Blocked"
                : autotradeStatus.profit_guard?.enabled
                  ? "Armed"
                  : "Disabled"
          }}
        </strong>
      </div>
      <div class="summary-chip summary-chip-wide">
        <span class="summary-label">Automatic Actions</span>
        <strong class="summary-value">
          Buy={{ autotradeStatus.auto_execute_buy_on_approve ? "on" : "off" }}
          / Buy mode={{ autotradeStatus.auto_execute_buy_dry_run ? "dry-run" : "live" }}
          / List={{ autotradeStatus.auto_execute_list_on_buy_success ? "on" : "off" }}
          / List mode={{ autotradeStatus.auto_execute_list_dry_run ? "dry-run" : "live" }}
        </strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">Last Run</span>
        <strong class="summary-value">{{ autotradeStatus.last_run_at || "-" }}</strong>
      </div>
      <div
        v-if="Array.isArray(autotradeStatus.source_position_controls) && autotradeStatus.source_position_controls.length"
        class="summary-chip summary-chip-wide"
      >
        <span class="summary-label">Source Positioning</span>
        <strong class="summary-value">
          {{
            autotradeStatus.source_position_controls
              .slice(0, 3)
              .map(item => `${item.source}:${item.strategy_mode}/cap ${item.batch_cap}/${toMoney(item.capital_cap || 0)}`)
              .join(" | ")
          }}
        </strong>
      </div>
      <div
        v-if="Array.isArray(autotradeStatus.seller_position_controls) && autotradeStatus.seller_position_controls.length"
        class="summary-chip summary-chip-wide"
      >
        <span class="summary-label">Seller Positioning</span>
        <strong class="summary-value">
          {{
            autotradeStatus.seller_position_controls
              .slice(0, 3)
              .map(item => `${item.source}/${item.seller_id}:${item.seller_lane}/cap ${item.batch_cap}`)
              .join(" | ")
          }}
        </strong>
      </div>
      <div
        v-if="Array.isArray(autotradeStatus.seller_controls?.items) && autotradeStatus.seller_controls.items.length"
        class="summary-chip summary-chip-wide"
      >
        <span class="summary-label">Seller Guards</span>
        <strong class="summary-value">
          {{
            autotradeStatus.seller_controls.items
              .slice(0, 3)
              .map((item) => {
                const runtime = item.runtime_control || {};
                const state = item.state || "normal";
                if (state === "observe") {
                  const progress = Math.round(Number(runtime.recovery_progress || 0) * 100);
                  return `${item.source}/${item.seller_id}:observe(${progress}%)`;
                }
                return `${item.source}/${item.seller_id}:${state}`;
              })
              .join(" | ")
          }}
        </strong>
      </div>
      <div
        v-if="autotradeStatus.seller_controls?.daily_report"
        class="summary-chip summary-chip-wide"
      >
        <span class="summary-label">Seller Ledger</span>
        <strong class="summary-value">
          {{
            [
              `freeze ${autotradeStatus.seller_controls.daily_report.counts_by_type?.auto_freeze || 0}`,
              `observe ${autotradeStatus.seller_controls.daily_report.counts_by_type?.auto_observe || 0}`,
              `complete ${autotradeStatus.seller_controls.daily_report.counts_by_type?.observe_complete || 0}`,
            ].join(" / ")
          }}
        </strong>
        <span class="summary-meta">
          {{
            autotradeStatus.seller_controls.daily_report.latest_event
              ? `${autotradeStatus.seller_controls.daily_report.latest_event.source}/${autotradeStatus.seller_controls.daily_report.latest_event.seller_id} -> ${autotradeStatus.seller_controls.daily_report.latest_event.event_type}`
              : "No recent seller-control events"
          }}
        </span>
      </div>
    </div>

    <div
      v-if="Array.isArray(metrics?.profit_cockpit?.seller_attribution_all_time) && metrics.profit_cockpit.seller_attribution_all_time.length"
      class="service-section"
    >
      <div class="section-title">Seller Attribution</div>
      <div class="section-subtitle">
        Shows the best all-time sellers together with current lane and reputation.
      </div>
      <div v-if="canOperate" class="seller-batch-bar">
        <div class="summary-meta">{{ selectedSellerKeys.length }} selected</div>
        <div class="seller-template-grid">
          <button
            v-for="template in sellerBatchTemplates"
            :key="template.key"
            class="seller-template-card"
            type="button"
            :disabled="template.items.length === 0"
            @click="applySellerTemplate(template)"
          >
            <strong>{{ template.label }}</strong>
            <span class="summary-meta">{{ template.items.length }} sellers · {{ template.action }}</span>
            <span class="summary-meta">{{ template.reason }}</span>
          </button>
        </div>
        <div class="seller-preset-manager">
          <div class="summary-meta">Team preset source: {{ activeSellerSelector.label }}</div>
          <div v-if="showRecommendedSellerPresetBar && recommendedSellerPreset" class="seller-recommend-bar">
            <span class="summary-meta">
              Recommended: {{ activeRecommendedSellerPreset.name }}
              <template v-if="savedSellerPresetRankText(activeRecommendedSellerPreset)">
                · {{ savedSellerPresetRankText(recommendedSellerPreset) }}
              </template>
            </span>
            <span class="summary-meta">{{ recommendedSellerPresetReasonText(recommendedSellerPreset) }}</span>
            <n-button
              size="small"
              type="primary"
              @click="applySavedSellerPreset(recommendedSellerPreset)"
            >
              Apply Top 1
            </n-button>
          </div>
          <div
            v-else-if="showDismissedSellerPresetBar && activeRecommendedSellerPreset"
            class="seller-recommend-bar is-muted"
          >
            <span class="summary-meta">
              {{ sellerPresetRecommendationDismissedText || `${activeRecommendedSellerPreset.name} hidden until it changes.` }}
            </span>
            <n-button
              secondary
              size="small"
              @click="$emit('restoreSellerPresetRecommendation')"
            >
              Show Again
            </n-button>
          </div>
          <div class="seller-preset-form">
            <n-input
              placeholder="Preset name"
              v-model:value="sellerPresetName"
            ></n-input>
            <n-select
              v-model:value="sellerPresetAction"
              :options="sellerPresetActionOptions"
            ></n-select>
            <n-button
              type="primary"
              :disabled="!sellerPresetName.trim()"
              :loading="sellerControlPresetActionLoading === `save:${sellerPresetName.trim()}`"
              @click="saveCurrentSellerPreset"
            >
              Save Preset
            </n-button>
          </div>
        </div>
        <div v-if="savedSellerPresets.length" class="seller-template-grid">
          <button
            v-for="preset in sortedSavedSellerPresets"
            :key="preset.id"
            class="seller-template-card"
            type="button"
            :class="[{ 'is-recommended': recommendedSellerPreset?.id === preset.id }]"
            @click="applySavedSellerPreset(preset)"
          >
            <strong>{{ preset.name }}</strong>
            <span v-if="savedSellerPresetRankText(preset)" class="summary-meta">
              {{ savedSellerPresetRankText(preset) }}
            </span>
            <span class="summary-meta">
              {{ formatSellerSelectorLabel(preset.base_preset, preset.source_filter) }}
              · {{ savedSellerPresetMatchCount(preset) }} visible
            </span>
            <span class="summary-meta">
              {{ preset.action }}
              <template v-if="preset.duration_hours"> · {{ preset.duration_hours }}h</template>
            </span>
            <span class="summary-meta">{{ savedSellerPresetStatsText(preset) }}</span>
            <span class="summary-meta">{{ savedSellerPresetLastRunText(preset) }}</span>
            <span class="summary-meta">{{ savedSellerPresetLastTargetsText(preset) }}</span>
            <span class="summary-meta">{{ preset.reason || "No reason" }}</span>
            <div v-if="Array.isArray(preset.recent_runs) && preset.recent_runs.length" class="seller-preset-history">
              <div
                v-for="run in preset.recent_runs.slice(0, 3)"
                :key="run.id"
                class="seller-preset-history-row"
              >
                <span class="summary-meta">{{ savedSellerPresetHistoryText(run) }}</span>
                <span class="summary-meta">{{ savedSellerPresetHistoryTargets(run) }}</span>
              </div>
            </div>
            <div class="seller-row-actions">
              <n-button
                tertiary
                size="tiny"
                @click.stop="applySavedSellerPreset(preset)"
              >
                Apply
              </n-button>
              <n-button
                tertiary
                size="tiny"
                :loading="sellerControlPresetHistoryLoading && selectedPresetHistoryId === preset.id"
                @click.stop="openSellerPresetHistory(preset)"
              >
                History
              </n-button>
              <n-button
                tertiary
                size="tiny"
                type="error"
                :loading="sellerControlPresetActionLoading === `delete:${preset.id}`"
                @click.stop="$emit('deleteSellerControlPreset', preset.id)"
              >
                Delete
              </n-button>
            </div>
          </button>
        </div>
        <n-drawer placement="right" width="min(560px, 100vw)" v-model:show="sellerPresetHistoryVisible">
          <n-drawer-content
            closable
            :title="selectedPresetHistory ? `${selectedPresetHistory.name} History` : 'Preset History'"
          >
            <template v-if="selectedPresetHistory">
              <div class="seller-detail-state">
                <n-tag size="small" type="info">
                  {{ formatSellerSelectorLabel(selectedPresetHistory.base_preset, selectedPresetHistory.source_filter) }}
                </n-tag>
                <span class="summary-meta">{{ savedSellerPresetStatsText(selectedPresetHistory) }}</span>
              </div>
              <div v-if="sellerControlPresetHistoryLoading" class="summary-meta">
                Loading preset history...
              </div>
              <div v-else-if="Array.isArray(sellerControlPresetHistory?.items) && sellerControlPresetHistory.items.length" class="seller-detail-list">
                <div
                  v-for="run in sellerControlPresetHistory.items"
                  :key="run.id"
                  class="seller-detail-row"
                >
                  <div class="seller-detail-main">
                    <strong>{{ savedSellerPresetHistoryText(run) }}</strong>
                    <span class="summary-meta">{{ run.reason || "No reason" }}</span>
                  </div>
                  <div class="seller-detail-side">
                    <span class="summary-meta">{{ savedSellerPresetHistoryTargets(run) }}</span>
                  </div>
                </div>
              </div>
              <div v-else class="summary-meta">
                No preset history recorded yet.
              </div>
            </template>
          </n-drawer-content>
        </n-drawer>
        <n-space wrap class="seller-preset-row">
          <n-button secondary size="tiny" @click="selectSellerPreset('all')">
            Visible
          </n-button>
          <n-button secondary size="tiny" @click="selectSellerPreset('manual')">
            Manual
          </n-button>
          <n-button secondary size="tiny" @click="selectSellerPreset('losing')">
            Losing
          </n-button>
          <n-button secondary size="tiny" @click="selectSellerPreset('observe')">
            Observe
          </n-button>
          <n-button secondary size="tiny" @click="selectSellerPreset('frozen')">
            Frozen
          </n-button>
          <n-button secondary size="tiny" @click="selectSellerPreset('clear')">
            Clear
          </n-button>
          <n-button
            v-for="source in visibleSellerSources"
            :key="source"
            secondary
            size="tiny"
            @click="selectSellerPreset('source', source)"
          >
            {{ source }}
          </n-button>
        </n-space>
        <div class="seller-control-form">
          <n-input
            placeholder="Batch reason"
            v-model:value="batchSellerActionNote"
          ></n-input>
          <n-input-number
            placeholder="Duration (hours)"
            v-model:value="batchSellerActionDurationHours"
            :max="24 * 30"
            :min="1"
          ></n-input-number>
        </div>
        <n-space wrap>
          <n-button
            size="small"
            type="error"
            :disabled="selectedSellerKeys.length === 0"
            :loading="sellerControlBatchActionLoading === 'freeze'"
            @click="submitSellerBatchAction('freeze')"
          >
            Batch Freeze
          </n-button>
          <n-button
            size="small"
            type="warning"
            :disabled="selectedSellerKeys.length === 0"
            :loading="sellerControlBatchActionLoading === 'observe'"
            @click="submitSellerBatchAction('observe')"
          >
            Batch Observe
          </n-button>
          <n-button
            size="small"
            :disabled="selectedSellerKeys.length === 0"
            :loading="sellerControlBatchActionLoading === 'normal'"
            @click="submitSellerBatchAction('normal')"
          >
            Batch Restore
          </n-button>
        </n-space>
      </div>
      <div class="seller-attribution-table">
        <table class="ops-table">
          <thead>
            <tr>
              <th v-if="canOperate">Select</th>
              <th>Seller</th>
              <th>All-time Net</th>
              <th>Sold</th>
              <th>Hit Rate</th>
              <th>Avg ROI</th>
              <th>Lane</th>
              <th>Reputation</th>
              <th>Override</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in visibleSellerAttributionItems"
              :key="`${item.source}-${item.seller_id}`"
            >
              <td v-if="canOperate" class="seller-selection-cell">
                <n-checkbox
                  :checked="sellerSelected(item)"
                  @update:checked="toggleSellerSelection(item, $event)"
                ></n-checkbox>
              </td>
              <td>{{ item.source }}/{{ item.seller_id }}</td>
              <td :class="{ good: Number(item.realized_net_profit || 0) > 0 }">
                {{ toMoney(item.realized_net_profit || 0) }}
              </td>
              <td>{{ item.sold_count || 0 }}</td>
              <td>{{ toPercent(item.profit_hit_rate || 0) }}</td>
              <td>{{ toPercent(item.avg_realized_roi || 0) }}</td>
              <td>{{ item.seller_lane || "neutral" }}</td>
              <td>{{ Number(item.reputation_score || 0).toFixed(1) }}</td>
              <td class="seller-override-cell">
                <template v-if="sellerHasManualOverride(item)">
                  <n-tag size="small" :type="sellerStateType(item, item.current_control)">
                    {{ sellerManualOverrideLabel(item) }}
                  </n-tag>
                  <span v-if="sellerManualOverrideMeta(item)" class="summary-meta">
                    {{ sellerManualOverrideMeta(item) }}
                  </span>
                </template>
                <span v-else class="summary-meta">Auto</span>
              </td>
              <td>
                <div class="seller-row-actions">
                  <n-button
                    text
                    type="primary"
                    @click="openSellerDetail(item, autotradeStatus.seller_controls?.items || [])"
                  >
                    View
                  </n-button>
                  <n-button
                    v-if="canOperate && sellerHasManualOverride(item)"
                    text
                    :loading="sellerControlActionLoading === sellerActionKey('normal', item)"
                    @click="submitSellerControlAction('normal', item, 'manual override cleared from leaderboard')"
                  >
                    Clear
                  </n-button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <n-drawer placement="right" width="min(560px, 100vw)" v-model:show="sellerDetailVisible">
      <n-drawer-content closable :title="selectedSeller ? `${selectedSeller.source}/${selectedSeller.seller_id}` : 'Seller Detail'">
        <template v-if="selectedSeller">
          <div class="seller-detail-state">
            <n-tag size="small" :type="sellerStateType(selectedSeller, selectedSellerRuntime)">
              {{ sellerStateLabel(selectedSeller, selectedSellerRuntime) }}
            </n-tag>
            <span class="summary-meta">
              {{
                selectedSeller.current_control?.reason
                  || selectedSeller.lane_summary
                  || "No active seller guard note"
              }}
            </span>
            <span v-if="sellerCurrentAuditText(selectedSeller)" class="summary-meta">
              {{ sellerCurrentAuditText(selectedSeller) }}
            </span>
          </div>

          <div class="seller-detail-grid">
            <div class="summary-chip">
              <span class="summary-label">All-time Net</span>
              <strong class="summary-value" :class="{ good: Number(selectedSeller.realized_net_profit || 0) > 0 }">
                {{ toMoney(selectedSeller.realized_net_profit || 0) }}
              </strong>
            </div>
            <div class="summary-chip">
              <span class="summary-label">Sold</span>
              <strong class="summary-value">{{ selectedSeller.sold_count || 0 }}</strong>
            </div>
            <div class="summary-chip">
              <span class="summary-label">Hit Rate</span>
              <strong class="summary-value">{{ toPercent(selectedSeller.profit_hit_rate || 0) }}</strong>
            </div>
            <div class="summary-chip">
              <span class="summary-label">Avg ROI</span>
              <strong class="summary-value">{{ toPercent(selectedSeller.avg_realized_roi || 0) }}</strong>
            </div>
            <div class="summary-chip">
              <span class="summary-label">Lane</span>
              <strong class="summary-value">{{ selectedSeller.seller_lane || "neutral" }}</strong>
            </div>
            <div class="summary-chip">
              <span class="summary-label">Reputation</span>
              <strong class="summary-value">{{ Number(selectedSeller.reputation_score || 0).toFixed(1) }}</strong>
            </div>
          </div>

          <div class="service-section seller-detail-section">
            <div class="section-title">Manual Controls</div>
            <div class="section-subtitle">Apply a manual seller override when you want to freeze, observe, or restore this seller immediately.</div>
            <div class="seller-control-form">
              <n-input
                placeholder="Optional reason"
                v-model:value="sellerActionNote"
              ></n-input>
              <n-input-number
                placeholder="Duration (hours)"
                v-model:value="sellerActionDurationHours"
                :max="24 * 30"
                :min="1"
              ></n-input-number>
            </div>
            <n-space wrap>
              <n-button
                size="small"
                type="error"
                :disabled="!canOperate"
                :loading="sellerControlActionLoading === sellerActionKey('freeze', selectedSeller)"
                @click="submitSellerControlAction('freeze')"
              >
                Freeze
              </n-button>
              <n-button
                size="small"
                type="warning"
                :disabled="!canOperate"
                :loading="sellerControlActionLoading === sellerActionKey('observe', selectedSeller)"
                @click="submitSellerControlAction('observe')"
              >
                Observe
              </n-button>
              <n-button
                size="small"
                :disabled="!canOperate"
                :loading="sellerControlActionLoading === sellerActionKey('normal', selectedSeller)"
                @click="submitSellerControlAction('normal')"
              >
                Restore
              </n-button>
            </n-space>
          </div>

          <div class="service-section seller-detail-section">
            <div class="section-title">Recent Trades</div>
            <div class="section-subtitle">Recent realized trades for this seller, so you can see whether it is making money or dragging the strategy down.</div>
            <div v-if="Array.isArray(selectedSeller.recent_trades) && selectedSeller.recent_trades.length" class="seller-detail-list">
              <div
                v-for="trade in selectedSeller.recent_trades"
                :key="trade.trade_id"
                class="seller-detail-row"
              >
                <div class="seller-detail-main">
                  <strong>#{{ trade.trade_id }} {{ trade.title || "-" }}</strong>
                  <span class="summary-meta">{{ trade.sold_at || "-" }}</span>
                </div>
                <div class="seller-detail-side">
                  <strong :class="{ good: Number(trade.net_profit || 0) > 0 }">
                    {{ toMoney(trade.net_profit || 0) }}
                  </strong>
                  <span class="summary-meta">
                    ROI {{ toPercent(trade.roi || 0) }}
                    | Buy {{ toMoney(trade.approved_buy_price || 0) }}
                    | Sell {{ toMoney(trade.sold_price || 0) }}
                  </span>
                </div>
              </div>
            </div>
            <div v-else class="summary-meta">No realized trades for this seller yet.</div>
          </div>

          <div class="service-section seller-detail-section">
            <div class="section-title">Control History</div>
            <div class="section-subtitle">Recent freeze, observe, and release events for this seller.</div>
            <div
              v-if="Array.isArray(selectedSeller.recent_control_events) && selectedSeller.recent_control_events.length"
              class="seller-detail-list"
            >
              <div
                v-for="event in selectedSeller.recent_control_events"
                :key="event.id"
                class="seller-detail-row"
              >
                <div class="seller-detail-main">
                  <n-tag size="small" :type="sellerEventType(event.event_type)">
                    {{ event.event_type || "event" }}
                  </n-tag>
                  <span class="summary-meta">{{ event.created_at || "-" }}</span>
                </div>
                <div class="seller-detail-side">
                  <span class="summary-meta">{{ event.reason || "-" }}</span>
                  <span v-if="sellerEventAuditText(event)" class="summary-meta">{{ sellerEventAuditText(event) }}</span>
                </div>
              </div>
            </div>
            <div v-else class="summary-meta">No seller-control events recorded for this seller.</div>
          </div>
        </template>
      </n-drawer-content>
    </n-drawer>
    <div class="service-section">
      <div class="section-title">Run Once</div>
      <div class="section-subtitle">High-frequency manual actions live here, useful for one-off retries or post-release checks.</div>
      <n-space wrap>
        <n-input
          placeholder="Live confirmation token"
          show-password-on="click"
          style="width: 220px"
          type="password"
          :disabled="!executionStatus.live_confirm_required"
          :value="executionLiveConfirmToken"
          @update:value="value => $emit('update:executionLiveConfirmToken', value)"
        ></n-input>
        <n-input-number
          placeholder="Approval count"
          style="width: 160px"
          :max="500"
          :min="0"
          :value="autotradeRunLimit"
          @update:value="value => $emit('update:autotradeRunLimit', value)"
        ></n-input-number>
        <n-switch
          :value="autotradeRunForce"
          @update:value="value => $emit('update:autotradeRunForce', value)"
        >
          <template #checked>Force run</template>
          <template #unchecked>Respect guards</template>
        </n-switch>
        <n-button
          type="warning"
          :loading="autotradeActionLoading === 'run_once'"
          @click="$emit('runAutotradeOnce')"
        >
          Run once
        </n-button>
      </n-space>
    </div>

    <div v-if="canOperate" class="service-section">
      <n-collapse>
        <n-collapse-item name="exec-live-settings" title="Execution Settings">
          <n-space wrap>
            <n-button-group size="small">
              <n-button
                :loading="executionConfigLoading"
                :type="executionStatus.provider === 'mock' ? 'primary' : 'default'"
                @click="$emit('setExecutionProvider', 'mock')"
              >
                mock
              </n-button>
              <n-button
                :loading="executionConfigLoading"
                :type="executionStatus.provider === 'webhook' ? 'primary' : 'default'"
                @click="$emit('setExecutionProvider', 'webhook')"
              >
                webhook
              </n-button>
              <n-button
                :loading="executionConfigLoading"
                :type="['disabled', 'none'].includes(executionStatus.provider) ? 'warning' : 'default'"
                @click="$emit('setExecutionProvider', 'disabled')"
              >
                disabled
              </n-button>
            </n-button-group>

            <n-button
              size="small"
              :loading="executionConfigLoading"
              :type="executionStatus.live_enabled ? 'success' : 'default'"
              @click="$emit('toggleExecutionFlag', 'live_enabled')"
            >
              {{ executionStatus.live_enabled ? "Live execution: on" : "Live execution: off" }}
            </n-button>

            <n-button
              size="small"
              :loading="executionConfigLoading"
              :type="executionStatus.live_confirm_required ? 'primary' : 'default'"
              @click="$emit('toggleExecutionFlag', 'live_confirm_required')"
            >
              {{ executionStatus.live_confirm_required ? "Double confirm: on" : "Double confirm: off" }}
            </n-button>

            <n-button-group size="small">
              <n-button
                :disabled="executionConfigLoading"
                @click="$emit('adjustExecutionNumber', 'live_max_buy_price', -5, 0, 1000000)"
              >
                -5 buy cap
              </n-button>
              <n-button quaternary>
                {{
                  executionStatus.live_max_buy_price > 0
                    ? `Buy cap ${toMoney(executionStatus.live_max_buy_price)}`
                    : "Buy cap unlimited"
                }}
              </n-button>
              <n-button
                :disabled="executionConfigLoading"
                @click="$emit('adjustExecutionNumber', 'live_max_buy_price', 5, 0, 1000000)"
              >
                +5 buy cap
              </n-button>
            </n-button-group>

            <n-button-group size="small">
              <n-button
                :disabled="executionConfigLoading"
                @click="$emit('adjustExecutionNumber', 'live_min_list_profit_ratio', -0.01, 0, 3)"
              >
                -1% list profit
              </n-button>
              <n-button quaternary>
                List profit {{ toPercent(executionStatus.live_min_list_profit_ratio || 0) }}
              </n-button>
              <n-button
                :disabled="executionConfigLoading"
                @click="$emit('adjustExecutionNumber', 'live_min_list_profit_ratio', 0.01, 0, 3)"
              >
                +1% list profit
              </n-button>
            </n-button-group>

            <n-button-group size="small">
              <n-button
                :disabled="executionConfigLoading"
                @click="$emit('adjustExecutionNumber', 'live_min_sell_profit_ratio', -0.01, 0, 3)"
              >
                -1% sell profit
              </n-button>
              <n-button quaternary>
                Sell profit {{ toPercent(executionStatus.live_min_sell_profit_ratio || 0) }}
              </n-button>
              <n-button
                :disabled="executionConfigLoading"
                @click="$emit('adjustExecutionNumber', 'live_min_sell_profit_ratio', 0.01, 0, 3)"
              >
                +1% sell profit
              </n-button>
            </n-button-group>
          </n-space>
        </n-collapse-item>
        <n-collapse-item name="autotrade-quick-tune" title="Quick Tune">
          <n-space wrap>
            <n-button-group size="small">
              <n-button
                :disabled="autotradeConfigLoading"
                @click="$emit('adjustAutotradeNumber', 'interval_sec', -5, 5, 3600)"
              >
                -5s
              </n-button>
              <n-button quaternary>{{ autotradeStatus.interval_sec ?? "-" }}s</n-button>
              <n-button
                :disabled="autotradeConfigLoading"
                @click="$emit('adjustAutotradeNumber', 'interval_sec', 5, 5, 3600)"
              >
                +5s
              </n-button>
            </n-button-group>

            <n-button-group size="small">
              <n-button
                :disabled="autotradeConfigLoading"
                @click="$emit('adjustAutotradeNumber', 'batch_size', -1, 1, 500)"
              >
                -1 batch
              </n-button>
              <n-button quaternary>Batch {{ autotradeStatus.batch_size ?? "-" }}</n-button>
              <n-button
                :disabled="autotradeConfigLoading"
                @click="$emit('adjustAutotradeNumber', 'batch_size', 1, 1, 500)"
              >
                +1 batch
              </n-button>
            </n-button-group>

            <n-button-group size="small">
              <n-button
                :disabled="autotradeConfigLoading"
                @click="$emit('adjustAutotradeNumber', 'min_score', -1, 0, 100)"
              >
                -1 score
              </n-button>
              <n-button quaternary>Score {{ autotradeStatus.min_score ?? "-" }}</n-button>
              <n-button
                :disabled="autotradeConfigLoading"
                @click="$emit('adjustAutotradeNumber', 'min_score', 1, 0, 100)"
              >
                +1 score
              </n-button>
            </n-button-group>

            <n-button-group size="small">
              <n-button :disabled="autotradeConfigLoading" @click="$emit('adjustAutotradeRoi', -0.01)">
                -1% ROI
              </n-button>
              <n-button quaternary>ROI {{ toPercent(autotradeStatus.min_roi || 0) }}</n-button>
              <n-button :disabled="autotradeConfigLoading" @click="$emit('adjustAutotradeRoi', 0.01)">
                +1% ROI
              </n-button>
            </n-button-group>

            <n-button-group size="small">
              <n-button
                :disabled="autotradeConfigLoading"
                @click="$emit('adjustAutotradeNumber', 'max_risk_score', -1, 0, 100)"
              >
                -1 risk
              </n-button>
              <n-button quaternary>Risk {{ autotradeStatus.max_risk_score ?? "-" }}</n-button>
              <n-button
                :disabled="autotradeConfigLoading"
                @click="$emit('adjustAutotradeNumber', 'max_risk_score', 1, 0, 100)"
              >
                +1 risk
              </n-button>
            </n-button-group>

            <n-button
              size="small"
              :loading="autotradeConfigLoading"
              :type="autotradeStatus.require_risk_score ? 'primary' : 'default'"
              @click="$emit('toggleAutotradeFlag', 'require_risk_score')"
            >
              {{ autotradeStatus.require_risk_score ? "Risk score required: on" : "Risk score required: off" }}
            </n-button>

            <n-button
              size="small"
              :loading="autotradeConfigLoading"
              :type="autotradeStatus.auto_execute_buy_on_approve ? 'success' : 'default'"
              @click="$emit('toggleAutotradeFlag', 'auto_execute_buy_on_approve')"
            >
              {{ autotradeStatus.auto_execute_buy_on_approve ? "Auto buy: on" : "Auto buy: off" }}
            </n-button>

            <n-button
              size="small"
              :loading="autotradeConfigLoading"
              :type="autotradeStatus.auto_execute_buy_dry_run ? 'warning' : 'error'"
              @click="$emit('toggleAutotradeFlag', 'auto_execute_buy_dry_run')"
            >
              Buy mode: {{ autotradeStatus.auto_execute_buy_dry_run ? "dry-run" : "live" }}
            </n-button>

            <n-button
              size="small"
              :loading="autotradeConfigLoading"
              :type="autotradeStatus.auto_execute_list_on_buy_success ? 'success' : 'default'"
              @click="$emit('toggleAutotradeFlag', 'auto_execute_list_on_buy_success')"
            >
              {{ autotradeStatus.auto_execute_list_on_buy_success ? "Auto list: on" : "Auto list: off" }}
            </n-button>

            <n-button
              size="small"
              :loading="autotradeConfigLoading"
              :type="autotradeStatus.auto_execute_list_dry_run ? 'warning' : 'error'"
              @click="$emit('toggleAutotradeFlag', 'auto_execute_list_dry_run')"
            >
              List mode: {{ autotradeStatus.auto_execute_list_dry_run ? "dry-run" : "live" }}
            </n-button>
          </n-space>
        </n-collapse-item>
      </n-collapse>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue";

const props = defineProps({
  autotradeStatus: { type: Object, default: () => ({}) },
  metrics: { type: Object, default: () => ({}) },
  executionStatus: { type: Object, default: () => ({}) },
  autotradeStatusLoading: { type: Boolean, default: false },
  autotradeActionLoading: { type: String, default: "" },
  autotradeConfigLoading: { type: Boolean, default: false },
  executionConfigLoading: { type: Boolean, default: false },
  sellerControlActionLoading: { type: String, default: "" },
  sellerControlBatchActionLoading: { type: String, default: "" },
  sellerControlPresetActionLoading: { type: String, default: "" },
  sellerControlPresetHistoryLoading: { type: Boolean, default: false },
  sellerControlPresetHistory: { type: Object, default: () => ({ preset: null, items: [], limit: 20 }) },
  sellerPresetRecommendation: { type: Object, default: null },
  sellerPresetRecommendationVisible: { type: Boolean, default: false },
  sellerPresetRecommendationDismissed: { type: Boolean, default: false },
  sellerPresetRecommendationDismissedText: { type: String, default: "" },
  canOperate: { type: Boolean, default: false },
  autotradeRunLimit: { type: Number, default: 0 },
  autotradeRunForce: { type: Boolean, default: false },
  executionLiveConfirmToken: { type: String, default: "" },
  toMoney: { type: Function, required: true },
  toPercent: { type: Function, required: true },
});
const emit = defineEmits([
  "loadAutotradeStatus",
  "startAutotrade",
  "stopAutotrade",
  "setExecutionProvider",
  "toggleExecutionFlag",
  "adjustExecutionNumber",
  "adjustAutotradeNumber",
  "adjustAutotradeRoi",
  "toggleAutotradeFlag",
  "update:executionLiveConfirmToken",
  "update:autotradeRunLimit",
  "update:autotradeRunForce",
  "runAutotradeOnce",
  "applySellerControlAction",
  "applySellerControlBatchAction",
  "applySellerControlPreset",
  "saveSellerControlPreset",
  "deleteSellerControlPreset",
  "loadSellerControlPresetHistory",
  "restoreSellerPresetRecommendation",
]);
const sellerDetailVisible = ref(false);
const selectedSeller = ref(null);
const selectedSellerRuntime = ref(null);
const sellerPresetHistoryVisible = ref(false);
const selectedPresetHistory = ref(null);
const selectedPresetHistoryId = ref(null);
const selectedSellerKeys = ref([]);
const sellerActionNote = ref("");
const sellerActionDurationHours = ref(48);
const batchSellerActionNote = ref("");
const batchSellerActionDurationHours = ref(48);
const activeSellerSelector = ref({
  basePreset: "all",
  sourceFilter: "",
  label: "Visible",
});
const sellerPresetName = ref("");
const sellerPresetAction = ref("observe");
const sellerPresetActionOptions = [
  { label: "Freeze", value: "freeze" },
  { label: "Observe", value: "observe" },
  { label: "Restore", value: "normal" },
];
const visibleSellerAttributionItems = computed(() =>
  Array.isArray(props.metrics?.profit_cockpit?.seller_attribution_all_time)
    ? props.metrics.profit_cockpit.seller_attribution_all_time.slice(0, 6)
    : [],
);
const visibleSellerSources = computed(() =>
  Array.from(new Set(
    visibleSellerAttributionItems.value
      .map((item) => String(item?.source || "").trim())
      .filter(Boolean),
  )),
);
const savedSellerPresets = computed(() =>
  Array.isArray(props.autotradeStatus?.seller_control_presets)
    ? props.autotradeStatus.seller_control_presets
    : [],
);
const sortedSavedSellerPresets = computed(() =>
  [...savedSellerPresets.value].sort((left, right) => {
    const leftRank = Number(left?.effectiveness_rank || 0);
    const rightRank = Number(right?.effectiveness_rank || 0);
    if (leftRank > 0 && rightRank > 0 && leftRank !== rightRank)
      return leftRank - rightRank;
    if (leftRank > 0 && rightRank <= 0)
      return -1;
    if (leftRank <= 0 && rightRank > 0)
      return 1;
    const scoreDelta = Number(right?.effectiveness_score || 0) - Number(left?.effectiveness_score || 0);
    if (Math.abs(scoreDelta) > 0.0001)
      return scoreDelta;
    return String(right?.updated_at || "").localeCompare(String(left?.updated_at || ""));
  }),
);
const recommendedSellerPreset = computed(() =>
  sortedSavedSellerPresets.value.find((preset) => isSellerPresetActionableRecommendation(preset)) || null,
);
const activeRecommendedSellerPreset = computed(() =>
  props.sellerPresetRecommendation || recommendedSellerPreset.value || null,
);
const showRecommendedSellerPresetBar = computed(() => {
  if (props.sellerPresetRecommendation)
    return props.sellerPresetRecommendationVisible;
  return Boolean(recommendedSellerPreset.value);
});
const showDismissedSellerPresetBar = computed(() =>
  Boolean(props.sellerPresetRecommendation && props.sellerPresetRecommendationDismissed),
);
const sellerBatchTemplates = computed(() => {
  const items = visibleSellerAttributionItems.value;
  return [
    {
      key: "observe_losers",
      label: "Observe Losers",
      action: "observe",
      durationHours: 72,
      reason: "negative roi or net profit",
      items: items.filter((item) =>
        !sellerHasManualOverride(item)
        && (Number(item?.realized_net_profit || 0) < 0 || Number(item?.avg_realized_roi || 0) < 0),
      ),
    },
    {
      key: "freeze_repeat_losers",
      label: "Freeze Repeat Losers",
      action: "freeze",
      durationHours: 48,
      reason: "repeat losses with weak hit rate",
      items: items.filter((item) =>
        !sellerHasManualOverride(item)
        && Number(item?.sold_count || 0) >= 2
        && Number(item?.realized_net_profit || 0) < 0
        && Number(item?.profit_hit_rate || 0) < 0.5,
      ),
    },
    {
      key: "clear_manual_observe",
      label: "Clear Manual Observe",
      action: "normal",
      durationHours: null,
      reason: "release manual observe overrides",
      items: items.filter((item) =>
        sellerHasManualOverride(item)
        && String(item?.current_control?.state || "") === "observe",
      ),
    },
    {
      key: "clear_all_manual",
      label: "Clear All Manual",
      action: "normal",
      durationHours: null,
      reason: "clear all manual overrides in visible list",
      items: items.filter((item) => sellerHasManualOverride(item)),
    },
  ];
});

function sellerItemKey(item) {
  return `${item?.source || ""}::${item?.seller_id || ""}`;
}

function openSellerDetail(item, runtimeItems = []) {
  selectedSeller.value = item || null;
  selectedSellerRuntime.value = Array.isArray(runtimeItems)
    ? runtimeItems.find((runtimeItem) => sellerItemKey(runtimeItem) === sellerItemKey(item))?.runtime_control || null
    : null;
  sellerActionNote.value = "";
  sellerActionDurationHours.value = defaultDurationHoursForState(item?.current_control?.state || item?.seller_lane);
  sellerDetailVisible.value = !!item;
}

function sellerActionKey(action, item) {
  return `${action}:${item?.source || ""}/${item?.seller_id || ""}`;
}

function sellerSelected(item) {
  return selectedSellerKeys.value.includes(sellerItemKey(item));
}

function openSellerPresetHistory(preset) {
  if (!preset)
    return;
  selectedPresetHistory.value = preset;
  selectedPresetHistoryId.value = preset.id;
  sellerPresetHistoryVisible.value = true;
  emit("loadSellerControlPresetHistory", preset.id);
}

function toggleSellerSelection(item, checked) {
  const key = sellerItemKey(item);
  if (!key)
    return;
  if (checked) {
    selectedSellerKeys.value = Array.from(new Set([...selectedSellerKeys.value, key]));
  } else {
    selectedSellerKeys.value = selectedSellerKeys.value.filter((current) => current !== key);
  }
}

function selectSellerPreset(preset, source = "") {
  const items = resolveSellerSelectorItems(preset, source);
  activeSellerSelector.value = {
    basePreset: preset,
    sourceFilter: String(source || ""),
    label: formatSellerSelectorLabel(preset, source),
  };
  selectedSellerKeys.value = items
    .map((item) => sellerItemKey(item))
    .filter(Boolean);
}

function resolveSellerSelectorItems(preset, source = "") {
  let items = visibleSellerAttributionItems.value;
  if (preset === "manual") {
    items = items.filter((item) => sellerHasManualOverride(item));
  } else if (preset === "losing") {
    items = items.filter((item) =>
      Number(item?.realized_net_profit || 0) <= 0
      || Number(item?.avg_realized_roi || 0) < 0,
    );
  } else if (preset === "observe") {
    items = items.filter((item) =>
      String(item?.current_control?.state || item?.seller_lane || "") === "observe",
    );
  } else if (preset === "frozen") {
    items = items.filter((item) =>
      String(item?.current_control?.state || "") === "frozen",
    );
  } else if (preset === "source") {
    items = items.filter((item) => String(item?.source || "") === String(source || ""));
  } else if (preset === "clear") {
    items = [];
  }
  return items;
}

function formatSellerSelectorLabel(basePreset, sourceFilter = "") {
  if (basePreset === "source")
    return `Source:${sourceFilter || "-"}`;
  const labelMap = {
    all: "Visible",
    manual: "Manual",
    losing: "Losing",
    observe: "Observe",
    frozen: "Frozen",
    clear: "Clear",
  };
  return labelMap[basePreset] || basePreset || "Visible";
}

function submitSellerBatchAction(action, itemsOverride = null, reasonOverride = null, durationOverride = null) {
  const selectedItems = Array.isArray(itemsOverride) && itemsOverride.length
    ? itemsOverride
    : visibleSellerAttributionItems.value
        .filter((item) => selectedSellerKeys.value.includes(sellerItemKey(item)))
        .map((item) => ({
          source: item.source,
          seller_id: item.seller_id,
        }));
  if (!selectedItems.length)
    return;
  emit("applySellerControlBatchAction", {
    items: selectedItems,
    action,
    reason: String(reasonOverride ?? batchSellerActionNote.value).trim(),
    durationHours: action === "normal" ? null : (durationOverride ?? batchSellerActionDurationHours.value),
  });
  selectedSellerKeys.value = [];
}

function applySellerTemplate(template) {
  if (!template?.items?.length)
    return;
  batchSellerActionNote.value = template.reason || "";
  if (template.durationHours)
    batchSellerActionDurationHours.value = template.durationHours;
  selectedSellerKeys.value = template.items.map((item) => sellerItemKey(item)).filter(Boolean);
  submitSellerBatchAction(
    template.action,
    template.items.map((item) => ({ source: item.source, seller_id: item.seller_id })),
    template.reason,
    template.durationHours,
  );
}

function saveCurrentSellerPreset() {
  emit("saveSellerControlPreset", {
    name: sellerPresetName.value.trim(),
    basePreset: activeSellerSelector.value.basePreset,
    sourceFilter: activeSellerSelector.value.sourceFilter,
    action: sellerPresetAction.value,
    reason: batchSellerActionNote.value.trim(),
    durationHours: sellerPresetAction.value === "normal" ? null : batchSellerActionDurationHours.value,
  });
  sellerPresetName.value = "";
}

function applySavedSellerPreset(preset) {
  if (!preset)
    return;
  const items = resolveSellerSelectorItems(preset.base_preset, preset.source_filter);
  activeSellerSelector.value = {
    basePreset: preset.base_preset,
    sourceFilter: String(preset.source_filter || ""),
    label: formatSellerSelectorLabel(preset.base_preset, preset.source_filter),
  };
  batchSellerActionNote.value = preset.reason || "";
  if (preset.duration_hours)
    batchSellerActionDurationHours.value = preset.duration_hours;
  sellerPresetAction.value = preset.action || "observe";
  selectedSellerKeys.value = items.map((item) => sellerItemKey(item)).filter(Boolean);
  emit("applySellerControlPreset", {
    presetId: preset.id,
    items: items.map((item) => ({ source: item.source, seller_id: item.seller_id })),
    action: preset.action,
    reason: preset.reason,
    durationHours: preset.duration_hours,
  });
}

function savedSellerPresetMatchCount(preset) {
  return resolveSellerSelectorItems(preset.base_preset, preset.source_filter).length;
}

function savedSellerPresetStatsText(preset) {
  const stats = preset?.recent_stats || {};
  const runCount = Number(stats.run_count || 0);
  if (runCount <= 0)
    return "Recent avg: no runs";
  const avgMatched = Number(stats.avg_matched_count || 0);
  const avgProcessed = Number(stats.avg_processed_count || 0);
  const avgProcessedRate = Number(stats.avg_processed_rate || 0);
  return `Recent avg: ${avgProcessed.toFixed(1)}/${avgMatched.toFixed(1)} · ${toPercent(avgProcessedRate)} over ${runCount} runs`;
}

function savedSellerPresetRankText(preset) {
  const rank = Number(preset?.effectiveness_rank || 0);
  const score = Number(preset?.effectiveness_score || 0);
  if (rank <= 0)
    return "";
  return `#${rank} score ${score.toFixed(2)}`;
}

function isSellerPresetActionableRecommendation(preset) {
  const stats = preset?.recent_stats || {};
  const runCount = Number(stats.run_count || 0);
  const score = Number(preset?.effectiveness_score || 0);
  const currentHits = savedSellerPresetMatchCount(preset);
  return runCount >= 2 && score >= 0.45 && currentHits > 0;
}

function recommendedSellerPresetReasonText(preset) {
  const stats = preset?.recent_stats || {};
  const runCount = Number(stats.run_count || 0);
  const avgProcessed = Number(stats.avg_processed_count || 0);
  const avgRate = Number(stats.avg_processed_rate || 0);
  const currentHits = savedSellerPresetMatchCount(preset);
  return `Why: ${currentHits} sellers match now · recent avg ${avgProcessed.toFixed(1)} processed · ${toPercent(avgRate)} processed rate over ${runCount} runs`;
}

function savedSellerPresetLastRunText(preset) {
  const at = String(preset?.last_applied_at || "").trim();
  if (!at)
    return "Last run: never";
  const action = String(preset?.last_applied_action || preset?.action || "").trim();
  const actor = String(preset?.last_applied_by || "").trim();
  const processed = Number(preset?.last_processed_count || 0);
  const matched = Number(preset?.last_matched_count || 0);
  return [
    `Last ${action || "run"}`,
    `${processed}/${matched}`,
    actor || "operator",
    at,
  ].join(" · ");
}

function savedSellerPresetLastTargetsText(preset) {
  const items = Array.isArray(preset?.last_matched_items) ? preset.last_matched_items : [];
  if (!items.length)
    return "Last sellers: none";
  const labels = items
    .map((item) => `${item.source}/${item.seller_id}`)
    .filter(Boolean);
  const preview = labels.slice(0, 3).join(" | ");
  const extra = labels.length > 3 ? ` +${labels.length - 3} more` : "";
  return `Last sellers: ${preview}${extra}`;
}

function savedSellerPresetHistoryText(run) {
  const action = String(run?.action || "").trim() || "run";
  const actor = String(run?.actor || "").trim() || "operator";
  const processed = Number(run?.processed_count || 0);
  const matched = Number(run?.matched_count || 0);
  const at = String(run?.created_at || "").trim() || "-";
  const reason = String(run?.reason || "").trim();
  const duration = run?.duration_hours ? ` | ${run.duration_hours}h` : "";
  return `${action} ${processed}/${matched} | ${actor}${duration} | ${at}${reason ? ` | ${reason}` : ""}`;
}

function savedSellerPresetHistoryTargets(run) {
  const items = Array.isArray(run?.matched_items) ? run.matched_items : [];
  if (!items.length)
    return "Targets: none";
  const labels = items
    .map((item) => `${item.source}/${item.seller_id}`)
    .filter(Boolean);
  const preview = labels.slice(0, 3).join(" | ");
  const extra = labels.length > 3 ? ` +${labels.length - 3} more` : "";
  return `Targets: ${preview}${extra}`;
}

function submitSellerControlAction(action, target = selectedSeller.value, reasonOverride = "") {
  if (!target)
    return;
  const reason = String(reasonOverride || sellerActionNote.value || "").trim();
  emit("applySellerControlAction", {
    source: target.source,
    sellerId: target.seller_id,
    action,
    reason,
    durationHours: action === "normal" ? null : sellerActionDurationHours.value,
  });

  const eventTypeMap = {
    freeze: "manual_freeze",
    observe: "manual_observe",
    normal: "manual_restore",
  };
  if (selectedSeller.value && sellerItemKey(selectedSeller.value) === sellerItemKey(target)) {
    selectedSeller.value = {
      ...selectedSeller.value,
      current_control: {
        ...(selectedSeller.value.current_control || {}),
        state: action === "normal" ? "normal" : action,
        reason: reason || `${action} applied from drawer`,
        frozen_until: action === "normal" ? null : estimateUntilIso(sellerActionDurationHours.value),
        metadata: {
          ...((selectedSeller.value.current_control || {}).metadata || {}),
          manual_actor: "operator",
          manual_action: action,
        },
      },
      recent_control_events: [
        {
          id: `manual-${Date.now()}`,
          event_type: eventTypeMap[action] || action,
          reason: reason || `${action} applied from drawer`,
          created_at: new Date().toISOString(),
          previous_state: selectedSeller.value.current_control || null,
          next_state: {
            ...(selectedSeller.value.current_control || {}),
            state: action === "normal" ? "normal" : action,
            frozen_until: action === "normal" ? null : estimateUntilIso(sellerActionDurationHours.value),
            metadata: {
              ...((selectedSeller.value.current_control || {}).metadata || {}),
              manual_actor: "operator",
              manual_action: action,
            },
          },
        },
        ...(selectedSeller.value.recent_control_events || []),
      ].slice(0, 5),
    };
    if (action === "observe") {
      selectedSellerRuntime.value = {
        ...(selectedSellerRuntime.value || {}),
        state: "observe",
        recovery_progress: 0,
      };
    } else if (action === "freeze") {
      selectedSellerRuntime.value = {
        ...(selectedSellerRuntime.value || {}),
        state: "frozen",
        recovery_progress: 0,
      };
    } else {
      selectedSellerRuntime.value = {
        ...(selectedSellerRuntime.value || {}),
        state: "normal",
        recovery_progress: 1,
      };
    }
  }
}

function defaultDurationHoursForState(state) {
  return state === "observe" ? 72 : 48;
}

function estimateUntilIso(hours) {
  const duration = Math.max(1, Number(hours || 0));
  return new Date(Date.now() + duration * 3600 * 1000).toISOString();
}

function sellerCurrentAuditText(item) {
  const actor = item?.current_control?.metadata?.manual_actor;
  const until = item?.current_control?.frozen_until;
  const parts = [];
  if (actor)
    parts.push(`By ${actor}`);
  if (until)
    parts.push(`Until ${until}`);
  return parts.join(" · ");
}

function sellerHasManualOverride(item) {
  return Boolean(item?.current_control?.metadata?.manual_actor);
}

function sellerManualOverrideLabel(item) {
  if (!sellerHasManualOverride(item))
    return "";
  return `manual ${item?.current_control?.state || "normal"}`;
}

function sellerManualOverrideMeta(item) {
  if (!sellerHasManualOverride(item))
    return "";
  const actor = item?.current_control?.metadata?.manual_actor;
  const until = item?.current_control?.frozen_until;
  const parts = [];
  if (actor)
    parts.push(actor);
  if (until)
    parts.push(`until ${until}`);
  return parts.join(" · ");
}

function sellerEventAuditText(event) {
  const actor = event?.next_state?.metadata?.manual_actor || event?.previous_state?.metadata?.manual_actor;
  const previous = event?.previous_state?.state;
  const next = event?.next_state?.state;
  const parts = [];
  if (previous || next)
    parts.push(`${previous || "none"} -> ${next || "none"}`);
  if (actor)
    parts.push(`By ${actor}`);
  return parts.join(" · ");
}

function sellerStateType(item, runtime) {
  const state = runtime?.state || item?.current_control?.state || "normal";
  if (state === "frozen")
    return "error";
  if (state === "observe")
    return "warning";
  if (state === "whitelist")
    return "success";
  return "default";
}

function sellerStateLabel(item, runtime) {
  const state = runtime?.state || item?.current_control?.state || "normal";
  if (state === "observe") {
    const progress = Math.round(Number(runtime?.recovery_progress || 0) * 100);
    return `observe ${progress}%`;
  }
  return state;
}

function sellerEventType(eventType) {
  const normalized = String(eventType || "").toLowerCase();
  if (normalized.includes("freeze"))
    return "error";
  if (normalized.includes("observe"))
    return "warning";
  if (normalized.includes("complete") || normalized.includes("unfreeze"))
    return "success";
  return "default";
}

watch(
  () => props.metrics?.profit_cockpit?.seller_attribution_all_time,
  (items) => {
    const visibleKeys = Array.isArray(items)
      ? items.slice(0, 6).map((item) => sellerItemKey(item))
      : [];
    selectedSellerKeys.value = selectedSellerKeys.value.filter((key) => visibleKeys.includes(key));
    if (!sellerDetailVisible.value || !selectedSeller.value || !Array.isArray(items))
      return;
    const nextSeller = items.find((item) => sellerItemKey(item) === sellerItemKey(selectedSeller.value));
    if (nextSeller)
      selectedSeller.value = nextSeller;
  },
  { deep: true },
);

watch(
  () => props.autotradeStatus?.seller_controls?.items,
  (items) => {
    if (!sellerDetailVisible.value || !selectedSeller.value || !Array.isArray(items))
      return;
    selectedSellerRuntime.value = items.find((item) => sellerItemKey(item) === sellerItemKey(selectedSeller.value))?.runtime_control || null;
  },
  { deep: true },
);

watch(
  () => props.sellerControlPresetHistory,
  (payload) => {
    const preset = payload?.preset;
    if (!preset || !sellerPresetHistoryVisible.value)
      return;
    if (selectedPresetHistoryId.value && Number(preset.id) === Number(selectedPresetHistoryId.value))
      selectedPresetHistory.value = preset;
  },
  { deep: true },
);
</script>
