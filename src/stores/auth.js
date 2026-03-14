import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { useLocalTokenStore } from "./localTokenManager";

const AUTH_ENDPOINTS = {
  login: ["/card-api/auth/login", "/auth/login"],
  register: ["/card-api/auth/register", "/auth/register"],
  logout: ["/card-api/auth/logout", "/auth/logout"],
  refresh: ["/card-api/auth/refresh", "/auth/refresh"],
  userInfo: [
    "/card-api/auth/user",
    "/card-api/auth/userinfo",
    "/card-api/user/profile",
    "/auth/user",
    "/auth/userinfo",
    "/user/profile",
  ],
};

const toStringArray = (value) => {
  if (!Array.isArray(value))
    return [];
  return value
    .filter((item) => typeof item === "string")
    .map((item) => item.trim())
    .filter(Boolean);
};

const uniqueStrings = (items) => {
  const normalized = [];
  const seen = new Set();
  for (const item of items) {
    const text = String(item || "").trim();
    if (!text)
      continue;
    const lowered = text.toLowerCase();
    if (seen.has(lowered))
      continue;
    seen.add(lowered);
    normalized.push(text);
  }
  return normalized;
};

const normalizeApiPayload = (payload) => {
  if (!payload || typeof payload !== "object")
    return {};
  if (payload.data && typeof payload.data === "object")
    return payload.data;
  return payload;
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
  if (payload.error && typeof payload.error === "string")
    return payload.error;
  return fallback;
};

const normalizeRoleKeys = (profile, payload) => {
  const roleKeys = [
    ...toStringArray(profile?.roleKeys),
    ...toStringArray(payload?.roleKeys),
  ];
  if (roleKeys.length)
    return uniqueStrings(roleKeys);

  const roleObjects = [
    ...(Array.isArray(profile?.roles) ? profile.roles : []),
    ...(Array.isArray(payload?.roles) ? payload.roles : []),
  ];
  const fromRoleObjects = roleObjects
    .filter((role) => role && typeof role === "object")
    .flatMap((role) => toStringArray([role.key, role.name]));

  return uniqueStrings(fromRoleObjects);
};

const normalizeUserPayload = (payload) => {
  const data = normalizeApiPayload(payload);
  const profile = data?.user && typeof data.user === "object" ? data.user : data;
  const username = String(profile?.username || "user").trim() || "user";
  const roleKeys = normalizeRoleKeys(profile, data);
  const permissions = uniqueStrings([
    ...toStringArray(profile?.permissions),
    ...toStringArray(profile?.perms),
    ...toStringArray(data?.permissions),
    ...toStringArray(data?.perms),
  ]);
  const roles = Array.isArray(profile?.roles) && profile.roles.length
    ? profile.roles
    : roleKeys.map((role) => ({
        key: role,
        name: role,
        permissions,
        perms: permissions,
      }));

  return {
    ...profile,
    id: profile?.id || `user_${username}`,
    username,
    nickname: profile?.nickname || username,
    roleKeys,
    permissions,
    perms: permissions,
    roles,
    isAdmin: Boolean(profile?.isAdmin) || roleKeys.includes("admin"),
  };
};

