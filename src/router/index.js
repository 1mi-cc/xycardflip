import { createRouter, createWebHistory } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const routes = [
  {
    path: "/",
    redirect: "/admin/dashboard",
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
    path: "/admin",
    name: "AdminLayout",
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
          title: "总览",
          permission: "dashboard:view",
          adminOnly: true,
        },
      },
      {
        path: "card-flip-ops",
        name: "CardFlipOps",
        component: () => import("@/views/card-flip-ops/CardFlipOpsPage.vue"),
        meta: {
          title: "卡片交易",
          permission: "cardflip:view",
        },
      },
    ],
  },
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
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition)
      return savedPosition;
    return { top: 0 };
  },
});

router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore();

  document.title = to.meta?.title
    ? `${to.meta.title} - XYZW 卡片倒卖后台`
    : "XYZW 卡片倒卖后台";

  if (!authStore.initialized)
    await authStore.initAuth();

  if (to.meta.guestOnly && authStore.isAuthenticated) {
    next(authStore.getDefaultHomeRoute());
    return;
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next({
      path: "/login",
      query: to.fullPath !== "/login" ? { redirect: to.fullPath } : undefined,
    });
    return;
  }

  const requiredPermission = to.meta?.permission;
  if (requiredPermission && authStore.isAuthenticated && !authStore.hasPermission(requiredPermission)) {
    next(authStore.getDefaultHomeRoute());
    return;
  }

  if (to.meta?.adminOnly && authStore.isAuthenticated && !authStore.userInfo?.isAdmin) {
    next(authStore.getDefaultHomeRoute());
    return;
  }

  next();
});

export default router;
