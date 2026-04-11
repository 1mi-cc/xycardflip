# Card Flip Assistant MVP Backend

This backend is a compliant MVP for virtual card trading assistance:
- ingest sales and listing data from manual/exported sources
- extract card features using Gemini (with rule-based fallback)
- estimate fair value and buy limit
- detect underpriced opportunities
- keep critical actions in manual approval flow

## 1. Quick start

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger UI: `http://127.0.0.1:8000/docs`

SQLite runtime defaults:

```env
SQLITE_JOURNAL_MODE=WAL
SQLITE_SYNCHRONOUS=NORMAL
SQLITE_BUSY_TIMEOUT_MS=5000
DB_WRITE_BATCH_SIZE=50
```

## 2. Core flow

1. `POST /ingest/sales` import recent transaction prices.
2. `POST /ingest/listings` import open listing snapshots.
3. `POST /opportunities/scan` run extraction + robust valuation + risk-aware scoring.
4. `GET /opportunities?status=pending_review` review candidates.
5. `GET /opportunities?status=blocked_risk` inspect blocked high-risk listings.
6. `POST /trades/approve` confirm buy manually.
7. `GET /trades?status=approved_for_buy|listed_for_sale|sold` for operations view.
8. `POST /trades/{trade_id}/mark-listed` after you manually create listing.
9. `POST /trades/{trade_id}/mark-sold` record final sale.
10. `POST /monitor/start|stop|run-once` and `GET /monitor/status` for monitor control.
11. `GET /trades/{trade_id}/pricing-plan` generate dynamic listing price suggestion.
12. `POST /trades/{trade_id}/apply-pricing-plan` apply suggested target sell price.
13. `POST /trades/reprice-open` batch reprice open trades (dry-run by default).
14. `POST /autotrade/run-once` auto-approve qualified pending opportunities once.
15. `GET /analysis/*` access analytics data/calc/decision endpoints, advanced metrics, automation recommendation, SSE stream, and report output.
16. `POST /autotrade/start|stop` and `GET /autotrade/status` for periodic auto-approval loop.
17. `GET /execution/status` view execution adapter mode (`mock`/`webhook`).
18. `POST /execution/buy/{trade_id}?dry_run=true|false&force=false|true` trigger buy execution adapter.
19. `GET /execution/logs` inspect execution result logs.
20. `GET /execution/readiness` validate whether webhook live execution is actually ready.
21. `POST /execution/retry-failed` replay latest failed executions once.
22. `GET|POST /execution-retry/status|start|stop` manage scheduled failed-execution retry service.
23. `POST /execution-retry/run-once` run one retry cycle with optional overrides.
24. `POST /trades/forward-validation/batches` start a forward-validation sample batch.
25. `GET|POST /trades/forward-validation/batches|{id}/close` inspect or close validation batches.
26. `GET|POST /automation/status|start|stop|run-once` orchestrate monitor + scan + autotrade + execution-retry.
27. `GET|POST /supabase/status|start|stop|run-once|reset-cursors` sync local DB tables into Supabase.
28. `GET /auth/user|/auth/userinfo|/user/profile` return frontend permission payload for menu filtering.
29. `GET /health` exposes a minimal public liveness snapshot.
30. `GET /health/ready` provides readiness status for Uptime Kuma / external probes.
31. `GET /autotrade/tuning-history|tuning-activity|tuning-daily-report|tuning-evaluation` inspect threshold audit trail, recent decisions, 24h report, and current auto-tune guard state.
32. `POST /autotrade/tuning/apply` apply a manual threshold tune with persistence.
33. `POST /autotrade/tuning-history/{id}/rollback` revert one recorded threshold tune.
34. `GET /autotrade/cockpit` returns a delivery/operations cockpit including readiness, blocking reasons, portfolio budget, and source/cluster controls.
35. `POST /autotrade/config` updates execution, recovery, and portfolio-risk knobs for live operations.
36. `GET /setup/status|audit|test-gemini` and `POST /setup/apply` support first-run setup flow.

## 3. Gemini setup

Set in `.env`:

```env
GEMINI_API_KEY=your_key_here
GEMINI_KEY_SOURCE_PATH=C:\path\to\gemini-balance
GEMINI_MODEL=gemini-2.0-flash
```

