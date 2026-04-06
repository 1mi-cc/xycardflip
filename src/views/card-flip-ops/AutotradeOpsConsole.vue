<template>
  <section class="service-panel autotrade-ops-console">
    <div class="service-head">
      <div class="service-copy">
        <div class="service-kicker">Operator Console</div>
        <h3>Automation Watchtower</h3>
        <p>
          Reviews live readiness, automatic routing, and incident outcomes without
          requiring manual intervention from the panel.
        </p>
      </div>

      <n-space>
        <n-tag size="small" :type="props.cockpit.ready ? 'success' : 'warning'">
          {{ props.cockpit.ready ? "Ready" : "Blocked" }}
        </n-tag>
        <n-tag
          size="small"
          :type="props.cockpit.alert_delivery?.email_ready ? 'info' : 'default'"
        >
          {{ props.cockpit.alert_delivery?.email_ready ? "Email ready" : "Email not ready" }}
        </n-tag>
        <n-tag
          size="small"
          :type="props.cockpit.alert_delivery?.slack_ready ? 'info' : 'default'"
        >
          {{ props.cockpit.alert_delivery?.slack_ready ? "Slack ready" : "Slack not ready" }}
        </n-tag>
        <n-tag
          size="small"
          :type="props.cockpit.alert_delivery?.telegram_ready ? 'info' : 'default'"
        >
          {{ props.cockpit.alert_delivery?.telegram_ready ? "Telegram ready" : "Telegram not ready" }}
        </n-tag>
        <n-tag
          size="small"
          :type="props.cockpit.alert_delivery?.webhook_ready ? 'info' : 'default'"
        >
          {{ props.cockpit.alert_delivery?.webhook_ready ? `${webhookChannelLabel} ready` : `${webhookChannelLabel} not ready` }}
        </n-tag>
        <n-tag
          size="small"
          :type="props.cockpit.alert_delivery?.auto_email_enabled ? 'success' : 'default'"
        >
          {{ props.cockpit.alert_delivery?.auto_email_enabled ? "Auto email on" : "Auto email off" }}
        </n-tag>
        <n-tag
          size="small"
          :type="props.cockpit.alert_delivery?.auto_slack_enabled ? 'success' : 'default'"
        >
          {{ props.cockpit.alert_delivery?.auto_slack_enabled ? "Auto Slack on" : "Auto Slack off" }}
        </n-tag>
        <n-tag
          size="small"
          :type="props.cockpit.alert_delivery?.auto_telegram_enabled ? 'success' : 'default'"
        >
          {{ props.cockpit.alert_delivery?.auto_telegram_enabled ? "Auto Telegram on" : "Auto Telegram off" }}
        </n-tag>
        <n-tag
          size="small"
          :type="props.cockpit.alert_delivery?.auto_webhook_enabled ? 'success' : 'default'"
        >
          {{ props.cockpit.alert_delivery?.auto_webhook_enabled ? `Auto ${webhookChannelLabel.toLowerCase()} on` : `Auto ${webhookChannelLabel.toLowerCase()} off` }}
        </n-tag>
        <n-button
          tertiary
          size="small"
          :loading="props.cockpitLoading || props.auditLoading"
          @click="$emit('loadAutotradeCockpit')"
        >
          Refresh Console
        </n-button>
        <n-button
          v-if="manualControlsEnabled"
          size="small"
          type="primary"
          :disabled="!props.canOperate"
          :loading="props.alertDispatchLoading"
          @click="$emit('dispatchAlertEmail')"
        >
          Email Alert Digest
        </n-button>
        <n-button
          v-if="manualControlsEnabled"
          size="small"
          type="primary"
          :disabled="!props.canOperate"
          :loading="props.slackDispatchLoading"
          @click="$emit('dispatchAlertSlack')"
        >
          Send Slack Escalation
        </n-button>
        <n-button
          v-if="manualControlsEnabled"
          size="small"
          type="primary"
          :disabled="!props.canOperate"
          :loading="props.telegramDispatchLoading"
          @click="$emit('dispatchAlertTelegram')"
        >
          Send Telegram Escalation
        </n-button>
        <n-button
          v-if="manualControlsEnabled"
          size="small"
          type="primary"
          :disabled="!props.canOperate"
          :loading="props.webhookDispatchLoading"
          @click="$emit('dispatchAlertWebhook')"
        >
          Send {{ webhookChannelLabel }} Escalation
        </n-button>
        <n-button
          v-if="manualControlsEnabled"
          size="small"
          :disabled="!props.canOperate"
          :type="props.cockpit.alert_delivery?.auto_email_enabled ? 'warning' : 'success'"
          @click="$emit('toggleAlertAutoEmail')"
        >
          {{ props.cockpit.alert_delivery?.auto_email_enabled ? "Disable Auto Email" : "Enable Auto Email" }}
        </n-button>
        <n-button
          v-if="manualControlsEnabled"
          size="small"
          :disabled="!props.canOperate"
          :type="props.cockpit.alert_delivery?.auto_slack_enabled ? 'warning' : 'success'"
          @click="$emit('toggleAlertAutoSlack')"
        >
          {{ props.cockpit.alert_delivery?.auto_slack_enabled ? "Disable Auto Slack" : "Enable Auto Slack" }}
        </n-button>
        <n-button
          v-if="manualControlsEnabled"
          size="small"
          :disabled="!props.canOperate"
          :type="props.cockpit.alert_delivery?.auto_telegram_enabled ? 'warning' : 'success'"
          @click="$emit('toggleAlertAutoTelegram')"
        >
          {{ props.cockpit.alert_delivery?.auto_telegram_enabled ? "Disable Auto Telegram" : "Enable Auto Telegram" }}
        </n-button>
        <n-button
          v-if="manualControlsEnabled"
          size="small"
          :disabled="!props.canOperate"
          :type="props.cockpit.alert_delivery?.auto_webhook_enabled ? 'warning' : 'success'"
          @click="$emit('toggleAlertAutoWebhook')"
        >
          {{ props.cockpit.alert_delivery?.auto_webhook_enabled ? `Disable Auto ${webhookChannelLabel}` : `Enable Auto ${webhookChannelLabel}` }}
        </n-button>
      </n-space>
    </div>

    <div v-if="alertItems.length" class="operator-alert-stack">
      <n-alert
        v-for="item in alertItems"
        :key="`${item.code}:${item.target || 'global'}`"
        :bordered="false"
        :type="alertType(item.effective_severity || item.severity)"
        show-icon
      >
        <template #header>
          {{ item.title }}
        </template>
        <div>{{ item.message }}</div>
        <div class="operator-alert-meta">
          <span v-if="item.target">target: {{ item.target }}</span>
          <span v-if="item.effective_severity && item.effective_severity !== item.severity">
            level: {{ item.severity }} -> {{ item.effective_severity }}
          </span>
          <span v-if="item.age_minutes">age: {{ item.age_minutes }}m</span>
          <span v-if="item.escalated">escalated</span>
          <span v-else-if="item.escalates_at">escalates: {{ item.escalates_at }}</span>
          <span v-if="item.renotify_stage">re-notify stage {{ item.renotify_stage }}</span>
          <span v-if="item.next_renotify_at">next follow-up: {{ item.next_renotify_at }}</span>
          <span v-if="item.delivery_lane">lane: {{ item.delivery_lane }} / {{ item.delivery_lane_reason }}</span>
          <span v-if="item.incident_priority">priority: {{ item.incident_priority }}</span>
          <span v-if="item.sla_due_at">
            SLA {{ item.sla_breached ? "breached" : "due" }}: {{ item.sla_due_at }}
          </span>
          <span v-if="item.incident_status">case: {{ item.incident_status }}</span>
          <span v-if="item.incident_owner">owner: {{ item.incident_owner }}</span>
          <span v-if="item.acknowledged">acknowledged</span>
          <span v-if="item.ack_expires_at">ack expires: {{ item.ack_expires_at }}</span>
          <span v-if="item.snoozed">snoozed until {{ item.snoozed_until }}</span>
          <span v-if="item.expires_at">expires: {{ item.expires_at }}</span>
        </div>
        <n-space size="small">
          <n-button
            size="tiny"
            tertiary
            :loading="props.alertTimelineLoading && selectedAlertKey === item.alert_key"
            @click="openAlertTimeline(item)"
          >
            Timeline
          </n-button>
          <n-button
            v-if="manualControlsEnabled"
            size="tiny"
            :disabled="!props.canOperate || item.acknowledged"
            :loading="props.alertControlLoading === `ack:${item.alert_key}`"
            @click="$emit('acknowledgeAlert', item)"
          >
            Acknowledge
          </n-button>
          <n-button
            v-if="manualControlsEnabled"
            size="tiny"
            :disabled="!props.canOperate || item.snoozed"
            :loading="props.alertControlLoading === `snooze:${item.alert_key}`"
            @click="$emit('snoozeAlert', item, 60)"
          >
            Snooze 60m
          </n-button>
          <n-button
            v-if="manualControlsEnabled"
            size="tiny"
            :disabled="!props.canOperate || (!item.acknowledged && !item.snoozed)"
            :loading="props.alertControlLoading === `resume:${item.alert_key}`"
            @click="$emit('resumeAlert', item)"
          >
            Resume
          </n-button>
        </n-space>
      </n-alert>
    </div>

    <div class="service-section">
      <div class="section-title">Incident Queue</div>
      <div class="section-subtitle">
        Ranked by incident priority, SLA pressure, and active delivery lane.
      </div>

      <div class="ops-table-wrap">
        <n-table class="ops-table" size="small" striped>
          <thead>
            <tr>
              <th>Incident</th>
              <th>Priority</th>
              <th>Owner / Status</th>
              <th>Lane</th>
              <th>SLA</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in alertItems" :key="`queue:${item.alert_key}`">
              <td>
                <strong>{{ item.title }}</strong>
                <div class="summary-meta">{{ item.target || item.code || "-" }}</div>
              </td>
              <td>
                <n-tag size="small" :type="priorityTagType(item.incident_priority)">
                  {{ item.incident_priority || "normal" }}
                </n-tag>
              </td>
              <td>
                <div class="summary-meta">{{ item.incident_owner || "-" }}</div>
                <div class="summary-meta">{{ item.incident_status || "open" }}</div>
              </td>
              <td>
                <div class="summary-meta">{{ item.delivery_lane || "-" }}</div>
                <div class="summary-meta">{{ item.delivery_lane_reason || "-" }}</div>
              </td>
              <td>
                <div class="summary-meta">{{ item.sla_due_at || "-" }}</div>
                <div class="summary-meta">
                  {{ item.sla_breached ? "breached" : `${item.sla_remaining_minutes || 0}m left` }}
                </div>
              </td>
            </tr>
            <tr v-if="!alertItems.length">
              <td colspan="5">
                <div class="empty-wrap">
                  <n-empty description="No active incidents"></n-empty>
                </div>
              </td>
            </tr>
          </tbody>
        </n-table>
      </div>
    </div>

    <div class="service-summary-grid">
      <div class="summary-chip">
        <span class="summary-label">Email Delivery</span>
        <strong class="summary-value">
          {{ lastEmailEvent?.success ? "Sent" : (props.cockpit.alert_delivery?.email_ready ? "Ready" : "Not ready") }}
        </strong>
        <span class="summary-meta">
          {{
            lastEmailEvent
              ? `${lastEmailEvent.created_at || "-"} / ${lastEmailEvent.reason || lastEmailEvent.subject || "-"}`
              : `No alert delivery history yet / cooldown ${props.cockpit.alert_delivery?.email_cooldown_minutes || 0}m`
          }}
        </span>
      </div>
      <div class="summary-chip">
        <span class="summary-label">Slack Delivery</span>
        <strong class="summary-value">
          {{ lastSlackEvent?.success ? "Sent" : (props.cockpit.alert_delivery?.slack_ready ? "Ready" : "Not ready") }}
        </strong>
        <span class="summary-meta">
          {{
            lastSlackEvent
              ? `${lastSlackEvent.created_at || "-"} / ${lastSlackEvent.reason || lastSlackEvent.subject || "-"}` 
              : `No Slack delivery history yet / cooldown ${props.cockpit.alert_delivery?.slack_cooldown_minutes || 0}m`
          }}
        </span>
      </div>
      <div class="summary-chip">
        <span class="summary-label">Telegram Delivery</span>
        <strong class="summary-value">
          {{ lastTelegramEvent?.success ? "Sent" : (props.cockpit.alert_delivery?.telegram_ready ? "Ready" : "Not ready") }}
        </strong>
        <span class="summary-meta">
          {{
            lastTelegramEvent
              ? `${lastTelegramEvent.created_at || "-"} / ${lastTelegramEvent.reason || lastTelegramEvent.subject || "-"}` 
              : `No Telegram delivery history yet / cooldown ${props.cockpit.alert_delivery?.telegram_cooldown_minutes || 0}m`
          }}
        </span>
      </div>
      <div class="summary-chip">
        <span class="summary-label">{{ webhookChannelLabel }} Delivery</span>
        <strong class="summary-value">
          {{ lastWebhookEvent?.success ? "Sent" : (props.cockpit.alert_delivery?.webhook_ready ? "Ready" : "Not ready") }}
        </strong>
        <span class="summary-meta">
          {{
            lastWebhookEvent
              ? `${lastWebhookEvent.created_at || "-"} / ${lastWebhookEvent.reason || lastWebhookEvent.subject || "-"}`
              : `No webhook delivery history yet / cooldown ${props.cockpit.alert_delivery?.webhook_cooldown_minutes || 0}m`
          }}
        </span>
      </div>
      <div class="summary-chip">
        <span class="summary-label">Auto Email Policy</span>
        <strong class="summary-value">
          {{ props.cockpit.alert_delivery?.auto_email_enabled ? "Active" : "Manual only" }}
        </strong>
        <span class="summary-meta">
          min={{ props.cockpit.alert_delivery?.auto_email_min_severity || "warning" }}
          / ack={{ props.cockpit.alert_delivery?.alert_ack_timeout_minutes || 0 }}m
          / escalate={{ props.cockpit.alert_delivery?.alert_escalation_minutes || 0 }}m
          / re-notify={{ props.cockpit.alert_delivery?.alert_renotify_minutes || 0 }}m
          / cooldown={{ props.cockpit.alert_delivery?.email_cooldown_minutes || 0 }}m
        </span>
      </div>
      <div class="summary-chip">
        <span class="summary-label">Auto Slack Policy</span>
        <strong class="summary-value">
          {{ props.cockpit.alert_delivery?.auto_slack_enabled ? "Active" : "Manual only" }}
        </strong>
        <span class="summary-meta">
          min={{ props.cockpit.alert_delivery?.auto_slack_min_severity || "error" }}
          / stage={{ props.cockpit.alert_delivery?.slack_min_stage || 1 }}
          / cooldown={{ props.cockpit.alert_delivery?.slack_cooldown_minutes || 0 }}m
        </span>
      </div>
      <div class="summary-chip">
        <span class="summary-label">Auto Telegram Policy</span>
        <strong class="summary-value">
          {{ props.cockpit.alert_delivery?.auto_telegram_enabled ? "Active" : "Manual only" }}
        </strong>
        <span class="summary-meta">
          min={{ props.cockpit.alert_delivery?.auto_telegram_min_severity || "error" }}
          / stage={{ props.cockpit.alert_delivery?.telegram_min_stage || 2 }}
          / cooldown={{ props.cockpit.alert_delivery?.telegram_cooldown_minutes || 0 }}m
        </span>
      </div>
      <div class="summary-chip">
        <span class="summary-label">Auto {{ webhookChannelLabel }} Policy</span>
        <strong class="summary-value">
          {{ props.cockpit.alert_delivery?.auto_webhook_enabled ? "Active" : "Manual only" }}
        </strong>
        <span class="summary-meta">
          min={{ props.cockpit.alert_delivery?.auto_webhook_min_severity || "error" }}
          / escalated only
          / cooldown={{ props.cockpit.alert_delivery?.webhook_cooldown_minutes || 0 }}m
        </span>
      </div>
      <div class="summary-chip">
        <span class="summary-label">Execution</span>
        <strong class="summary-value">
          {{ props.cockpit.execution_readiness?.live_ready ? "Live ready" : "Not live ready" }}
        </strong>
        <span class="summary-meta">
          {{ props.cockpit.execution_readiness?.webhook_provider || props.cockpit.execution_readiness?.provider || "-" }}
        </span>
      </div>
      <div class="summary-chip">
        <span class="summary-label">Operating State</span>
        <strong class="summary-value">{{ props.cockpit.operating_state?.state || "-" }}</strong>
        <span class="summary-meta">
          {{ props.cockpit.operating_state?.reason || "No active recovery guard" }}
        </span>
      </div>
      <div class="summary-chip">
        <span class="summary-label">Remaining Capital</span>
        <strong class="summary-value">{{ props.toMoney(props.cockpit.portfolio?.remaining_capital || 0) }}</strong>
        <span class="summary-meta">
          deployed {{ props.toMoney(props.cockpit.portfolio?.deployed_capital || 0) }}
        </span>
      </div>
      <div class="summary-chip">
        <span class="summary-label">Manual Overrides</span>
        <strong class="summary-value">
          S{{ props.cockpit.source_overrides?.active_freeze_count || 0 }}/{{ props.cockpit.source_overrides?.active_observe_count || 0 }}
          /
          C{{ props.cockpit.cluster_overrides?.active_freeze_count || 0 }}/{{ props.cockpit.cluster_overrides?.active_observe_count || 0 }}
        </strong>
        <span class="summary-meta">freeze/observe counts</span>
      </div>
      <div class="summary-chip summary-chip-wide">
        <span class="summary-label">Blocking Reasons</span>
        <strong class="summary-value">{{ blockingReasonText }}</strong>
      </div>
    </div>

    <div class="service-section">
      <div class="section-title">Automation Policy</div>
      <div class="section-subtitle">
        Read-only backend routing and closure rules currently driving incidents.
      </div>

      <div class="service-summary-grid">
        <div class="summary-chip">
          <span class="summary-label">Auto Assign</span>
          <strong class="summary-value">
            {{ props.cockpit.incident_automation?.auto_assign_enabled ? "Enabled" : "Disabled" }}
          </strong>
          <span class="summary-meta">default {{ props.cockpit.incident_automation?.default_owner || "-" }}</span>
        </div>
        <div class="summary-chip">
          <span class="summary-label">High / Critical</span>
          <strong class="summary-value">
            {{ props.cockpit.incident_automation?.high_priority_owner || "-" }}
          </strong>
          <span class="summary-meta">critical {{ props.cockpit.incident_automation?.critical_priority_owner || "-" }}</span>
        </div>
        <div class="summary-chip">
          <span class="summary-label">Lane Owners</span>
          <strong class="summary-value">
            Slack {{ props.cockpit.incident_automation?.slack_owner || "-" }}
          </strong>
          <span class="summary-meta">Telegram {{ props.cockpit.incident_automation?.telegram_owner || "-" }}</span>
        </div>
        <div class="summary-chip">
          <span class="summary-label">Auto Resolve</span>
          <strong class="summary-value">
            {{ props.cockpit.incident_automation?.auto_resolve_enabled ? "Enabled" : "Disabled" }}
          </strong>
          <span class="summary-meta">
            SLA escalation {{ props.cockpit.incident_automation?.auto_escalate_on_sla_breach ? "enabled" : "disabled" }}
          </span>
        </div>
      </div>
    </div>

    <n-drawer placement="right" width="min(560px, 100vw)" v-model:show="alertTimelineVisible">
      <n-drawer-content
        closable
        :title="selectedAlert ? selectedAlert.title || 'Alert Timeline' : 'Alert Timeline'"
      >
        <template v-if="selectedAlert">
          <div class="seller-detail-state">
            <n-tag size="small" :type="alertType(selectedAlert.effective_severity || selectedAlert.severity)">
              {{ selectedAlert.effective_severity || selectedAlert.severity }}
            </n-tag>
            <span class="summary-meta">{{ selectedAlert.target || selectedAlert.code || "-" }}</span>
          </div>
          <div class="summary-meta" style="margin-bottom: 12px">
            age {{ selectedAlert.age_minutes || 0 }}m
            <template v-if="selectedAlert.next_renotify_at">
              / next follow-up {{ selectedAlert.next_renotify_at }}
            </template>
          </div>
          <div class="service-summary-grid" style="margin-bottom: 12px">
            <div class="summary-chip">
              <span class="summary-label">Incident Owner</span>
              <strong class="summary-value">{{ selectedAlert.incident_owner || "-" }}</strong>
              <span class="summary-meta">status {{ selectedAlert.incident_status || "open" }}</span>
            </div>
            <div class="summary-chip">
              <span class="summary-label">Priority</span>
              <strong class="summary-value">{{ selectedAlert.incident_priority || "normal" }}</strong>
              <span class="summary-meta">
                {{ selectedAlert.sla_breached ? "SLA breached" : `SLA ${selectedAlert.sla_due_at || "-"}` }}
              </span>
            </div>
            <div class="summary-chip summary-chip-wide">
              <span class="summary-label">Latest Note</span>
              <strong class="summary-value">{{ selectedAlert.latest_case_note || "-" }}</strong>
              <span class="summary-meta">
                {{ selectedAlert.last_case_actor || "-" }} / {{ selectedAlert.last_case_updated_at || "-" }}
              </span>
            </div>
          </div>
          <div v-if="manualControlsEnabled" class="override-direct-form" style="margin-bottom: 12px">
            <n-input
              v-model:value="incidentForm.owner"
              placeholder="Owner"
            ></n-input>
            <n-select
              v-model:value="incidentForm.priority"
              :options="priorityOptions"
              style="min-width: 140px"
            ></n-select>
            <n-input
              v-model:value="incidentForm.note"
              placeholder="Note / handoff / resolution"
            ></n-input>
            <n-space>
              <n-button
                size="small"
                :disabled="!props.canOperate || !selectedAlertKey || !incidentForm.owner.trim()"
                :loading="props.alertControlLoading === `assign:${selectedAlertKey}`"
                @click="submitIncidentAssign()"
              >
                Assign
              </n-button>
              <n-button
                size="small"
                :disabled="!props.canOperate || !selectedAlertKey"
                :loading="props.alertControlLoading === `priority:${selectedAlertKey}`"
                @click="submitIncidentPriority()"
              >
                Set Priority
              </n-button>
              <n-button
                size="small"
                :disabled="!props.canOperate || !selectedAlertKey || !incidentForm.note.trim()"
                :loading="props.alertControlLoading === `note:${selectedAlertKey}`"
                @click="submitIncidentNote()"
              >
                Add Note
              </n-button>
              <n-button
                size="small"
                :disabled="!props.canOperate || !selectedAlertKey || !incidentForm.owner.trim()"
                :loading="props.alertControlLoading === `handoff:${selectedAlertKey}`"
                @click="submitIncidentHandoff()"
              >
                Handoff
              </n-button>
              <n-button
                size="small"
                type="success"
                :disabled="!props.canOperate || !selectedAlertKey"
                :loading="props.alertControlLoading === `resolve:${selectedAlertKey}`"
                @click="submitIncidentResolve()"
              >
                Resolve
              </n-button>
            </n-space>
          </div>
          <div v-if="props.alertTimelineLoading" class="summary-meta">
            Loading alert timeline...
          </div>
          <div
            v-else-if="Array.isArray(props.alertTimeline?.items) && props.alertTimeline.items.length"
            class="seller-detail-list"
          >
            <div
              v-for="event in props.alertTimeline.items"
              :key="event.id"
              class="seller-detail-row"
            >
              <div class="seller-detail-main">
                <strong>{{ formatTimelineAction(event) }}</strong>
                <span class="summary-meta">{{ event.summary || event.reason || "-" }}</span>
                <span v-if="event.kind === 'delivery'" class="summary-meta">
                  {{ event.channel_label || event.channel || "delivery" }}
                  <template v-if="event.delivery_stage">
                    / {{ event.delivery_stage }}
                  </template>
                  <template v-if="event.success === true">
                    / sent
                  </template>
                  <template v-else-if="event.success === false">
                    / skipped
                  </template>
                </span>
              </div>
              <div class="seller-detail-side">
                <span class="summary-meta">{{ event.actor || "-" }}</span>
                <span class="summary-meta">{{ event.created_at || "-" }}</span>
              </div>
            </div>
          </div>
          <div v-else class="summary-meta">
            No alert timeline recorded yet.
          </div>
        </template>
      </n-drawer-content>
    </n-drawer>

    <div class="service-section">
      <div class="section-title">Alert Policy</div>
      <div class="section-subtitle">
        Read-only escalation, re-notify cadence, and delivery thresholds from backend automation.
      </div>

      <div v-if="manualControlsEnabled" class="alert-policy-grid">
        <div class="summary-chip">
          <span class="summary-label">Email Min Severity</span>
          <n-select
            :disabled="!props.canOperate || props.autotradeConfigLoading"
            :options="severityOptions"
            :value="props.autotradeStatus?.alert_email_min_severity || 'warning'"
            @update:value="$emit('setAlertPolicySeverity', 'alert_email_min_severity', $event)"
          ></n-select>
        </div>
        <div class="summary-chip">
          <span class="summary-label">Slack Min Severity</span>
          <n-select
            :disabled="!props.canOperate || props.autotradeConfigLoading"
            :options="severityOptions"
            :value="props.autotradeStatus?.alert_slack_min_severity || 'error'"
            @update:value="$emit('setAlertPolicySeverity', 'alert_slack_min_severity', $event)"
          ></n-select>
        </div>
        <div class="summary-chip">
          <span class="summary-label">Telegram Min Severity</span>
          <n-select
            :disabled="!props.canOperate || props.autotradeConfigLoading"
            :options="severityOptions"
            :value="props.autotradeStatus?.alert_telegram_min_severity || 'error'"
            @update:value="$emit('setAlertPolicySeverity', 'alert_telegram_min_severity', $event)"
          ></n-select>
        </div>
        <div class="summary-chip">
          <span class="summary-label">Webhook Min Severity</span>
          <n-select
            :disabled="!props.canOperate || props.autotradeConfigLoading"
            :options="severityOptions"
            :value="props.autotradeStatus?.alert_webhook_min_severity || 'error'"
            @update:value="$emit('setAlertPolicySeverity', 'alert_webhook_min_severity', $event)"
          ></n-select>
        </div>
        <div class="summary-chip">
          <span class="summary-label">Ack Timeout</span>
          <div class="policy-stepper">
            <n-button
              size="tiny"
              :disabled="!props.canOperate || props.autotradeConfigLoading"
              @click="$emit('adjustAlertPolicyNumber', 'alert_ack_timeout_minutes', -30, 1, 1440)"
            >
              -30
            </n-button>
            <strong class="summary-value">{{ props.autotradeStatus?.alert_ack_timeout_minutes || 0 }}m</strong>
            <n-button
              size="tiny"
              :disabled="!props.canOperate || props.autotradeConfigLoading"
              @click="$emit('adjustAlertPolicyNumber', 'alert_ack_timeout_minutes', 30, 1, 1440)"
            >
              +30
            </n-button>
          </div>
        </div>
        <div class="summary-chip">
          <span class="summary-label">Escalation Minutes</span>
          <div class="policy-stepper">
            <n-button
              size="tiny"
              :disabled="!props.canOperate || props.autotradeConfigLoading"
              @click="$emit('adjustAlertPolicyNumber', 'alert_escalation_minutes', -15, 1, 1440)"
            >
              -15
            </n-button>
            <strong class="summary-value">{{ props.autotradeStatus?.alert_escalation_minutes || 0 }}m</strong>
            <n-button
              size="tiny"
              :disabled="!props.canOperate || props.autotradeConfigLoading"
              @click="$emit('adjustAlertPolicyNumber', 'alert_escalation_minutes', 15, 1, 1440)"
            >
              +15
            </n-button>
          </div>
        </div>
        <div class="summary-chip">
          <span class="summary-label">Re-notify Minutes</span>
          <div class="policy-stepper">
            <n-button
              size="tiny"
              :disabled="!props.canOperate || props.autotradeConfigLoading"
              @click="$emit('adjustAlertPolicyNumber', 'alert_renotify_minutes', -30, 1, 1440)"
            >
              -30
            </n-button>
            <strong class="summary-value">{{ props.autotradeStatus?.alert_renotify_minutes || 0 }}m</strong>
            <n-button
              size="tiny"
              :disabled="!props.canOperate || props.autotradeConfigLoading"
              @click="$emit('adjustAlertPolicyNumber', 'alert_renotify_minutes', 30, 1, 1440)"
            >
              +30
            </n-button>
          </div>
        </div>
        <div class="summary-chip">
          <span class="summary-label">Slack Stage</span>
          <div class="policy-stepper">
            <n-button
              size="tiny"
              :disabled="!props.canOperate || props.autotradeConfigLoading"
              @click="$emit('adjustAlertPolicyNumber', 'alert_slack_min_stage', -1, 1, 10)"
            >
              -1
            </n-button>
            <strong class="summary-value">{{ props.autotradeStatus?.alert_slack_min_stage || 1 }}</strong>
            <n-button
              size="tiny"
              :disabled="!props.canOperate || props.autotradeConfigLoading"
              @click="$emit('adjustAlertPolicyNumber', 'alert_slack_min_stage', 1, 1, 10)"
            >
              +1
            </n-button>
          </div>
        </div>
        <div class="summary-chip">
          <span class="summary-label">Telegram Stage</span>
          <div class="policy-stepper">
            <n-button
              size="tiny"
              :disabled="!props.canOperate || props.autotradeConfigLoading"
              @click="$emit('adjustAlertPolicyNumber', 'alert_telegram_min_stage', -1, 1, 10)"
            >
              -1
            </n-button>
            <strong class="summary-value">{{ props.autotradeStatus?.alert_telegram_min_stage || 2 }}</strong>
            <n-button
              size="tiny"
              :disabled="!props.canOperate || props.autotradeConfigLoading"
              @click="$emit('adjustAlertPolicyNumber', 'alert_telegram_min_stage', 1, 1, 10)"
            >
              +1
            </n-button>
          </div>
        </div>
        <div class="summary-chip">
          <span class="summary-label">Email Cooldown</span>
          <div class="policy-stepper">
            <n-button
              size="tiny"
              :disabled="!props.canOperate || props.autotradeConfigLoading"
              @click="$emit('adjustAlertPolicyNumber', 'alert_email_cooldown_minutes', -15, 1, 1440)"
            >
              -15
            </n-button>
            <strong class="summary-value">{{ props.autotradeStatus?.alert_email_cooldown_minutes || 0 }}m</strong>
            <n-button
              size="tiny"
              :disabled="!props.canOperate || props.autotradeConfigLoading"
              @click="$emit('adjustAlertPolicyNumber', 'alert_email_cooldown_minutes', 15, 1, 1440)"
            >
              +15
            </n-button>
          </div>
        </div>
        <div class="summary-chip">
          <span class="summary-label">Slack Cooldown</span>
          <div class="policy-stepper">
            <n-button
              size="tiny"
              :disabled="!props.canOperate || props.autotradeConfigLoading"
              @click="$emit('adjustAlertPolicyNumber', 'alert_slack_cooldown_minutes', -15, 1, 1440)"
            >
              -15
            </n-button>
            <strong class="summary-value">{{ props.autotradeStatus?.alert_slack_cooldown_minutes || 0 }}m</strong>
            <n-button
              size="tiny"
              :disabled="!props.canOperate || props.autotradeConfigLoading"
              @click="$emit('adjustAlertPolicyNumber', 'alert_slack_cooldown_minutes', 15, 1, 1440)"
            >
              +15
            </n-button>
          </div>
        </div>
        <div class="summary-chip">
          <span class="summary-label">Telegram Cooldown</span>
          <div class="policy-stepper">
            <n-button
              size="tiny"
              :disabled="!props.canOperate || props.autotradeConfigLoading"
              @click="$emit('adjustAlertPolicyNumber', 'alert_telegram_cooldown_minutes', -15, 1, 1440)"
            >
              -15
            </n-button>
            <strong class="summary-value">{{ props.autotradeStatus?.alert_telegram_cooldown_minutes || 0 }}m</strong>
            <n-button
              size="tiny"
              :disabled="!props.canOperate || props.autotradeConfigLoading"
              @click="$emit('adjustAlertPolicyNumber', 'alert_telegram_cooldown_minutes', 15, 1, 1440)"
            >
              +15
            </n-button>
          </div>
        </div>
        <div class="summary-chip">
          <span class="summary-label">Webhook Cooldown</span>
          <div class="policy-stepper">
            <n-button
              size="tiny"
              :disabled="!props.canOperate || props.autotradeConfigLoading"
              @click="$emit('adjustAlertPolicyNumber', 'alert_webhook_cooldown_minutes', -15, 1, 1440)"
            >
              -15
            </n-button>
            <strong class="summary-value">{{ props.autotradeStatus?.alert_webhook_cooldown_minutes || 0 }}m</strong>
            <n-button
              size="tiny"
              :disabled="!props.canOperate || props.autotradeConfigLoading"
              @click="$emit('adjustAlertPolicyNumber', 'alert_webhook_cooldown_minutes', 15, 1, 1440)"
            >
              +15
            </n-button>
          </div>
        </div>
      </div>
      <div v-else class="alert-policy-grid">
        <div class="summary-chip">
          <span class="summary-label">Email Policy</span>
          <strong class="summary-value">{{ props.autotradeStatus?.alert_email_min_severity || "warning" }}</strong>
          <span class="summary-meta">
            ack {{ props.autotradeStatus?.alert_ack_timeout_minutes || 0 }}m / escalate {{ props.autotradeStatus?.alert_escalation_minutes || 0 }}m / renotify {{ props.autotradeStatus?.alert_renotify_minutes || 0 }}m
          </span>
        </div>
        <div class="summary-chip">
          <span class="summary-label">Slack Policy</span>
          <strong class="summary-value">{{ props.autotradeStatus?.alert_slack_min_severity || "error" }}</strong>
          <span class="summary-meta">
            stage {{ props.autotradeStatus?.alert_slack_min_stage || 1 }} / cooldown {{ props.autotradeStatus?.alert_slack_cooldown_minutes || 0 }}m
          </span>
        </div>
        <div class="summary-chip">
          <span class="summary-label">Telegram Policy</span>
          <strong class="summary-value">{{ props.autotradeStatus?.alert_telegram_min_severity || "error" }}</strong>
          <span class="summary-meta">
            stage {{ props.autotradeStatus?.alert_telegram_min_stage || 2 }} / cooldown {{ props.autotradeStatus?.alert_telegram_cooldown_minutes || 0 }}m
          </span>
        </div>
        <div class="summary-chip">
          <span class="summary-label">Webhook Policy</span>
          <strong class="summary-value">{{ props.autotradeStatus?.alert_webhook_min_severity || "error" }}</strong>
          <span class="summary-meta">
            cooldown {{ props.autotradeStatus?.alert_webhook_cooldown_minutes || 0 }}m
          </span>
        </div>
      </div>
    </div>

    <div class="service-section">
      <div class="section-title">Source Overrides</div>
      <div class="section-subtitle">
        Read-only source lane and override state from backend automation.
      </div>

      <div v-if="manualControlsEnabled" class="override-direct-form">
        <n-input v-model:value="directSource.source" placeholder="Source key"></n-input>
        <n-input v-model:value="directSource.reason" placeholder="Reason"></n-input>
        <n-input-number
          v-model:value="directSource.durationHours"
          :min="1"
          :max="24 * 30"
          placeholder="Hours"
        ></n-input-number>
        <n-space>
          <n-button
            size="small"
            type="error"
            :disabled="!props.canOperate || !directSource.source.trim()"
            :loading="props.overrideActionLoading === `source:freeze:${directSource.source.trim()}`"
            @click="submitDirectSource('freeze')"
          >
            Freeze
          </n-button>
          <n-button
            size="small"
            type="warning"
            :disabled="!props.canOperate || !directSource.source.trim()"
            :loading="props.overrideActionLoading === `source:observe:${directSource.source.trim()}`"
            @click="submitDirectSource('observe')"
          >
            Observe
          </n-button>
          <n-button
            size="small"
            :disabled="!props.canOperate || !directSource.source.trim()"
            :loading="props.overrideActionLoading === `source:normal:${directSource.source.trim()}`"
            @click="submitDirectSource('normal')"
          >
            Restore
          </n-button>
        </n-space>
      </div>

      <div class="ops-table-wrap">
        <n-table class="ops-table" size="small" striped>
          <thead>
            <tr>
              <th>Source</th>
              <th>Auto Lane</th>
              <th>Manual State</th>
              <th>Reason</th>
              <th>Until</th>
              <th v-if="manualControlsEnabled">Per-row Controls</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in sourceRows" :key="row.source">
              <td>
                <strong>{{ row.source }}</strong>
                <div class="summary-meta">
                  batch {{ row.batch_cap ?? "-" }} / capital {{ props.toMoney(row.capital_cap || 0) }}
                </div>
              </td>
              <td>{{ row.strategy_mode || row.source_lane || "-" }}</td>
              <td>
                <n-tag size="small" :type="overrideTagType(row.override_state)">
                  {{ row.override_state || "normal" }}
                </n-tag>
              </td>
              <td>{{ row.override_reason || "-" }}</td>
              <td>{{ row.override_until || "-" }}</td>
              <td v-if="manualControlsEnabled">
                <div class="override-row-form">
                  <n-input
                    v-model:value="sourceActionReasons[row.source]"
                    placeholder="Reason"
                  ></n-input>
                  <n-input-number
                    v-model:value="sourceActionHours[row.source]"
                    :min="1"
                    :max="24 * 30"
                    placeholder="Hours"
                  ></n-input-number>
                  <n-space>
                    <n-button
                      size="tiny"
                      type="error"
                      :disabled="!props.canOperate"
                      :loading="props.overrideActionLoading === `source:freeze:${row.source}`"
                      @click="submitSourceRow(row, 'freeze')"
                    >
                      Freeze
                    </n-button>
                    <n-button
                      size="tiny"
                      type="warning"
                      :disabled="!props.canOperate"
                      :loading="props.overrideActionLoading === `source:observe:${row.source}`"
                      @click="submitSourceRow(row, 'observe')"
                    >
                      Observe
                    </n-button>
                    <n-button
                      size="tiny"
                      :disabled="!props.canOperate"
                      :loading="props.overrideActionLoading === `source:normal:${row.source}`"
                      @click="submitSourceRow(row, 'normal')"
                    >
                      Restore
                    </n-button>
                  </n-space>
                </div>
              </td>
            </tr>
            <tr v-if="!sourceRows.length">
              <td :colspan="manualControlsEnabled ? 6 : 5">
                <div class="empty-wrap">
                  <n-empty description="No source controls yet"></n-empty>
                </div>
              </td>
            </tr>
          </tbody>
        </n-table>
      </div>
    </div>

    <div class="service-section">
      <div class="section-title">Cluster Overrides</div>
      <div class="section-subtitle">
        Read-only cluster lane and override state from backend automation.
      </div>

      <div v-if="manualControlsEnabled" class="override-direct-form">
        <n-input v-model:value="directCluster.riskCluster" placeholder="Risk cluster"></n-input>
        <n-input v-model:value="directCluster.reason" placeholder="Reason"></n-input>
        <n-input-number
          v-model:value="directCluster.durationHours"
          :min="1"
          :max="24 * 30"
          placeholder="Hours"
        ></n-input-number>
        <n-space>
          <n-button
            size="small"
            type="error"
            :disabled="!props.canOperate || !directCluster.riskCluster.trim()"
            :loading="props.overrideActionLoading === `cluster:freeze:${directCluster.riskCluster.trim()}`"
            @click="submitDirectCluster('freeze')"
          >
            Freeze
          </n-button>
          <n-button
            size="small"
            type="warning"
            :disabled="!props.canOperate || !directCluster.riskCluster.trim()"
            :loading="props.overrideActionLoading === `cluster:observe:${directCluster.riskCluster.trim()}`"
            @click="submitDirectCluster('observe')"
          >
            Observe
          </n-button>
          <n-button
            size="small"
            :disabled="!props.canOperate || !directCluster.riskCluster.trim()"
            :loading="props.overrideActionLoading === `cluster:normal:${directCluster.riskCluster.trim()}`"
            @click="submitDirectCluster('normal')"
          >
            Restore
          </n-button>
        </n-space>
      </div>

      <div class="ops-table-wrap">
        <n-table class="ops-table" size="small" striped>
          <thead>
            <tr>
              <th>Cluster</th>
              <th>Auto Lane</th>
              <th>Manual State</th>
              <th>Reason</th>
              <th>Until</th>
              <th v-if="manualControlsEnabled">Per-row Controls</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in clusterRows" :key="row.risk_cluster">
              <td>
                <strong>{{ row.risk_cluster }}</strong>
                <div class="summary-meta">
                  batch {{ row.cluster_batch_cap ?? row.batch_cap ?? "-" }} / capital {{ props.toMoney(row.cluster_capital_cap || row.capital_cap || 0) }}
                </div>
              </td>
              <td>{{ row.cluster_lane || row.strategy_mode || "-" }}</td>
              <td>
                <n-tag size="small" :type="overrideTagType(row.override_state)">
                  {{ row.override_state || "normal" }}
                </n-tag>
              </td>
              <td>{{ row.override_reason || "-" }}</td>
              <td>{{ row.override_until || "-" }}</td>
              <td v-if="manualControlsEnabled">
                <div class="override-row-form">
                  <n-input
                    v-model:value="clusterActionReasons[row.risk_cluster]"
                    placeholder="Reason"
                  ></n-input>
                  <n-input-number
                    v-model:value="clusterActionHours[row.risk_cluster]"
                    :min="1"
                    :max="24 * 30"
                    placeholder="Hours"
                  ></n-input-number>
                  <n-space>
                    <n-button
                      size="tiny"
                      type="error"
                      :disabled="!props.canOperate"
                      :loading="props.overrideActionLoading === `cluster:freeze:${row.risk_cluster}`"
                      @click="submitClusterRow(row, 'freeze')"
                    >
                      Freeze
                    </n-button>
                    <n-button
                      size="tiny"
                      type="warning"
                      :disabled="!props.canOperate"
                      :loading="props.overrideActionLoading === `cluster:observe:${row.risk_cluster}`"
                      @click="submitClusterRow(row, 'observe')"
                    >
                      Observe
                    </n-button>
                    <n-button
                      size="tiny"
                      :disabled="!props.canOperate"
                      :loading="props.overrideActionLoading === `cluster:normal:${row.risk_cluster}`"
                      @click="submitClusterRow(row, 'normal')"
                    >
                      Restore
                    </n-button>
                  </n-space>
                </div>
              </td>
            </tr>
            <tr v-if="!clusterRows.length">
              <td :colspan="manualControlsEnabled ? 6 : 5">
                <div class="empty-wrap">
                  <n-empty description="No cluster controls yet"></n-empty>
                </div>
              </td>
            </tr>
          </tbody>
        </n-table>
      </div>
    </div>

    <div class="service-section">
      <div class="section-title">Recent Audit Feed</div>
      <div class="section-subtitle">
        Latest override, incident, and delivery events for operator traceability.
      </div>

      <div v-if="props.auditLoading" class="summary-meta">Loading audit feed...</div>
      <div v-else-if="props.auditFeed.length" class="audit-feed">
        <div
          v-for="item in props.auditFeed"
          :key="`${item.scope}:${item.id}`"
          class="audit-feed-row"
        >
          <div class="audit-feed-main">
            <strong>{{ item.scope.toUpperCase() }} / {{ item.target }}</strong>
            <span class="summary-meta">{{ item.event_type }}</span>
          </div>
          <div class="audit-feed-side">
            <span class="summary-meta">{{ item.reason || "No reason" }}</span>
            <span class="summary-meta">{{ item.created_at || "-" }}</span>
          </div>
        </div>
      </div>
      <div v-else class="empty-wrap">
        <n-empty description="No recent incident events"></n-empty>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";

