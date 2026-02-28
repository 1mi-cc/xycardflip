import { createRouter, createWebHistory } from "vue-router";
import * as autoRoutes from "vue-router/auto-routes";
import { useTokenStore } from "@/stores/tokenStore";

const generatedRoutes = autoRoutes.routes ?? [];

const myRoutes = [
  {
    path: "/",
    name: "Home",
    component: () => import("@/views/Home.vue"),
    meta: {
      title: "首页",
      requiresToken: false,
    },
  },
  {
    path: "/tokens",
    name: "TokenImport",
    component: () => import("@/views/TokenImport/index.vue"),
    meta: {
      title: "Token 管理",
      requiresToken: false,
    },
    props: (route) => ({
      token: route.query.token,
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
    children: [
      {
        path: "dashboard",
        name: "Dashboard",
        component: () => import("@/views/Dashboard.vue"),
        meta: {
          title: "控制台",
          requiresToken: true,
        },
      },
      {
        path: "game-features",
        name: "GameFeatures",
        component: () => import("@/views/GameFeatures.vue"),
        meta: {
          title: "游戏功能",
          requiresToken: true,
        },
      },
      {
        path: "card-flip-ops",
        name: "CardFlipOps",
        component: () => import("@/views/CardFlipOps.vue"),
        meta: {
          title: "卡片倒卖助手",
          requiresToken: true,
        },
      },
      {
        path: "message-test",
        name: "MessageTest",
        component: () => import("@/components/Test/MessageTester.vue"),
        meta: {
          title: "消息测试",
          requiresToken: true,
        },
      },
      {
        path: "profile",
        name: "Profile",
        component: () => import("@/views/Profile.vue"),
        meta: {
          title: "个人设置",
          requiresToken: true,
        },
      },
      {
        path: "daily-tasks",
        name: "DailyTasks",
        component: () => import("@/views/DailyTasks.vue"),
        meta: {
          title: "日常任务",
          requiresToken: true,
        },
      },
      {
        path: "batch-daily-tasks",
        name: "BatchDailyTasks",
        component: () => import("@/views/BatchDailyTasks.vue"),
        meta: {
          title: "批量日常",
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
      requiresToken: true,
    },
  },
  {
    path: "/login",
    redirect: "/tokens",
  },
  {
    path: "/register",
    redirect: "/tokens",
  },
  {
    path: "/game-roles",
    redirect: "/tokens",
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
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition)
      return savedPosition;
    return { top: 0 };
  },
});

router.beforeEach((to, from, next) => {
  const tokenStore = useTokenStore();

  document.title = to.meta.title
    ? `${to.meta.title} - XYZW 游戏管理系统`
    : "XYZW 游戏管理系统";

  if (to.meta.requiresToken && !tokenStore.hasTokens) {
    next("/tokens");
  } else if (to.path === "/" && tokenStore.hasTokens) {
    if (tokenStore.selectedToken)
      next("/admin/dashboard");
    else
      next("/tokens");
  } else {
    next();
  }
});

export default router;
