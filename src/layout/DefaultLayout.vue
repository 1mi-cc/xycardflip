<template>
  <div class="admin-shell" :class="{ collapsed: isSidebarCollapsed }">
    <aside class="sidebar">
      <div class="logo-wrap">
        <img alt="XYZW" class="brand-logo" src="/icons/xiaoyugan.png">
        <div v-if="!isSidebarCollapsed" class="brand-copy">
          <div class="brand-title">XYZW 数据台</div>
          <div class="brand-subtitle">只看结果，不看参数</div>
        </div>
      </div>

      <n-scrollbar class="menu-scroll">
        <template v-if="isSidebarCollapsed">
          <router-link
            v-for="item in flatNavItems"
            :key="item.path"
            active-class="active"
            class="nav-link nav-link-collapsed"
            :to="item.path"
          >
            <n-tooltip placement="right" trigger="hover">
              <template #trigger>
                <n-icon class="nav-icon">
                  <component :is="item.icon"></component>
                </n-icon>
              </template>
              {{ item.label }}
            </n-tooltip>
          </router-link>
        </template>

        <template v-else>
          <section v-for="group in navGroups" :key="group.key" class="nav-group">
            <button class="group-header" @click="toggleGroup(group.key)">
              <div class="group-label">
                <n-icon class="nav-icon">
                  <component :is="group.icon"></component>
                </n-icon>
                <span>{{ group.label }}</span>
              </div>
              <n-icon class="group-arrow" :class="{ open: isGroupExpanded(group.key) }">
                <ChevronDown></ChevronDown>
              </n-icon>
            </button>

            <div v-show="isGroupExpanded(group.key)" class="group-body">
              <router-link
                v-for="item in group.children"
                :key="item.path"
                active-class="active"
                class="nav-link"
                :to="item.path"
              >
                <n-icon class="nav-icon">
                  <component :is="item.icon"></component>
                </n-icon>
                <span>{{ item.label }}</span>
              </router-link>
            </div>
          </section>
        </template>
      </n-scrollbar>
    </aside>

    <div class="main-shell">
      <header class="topbar">
        <div class="topbar-left">
          <button class="icon-btn mobile-only" type="button" @click="isMobileMenuOpen = true">
            <n-icon><Menu></Menu></n-icon>
          </button>
          <button class="icon-btn desktop-only" type="button" @click="toggleSidebar">
            <n-icon><Menu></Menu></n-icon>
          </button>
          <div class="page-heading">
            <div class="page-title">{{ currentPageTitle }}</div>
            <div class="page-subtitle">{{ currentPageSubtitle }}</div>
          </div>
        </div>

        <div class="topbar-right">
          <n-tag size="small" type="info" round>{{ currentRoleLabel }}</n-tag>
          <ThemeToggle></ThemeToggle>
          <n-dropdown :options="userMenuOptions" @select="handleUserAction">
            <button class="user-chip" type="button">
              <n-avatar fallback-src="/icons/xiaoyugan.png" size="small" src=""></n-avatar>
              <span>{{ authDisplayName }}</span>
              <n-icon><ChevronDown></ChevronDown></n-icon>
            </button>
          </n-dropdown>
        </div>
      </header>

      <div class="breadcrumb-bar">
        <n-breadcrumb>
          <n-breadcrumb-item v-for="crumb in breadcrumbItems" :key="crumb.path">
            <span class="crumb-link" @click="goTo(crumb.path)">{{ crumb.title }}</span>
          </n-breadcrumb-item>
        </n-breadcrumb>
      </div>

      <main class="page-container">
        <router-view :key="route.fullPath"></router-view>
      </main>
    </div>

    <n-drawer
      class="mobile-drawer"
      placement="left"
      v-model:show="isMobileMenuOpen"
      :width="280"
    >
      <div class="drawer-shell">
        <div v-for="group in navGroups" :key="`drawer-${group.key}`" class="drawer-group">
          <div class="drawer-group-title">{{ group.label }}</div>
          <router-link
            v-for="item in group.children"
            :key="item.path"
            active-class="active"
            class="drawer-link"
            :to="item.path"
            @click="isMobileMenuOpen = false"
          >
            <n-icon class="nav-icon">
              <component :is="item.icon"></component>
            </n-icon>
            <span>{{ item.label }}</span>
          </router-link>
        </div>
      </div>
    </n-drawer>
  </div>