const props = defineProps({
  cockpit: { type: Object, default: () => ({}) },
  cockpitLoading: { type: Boolean, default: false },
  autotradeStatus: { type: Object, default: () => ({}) },
  autotradeConfigLoading: { type: Boolean, default: false },
  overrideActionLoading: { type: String, default: "" },
  auditLoading: { type: Boolean, default: false },
  alertDispatchLoading: { type: Boolean, default: false },
  slackDispatchLoading: { type: Boolean, default: false },
  telegramDispatchLoading: { type: Boolean, default: false },
  alertControlLoading: { type: String, default: "" },
  alertTimelineLoading: { type: Boolean, default: false },
  alertTimeline: { type: Object, default: () => ({ alert: null, items: [] }) },
  webhookDispatchLoading: { type: Boolean, default: false },
  auditFeed: { type: Array, default: () => [] },
  canOperate: { type: Boolean, default: false },
  toMoney: { type: Function, required: true },
});

const emit = defineEmits([
  "loadAutotradeCockpit",
  "applySourceControlAction",
  "applyClusterControlAction",
  "acknowledgeAlert",
  "assignAlertIncident",
  "adjustAlertPolicyNumber",
  "dispatchAlertEmail",
  "dispatchAlertSlack",
  "dispatchAlertTelegram",
  "dispatchAlertWebhook",
  "handoffAlertIncident",
  "loadAlertTimeline",
  "noteAlertIncident",
  "prioritizeAlertIncident",
  "resolveAlertIncident",
  "toggleAlertAutoEmail",
  "toggleAlertAutoSlack",
  "toggleAlertAutoTelegram",
  "toggleAlertAutoWebhook",
  "setAlertPolicySeverity",
  "resumeAlert",
  "snoozeAlert",
]);

