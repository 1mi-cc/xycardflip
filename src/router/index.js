import { createRouter, createWebHistory } from "vue-router";
import * as autoRoutes from "vue-router/auto-routes";

import { useAuthStore } from "@/stores/auth";
import { useTokenStore } from "@/stores/tokenStore";

const generatedRoutes = autoRoutes.routes ?? [];

const myRoutes = [
  {
    path: "/",
    redirect: "/login",
  },
  {
    path: "/login",
    name: "Login",
    component: () => import("@/views/Login.vue"),
    meta: {
      title: "登录",
      guestOnly: true,
    },
  },
  {
    path: "/register",
    name: "Register",
    component: () => import("@/views/Register.vue"),
    meta: {
      title: "注册",
      guestOnly: true,
    },
  },
  {
    path: "/support/tickets",
    name: "SupportTicketsPortal",
    component: () => import("@/views/SupportTickets.vue"),
    meta: {
      title: "工单中心",
      requiresAuth: true,
      permission: "support:ticket:view",
    },
  },
  {
    path: "/tokens",
    name: "TokenImport",
    component: () => import("@/views/TokenImport/index.vue"),
    meta: {
      title: "Token 管理",
      requiresAuth: true,
      permission: "token:view",
    },
    props: (route) => ({
      importToken: route.query.token,
      name: route.query.name,
      server: route.query.server,
      wsUrl: route.query.wsUrl,
      api: route.query.api,
      auto: route.query.auto === "true",
    }),
  },
  {
    name: "DefaultLayout",
    path: "/admin",
    component: () => import("@/layout/DefaultLayout.vue"),
    meta: {
      requiresAuth: true,
    },
    children: [
      {
        path: "dashboard",
        name: "Dashboard",
        component: () => import("@/views/Dashboard.vue"),
        meta: {
          title: "控制台",
          permission: "dashboard:view",
        },
      },
      {
        path: "game-features",
        name: "GameFeatures",
        component: () => import("@/views/GameFeatures.vue"),
        meta: {
          title: "游戏功能",
          permission: "game:feature:view",
          requiresToken: true,
        },
      },
      {
        path: "card-flip-ops",
        name: "CardFlipOps",
        component: () => import("@/views/card-flip-ops/CardFlipOpsPage.vue"),
        meta: {
          title: "卡片倒卖 · 操作台",
          permission: "cardflip:view",
        },
      },
      {
        path: "card-flip",
        redirect: "/admin/card-flip/sim",
      },
      {
        path: "card-flip/sim",
        name: "CardFlipSimulation",
        component: () => import("@/views/CardFlipModeDashboard.vue"),
        props: { mode: "simulation" },
        meta: {
          title: "卡片倒卖 · 模拟盘",
          permission: "cardflip:view",
        },
      },
      {
        path: "card-flip/live",
        name: "CardFlipLive",
        component: () => import("@/views/CardFlipModeDashboard.vue"),
        props: { mode: "live" },
        meta: {
          title: "卡片倒卖 · 实战盘",
          permission: "cardflip:view",
        },
      },
      {
        path: "card-flip/docs",
        name: "CardFlipDocs",
        component: () => import("@/views/card-flip-ops/CardFlipDocsPage.vue"),
        meta: {
          title: "卡片倒卖 · 使用文档",
          permission: "cardflip:view",
        },
      },
      {
        path: "support-tickets",
        name: "SupportTicketsAdmin",
        component: () => import("@/views/SupportTickets.vue"),
        meta: {
          title: "工单处理台",
          permission: "support:ticket:manage",
        },
      },
      {
        path: "message-test",
        name: "MessageTest",
        component: () => import("@/components/Test/MessageTester.vue"),
        meta: {
          title: "消息测试",
          permission: "message:test",
        },
      },
      {
        path: "profile",
        name: "Profile",
        component: () => import("@/views/Profile.vue"),
        meta: {
          title: "个人设置",
          permission: "profile:view",
        },
      },
      {
        path: "daily-tasks",
        name: "DailyTasks",
        component: () => import("@/views/DailyTasks.vue"),
        meta: {
          title: "日常任务",
          permission: "task:view",
          requiresToken: true,
        },
      },
      {
        path: "batch-daily-tasks",
        name: "BatchDailyTasks",
        component: () => import("@/views/BatchDailyTasks.vue"),
        meta: {
          title: "批量日常",
          permission: "task:batch",
          requiresToken: true,
        },
      },
    ],
  },
  {
    path: "/websocket-test",
    name: "WebSocketTest",
    component: () => import("@/components/Test/WebSocketTester.vue"),
    meta: {
      title: "WebSocket 测试",
      requiresAuth: true,
      permission: "message:test",
      requiresToken: true,
    },
  },
  ...generatedRoutes,
  {
    path: "/:pathMatch(.*)*",
    name: "NotFound",
    component: () => import("@/views/NotFound.vue"),
    meta: {
      title: "页面不存在",
    },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes: myRoutes,
  scrollBehavior(to, _from, savedPosition) {
    if (savedPosition)
      return savedPosition;
    return { top: 0 };
  },
});

router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore();
  const tokenStore = useTokenStore();

  document.title = to.meta.title
    ? `${to.meta.title} - XYZW 游戏管理系统`
    : "XYZW 游戏管理系统";

  if (!authStore.initialized) {
    await authStore.initAuth();
  }

  if (to.meta.guestOnly && authStore.isAuthenticated) {
    next(authStore.getDefaultHomeRoute());
    return;
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next({
      path: "/login",
      query: to.fullPath && to.fullPath !== "/login" ? { redirect: to.fullPath } : undefined,
    });
    return;
  }

  const requiredPermission = to.meta.permission;
  if (requiredPermission && authStore.isAuthenticated && !authStore.hasPermission(requiredPermission)) {
    next(authStore.getDefaultHomeRoute());
    return;
  }

  if (to.meta.requiresToken && !tokenStore.hasTokens) {
    next("/tokens");
    return;
  }

  next();
});

export default router;
