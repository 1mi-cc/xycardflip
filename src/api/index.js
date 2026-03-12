import axios from "axios";

import { useAuthStore } from "@/stores/auth";

// 创建axios实例
const request = axios.create({
  baseURL: "/api/v1",
  timeout: 10000,
  proxy: false,
  headers: {
    "Content-Type": "application/json",
  },
});

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    const authStore = useAuthStore();
    if (authStore.token) {
      config.headers.Authorization = `Bearer ${authStore.token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

// 响应拦截器
request.interceptors.response.use(
  (response) => {
    const data = response.data;

    // 统一处理响应格式
    if (data.success !== undefined) {
      return data;
    }

    // 兼容不同的响应格式
    return {
      success: true,
      data,
      message: "success",
    };
  },
  (error) => {
    const authStore = useAuthStore();

    // 处理HTTP错误
    if (error.response) {
      const { status, data } = error.response;

      const makeError = (message) => {
        const err = new Error(message);
        err.success = false;
        return err;
      };

      switch (status) {
        case 401:
          // 未授权，清除登录状态
          authStore.logout();
          window.location.href = "/login";
          return Promise.reject(makeError("登录已过期，请重新登录"));
        case 403:
          return Promise.reject(makeError("没有权限访问"));
        case 404:
          return Promise.reject(makeError("请求的资源不存在"));
        case 500:
          return Promise.reject(makeError("服务器内部错误"));
        default:
          return Promise.reject(makeError(data?.message || "请求失败"));
      }
    } else if (error.request) {
      // 网络错误
      const networkErr = new Error("网络连接失败，请检查网络");
      networkErr.success = false;
      return Promise.reject(networkErr);
    } else {
      // 其他错误
      const unknownErr = new Error(error.message || "未知错误");
      unknownErr.success = false;
      return Promise.reject(unknownErr);
    }
  },
);

// API接口定义
const api = {
  // 认证相关
  auth: {
    login: (credentials) => request.post("/auth/login", credentials),
    register: (userInfo) => request.post("/auth/register", userInfo),
    logout: () => request.post("/auth/logout"),
    getUserInfo: () => request.get("/auth/user"),
    refreshToken: () => request.post("/auth/refresh"),
  },

  // 游戏角色相关
  gameRoles: {
    getList: () => request.get("/gamerole_list"),
    add: (roleData) => request.post("/gameroles", roleData),
    update: (roleId, roleData) => request.put(`/gameroles/${roleId}`, roleData),
    delete: (roleId) => request.delete(`/gameroles/${roleId}`),
    getDetail: (roleId) => request.get(`/gameroles/${roleId}`),
  },

  // 日常任务相关
  dailyTasks: {
    getList: (roleId) => request.get(`/daily-tasks?roleId=${roleId}`),
    getStatus: (roleId) => request.get(`/daily-tasks/status?roleId=${roleId}`),
    complete: (taskId, roleId) =>
      request.post(`/daily-tasks/${taskId}/complete`, { roleId }),
    getHistory: (roleId, page = 1, limit = 20) =>
      request.get(
        `/daily-tasks/history?roleId=${roleId}&page=${page}&limit=${limit}`,
      ),
  },

  // 用户相关
  user: {
    getProfile: () => request.get("/user/profile"),
    updateProfile: (profileData) => request.put("/user/profile", profileData),
    changePassword: (passwordData) =>
      request.put("/user/password", passwordData),
    getStats: () => request.get("/user/stats"),
  },
};

export default api;
