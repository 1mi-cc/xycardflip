import axios from "axios";

import { useAuthStore } from "@/stores/auth";

const request = axios.create({
  baseURL: import.meta.env.VITE_CARD_FLIP_API_BASE || "/card-api",
  timeout: 60000,
  headers: {
    "Content-Type": "application/json",
  },
});

const stringifyError = (value) => {
  if (typeof value === "string") {
    const text = value.trim();
    return text && text !== "[object Object]" ? text : "";
  }
  if (Array.isArray(value)) {
    return value.map(item => stringifyError(item)).filter(Boolean).join("; ");
  }
  if (!value || typeof value !== "object")
    return "";

  for (const key of ["detail", "message", "reason", "error", "msg"]) {
    const text = stringifyError(value[key]);
    if (text)
      return text;
  }

  return Object.values(value)
    .map(item => stringifyError(item))
    .filter(Boolean)
    .join("; ");
};

request.interceptors.request.use((config) => {
  const authStore = useAuthStore();
  if (authStore.token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${authStore.token}`;
  }
  return config;
});

request.interceptors.response.use(
  response => response.data,
  (error) => {
    const message = stringifyError(error?.response?.data)
      || stringifyError(error?.message)
      || "请求失败，请稍后重试";
    const wrapped = new Error(message);
    wrapped.status = error?.response?.status || 0;
    wrapped.payload = error?.response?.data || null;
    return Promise.reject(wrapped);
  },
);

const cardFlipApi = {
  getAdminTransparencyOverview() {
    return request.get("/analysis/admin-overview");
  },
  getMetrics() {
    return request.get("/trades/metrics-summary");
  },
  getAutotradeStatus() {
    return request.get("/autotrade/status");
  },
  listExecutionLogs(params = {}) {
    return request.get("/execution/logs", {
      params: {
        ...params,
        limit: Number.isFinite(Number(params.limit))
          ? Math.min(500, Math.max(1, Math.trunc(Number(params.limit))))
          : 100,
      },
    });
  },
};

export default cardFlipApi;