const manualControlsEnabled = false;

const directSource = reactive({
  source: "",
  reason: "",
  durationHours: 48,
});
const directCluster = reactive({
  riskCluster: "",
  reason: "",
  durationHours: 48,
});
const sourceActionReasons = reactive({});
const sourceActionHours = reactive({});
const clusterActionReasons = reactive({});
const clusterActionHours = reactive({});
const alertTimelineVisible = ref(false);
const selectedAlert = ref(null);
const selectedAlertKey = computed(() => String(selectedAlert.value?.alert_key || "").trim());
const incidentForm = reactive({
  owner: "",
  priority: "normal",
  note: "",
});

const blockingReasonText = computed(() => {
  const reasons = Array.isArray(props.cockpit.blocking_reasons)
    ? props.cockpit.blocking_reasons
    : [];
  return reasons.length ? reasons.join(" / ") : "No blocking reasons";
});

const alertItems = computed(() =>
  Array.isArray(props.cockpit.alerts) ? props.cockpit.alerts : [],
);
const lastEmailEvent = computed(() => props.cockpit.alert_delivery?.last_email_event || null);
const lastSlackEvent = computed(() => props.cockpit.alert_delivery?.last_slack_event || null);
const lastTelegramEvent = computed(() => props.cockpit.alert_delivery?.last_telegram_event || null);
const lastWebhookEvent = computed(() => props.cockpit.alert_delivery?.last_webhook_event || null);
const webhookChannelLabel = computed(() =>
  String(props.cockpit.alert_delivery?.webhook_channel_label || "Webhook"),
);
const severityOptions = [
  { label: "Info", value: "info" },
  { label: "Warning", value: "warning" },
  { label: "Error", value: "error" },
];

