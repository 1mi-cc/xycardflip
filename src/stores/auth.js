import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { useLocalTokenStore } from "./localTokenManager";

const AUTH_ENDPOINTS = {
  login: ["/card-api/auth/login", "/auth/login", "/api/v1/auth/login"],
  register: ["/card-api/auth/register", "/auth/register", "/api/v1/auth/register"],
  logout: ["/card-api/auth/logout", "/auth/logout", "/api/v1/auth/logout"],
  refresh: ["/card-api/auth/refresh", "/auth/refresh", "/api/v1/auth/refresh"],
  userInfo: [
    "/card-api/auth/user",
    "/card-api/auth/userinfo",
    "/card-api/user/profile",
    "/auth/user",
    "/auth/userinfo",
    "/user/profile",
    "/api/v1/auth/user",
    "/api/v1/auth/userinfo",
    "/api/v1/user/profile",
  ],
};

const FALLBACK_ROLE_PERMISSIONS = {
  admin: [
    "dashboard:view",
    "game:feature:view",
    "cardflip:view",
    "task:view",
    "task:batch",
    "message:test",
    "token:view",
    "profile:view",
  ],
  ops: [
    "dashboard:view",
    "cardflip:view",
    "task:view",
    "task:batch",
    "message:test",
    "token:view",
  ],
  viewer: [
    "dashboard:view",
    "cardflip:view",
    "token:view",
    "profile:view",
  ],
};

const toStringArray = (value) => {
  if (!Array.isArray(value))
    return [];
  return value
    .filter(item => typeof item === "string")
    .map(item => item.trim())
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
  if (payload.success !== undefined && payload.data && typeof payload.data === "object")
    return payload.data;
  if (payload.data && typeof payload.data === "object")
    return payload.data;
  return payload;
};

const inferRoleFromUsername = (username) => {
  const lowered = String(username || "").toLowerCase();
  if (lowered.includes("ops"))
    return "ops";
  if (lowered.includes("viewer") || lowered.includes("guest"))
    return "viewer";
  return "admin";
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
    .filter(role => role && typeof role === "object")
    .flatMap(role => toStringArray([role.key, role.name]));

  if (fromRoleObjects.length)
    return uniqueStrings(fromRoleObjects);

  return [];
};

const normalizePermissions = (profile, payload, roleKeys, username) => {
  const permissions = uniqueStrings([
    ...toStringArray(profile?.permissions),
    ...toStringArray(profile?.perms),
    ...toStringArray(payload?.permissions),
    ...toStringArray(payload?.perms),
  ]);

  if (permissions.length)
    return permissions;

  const primaryRole = roleKeys[0] || inferRoleFromUsername(username);
  return FALLBACK_ROLE_PERMISSIONS[primaryRole] || FALLBACK_ROLE_PERMISSIONS.admin;
};

const normalizeUserPayload = (payload) => {
  const data = normalizeApiPayload(payload);
  const profile = data?.user && typeof data.user === "object" ? data.user : data;
  const username = String(profile?.username || data?.username || "operator").trim() || "operator";
  const roleKeys = normalizeRoleKeys(profile, data);
  if (!roleKeys.length) {
    roleKeys.push(inferRoleFromUsername(username));
  }
  const permissions = normalizePermissions(profile, data, roleKeys, username);
  const roles = roleKeys.map(role => ({
    key: role,
    name: role,
    permissions,
    perms: permissions,
  }));

  return {
    ...profile,
    id: profile?.id || `user_${username}`,
    username,
    roleKeys,
    roles,
    permissions,
    perms: permissions,
  };
};

const createFallbackLoginData = (credentials) => {
  const username = String(credentials?.username || "operator").trim() || "operator";
  const role = inferRoleFromUsername(username);
  const permissions = FALLBACK_ROLE_PERMISSIONS[role] || FALLBACK_ROLE_PERMISSIONS.admin;
  const user = {
    id: `local_user_${Date.now()}`,
    username,
    email: credentials?.email || `${username}@local.game`,
    avatar: "/icons/xiaoyugan.png",
    createdAt: new Date().toISOString(),
    roleKeys: [role],
    roles: [{ key: role, name: role, permissions, perms: permissions }],
    permissions,
    perms: permissions,
  };
  const token = `local_token_${username}`;
  return { user, token };
};

const requestAuth = async ({
  method = "GET",
  endpoints = [],
  body = null,
  authToken = "",
}) => {
  for (const endpoint of endpoints) {
    try {
      const headers = { Accept: "application/json" };
      if (body !== null) {
        headers["Content-Type"] = "application/json";
      }
      if (authToken) {
        headers.Authorization = `Bearer ${authToken}`;
      }
      const response = await fetch(endpoint, {
        method,
        headers,
        credentials: "same-origin",
        body: body !== null ? JSON.stringify(body) : undefined,
      });
      if (!response.ok)
        continue;
      const payload = await response.json().catch(() => null);
      if (payload && typeof payload === "object") {
        return payload;
      }
    }
    catch {
      // keep trying next endpoint
    }
  }
  return null;
};