If `GEMINI_KEY_SOURCE_PATH` points to a `gemini-balance` directory or its `.env`,
the backend reads `API_KEYS=[...]` from that file and reuses the same key pool for
its own local round-robin Gemini calls. If neither local key nor external source
is configured, the extractor automatically switches to rule-based mode.

## 4. Example payload

`POST /ingest/listings`

```json
[
  {
    "source": "manual_export",
    "listing_id": "xy123",
    "seller_id": "u_88",
    "title": "Blue Dragon SSR Near Mint",
    "description": "first owner, no scratches",
    "list_price": 160,
    "listed_at": "2026-02-25T09:10:00Z",
    "status": "open",
    "raw": {
      "platform": "xianyu"
    }
  }
]
```

## 5. Risk controls

- `MIN_PROFIT`, `MIN_ROI`, and `RISK_DISCOUNT` gate opportunity status.
- `RISK_*` controls can block suspicious listings (`blocked_risk`) before manual review.
- Valuation now uses robust quantiles with outlier filtering instead of plain median.
- Pricing strategy uses holding days, inventory pressure, and volatility to suggest sell targets.
- Default status is `pending_review`; optional auto-approval exists via `/autotrade/*` (disabled by default).
- No real exchange buy/sell execution API exists yet (mark-listed/mark-sold are still operation records).
- Execution adapter is now available with `mock`/`webhook` provider and `dry_run` support.
- `GET /execution/readiness` summarizes whether real webhook execution is live-ready or still missing config.
- Execution API now includes `/execution/buy|list|sell/{trade_id}` and writes full logs to `execution_logs`.
- Failed executions can be replayed via `/execution/retry-failed`.
- Failed-execution replay now has a background loop via `/execution-retry/*`.
- Monitor can auto-trigger opportunity scanning via `MONITOR_AUTO_SCAN_AFTER_INGEST=true`.
- Unified orchestration is available via `/automation/*`.
- Background services can auto-start on API boot via `AUTO_START_*`.
- Auto-approval can optionally trigger buy execution via `AUTO_EXECUTE_BUY_ON_APPROVE`.
- All approvals are traceable in `opportunities` and `trades`.
- Forward validation batches let you enroll the next 30-100 approved trades automatically and review realized hit rate / holding days.
- Auto-tune can optionally apply threshold changes after a forward-validation batch is closed, but only if guardrails pass.
- Auto-tune decisions are written to both a tuning history table and an activity feed so you can audit why the system tuned, skipped, or blocked itself.
- Autotrade now exposes operator-ready delivery controls:
  - source-level batch/capital controls
  - source-action lanes for `buy|list|sell`
  - risk-cluster controls using `normalized_key` / `item_type`
  - portfolio-level capital cap and single-source concentration cap
- `GET /autotrade/cockpit` is the primary operator surface for go-live checks.

### Auto-tune env

```env
AUTO_TUNE_AUTO_APPLY_ENABLED=false
AUTO_TUNE_COOLDOWN_HOURS=24
AUTO_TUNE_MIN_CLOSED_BATCHES=2
AUTO_TUNE_LATEST_MIN_SOLD_COUNT=5
AUTO_TUNE_PREVIOUS_MIN_SOLD_COUNT=3
```

Behavior:
- `AUTO_TUNE_AUTO_APPLY_ENABLED=true` lets the backend auto-apply a threshold tune when you close a forward-validation batch.
- `AUTO_TUNE_COOLDOWN_HOURS` prevents repeated retuning too frequently.
- `AUTO_TUNE_MIN_CLOSED_BATCHES` requires enough closed validation batches before auto-apply is allowed.
- `AUTO_TUNE_LATEST_MIN_SOLD_COUNT` and `AUTO_TUNE_PREVIOUS_MIN_SOLD_COUNT` enforce minimum sold-trade evidence on recent closed batches.
- If a guardrail blocks auto-apply, the block reason is still recorded in the activity feed and appears in the 24h tuning report.

### Execution env