</template>

<script setup>
import {
  ChatbubbleEllipsesSharp,
  ChevronDown,
  Cube,
  Home,
  Menu,
  PersonCircle,
  TrendingUp,
} from "@vicons/ionicons5";
import { useMessage } from "naive-ui";
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import ThemeToggle from "@/components/Common/ThemeToggle.vue";
import { useAuthStore } from "@/stores/auth";
import { selectedToken } from "@/stores/tokenStore";

const SIDEBAR_COLLAPSE_KEY = "xyzw_layout_sidebar_collapsed_apple_v1";
const SIDEBAR_GROUPS_KEY = "xyzw_layout_sidebar_groups_apple_v1";
const LAYOUT_PERMISSION_KEY = "xyzw_layout_permissions_apple_v1";
const REMOTE_PERMISSION_ENDPOINTS = [
  "/card-api/auth/user",
  "/card-api/auth/userinfo",
  "/card-api/user/profile",
  "/auth/user",
  "/auth/userinfo",
  "/user/profile",
];

const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();
const message = useMessage();

const isMobileMenuOpen = ref(false);
const isSidebarCollapsed = ref(false);
const expandedGroupKeys = ref([]);
const userPermissions = ref([]);
const permissionFetchInFlight = ref(false);

const navDefinitions = [
  {
    key: "overview",
    label: "总览",
    icon: Home,
    items: [
      { label: "控制台", path: "/admin/dashboard", icon: Home, permission: "dashboard:view", adminOnly: true },
      { label: "数据台", path: "/admin/card-flip-ops", icon: Cube, permission: "cardflip:view" },
    ],
  },
  {
    key: "cardflip",
    label: "卡片倒卖",
    icon: TrendingUp,
    items: [
      { label: "模拟盘", path: "/admin/card-flip/sim", icon: TrendingUp, permission: "cardflip:view" },
      { label: "实战盘", path: "/admin/card-flip/live", icon: TrendingUp, permission: "cardflip:view" },
      { label: "使用文档", path: "/admin/card-flip/docs", icon: ChatbubbleEllipsesSharp, permission: "cardflip:view" },
    ],
  },
  {
    key: "account",
    label: "账户",
    icon: PersonCircle,
    items: [
      { label: "账号管理", path: "/tokens", icon: PersonCircle, permission: "token:view" },
      { label: "个人设置", path: "/admin/profile", icon: PersonCircle, permission: "profile:view" },
    ],
  },
];

const userMenuOptions = [
  { label: "个人设置", key: "profile" },
  { label: "系统设置", key: "settings" },
  { type: "divider" },
  { label: "退出登录", key: "logout" },
];

const toStringArray = (value) => {
  if (!Array.isArray(value))
    return [];
  return value
    .filter(item => typeof item === "string")
    .map(item => item.trim())
    .filter(Boolean);
};

const normalizeRemotePayload = (payload) => {
  if (!payload || typeof payload !== "object")
    return {};
  if (payload.success !== undefined && payload.data && typeof payload.data === "object")
    return payload.data;
  if (payload.data && typeof payload.data === "object")
    return payload.data;
  return payload;
};

const extractPermissionsFromPayload = (payload) => {
  const normalized = normalizeRemotePayload(payload);
  const direct = [
    ...toStringArray(normalized.permissions),
    ...toStringArray(normalized.perms),
  ];
  if (direct.length)
    return [...new Set(direct)];

  if (Array.isArray(normalized.roles)) {
    const rolePerms = normalized.roles.flatMap((role) => {
      if (!role || typeof role !== "object")
        return [];
      return [
        ...toStringArray(role.permissions),
        ...toStringArray(role.perms),
      ];
    });
    if (rolePerms.length)
      return [...new Set(rolePerms)];
  }

  if (normalized.user && typeof normalized.user === "object") {
    const userDirect = [
      ...toStringArray(normalized.user.permissions),
      ...toStringArray(normalized.user.perms),
    ];
    if (userDirect.length)
      return [...new Set(userDirect)];
  }

  return [];
};

