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
      title: "Sign In",
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
          title: "Overview",
          permission: "dashboard:view",
          adminOnly: true,
        },
      },
      {
        path: "card-flip-ops",
        name: "CardFlipOps",
        component: () => import("@/views/card-flip-ops/CardFlipOpsPage.vue"),
        meta: {
          title: "Card Trading",
          permission: "cardflip:view",
        },
      },
      {
        path: "matching-lab",
        name: "MatchingLab",
        component: () => import("@/views/MatchingLab.vue"),
        meta: {
          title: "Matching Lab",
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
      title: "Not Found",
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

const CHUNK_RELOAD_GUARD_KEY = "xycardflip:chunk-reload-guard";

function isDynamicImportFailure(error) {
  const text = String(error?.message || error || "").trim();
  if (!text)
    return false;
  return [
    "Failed to fetch dynamically imported module",
    "Importing a module script failed",
    "Loading chunk",
    "Unable to preload CSS",
  ].some(pattern => text.includes(pattern));
}

router.onError((error, to) => {
  if (!isDynamicImportFailure(error))
    return;

  const targetPath = String(
    to?.fullPath
    || `${window.location.pathname || "/"}${window.location.search || ""}${window.location.hash || ""}`,
  ).trim() || "/";
  const guardValue = sessionStorage.getItem(CHUNK_RELOAD_GUARD_KEY);

  if (guardValue === targetPath)
    return;

  sessionStorage.setItem(CHUNK_RELOAD_GUARD_KEY, targetPath);
  window.location.assign(targetPath);
});

router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore();

  document.title = to.meta?.title
    ? `${to.meta.title} - XYZW Card Trading Console`
    : "XYZW Card Trading Console";

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

router.afterEach((to) => {
  const guardValue = sessionStorage.getItem(CHUNK_RELOAD_GUARD_KEY);
  if (guardValue && guardValue === String(to?.fullPath || ""))
    sessionStorage.removeItem(CHUNK_RELOAD_GUARD_KEY);
});

export default router;