const openAlertTimeline = (alert) => {
  selectedAlert.value = alert;
  alertTimelineVisible.value = true;
  emit("loadAlertTimeline", alert);
};

watch(
  [selectedAlertKey, alertItems],
  ([alertKey, items]) => {
    if (!alertKey)
      return;
    const matched = (Array.isArray(items) ? items : []).find(
      item => String(item?.alert_key || "").trim() === alertKey,
    );
    if (matched)
      selectedAlert.value = matched;
  },
  { deep: true },
);

watch(
  selectedAlert,
  (alert) => {
    incidentForm.owner = String(alert?.incident_owner || "").trim();
    incidentForm.priority = String(alert?.incident_priority || "normal").trim() || "normal";
    incidentForm.note = String(alert?.latest_case_note || "").trim();
  },
  { immediate: true },
);

const formatTimelineAction = (event) =>
  String(event?.action_label || event?.action || "")
    .split("_")
    .filter(Boolean)
    .join(" ");

const priorityOptions = [
  { label: "Low", value: "low" },
  { label: "Normal", value: "normal" },
  { label: "High", value: "high" },
  { label: "Critical", value: "critical" },
];

const submitIncidentAssign = () => {
  if (!selectedAlert.value)
    return;
  emit("assignAlertIncident", selectedAlert.value, incidentForm.owner, incidentForm.note);
};