```env
EXECUTION_PROVIDER=mock            # mock | webhook | disabled
EXECUTION_TIMEOUT_SEC=8
EXECUTION_AUTH_TOKEN=
EXECUTION_WEBHOOK_SECRET=
EXECUTION_WEBHOOK_MAX_RETRIES=2
EXECUTION_WEBHOOK_RETRY_BACKOFF_SEC=1.5
EXECUTION_WEBHOOK_BUY_URL=
EXECUTION_LIVE_ENABLED=false       # gate for all non-dry-run execution actions
EXECUTION_LIVE_CONFIRM_TOKEN=      # optional second-factor token for live execution
EXECUTION_LIVE_MAX_BUY_PRICE=0     # <=0 means no cap
EXECUTION_LIVE_MIN_LIST_PROFIT_RATIO=0
EXECUTION_LIVE_MIN_SELL_PROFIT_RATIO=0
EXECUTION_RETRY_ENABLED=false
EXECUTION_RETRY_INTERVAL_SEC=45
EXECUTION_RETRY_BATCH_SIZE=20
EXECUTION_RETRY_ACTION=all         # all | buy | list | sell
EXECUTION_RETRY_DRY_RUN=true
EXECUTION_RETRY_FORCE=false
EXECUTION_RETRY_CONFIRM_TOKEN=      # optional; fallback to EXECUTION_LIVE_CONFIRM_TOKEN
AUTOMATION_DEFAULT_INCLUDE_MONITOR=true
AUTOMATION_DEFAULT_INCLUDE_SCAN=true
AUTOMATION_DEFAULT_INCLUDE_AUTOTRADE=true
AUTOMATION_DEFAULT_INCLUDE_EXECUTION_RETRY=true
AUTOMATION_DEFAULT_INCLUDE_SUPABASE_SYNC=false
AUTOMATION_DEFAULT_SCAN_LIMIT=120

AUTO_EXECUTE_BUY_ON_APPROVE=false
AUTO_EXECUTE_BUY_DRY_RUN=true
AUTO_EXECUTE_LIST_ON_BUY_SUCCESS=false
AUTO_EXECUTE_LIST_DRY_RUN=true
AUTO_START_AUTOTRADE=false
AUTO_START_EXECUTION_RETRY=false

AUTO_APPROVE_SOURCE_OBSERVE_BASE_MULTIPLIER=0.2
AUTO_APPROVE_SOURCE_OBSERVE_RELEASE_STREAK=3
AUTO_APPROVE_SOURCE_CASHOUT_MAX_HOLDING_DAYS=5.0

AUTO_APPROVE_PORTFOLIO_MAX_DEPLOYED_CAPITAL=0
AUTO_APPROVE_MAX_SOURCE_CAPITAL_SHARE=0.6
AUTO_APPROVE_MAX_CLUSTER_BATCH_SHARE=0.6
AUTO_APPROVE_MAX_CLUSTER_CAPITAL_SHARE=0.6
```

When `EXECUTION_WEBHOOK_SECRET` is set, webhook requests include:
- `X-CardFlip-Timestamp`
- `X-CardFlip-Signature` (`HMAC-SHA256(secret, timestamp + "." + rawBody)`)
- `X-Idempotency-Key`

### Delivery Controls

- `AUTO_APPROVE_SOURCE_OBSERVE_BASE_MULTIPLIER`
  Base approval flow allowed when a source is in `observe`.
- `AUTO_APPROVE_SOURCE_OBSERVE_RELEASE_STREAK`
  Number of consecutive live execution successes required before a recovering source can fully expand again.
- `AUTO_APPROVE_SOURCE_CASHOUT_MAX_HOLDING_DAYS`
  Cashout quality threshold used before `list/sell` lanes can expand.
- `AUTO_APPROVE_PORTFOLIO_MAX_DEPLOYED_CAPITAL`
  Hard portfolio capital ceiling for approved/open exposure. `0` means disabled.
- `AUTO_APPROVE_MAX_SOURCE_CAPITAL_SHARE`
  Max fraction of the current portfolio capital budget assignable to one source.
- `AUTO_APPROVE_MAX_CLUSTER_BATCH_SHARE`
  Max fraction of one run's approval batch assignable to one risk cluster.
- `AUTO_APPROVE_MAX_CLUSTER_CAPITAL_SHARE`
  Max fraction of one run's capital budget assignable to one risk cluster.

## 7. Operator Runbook

Before enabling live automation:

