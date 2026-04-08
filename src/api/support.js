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

    // Separate network-level fetch from response processing so that a real
    // server error is never silently replaced by a fallback-endpoint 404.
    let response;
    try {
      const headers = { Accept: "application/json" };
      if (body !== null)
        headers["Content-Type"] = "application/json";
      if (token)
        headers.Authorization = `Bearer ${token}`;

      response = await fetch(url, {
        method,
        headers,
        credentials: "same-origin",
        body: body !== null ? JSON.stringify(body) : undefined,
      });
    } catch {
      // Network error – backend unreachable. Try the next endpoint.
      if (!lastError)
        lastError = new Error("无法连接到服务器，请确认后端服务已启动");
      continue;
    }

    const payload = await response.json().catch(() => null);
    if (response.ok) {
      // If the body could not be parsed as JSON (e.g. the Vite dev-server
      // served its SPA index.html for an unmatched path), do not return this
      // as a successful response – fall through to the next endpoint.
      if (payload === null) {
        if (!lastError)
          lastError = new Error("接口返回了非 JSON 响应");
        continue;
      }
      return payload?.data || payload || {};
    }

    if (response.status === 404) {
      // Endpoint not found on this host – try the next fallback URL, but do
      // not overwrite a more specific error already recorded.
      if (!lastError)
        lastError = new Error("接口不存在");
      continue;
    }

    // If the error response body is not valid JSON, this is likely a
    // proxy / gateway error (e.g. Vite proxy returning 500 because the
    // backend is unreachable) rather than a real API error.  Fall through
    // to the next endpoint so the fallback chain keeps working.
    if (payload === null) {
      if (!lastError)
        lastError = new Error("请求失败");
      continue;
    }

    // Any other HTTP error with a parseable JSON body means the endpoint
    // exists and returned a real error.  Surface it immediately without
    // trying further endpoints.
    throw new Error(extractErrorMessage(payload, "请求失败"));
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
