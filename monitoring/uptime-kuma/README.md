# Uptime Kuma Integration

This project ships an optional Uptime Kuma instance for service monitoring.

## 1) Start

From project root:

```powershell
docker compose -f monitoring/uptime-kuma/docker-compose.yml up -d
```

Or on Windows:

```cmd
start_uptime_kuma.cmd
```

Open: http://127.0.0.1:3001

## 2) Suggested monitors

Use `targets.example.json` as your monitor checklist:

- Backend readiness: `http://host.docker.internal:8000/health/ready`
- Frontend admin: `http://host.docker.internal:3000/admin/card-flip-ops`
- Proxy pool: `http://host.docker.internal:8899/`
- RAGFlow: `http://host.docker.internal:9380/`

Recommended alerting behavior:

- Alert on backend readiness when status is not `200`.
- Use `GET /health` for operator diagnostics, but keep uptime probes pointed at `/health/ready`.
- Treat `database.degraded_reasons` and `database.vacuum_recommended` in `/health` as operator signals, not end-user uptime checks.

`host.docker.internal` is used so the container can reach host services on Windows/macOS.

## 3) Stop

```powershell
docker compose -f monitoring/uptime-kuma/docker-compose.yml down
```

Or on Windows:

```cmd
stop_uptime_kuma.cmd
```