const submitIncidentNote = () => {
  if (!selectedAlert.value)
    return;
  emit("noteAlertIncident", selectedAlert.value, incidentForm.note);
};

const submitIncidentPriority = () => {
  if (!selectedAlert.value)
    return;
  emit("prioritizeAlertIncident", selectedAlert.value, incidentForm.priority, incidentForm.note);
};

const submitIncidentHandoff = () => {
  if (!selectedAlert.value)
    return;
  emit("handoffAlertIncident", selectedAlert.value, incidentForm.owner, incidentForm.note);
};

const submitIncidentResolve = () => {
  if (!selectedAlert.value)
    return;
  emit("resolveAlertIncident", selectedAlert.value, incidentForm.note);
};

const sourceOverrideMap = computed(() => {
  const items = Array.isArray(props.cockpit.source_overrides?.items)
    ? props.cockpit.source_overrides.items
    : [];
  return Object.fromEntries(
    items
      .map((item) => [String(item?.source || "").trim(), item])
      .filter(([key]) => key),
  );
});

const clusterOverrideMap = computed(() => {
  const items = Array.isArray(props.cockpit.cluster_overrides?.items)
    ? props.cockpit.cluster_overrides.items
    : [];
  return Object.fromEntries(
    items
      .map((item) => [String(item?.risk_cluster || "").trim(), item])
      .filter(([key]) => key),
  );
});