export const useAuthStore = defineStore("auth", () => {
  const user = ref(null);
  const token = ref(localStorage.getItem("token") || null);
  const isLoading = ref(false);

  const localTokenStore = useLocalTokenStore();

  const isAuthenticated = computed(() => !!token.value && !!user.value);
  const userInfo = computed(() => user.value);

  const persistAuthState = () => {
    if (token.value) {
      localStorage.setItem("token", token.value);
      localTokenStore.setUserToken(token.value);
    }
    if (user.value) {
      localStorage.setItem("user", JSON.stringify(user.value));
    }
  };

  const clearPersistedAuthState = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    localStorage.removeItem("gameRoles");
    localTokenStore.clearUserToken();
    localTokenStore.clearAllGameTokens();
  };

  const login = async (credentials) => {
    try {
      isLoading.value = true;

      const remotePayload = await requestAuth({
        method: "POST",
        endpoints: AUTH_ENDPOINTS.login,
        body: {
          username: credentials?.username,
          password: credentials?.password,
          email: credentials?.email,
        },
      });

      if (remotePayload) {
        const normalizedUser = normalizeUserPayload(remotePayload);
        const data = normalizeApiPayload(remotePayload);
        const remoteToken = String(data?.token || `local_token_${normalizedUser.username}`).trim();
        token.value = remoteToken || `local_token_${normalizedUser.username}`;
        user.value = normalizedUser;
        persistAuthState();
        return { success: true };
      }

      const fallback = createFallbackLoginData(credentials);
      token.value = fallback.token;
      user.value = fallback.user;
      persistAuthState();
      return { success: true };
    }
    catch (error) {
      console.error("登录错误:", error);
      return { success: false, message: "登录失败" };
    }
    finally {
      isLoading.value = false;
    }
  };

  const register = async (userInfoData) => {
    try {
      isLoading.value = true;

      const remotePayload = await requestAuth({
        method: "POST",
        endpoints: AUTH_ENDPOINTS.register,
        body: userInfoData || {},
      });
      if (remotePayload) {
        return { success: true, message: "注册成功，请登录" };
      }

      const existingUsers = JSON.parse(localStorage.getItem("registeredUsers") || "[]");
      const userExists = existingUsers.some(u => u.username === userInfoData.username);
      if (userExists) {
        return { success: false, message: "用户名已存在" };
      }
      const newUser = {
        ...userInfoData,
        id: `user_${Date.now()}`,
        createdAt: new Date().toISOString(),
      };
      existingUsers.push(newUser);
      localStorage.setItem("registeredUsers", JSON.stringify(existingUsers));
      return { success: true, message: "注册成功，请登录" };
    }
    catch (error) {
      console.error("注册错误:", error);
      return { success: false, message: "注册失败" };
    }
    finally {
      isLoading.value = false;
    }
  };

  const logout = () => {
    const tokenSnapshot = token.value;
    void requestAuth({
      method: "POST",
      endpoints: AUTH_ENDPOINTS.logout,
      authToken: tokenSnapshot || "",
    });

    user.value = null;
    token.value = null;
    clearPersistedAuthState();
  };

  const fetchUserInfo = async () => {
    try {
      if (!token.value)
        return false;

      const remotePayload = await requestAuth({
        method: "GET",
        endpoints: AUTH_ENDPOINTS.userInfo,
        authToken: token.value,
      });

      if (remotePayload) {
        user.value = normalizeUserPayload(remotePayload);
        persistAuthState();
        return true;
      }

      const savedUser = localStorage.getItem("user");
      if (!savedUser) {
        logout();
        return false;
      }
      user.value = normalizeUserPayload(JSON.parse(savedUser));
      persistAuthState();
      return true;
    }
    catch (error) {
      console.error("获取用户信息失败:", error);
      logout();
      return false;
    }
  };

  const initAuth = async () => {
    if (!token.value)
      return;

    const ok = await fetchUserInfo();
    if (ok) {
      localTokenStore.initTokenManager();
    }
  };

  const refreshToken = async () => {
    if (!token.value)
      return false;
    const remotePayload = await requestAuth({
      method: "POST",
      endpoints: AUTH_ENDPOINTS.refresh,
      authToken: token.value,
    });
    if (!remotePayload)
      return false;
    const data = normalizeApiPayload(remotePayload);
    const nextToken = String(data?.token || "").trim();
    if (nextToken) {
      token.value = nextToken;
    }
    user.value = normalizeUserPayload(remotePayload);
    persistAuthState();
    return true;
  };

  return {
    user,
    token,
    isLoading,
    isAuthenticated,
    userInfo,
    login,
    register,
    logout,
    fetchUserInfo,
    initAuth,
    refreshToken,
  };
});