const fetchRemotePermissions = async () => {
  if (permissionFetchInFlight.value || !authStore.token)
    return [];
  permissionFetchInFlight.value = true;
  try {
    for (const endpoint of REMOTE_PERMISSION_ENDPOINTS) {
      try {
        const response = await fetch(endpoint, {
          method: "GET",
          headers: {
            Accept: "application/json",
            Authorization: `Bearer ${authStore.token}`,
          },
          credentials: "same-origin",
        });
        if (!response.ok)
          continue;
        const payload = await response.json().catch(() => null);
        const perms = extractPermissionsFromPayload(payload);
        if (perms.length)
          return perms;
      } catch {
        // ignore
      }
    }
  } finally {
    permissionFetchInFlight.value = false;
  }
  return [];
};

const syncLayoutPermissions = async () => {
  const fromAuth = extractPermissionsFromPayload(authStore.userInfo || {});
  if (fromAuth.length) {
    userPermissions.value = fromAuth;
    localStorage.setItem(LAYOUT_PERMISSION_KEY, JSON.stringify(fromAuth));
    return;
  }

  const fromRemote = await fetchRemotePermissions();
  if (fromRemote.length) {
    userPermissions.value = fromRemote;
    localStorage.setItem(LAYOUT_PERMISSION_KEY, JSON.stringify(fromRemote));
    return;
  }

  try {
    const saved = localStorage.getItem(LAYOUT_PERMISSION_KEY);
    userPermissions.value = saved ? JSON.parse(saved) : [];
  } catch {
    userPermissions.value = [];
  }
};

const hasPermission = (permission) => {
  if (!permission)
    return true;
  if (!Array.isArray(userPermissions.value) || userPermissions.value.length === 0)
    return true;
  return userPermissions.value.includes(permission);
};

const navGroups = computed(() =>
  navDefinitions
    .map(group => ({
      ...group,
      children: group.items.filter((item) => {
        if (item.adminOnly && !authStore.userInfo?.isAdmin)
          return false;
        return hasPermission(item.permission);
      }),
    }))
    .filter(group => group.children.length > 0),
);

const flatNavItems = computed(() => navGroups.value.flatMap(group => group.children));

const normalizePath = path => (path || "").split("?")[0];

const currentNavItem = computed(() => {
  const normalizedPath = normalizePath(route.path);
  for (const group of navGroups.value) {
    const hit = group.children.find(item => item.path === normalizedPath);
    if (hit)
      return hit;
  }
  return null;
});

const currentPageTitle = computed(() =>
  String(route.meta?.title || currentNavItem.value?.label || "数据台"),
);

const currentPageSubtitle = computed(() => {
  const path = normalizePath(route.path);
  if (path === "/admin/dashboard")
    return "CEO 只读总览";
  if (path === "/admin/card-flip-ops")
    return "卡片倒卖只读数据台";
  if (path.startsWith("/admin/card-flip"))
    return "只保留结果数据";
  if (path === "/tokens")
    return "账号与令牌状态";
  return "精简后台入口";
});

const breadcrumbItems = computed(() => {
  const path = normalizePath(route.path);
  if (path === "/admin/dashboard")
    return [{ title: "首页", path: "/admin/dashboard" }];
  if (path.startsWith("/admin")) {
    return [
      { title: "首页", path: "/admin/dashboard" },
      { title: currentPageTitle.value, path },
    ];
  }
  if (path === "/tokens") {
    return [
      { title: "首页", path: "/admin/dashboard" },
      { title: "账号管理", path: "/tokens" },
    ];
  }
  return [{ title: currentPageTitle.value, path }];
});

const currentRoleLabel = computed(() => {
  const roleKeys = Array.isArray(authStore.userInfo?.roleKeys) ? authStore.userInfo.roleKeys : [];
  const role = String(roleKeys[0] || "viewer").toLowerCase();
  if (role === "admin")
    return "管理员";
  if (role === "ops")
    return "运营";
  return "只读";
});