const sourceRows = computed(() => {
  const rows = new Map();
  const positionItems = Array.isArray(props.cockpit.autotrade?.source_position_controls)
    ? props.cockpit.autotrade.source_position_controls
    : [];
  for (const item of positionItems) {
    const source = String(item?.source || "").trim();
    if (!source)
      continue;
    rows.set(source, { ...item, source });
  }
  for (const item of Object.values(sourceOverrideMap.value)) {
    const source = String(item?.source || "").trim();
    if (!source)
      continue;
    rows.set(source, { ...(rows.get(source) || {}), source });
  }
  return Array.from(rows.values()).map((row) => {
    const override = sourceOverrideMap.value[row.source] || {};
    return {
      ...row,
      override_state: String(override?.state || "normal"),
      override_reason: String(override?.reason || ""),
      override_until: override?.frozen_until || "",
    };
  });
});

const clusterRows = computed(() => {
  const rows = new Map();
  const positionItems = Array.isArray(props.cockpit.autotrade?.cluster_position_controls)
    ? props.cockpit.autotrade.cluster_position_controls
    : [];
  for (const item of positionItems) {
    const riskCluster = String(item?.risk_cluster || "").trim();
    if (!riskCluster)
      continue;
    rows.set(riskCluster, { ...item, risk_cluster: riskCluster });
  }
  for (const item of Object.values(clusterOverrideMap.value)) {
    const riskCluster = String(item?.risk_cluster || "").trim();
    if (!riskCluster)
      continue;
    rows.set(riskCluster, { ...(rows.get(riskCluster) || {}), risk_cluster: riskCluster });
  }
  return Array.from(rows.values()).map((row) => {
    const override = clusterOverrideMap.value[row.risk_cluster] || {};
    return {
      ...row,
      override_state: String(override?.state || "normal"),
      override_reason: String(override?.reason || ""),
      override_until: override?.frozen_until || "",
    };
  });
});

