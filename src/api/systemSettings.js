const SETUP_ENDPOINTS = {
  status: ["/card-api/setup/status", "/setup/status"],
  apply: ["/card-api/setup/apply", "/setup/apply"],
  audit: ["/card-api/setup/audit", "/setup/audit"],
};

const extractSetupError = (payload, fallback = "Setup request failed") => {
  if (!payload)
    return fallback;
  if (typeof payload === "string")
    return payload;
  if (typeof payload.detail === "string" && payload.detail.trim())
    return payload.detail.trim();
  if (typeof payload.message === "string" && payload.message.trim())
    return payload.message.trim();
  return fallback;
};

const requestSetup = async ({
  method = "GET",
  endpoints = [],
  body = null,
  authToken = "",
}) => {
  let lastError = null;
  for (const endpoint of endpoints) {
    try {
      const response = await fetch(endpoint, {
        method,
        headers: {
          Accept: "application/json",
          ...(body !== null ? { "Content-Type": "application/json" } : {}),
          ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        },
        credentials: "same-origin",
        body: body !== null ? JSON.stringify(body) : undefined,
      });
      const payload = await response.json().catch(() => null);
      if (response.ok)
        return payload;
      if (response.status === 404) {
        lastError = new Error("Setup endpoint not found");
        continue;
      }
      throw new Error(extractSetupError(payload));
    } catch (error) {
      lastError = error instanceof Error ? error : new Error("Setup request failed");
    }
  }
  throw lastError || new Error("Setup request failed");
};

const systemSettingsApi = {
  getStatus(authToken = "") {
    return requestSetup({
      method: "GET",
      endpoints: SETUP_ENDPOINTS.status,
      authToken,
    });
  },
  listAudit(limit = 50, authToken = "") {
    return requestSetup({
      method: "GET",
      endpoints: SETUP_ENDPOINTS.audit.map((endpoint) => `${endpoint}?limit=${limit}`),
      authToken,
    });
  },
  rollbackAudit(auditId, authToken = "") {
    return requestSetup({
      method: "POST",
      endpoints: SETUP_ENDPOINTS.audit.map((endpoint) => `${endpoint}/${auditId}/rollback`),
      authToken,
    });
  },
  testGemini(authToken = "") {
    return requestSetup({
      method: "GET",
      endpoints: ["/card-api/setup/test-gemini", "/setup/test-gemini"],
      authToken,
    });
  },
  apply(payload, authToken = "") {
    return requestSetup({
      method: "POST",
      endpoints: SETUP_ENDPOINTS.apply,
      body: payload,
      authToken,
    });
  },
};

export default systemSettingsApi;
