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
- Default status is `pending_review`; no auto-buy or auto-sell API exists.
- All approvals are traceable in `opportunities` and `trades`.

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
set CARD_FLIP_ROOT=C:\Users\25901\Desktop\目录\xyzw_web_helper
start_card_flip.bat check
start_card_flip.bat
```

Default proxy pool API is `http://127.0.0.1:8899/` to avoid conflict with backend `8000`.

When enabled via `MONITOR_USE_PROXY_POOL=true`, monitor requests will fetch proxy IP from `PROXY_POOL_API` before pulling market data.

## 9. Xianyu monitor profile (anti-crawl aware)

Set in `.env`:

```
MONITOR_PROVIDER=xianyu
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

ALERT_EMAIL_ENABLED=true
ALERT_EMAIL_TO=2590197063@qq.com
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=you@example.com
SMTP_PASSWORD=app_password
SMTP_USE_TLS=true
```

Behavior:
- Daytime (08:00–17:00): 15–30s triangular random delay.
- Evening peak (17:00–24:00): 3–8s triangular random delay.
- Night (00:00–08:00): 25–45s delay.
- Circuit breaker: on repeated errors / 403 the monitor stops, reports `circuit_open` via `/monitor/status`, and requires manual `/monitor/start` to resume.
- Circuit alert: when circuit opens, an email is sent if SMTP is configured.

## 10. One-shot Xianyu spider

`python scripts/xianyu_spider.py`  
Uses the same parser as the monitor to fetch `MONITOR_PAGES` pages once, filters by `MONITOR_MAX_PRICE`, and inserts as `source=xianyu_spider` into the DB. Use it to快速补充训练数据或手动触发一次批量入库。