const authDisplayName = computed(() => {
  const info = authStore.userInfo || {};
  return info.nickname || info.username || selectedToken?.value?.name || "未登录";
});

const ensureExpandedGroupForPath = (path) => {
  const normalizedPath = normalizePath(path);
  const owner = navGroups.value.find(group => group.children.some(item => item.path === normalizedPath));
  if (owner && !expandedGroupKeys.value.includes(owner.key)) {
    expandedGroupKeys.value = [...expandedGroupKeys.value, owner.key];
    localStorage.setItem(SIDEBAR_GROUPS_KEY, JSON.stringify(expandedGroupKeys.value));
  }
};

const toggleSidebar = () => {
  isSidebarCollapsed.value = !isSidebarCollapsed.value;
  localStorage.setItem(SIDEBAR_COLLAPSE_KEY, String(isSidebarCollapsed.value));
};

const isGroupExpanded = key => expandedGroupKeys.value.includes(key);

const toggleGroup = (key) => {
  if (isGroupExpanded(key))
    expandedGroupKeys.value = expandedGroupKeys.value.filter(item => item !== key);
  else
    expandedGroupKeys.value = [...expandedGroupKeys.value, key];
  localStorage.setItem(SIDEBAR_GROUPS_KEY, JSON.stringify(expandedGroupKeys.value));
};

const goTo = (path) => {
  const normalizedPath = normalizePath(path);
  if (!normalizedPath || normalizePath(route.path) === normalizedPath)
    return;
  router.push(normalizedPath);
};

const handleUserAction = (key) => {
  switch (key) {
    case "profile":
      router.push("/admin/profile");
      break;
    case "settings":
      router.push("/admin/system-settings");
      break;
    case "logout":
      authStore.logout();
      message.success("已退出登录");
      router.push("/login");
      break;
  }
};

onMounted(async () => {
  await syncLayoutPermissions();

  const savedCollapsed = localStorage.getItem(SIDEBAR_COLLAPSE_KEY);
  if (savedCollapsed !== null)
    isSidebarCollapsed.value = savedCollapsed === "true";

  try {
    const savedGroupsRaw = localStorage.getItem(SIDEBAR_GROUPS_KEY);
    if (savedGroupsRaw) {
      const savedGroups = JSON.parse(savedGroupsRaw);
      if (Array.isArray(savedGroups))
        expandedGroupKeys.value = savedGroups;
    }
  } catch {
    expandedGroupKeys.value = [];
  }

  if (!expandedGroupKeys.value.length)
    expandedGroupKeys.value = navGroups.value.map(group => group.key);

  ensureExpandedGroupForPath(route.path);
});

watch(() => route.fullPath, () => {
  ensureExpandedGroupForPath(route.path);
});

watch(() => authStore.userInfo, async () => {
  await syncLayoutPermissions();
}, { deep: true });

watch(() => authStore.token, async () => {
  await syncLayoutPermissions();
});

watch(navGroups, (groups) => {
  const allowedKeys = new Set(groups.map(group => group.key));
  const filtered = expandedGroupKeys.value.filter(key => allowedKeys.has(key));
  expandedGroupKeys.value = filtered.length ? filtered : groups.map(group => group.key);
  localStorage.setItem(SIDEBAR_GROUPS_KEY, JSON.stringify(expandedGroupKeys.value));
}, { deep: true });
</script>

<style scoped lang="scss">
.admin-shell {
  display: flex;
  min-height: 100vh;
  background: #000;
}

.sidebar {
  width: 248px;
  background: rgba(0, 0, 0, 0.88);
  backdrop-filter: saturate(180%) blur(20px);
  color: rgba(255, 255, 255, 0.82);
  transition: width 0.2s ease;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
}

.admin-shell.collapsed .sidebar {
  width: 84px;
}