1. `GET /health/ready`
   Ensure the API reports ready and there is no degraded reason.
2. `GET /execution/readiness`
   Confirm webhook/live execution is actually ready.
3. `GET /autotrade/cockpit`
   Verify `ready=true`, inspect `blocking_reasons`, and confirm portfolio remaining capital is positive.
4. `POST /autotrade/config`
   Set portfolio and concentration caps for the current bankroll.
5. `POST /autotrade/run-once?force=true`
   Run one dry operational approval cycle and inspect `source_position_controls`, `cluster_position_controls`, and execution counters.
6. `POST /automation/run-once`
   Run the full orchestrated loop only after the previous checks are clean.

During operations, use:

- `GET /autotrade/cockpit` for the top-level operator view
- `GET /trades/metrics-summary` for realized performance and cashout quality
- `GET /execution/logs` for action-level execution audit
- `GET /autotrade/tuning-history` and `GET /autotrade/tuning-activity` for threshold audit trail

### UI permission env

```env
UI_AUTH_USERNAME=operator
UI_AUTH_PASSWORD=
UI_AUTH_NICKNAME=本地操作员
UI_AUTH_DEFAULT_ROLE=admin
UI_AUTH_SESSION_HOURS=72
UI_AUTH_ALLOW_REGISTRATION=true
UI_USER_ROLES=admin:admin,ops:ops,viewer:viewer
UI_MENU_ROLES=admin
UI_MENU_PERMISSIONS=dashboard:view,game:feature:view,cardflip:view,task:view,task:batch,message:test,token:view,profile:view
UI_ROLE_PERMISSIONS_ADMIN=dashboard:view,game:feature:view,cardflip:view,task:view,task:batch,message:test,token:view,profile:view
UI_ROLE_PERMISSIONS_OPS=dashboard:view,cardflip:view,task:view,task:batch,message:test,token:view
UI_ROLE_PERMISSIONS_VIEWER=dashboard:view,cardflip:view,token:view,profile:view
```

If `UI_AUTH_PASSWORD` is left empty on first boot, the backend creates a one-time bootstrap admin password at:

```text
<sqlite_dir>/bootstrap_admin_credentials.json
```

Existing seeded admin accounts are no longer force-reset on every startup.

## 6. Smoke test

Run the end-to-end smoke script:

```bash
cd backend
python scripts/smoke_test.py
```

Expected output: `smoke_test_passed`

Read-only database diagnostics:

```bash
cd backend
python scripts/db_diagnostics.py
```

Public `/health` intentionally omits internal startup details, proxy runtime state, and private infrastructure URLs.

## 7. Market monitor loop script

You asked to add the monitor loop logic. It is available at:

```bash
python backend/scripts/market_monitor_loop.py
```

Environment variables (in `backend/.env`):

- `MONITOR_TARGET_URL`
- `MONITOR_USE_PROXY_POOL`
- `PROXY_POOL_API`
- `PROXY_POOL_PARAMS`
- `INGEST_URL`
- `AUTO_SCAN_URL`
- `AUTO_SCAN_AFTER_INGEST`

The script fetches market items, converts them to listing rows, ingests them, then optionally triggers opportunity scan.

## 8. IPProxyPool integration

IPProxyPool repository has been added under:

```bash
third_party/IPProxyPool
```

Start it with:

```bash
start_proxy_pool.bat
```

Or launch all services with proxy pool:

```bash
start_card_flip.bat proxy
```

Launcher options:

```bash
start_card_flip.bat check   # only print root/dependency check
start_card_flip.bat fresh   # force reinstall backend/frontend dependencies
start_proxy_pool.bat check  # only check proxy pool path/deps state
start_proxy_pool.bat fresh  # force reinstall proxy dependencies
```

Launcher behavior notes:
- If port `8000`, `3000`, or `8899` is already listening, launcher skips duplicate startup for that service.
- After starting services, launcher waits for HTTP readiness checks (`/health` for backend, `/` for frontend/proxy when available).

If you run launcher scripts from a copied desktop `.bat`, set a fixed project path first:

```bash
set CARD_FLIP_ROOT=%USERPROFILE%\Desktop\filess\xyzw_web_helper
start_card_flip.bat check
start_card_flip.bat
```