const requestAuth = async ({
  method = "GET",
  endpoints = [],
  body = null,
  authToken = "",
}) => {
  let lastError = null;

  for (const endpoint of endpoints) {
    // Separate the network-level fetch from response processing so that a
    // real server error (e.g. 401 "用户名或密码错误") is never silently
    // replaced by a 404 returned from a fallback endpoint.
    let response;
    try {
      const headers = { Accept: "application/json" };
      if (body !== null)
        headers["Content-Type"] = "application/json";
      if (authToken)
        headers.Authorization = `Bearer ${authToken}`;

      response = await fetch(endpoint, {
        method,
        headers,
        credentials: "same-origin",
        body: body !== null ? JSON.stringify(body) : undefined,
      });
    } catch {
      // Network error – backend unreachable. Only record if no earlier real
      // error has been captured, then try the next endpoint.
      if (!lastError)
        lastError = new Error("无法连接到服务器，请确认后端服务已启动");
      continue;
    }

    const payload = await response.json().catch(() => null);
    if (response.ok) {
      // If the body could not be parsed as JSON (e.g. the Vite dev-server
      // served its SPA index.html for an unmatched path), do not treat this
      // as a successful auth response – fall through to the next endpoint.
      if (payload === null) {
        if (!lastError)
          lastError = new Error("接口返回了非 JSON 响应");
        continue;
      }
      return payload;
    }

    if (response.status === 404) {
      // Endpoint not found on this host – try the next fallback URL, but
      // do not overwrite a more specific error already recorded.
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

export const useAuthStore = defineStore("auth", () => {
  const user = ref(null);
  const token = ref(localStorage.getItem("token") || "");
  const isLoading = ref(false);
  const initialized = ref(false);

  const localTokenStore = useLocalTokenStore();

  const isAuthenticated = computed(() => Boolean(token.value && user.value));
  const userInfo = computed(() => user.value);

  const permissions = computed(() => {
    const info = user.value || {};
    return uniqueStrings([
      ...toStringArray(info?.permissions),
      ...toStringArray(info?.perms),
    ]);
  });

  const hasPermission = (permission) => {
    if (!permission)
      return true;
    return permissions.value.includes(permission);
  };

  const getDefaultHomeRoute = () => {
    if (hasPermission("support:ticket:manage"))
      return "/admin/dashboard";
    if (hasPermission("support:ticket:view"))
      return "/support/tickets";
    return "/login";
  };

  const persistAuthState = () => {
    if (token.value)
      localStorage.setItem("token", token.value);
    else
      localStorage.removeItem("token");

    if (user.value)
      localStorage.setItem("user", JSON.stringify(user.value));
    else
      localStorage.removeItem("user");
  };

  const clearPersistedAuthState = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    localStorage.removeItem("gameRoles");
    localTokenStore.clearUserToken();
    localTokenStore.clearAllGameTokens();
  };

  const applyAuthPayload = (payload, fallbackToken = "") => {
    const normalizedUser = normalizeUserPayload(payload);
    const data = normalizeApiPayload(payload);
    const nextToken = String(data?.token || fallbackToken || token.value || "").trim();

    user.value = normalizedUser;
    token.value = nextToken;
    if (nextToken)
      localTokenStore.setUserToken(nextToken);
    persistAuthState();
  };

  const login = async (credentials) => {
    try {
      isLoading.value = true;
      const payload = await requestAuth({
        method: "POST",
        endpoints: AUTH_ENDPOINTS.login,
        body: {
          username: credentials?.username,
          password: credentials?.password,
        },
      });
      applyAuthPayload(payload);
      initialized.value = true;
      return { success: true };
    } catch (error) {
      return {
        success: false,
        message: error instanceof Error ? error.message : "登录失败",
      };
    } finally {
      isLoading.value = false;
    }
  };

  const register = async (userInfoData) => {
    try {
      isLoading.value = true;
      await requestAuth({
        method: "POST",
        endpoints: AUTH_ENDPOINTS.register,
        body: userInfoData || {},
      });
      return { success: true, message: "注册成功，请登录" };
    } catch (error) {
      return {
        success: false,
        message: error instanceof Error ? error.message : "注册失败",
      };
    } finally {
      isLoading.value = false;
    }
  };

  const logout = async () => {
    const tokenSnapshot = token.value;
    try {
      if (tokenSnapshot) {
        await requestAuth({
          method: "POST",
          endpoints: AUTH_ENDPOINTS.logout,
          authToken: tokenSnapshot,
        });
      }
    } catch {
      // ignore logout transport errors
    }
    user.value = null;
    token.value = "";
    initialized.value = true;
    clearPersistedAuthState();
  };

  const fetchUserInfo = async () => {
    if (!token.value) {
      user.value = null;
      initialized.value = true;
      return false;
    }
    try {
      const payload = await requestAuth({
        method: "GET",
        endpoints: AUTH_ENDPOINTS.userInfo,
        authToken: token.value,
      });
      applyAuthPayload(payload, token.value);
      initialized.value = true;
      return true;
    } catch {
      user.value = null;
      token.value = "";
      clearPersistedAuthState();
      initialized.value = true;
      return false;
    }
  };

  const initAuth = async () => {
    if (initialized.value)
      return isAuthenticated.value;

    const savedUser = localStorage.getItem("user");
    if (savedUser && !user.value) {
      try {
        user.value = normalizeUserPayload(JSON.parse(savedUser));
      } catch {
        user.value = null;
      }
    }

    if (!token.value) {
      initialized.value = true;
      return false;
    }

    return fetchUserInfo();
  };

  const refreshToken = async () => {
    if (!token.value)
      return false;
    try {
      const payload = await requestAuth({
        method: "POST",
        endpoints: AUTH_ENDPOINTS.refresh,
        authToken: token.value,
      });
      applyAuthPayload(payload, token.value);
      return true;
    } catch {
      return false;
    }
  };

  return {
    user,
    token,
    isLoading,
    initialized,
    isAuthenticated,
    userInfo,
    permissions,
    hasPermission,
    getDefaultHomeRoute,
    login,
    register,
    logout,
    fetchUserInfo,
    initAuth,
    refreshToken,
  };
});