.logo-wrap {
  height: 52px;
  padding: 0 18px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.brand-logo {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  flex: 0 0 auto;
}

.brand-copy {
  display: grid;
  gap: 2px;
}

.brand-title {
  color: #fff;
  font-family: "SF Pro Display", "SF Pro Icons", "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.1;
  letter-spacing: -0.28px;
}

.brand-subtitle {
  color: rgba(255, 255, 255, 0.55);
  font-family: "SF Pro Text", "SF Pro Icons", "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 12px;
  line-height: 1.33;
  letter-spacing: -0.12px;
}

.menu-scroll {
  height: calc(100vh - 52px);
  padding: 14px 0 20px;
}

.nav-group {
  margin: 0 12px 14px;
}

.group-header {
  width: 100%;
  height: 40px;
  border: none;
  background: transparent;
  color: rgba(255, 255, 255, 0.78);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  cursor: pointer;
  font-family: "SF Pro Text", "SF Pro Icons", "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: -0.224px;
}

.group-header:hover {
  color: #fff;
}

.group-label {
  display: flex;
  align-items: center;
  gap: 10px;
}

.group-arrow {
  font-size: 14px;
  opacity: 0.68;
  transition: transform 0.15s ease;
}

.group-arrow.open {
  transform: rotate(180deg);
}

.group-body {
  padding-top: 4px;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 36px;
  margin: 4px 0;
  padding: 0 12px;
  border-radius: 12px;
  color: rgba(255, 255, 255, 0.72);
  text-decoration: none;
  font-family: "SF Pro Text", "SF Pro Icons", "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 14px;
  letter-spacing: -0.224px;
  transition: background 0.15s ease, color 0.15s ease;
}

.nav-link:hover,
.nav-link.active {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.nav-link-collapsed {
  justify-content: center;
  padding: 0;
  margin: 4px 10px;
}

.nav-icon {
  font-size: 18px;
  flex: 0 0 auto;
}

.main-shell {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: #f5f5f7;
}

.topbar,
.breadcrumb-bar {
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: saturate(180%) blur(20px);
}

.topbar {
  height: 48px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 18px;
}

.topbar-left,
.topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.icon-btn {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 50%;
  background: rgba(210, 210, 215, 0.16);
  color: rgba(255, 255, 255, 0.88);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}

.page-heading {
  display: grid;
  gap: 1px;
}

.page-title {
  color: #fff;
  font-family: "SF Pro Display", "SF Pro Icons", "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 21px;
  font-weight: 600;
  line-height: 1.19;
  letter-spacing: 0.231px;
}

.page-subtitle {
  color: rgba(255, 255, 255, 0.55);
  font-family: "SF Pro Text", "SF Pro Icons", "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 12px;
  line-height: 1.33;
  letter-spacing: -0.12px;
}

.user-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: none;
  background: transparent;
  color: rgba(255, 255, 255, 0.92);
  cursor: pointer;
  padding: 4px 0 4px 8px;
}

.breadcrumb-bar {
  padding: 8px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.crumb-link {
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  font-size: 12px;
}

.page-container {
  padding: 24px;
  min-height: 0;
  flex: 1;
  overflow: auto;
}

.drawer-shell {
  padding: 10px 6px;
}

.drawer-group + .drawer-group {
  margin-top: 14px;
}

.drawer-group-title {
  font-size: 12px;
  color: #6e6e73;
  margin: 0 8px 8px;
  letter-spacing: -0.12px;
}

.drawer-link {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 40px;
  padding: 0 12px;
  text-decoration: none;
  border-radius: 12px;
  color: #1d1d1f;
  font-size: 14px;
}

.drawer-link:hover,
.drawer-link.active {
  background: rgba(0, 113, 227, 0.08);
  color: #0066cc;
}

.desktop-only {
  display: inline-flex;
}

.mobile-only {
  display: none;
}

@media (max-width: 992px) {
  .sidebar {
    display: none;
  }

  .desktop-only {
    display: none;
  }

  .mobile-only {
    display: inline-flex;
  }

  .page-container {
    padding: 16px;
  }
}

@media (max-width: 640px) {
  .topbar {
    padding: 0 12px;
  }

  .page-subtitle,
  .role-pill,
  .user-chip span {
    display: none;
  }

  .page-title {
    font-size: 18px;
  }
}
</style>