Default proxy pool API is `http://127.0.0.1:8899/` to avoid conflict with backend `8000`.

When enabled via `MONITOR_USE_PROXY_POOL=true`, monitor requests will fetch proxy IP from `PROXY_POOL_API` before pulling market data.

## 9. Xianyu monitor profile (anti-crawl aware)

Set in `.env`:

```
MONITOR_PROVIDER=xianyu
# 支持多关键词（逗号/分号/换行分隔）
XIAN_YU_KEYWORDS=咸鱼之王功法,咸鱼之王洗练石,咸鱼之王珍珠
# 兼容老配置：未设置 XIAN_YU_KEYWORDS 时使用这个
XIAN_YU_KEYWORD=咸鱼之王功法
XIAN_YU_COOKIE=your_cookie_if_needed   # optional, improves success rate
MONITOR_MAX_PRICE=100                  # skip listings priced above this
MONITOR_DAY_DELAY_MIN=15
MONITOR_DAY_DELAY_MAX=30
MONITOR_PEAK_DELAY_MIN=3
MONITOR_PEAK_DELAY_MAX=8
MONITOR_NIGHT_DELAY_MIN=25
MONITOR_NIGHT_DELAY_MAX=45
MONITOR_CIRCUIT_MAX_ERRORS=3           # consecutive errors before circuit opens
MONITOR_CIRCUIT_403_THRESHOLD=2        # consecutive 403s trigger immediate stop
MONITOR_PAGES=2                        # how many search pages per run (1-10)
MONITOR_AUTO_SCAN_AFTER_INGEST=false
MONITOR_AUTO_SCAN_LIMIT=80
AUTO_START_MONITOR=false

ALERT_EMAIL_ENABLED=true
ALERT_EMAIL_TO=2590197063@qq.com
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=you@example.com
SMTP_PASSWORD=app_password
SMTP_USE_TLS=true
```

Behavior:
- Daytime (08:00-17:00): 15-30s triangular random delay.
- Evening peak (17:00-24:00): 3-8s triangular random delay.
- Night (00:00-08:00): 25-45s delay.
- Circuit breaker: on repeated errors / 403 the monitor stops, reports `circuit_open` via `/monitor/status`, and requires manual `/monitor/start` to resume.
- Circuit alert: when circuit opens, an email is sent if SMTP is configured.

## 10. One-shot Xianyu spider

`python scripts/xianyu_spider.py`  
Uses the same parser as the monitor to fetch `MONITOR_PAGES` pages once, filters by `MONITOR_MAX_PRICE`, and inserts as `source=xianyu_spider` into the DB. Use it to quickly backfill training data or trigger one manual batch ingest.

## 11. Supabase coupling

The backend now supports incremental sync from local SQLite to Supabase REST API.

Set in `.env`:

```env
SUPABASE_ENABLED=true
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SUPABASE_SCHEMA=public
SUPABASE_TABLE_PREFIX=cardflip_
SUPABASE_TIMEOUT_SEC=8
SUPABASE_SYNC_INTERVAL_SEC=30
SUPABASE_SYNC_BATCH_SIZE=200
AUTO_START_SUPABASE_SYNC=false
```

Create mirror tables in Supabase SQL editor first:

```sql
-- run file:
-- backend/sql/supabase_schema.sql
```

Manual one-shot sync command:

```bash
cd backend
python scripts/supabase_sync_once.py --force
```

Reset cursor and do full replay:

```bash
cd backend
python scripts/supabase_sync_once.py --reset-cursors --force
```

API controls:
- `GET /supabase/status`
- `POST /supabase/start`
- `POST /supabase/stop`
- `POST /supabase/run-once?force=true`
- `POST /supabase/reset-cursors?table=sales_raw` (optional `table`; empty means reset all)

## 12. Marketplace provider templates

The read-only arbitrage layer uses `marketplace_offers` and does **not** write into
`pending_review`, `trades`, or `execution`.

### Taobao TOP

Set in `.env`:

```env
TAOBAO_TOP_GATEWAY_URL=https://eco.taobao.com/router/rest
TAOBAO_TOP_APP_KEY=
TAOBAO_TOP_APP_SECRET=
TAOBAO_TOP_METHOD=alibaba.tuike.offer.get
TAOBAO_TOP_SIGN_METHOD=hmac
TAOBAO_TOP_ISV_CODE=
TAOBAO_TOP_SESSION=
TAOBAO_TOP_QUERY_STRING={"filter_param":{"price_range":{"price_range_max":5000,"price_range_min":50},"start_order_num":1},"query_param":{"offer_name":["Pokemon Card PSA 10"],"top_category_id":0,"top_category_name":"","company_name":["",""],"owner_id":null,"category_id":null,"user_tags":[]},"sort_param":{"price":"+"}}
TAOBAO_TOP_TIMEOUT_SEC=15
```

Runtime paths:
- `GET /marketplace/providers/taobao/status`
- `POST /marketplace/providers/taobao/sync-once`
- `POST /marketplace/providers/taobao/ingest-snapshot`
- `python scripts/taobao_sync_once.py`

### Pinduoduo

Set in `.env`:

```env
PINDUODUO_API_URL=https://gw-api.pinduoduo.com/api/router
PINDUODUO_CLIENT_ID=
PINDUODUO_CLIENT_SECRET=
PINDUODUO_TYPE=pdd.ddk.goods.search
PINDUODUO_ACCESS_TOKEN=
PINDUODUO_DATA_TYPE=JSON
PINDUODUO_PARAMS_JSON={"keyword":"Pokemon Card PSA 10","page":1,"page_size":30,"sort_type":0,"with_coupon":false}
PINDUODUO_TIMEOUT_SEC=15
```

Runtime paths:
- `GET /marketplace/providers/pinduoduo/status`
- `POST /marketplace/providers/pinduoduo/sync-once`
- `POST /marketplace/providers/pinduoduo/ingest-snapshot`

### JD

Set in `.env`:

```env
JD_API_URL=https://router.jd.com/api
JD_APP_KEY=
JD_APP_SECRET=
JD_METHOD=jd.union.open.goods.query
JD_ACCESS_TOKEN=
JD_SIGN_METHOD=md5
JD_VERSION=1.0
JD_FORMAT=json
JD_PARAM_JSON={"goodsReq":{"keyword":"Pokemon Card PSA 10","pageIndex":1,"pageSize":20,"sortName":"price","sort":"asc"}}
JD_TIMEOUT_SEC=15
```

Runtime paths:
- `GET /marketplace/providers/jd/status`
- `POST /marketplace/providers/jd/sync-once`
- `POST /marketplace/providers/jd/ingest-snapshot`

### Snapshot examples

You can validate the arbitrage layer before credential approval by importing snapshot JSON manually:

- `Import Taobao Snapshot`
- `Import Pinduoduo Snapshot`
- `Import JD Snapshot`

Those actions only write to `marketplace_offers`.

### Generic cookie refresh

For cookie-first providers, use the generic browser cookie refresher instead of maintaining
one script per marketplace:

```powershell
python backend/scripts/refresh_marketplace_cookie.py --provider xianyu --kill-browsers
python backend/scripts/refresh_marketplace_cookie.py --provider jd --kill-browsers
python backend/scripts/refresh_marketplace_cookie.py --provider pinduoduo --kill-browsers
```

Compatibility wrappers are also available:

```powershell
python backend/scripts/refresh_xianyu_cookie.py --kill-browsers
python backend/scripts/refresh_jd_cookie.py --kill-browsers
python backend/scripts/refresh_pinduoduo_cookie.py --kill-browsers
```

To sync the refreshed cookie to the server `.env` for the active release:

```powershell
powershell -ExecutionPolicy Bypass -File backend/scripts/sync_marketplace_cookie_to_server.ps1 -Provider xianyu
powershell -ExecutionPolicy Bypass -File backend/scripts/sync_marketplace_cookie_to_server.ps1 -Provider jd
powershell -ExecutionPolicy Bypass -File backend/scripts/sync_marketplace_cookie_to_server.ps1 -Provider pinduoduo
```

To keep a provider cookie synced in a loop:

```powershell
powershell -ExecutionPolicy Bypass -File backend/scripts/run_cookie_bridge.ps1 -Provider xianyu -IntervalMinutes 20 -RemoteAction run-once
powershell -ExecutionPolicy Bypass -File backend/scripts/run_cookie_bridge.ps1 -Provider jd -IntervalMinutes 20
powershell -ExecutionPolicy Bypass -File backend/scripts/run_cookie_bridge.ps1 -Provider pinduoduo -IntervalMinutes 20
```

