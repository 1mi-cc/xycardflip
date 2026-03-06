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
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger UI: `http://127.0.0.1:8000/docs`

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
15. `POST /autotrade/start|stop` and `GET /autotrade/status` for periodic auto-approval loop.
16. `GET /execution/status` view execution adapter mode (`mock`/`webhook`).
17. `POST /execution/buy/{trade_id}?dry_run=true|false&force=false|true` trigger buy execution adapter.
18. `GET /execution/logs` inspect execution result logs.
19. `POST /execution/retry-failed` replay latest failed executions once.
20. `GET|POST /execution-retry/status|start|stop` manage scheduled failed-execution retry service.
21. `POST /execution-retry/run-once` run one retry cycle with optional overrides.
22. `GET|POST /automation/status|start|stop|run-once` orchestrate monitor + scan + autotrade + execution-retry.
23. `GET|POST /supabase/status|start|stop|run-once|reset-cursors` sync local DB tables into Supabase.
24. `GET /auth/user|/auth/userinfo|/user/profile` return frontend permission payload for menu filtering.

## 3. Gemini setup

Set in `.env`:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.0-flash
```

Without API key, the extractor automatically switches to rule-based mode.

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
- Execution API now includes `/execution/buy|list|sell/{trade_id}` and writes full logs to `execution_logs`.
- Failed executions can be replayed via `/execution/retry-failed`.
- Failed-execution replay now has a background loop via `/execution-retry/*`.
- Monitor can auto-trigger opportunity scanning via `MONITOR_AUTO_SCAN_AFTER_INGEST=true`.
- Unified orchestration is available via `/automation/*`.
- Background services can auto-start on API boot via `AUTO_START_*`.
- Auto-approval can optionally trigger buy execution via `AUTO_EXECUTE_BUY_ON_APPROVE`.
- All approvals are traceable in `opportunities` and `trades`.

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
```

When `EXECUTION_WEBHOOK_SECRET` is set, webhook requests include:
- `X-CardFlip-Timestamp`
- `X-CardFlip-Signature` (`HMAC-SHA256(secret, timestamp + "." + rawBody)`)
- `X-Idempotency-Key`

### UI permission env

```env
UI_AUTH_USERNAME=operator
UI_AUTH_PASSWORD=admin123456
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

## 6. Smoke test

Run the end-to-end smoke script:

```bash
cd backend
python scripts/smoke_test.py
```

Expected output: `smoke_test_passed`

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
- Daytime (08:00鈥?7:00): 15鈥?0s triangular random delay.
- Evening peak (17:00鈥?4:00): 3鈥?s triangular random delay.
- Night (00:00鈥?8:00): 25鈥?5s delay.
- Circuit breaker: on repeated errors / 403 the monitor stops, reports `circuit_open` via `/monitor/status`, and requires manual `/monitor/start` to resume.
- Circuit alert: when circuit opens, an email is sent if SMTP is configured.

## 10. One-shot Xianyu spider

`python scripts/xianyu_spider.py`  
Uses the same parser as the monitor to fetch `MONITOR_PAGES` pages once, filters by `MONITOR_MAX_PRICE`, and inserts as `source=xianyu_spider` into the DB. Use it to蹇€熻ˉ鍏呰缁冩暟鎹垨鎵嬪姩瑙﹀彂涓€娆℃壒閲忓叆搴撱€?

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