watch(
  sourceRows,
  (rows) => {
    for (const row of rows) {
      if (sourceActionReasons[row.source] === undefined)
        sourceActionReasons[row.source] = row.override_reason || "";
      if (sourceActionHours[row.source] === undefined)
        sourceActionHours[row.source] = 48;
    }
  },
  { immediate: true },
);

watch(
  clusterRows,
  (rows) => {
    for (const row of rows) {
      if (clusterActionReasons[row.risk_cluster] === undefined)
        clusterActionReasons[row.risk_cluster] = row.override_reason || "";
      if (clusterActionHours[row.risk_cluster] === undefined)
        clusterActionHours[row.risk_cluster] = 48;
    }
  },
  { immediate: true },
);

const overrideTagType = (state) => {
  if (state === "frozen")
    return "error";
  if (state === "observe")
    return "warning";
  return "default";
};

const alertType = (severity) => {
  if (severity === "error")
    return "error";
  if (severity === "warning")
    return "warning";
  return "info";
};

const priorityTagType = (priority) => {
  if (priority === "critical")
    return "error";
  if (priority === "high")
    return "warning";
  if (priority === "low")
    return "default";
  return "info";
};

const submitSourceRow = (row, action) =>
  emit("applySourceControlAction", {
    source: row.source,
    action,
    reason: String(sourceActionReasons[row.source] || "").trim(),
    durationHours: Number(sourceActionHours[row.source]) || null,
  });

const submitClusterRow = (row, action) =>
  emit("applyClusterControlAction", {
    riskCluster: row.risk_cluster,
    action,
    reason: String(clusterActionReasons[row.risk_cluster] || "").trim(),
    durationHours: Number(clusterActionHours[row.risk_cluster]) || null,
  });

const submitDirectSource = (action) =>
  emit("applySourceControlAction", {
    source: directSource.source,
    action,
    reason: String(directSource.reason || "").trim(),
    durationHours: Number(directSource.durationHours) || null,
  });

const submitDirectCluster = (action) =>
  emit("applyClusterControlAction", {
    riskCluster: directCluster.riskCluster,
    action,
    reason: String(directCluster.reason || "").trim(),
    durationHours: Number(directCluster.durationHours) || null,
  });
</script>