Convenience launchers:

```cmd
start_cookie_bridge.cmd
start_jd_cookie_bridge.cmd
start_pinduoduo_cookie_bridge.cmd
```

Notes:
- The refresher only updates the target provider env key.
- It never prints the full cookie value.
- `xianyu` still validates `_m_h5_tk` and `_m_h5_tk_enc`.
- `jd` and `pinduoduo` are cookie-mode first, but still high-risk and unstable until a real
  snapshot bridge is proven against live pages.

### Cookie-mode snapshot bridge

`JD` and `Pinduoduo` cookie-mode `sync-once` can now take a bridge URL override instead of
requiring only env-configured provider URLs.

Examples:

```http
POST /card-api/marketplace/providers/jd/sync-once?snapshot_url=https://bridge.example/jd/snapshot
POST /card-api/marketplace/providers/pinduoduo/sync-once?snapshot_url=https://bridge.example/pinduoduo/snapshot
```

The bridge only needs to return standard JSON snapshot payloads already accepted by:
- `POST /marketplace/providers/jd/ingest-snapshot`
- `POST /marketplace/providers/pinduoduo/ingest-snapshot`

### Local snapshot bridge

You can now run a local cookie-backed snapshot bridge for `JD` or `Pinduoduo`.
The bridge listens only on `127.0.0.1`, injects the locally refreshed cookie, and
returns JSON from the upstream source URL without writing to the database.

Examples:

```powershell
powershell -ExecutionPolicy Bypass -File backend/scripts/run_snapshot_bridge.ps1 `
  -Provider jd `
  -SourceUrl "https://your-local-or-discovered-json-endpoint.example/jd" `
  -UpstreamMethod GET `
  -Port 8765

powershell -ExecutionPolicy Bypass -File backend/scripts/run_snapshot_bridge.ps1 `
  -Provider pinduoduo `
  -SourceUrl "https://your-local-or-discovered-json-endpoint.example/pdd" `
  -UpstreamMethod GET `
  -Port 8766
```

Provider-specific wrappers:

```powershell
python backend/scripts/jd_snapshot_bridge.py --source-url "https://example/jd" --port 8765
python backend/scripts/pinduoduo_snapshot_bridge.py --source-url "https://example/pdd" --port 8766
```

Once running, use these bridge URLs in the dashboard:

- `http://127.0.0.1:8765/snapshot`
- `http://127.0.0.1:8766/snapshot`

Health endpoints:

- `http://127.0.0.1:8765/health`
- `http://127.0.0.1:8766/health`

Constraints:
- The bridge never prints the full cookie.
- It is `cookie-mode / high-risk / unstable`.
- It expects the upstream source URL to already return JSON.
- It does not implement general-purpose webpage parsing.

### Local upstream capture

If you do not know the upstream JSON URL yet, use the local capture helper. It connects to
your logged-in Edge session through CDP, watches `Fetch/XHR` traffic, and prints candidate
JSON request URLs without exposing cookies or full headers.

Examples:

```powershell
powershell -ExecutionPolicy Bypass -File backend/scripts/run_upstream_capture.ps1 -Provider jd -WatchSeconds 25
powershell -ExecutionPolicy Bypass -File backend/scripts/run_upstream_capture.ps1 -Provider pinduoduo -WatchSeconds 25
```

Wrappers:

```powershell
python backend/scripts/capture_jd_upstream.py --watch-seconds 25
python backend/scripts/capture_pinduoduo_upstream.py --watch-seconds 25
```

Expected workflow:
1. Start capture.
2. During the watch window, use the opened browser page to search the product you care about.
3. Review the printed candidate JSON URLs.
4. Pick one and feed it into the local snapshot bridge or dashboard `snapshot bridge URL` input.

### Browser snapshot bridge

If no stable upstream JSON URL is available, use the browser snapshot bridge instead.
It extracts product cards directly from the rendered page in your logged-in Edge session and
returns standard snapshot JSON for `sync-once`.

Examples:

```powershell
powershell -ExecutionPolicy Bypass -File backend/scripts/run_browser_snapshot_bridge.ps1 `
  -Provider jd `
  -Keyword "Q coin auto recharge" `
  -Port 8785

powershell -ExecutionPolicy Bypass -File backend/scripts/run_browser_snapshot_bridge.ps1 `
  -Provider pinduoduo `
  -Keyword "Q币 自动充值" `
  -Port 8786
```

Wrappers:

```powershell
python backend/scripts/jd_browser_snapshot.py --keyword "Q coin auto recharge" --port 8785
python backend/scripts/pinduoduo_browser_snapshot.py --keyword "Q币 自动充值" --port 8786
```

Use these bridge URLs in the dashboard:

- `http://127.0.0.1:8785/snapshot`
- `http://127.0.0.1:8786/snapshot`

Notes:
- This is still `cookie-mode / high-risk / unstable`.
- It extracts visible browser results, not a formal API.
- It does not print cookies or raw response bodies.

### Browser session keeper

For providers that need a stable logged-in browser session, start a persistent Edge remote-debug
window first, keep it open, then run the browser snapshot bridge with `--reuse-browser`.

Examples:

```powershell
powershell -ExecutionPolicy Bypass -File backend/scripts/run_browser_session_keeper.ps1 `
  -Provider jd `
  -ReuseIfRunning

powershell -ExecutionPolicy Bypass -File backend/scripts/run_browser_session_keeper.ps1 `
  -Provider pinduoduo `
  -ReuseIfRunning
```

If no keyword is provided, `jd` and `pinduoduo` now default to virtual-goods seeds:

- `jd`: `Q coin auto recharge`
- `Q币 自动充值`

Probe the current keeper session without launching a new browser:

```powershell
powershell -ExecutionPolicy Bypass -File backend/scripts/run_browser_session_keeper.ps1 `
  -Provider pinduoduo `
  -CheckOnly
```

The probe returns:

- `current_url`
- `page_title`
- `page_state = login | search_results | unknown`
- `login_required`

Convenience launchers:

```cmd
start_jd_browser_keeper.cmd
start_pinduoduo_browser_keeper.cmd
```

Then start the snapshot bridge against the same remote debug browser:

```powershell
powershell -ExecutionPolicy Bypass -File backend/scripts/run_browser_snapshot_bridge.ps1 -Provider pinduoduo -ReuseBrowser
```

`jd` and `pinduoduo` browser snapshots now apply `virtual_goods_only` by default.

### Push local browser snapshot to remote server

Because the remote backend cannot reach your local `127.0.0.1` bridge directly, use the
push helper to fetch from the local browser bridge and then call the remote ingest endpoint.

Examples:

```powershell
powershell -ExecutionPolicy Bypass -File backend/scripts/sync_marketplace_snapshot_to_server.ps1 `
  -Provider jd `
  -BridgeUrl "http://127.0.0.1:8785/snapshot" `
  -Limit 20

powershell -ExecutionPolicy Bypass -File backend/scripts/sync_marketplace_snapshot_to_server.ps1 `
  -Provider pinduoduo `
  -BridgeUrl "http://127.0.0.1:8786/snapshot" `
  -Limit 20
```

Push is fail-closed:

- The local snapshot must return `ready_for_push = true`
- `ready_for_push` only becomes true when:
  - `login_required = false`
  - `low_confidence = false`
  - `accepted_item_count > 0`
  - `virtual_candidate_count > 0`
  - `virtual_goods_only_applied = true`

### Marketplace shadow dry-run

`POST /marketplace/shadow/run-once` is dry-run-only and limited to `virtual_goods` marketplace offers. It always evaluates virtual-only arbitrage with `shipping_cost = 0.0`; non-virtual marketplace rows are ignored by this shadow layer. Use it only after manual or Pinduoduo virtual offers are present, and keep JD fail-closed while abnormal/risk pages are present.

Virtual shadow uses separate observation thresholds:

- `MARKETPLACE_SHADOW_VIRTUAL_MIN_NET_PROFIT=5`
- `MARKETPLACE_SHADOW_VIRTUAL_MIN_ROI=0.02`
- `MARKETPLACE_SHADOW_VIRTUAL_MIN_CONFIDENCE=0.75`
