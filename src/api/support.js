const ENDPOINTS = {
  list: ["/card-api/support/tickets", "/support/tickets"],
};

const toQueryString = (params = {}) => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "")
      return;
    search.set(key, String(value));
  });
  const text = search.toString();
  return text ? `?${text}` : "";
};

const extractErrorMessage = (payload, fallback = "请求失败") => {
  if (!payload)
    return fallback;
  if (typeof payload === "string")
    return payload;
  if (typeof payload.message === "string" && payload.message.trim())
    return payload.message.trim();
  if (typeof payload.detail === "string" && payload.detail.trim())
    return payload.detail.trim();
  if (Array.isArray(payload.detail) && payload.detail.length) {
    const first = payload.detail[0];
    if (typeof first === "string")
      return first;
    if (first && typeof first === "object") {
      const msg = first.msg || first.message || first.detail;
      if (typeof msg === "string" && msg.trim())
        return msg.trim();
    }
  }
  return fallback;
};

const requestSupport = async ({
  method = "GET",
  endpointSuffix = "",
  query = null,
  body = null,
  token = "",
}) => {
  let lastError = null;

  for (const base of ENDPOINTS.list) {
    const url = `${base}${endpointSuffix}${toQueryString(query || {})}`;
    try {
      const headers = { Accept: "application/json" };
      if (body !== null)
        headers["Content-Type"] = "application/json";
      if (token)
        headers.Authorization = `Bearer ${token}`;

      const response = await fetch(url, {
        method,
        headers,
        credentials: "same-origin",
        body: body !== null ? JSON.stringify(body) : undefined,
      });
      const payload = await response.json().catch(() => null);
      if (response.ok)
        return payload?.data || payload || {};
      if (response.status === 404) {
        lastError = new Error("接口不存在");
        continue;
      }
      throw new Error(extractErrorMessage(payload, "请求失败"));
    } catch (error) {
      lastError = error instanceof Error ? error : new Error("请求失败");
    }
  }

  throw lastError || new Error("服务暂时不可用");
};

export const listSupportTickets = ({ token, ...query }) =>
  requestSupport({ method: "GET", query, token });

export const createSupportTicket = ({ token, ...body }) =>
  requestSupport({ method: "POST", body, token });

export const getSupportTicketDetail = (ticketId, token) =>
  requestSupport({ method: "GET", endpointSuffix: `/${ticketId}`, token });

export const replySupportTicket = (ticketId, body, token) =>
  requestSupport({ method: "POST", endpointSuffix: `/${ticketId}/reply`, body, token });

export const updateSupportTicket = (ticketId, body, token) =>
  requestSupport({ method: "PATCH", endpointSuffix: `/${ticketId}`, body, token });
