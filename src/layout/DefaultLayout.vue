<template>
  <div class="admin-shell" :class="{ collapsed: isSidebarCollapsed }">
    <aside class="sidebar">
      <div class="logo-wrap">
        <img alt="XYZW" class="brand-logo" src="/icons/xiaoyugan.png">
        <span v-if="!isSidebarCollapsed" class="brand-text">XYZW Admin</span>
      </div>

      <n-scrollbar class="menu-scroll">
        <template v-if="isSidebarCollapsed">
          <router-link
            v-for="item in flatNavItems"
            :key="item.path"
            active-class="active"
            class="side-link side-link-collapsed"
            :to="item.path"
          >
            <n-tooltip placement="right" trigger="hover">
              <template #trigger>
                <n-icon class="side-icon">
                  <component :is="item.icon"></component>
                </n-icon>
              </template>
              {{ item.label }}
            </n-tooltip>
          </router-link>
        </template>

        <template v-else>
          <div v-for="group in navGroups" :key="group.key" class="menu-group">
            <button class="group-header" @click="toggleGroup(group.key)">
              <div class="group-title-wrap">
                <n-icon class="side-icon">
                  <component :is="group.icon"></component>
                </n-icon>
                <span>{{ group.label }}</span>
              </div>
              <n-icon class="group-arrow" :class="{ open: isGroupExpanded(group.key) }">
                <ChevronDown></ChevronDown>
              </n-icon>
            </button>

            <div v-show="isGroupExpanded(group.key)" class="group-body">
              <template v-for="item in group.children" :key="item.path || `${group.key}-${item.label}`">
                <router-link
                  v-if="!item.children || !item.children.length"
                  active-class="active"
                  class="side-link side-link-child"
                  :to="item.path"
                >
                  <n-icon class="side-icon">
                    <component :is="item.icon"></component>
                  </n-icon>
                  <span>{{ item.label }}</span>
                </router-link>

                <div v-else class="subtree-wrap">
                  <div class="side-link side-link-parent">
                    <n-icon class="side-icon">
                      <component :is="item.icon"></component>
                    </n-icon>
                    <span>{{ item.label }}</span>
                  </div>

                  <router-link
                    v-for="child in item.children"
                    :key="child.path"
                    active-class="active"
                    class="side-link side-link-grandchild"
                    :to="child.path"
                  >
                    <n-icon class="side-icon">
                      <component :is="child.icon"></component>
                    </n-icon>
                    <span>{{ child.label }}</span>
                  </router-link>
                </div>
              </template>
            </div>
          </div>
        </template>
      </n-scrollbar>
    </aside>

    <div class="content-shell">
      <header class="topbar">
        <div class="topbar-left">
          <button class="icon-btn mobile-only" @click="isMobileMenuOpen = true">
            <n-icon><Menu></Menu></n-icon>
          </button>
          <button class="icon-btn desktop-only" @click="toggleSidebar">
            <n-icon><Menu></Menu></n-icon>
          </button>
          <div class="page-title">{{ currentPageTitle }}</div>
        </div>

        <div class="topbar-right">
          <n-tag class="role-pill" size="small" type="info">
            {{ currentRoleLabel }}
          </n-tag>
          <n-tag class="perm-pill" size="small" :bordered="false">
            {{ permissionSourceLabel }}
          </n-tag>
          <ThemeToggle></ThemeToggle>
          <n-dropdown :options="userMenuOptions" @select="handleUserAction">
            <div class="user-info">
              <n-avatar fallback-src="/icons/xiaoyugan.png" size="small" src=""></n-avatar>
              <span class="username">{{ authDisplayName }}</span>
              <n-icon><ChevronDown></ChevronDown></n-icon>
            </div>
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

      <div class="tags-bar">
        <div class="tags-scroll">
          <button
            v-for="tag in visitedTags"
            :key="tag.path"
            class="tag-item"
            :class="{ active: isTagActive(tag) }"
            @click="goTo(tag.path)"
            @contextmenu.prevent="openTagContextMenu(tag, $event)"
          >
            <span class="tag-text">{{ tag.title }}</span>
            <n-icon v-if="!tag.affix" class="tag-close" @click.stop="closeTag(tag)">
              <Close></Close>
            </n-icon>
          </button>
        </div>

        <n-dropdown :options="tagActionOptions" @select="handleTagAction">
          <button class="tag-action-btn">标签操作</button>
        </n-dropdown>

        <n-dropdown
          placement="bottom-start"
          trigger="manual"
          :options="tagContextMenuOptions"
          :show="tagContextMenuShow"
          :x="tagContextMenuX"
          :y="tagContextMenuY"
          @select="handleTagContextAction"
        ></n-dropdown>
      </div>

      <main class="page-container">
        <router-view :key="routeViewKey"></router-view>
      </main>
    </div>

    <n-drawer
      class="mobile-drawer"
      placement="left"
      v-model:show="isMobileMenuOpen"
      :width="260"
    >
      <div class="drawer-menu">
        <div v-for="group in navGroups" :key="`drawer-${group.key}`" class="drawer-group">
          <div class="drawer-group-title">{{ group.label }}</div>
          <template v-for="item in group.children" :key="item.path || `drawer-${group.key}-${item.label}`">
            <router-link
              v-if="!item.children || !item.children.length"
              active-class="active"
              class="drawer-item"
              :to="item.path"
              @click="isMobileMenuOpen = false"
            >
              <n-icon class="side-icon">
                <component :is="item.icon"></component>
              </n-icon>
              <span>{{ item.label }}</span>
            </router-link>

            <div v-else class="drawer-subtree">
              <div class="drawer-subtitle">{{ item.label }}</div>
              <router-link
                v-for="child in item.children"
                :key="child.path"
                active-class="active"
                class="drawer-item drawer-item-child"
                :to="child.path"
                @click="isMobileMenuOpen = false"
              >
                <n-icon class="side-icon">
                  <component :is="child.icon"></component>
                </n-icon>
                <span>{{ child.label }}</span>
              </router-link>
            </div>
          </template>
        </div>
      </div>
    </n-drawer>
  </div>
</template>

<script setup>
import {
  ChatbubbleEllipsesSharp,
  ChevronDown,
  Close,
  Cube,
  Home,
  Layers,
  Menu,
  PersonCircle,
  Settings,
  TrendingUp,
} from "@vicons/ionicons5";
import { useMessage } from "naive-ui";
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import ThemeToggle from "@/components/Common/ThemeToggle.vue";
import { useAuthStore } from "@/stores/auth";
import { selectedToken, useTokenStore } from "@/stores/tokenStore";

const SIDEBAR_COLLAPSE_KEY = "xyzw_layout_sidebar_collapsed_v1";
const SIDEBAR_GROUPS_KEY = "xyzw_layout_sidebar_groups_v1";
const VISITED_TAGS_KEY = "xyzw_layout_tags_v1";
const LAYOUT_PERMISSION_KEY = "xyzw_layout_permissions_v1";
const REMOTE_PERMISSION_ENDPOINTS = [
  "/card-api/auth/user",
  "/card-api/auth/userinfo",
  "/card-api/user/profile",
  "/auth/user",
  "/auth/userinfo",
  "/user/profile",
  "/api/v1/auth/user",
  "/api/v1/auth/userinfo",
  "/api/v1/user/profile",
];

const tokenStore = useTokenStore();
const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();
const message = useMessage();

const isMobileMenuOpen = ref(false);
const isSidebarCollapsed = ref(false);
const expandedGroupKeys = ref([]);
const visitedTags = ref([]);
const userPermissions = ref([]);
const permissionFetchInFlight = ref(false);
const permissionSource = ref("none");

const tagContextMenuShow = ref(false);
const tagContextMenuX = ref(0);
const tagContextMenuY = ref(0);
const tagContextMenuTag = ref(null);

const viewRefreshSeed = ref(0);
const routeViewKey = computed(() => `${route.fullPath}::${viewRefreshSeed.value}`);

const rawNavGroups = [
  {
    key: "core",
    label: "核心",
    icon: Home,
    children: [
      { label: "控制台", path: "/admin/dashboard", icon: Home, permission: "dashboard:view" },
      { label: "游戏功能", path: "/admin/game-features", icon: Cube, permission: "game:feature:view" },
      {
        label: "卡片倒卖",
        icon: Cube,
        permission: "cardflip:view",
        children: [
          { label: "模拟盘", path: "/admin/card-flip/sim", icon: TrendingUp, permission: "cardflip:view" },
          { label: "实战盘", path: "/admin/card-flip/live", icon: TrendingUp, permission: "cardflip:view" },
          { label: "操作台", path: "/admin/card-flip-ops", icon: Settings, permission: "cardflip:view" },
          { label: "使用文档", path: "/admin/card-flip/docs", icon: ChatbubbleEllipsesSharp, permission: "cardflip:view" },
        ],
      },
    ],
  },
  {
    key: "ops",
    label: "运营",
    icon: Layers,
    children: [
      { label: "任务管理", path: "/admin/daily-tasks", icon: Settings, permission: "task:view" },
      { label: "批量日常", path: "/admin/batch-daily-tasks", icon: Layers, permission: "task:batch" },
      { label: "消息测试", path: "/admin/message-test", icon: ChatbubbleEllipsesSharp, permission: "message:test" },
    ],
  },
  {
    key: "support",
    label: "支持",
    icon: ChatbubbleEllipsesSharp,
    children: [
      { label: "工单处理台", path: "/admin/support-tickets", icon: ChatbubbleEllipsesSharp, permission: "support:ticket:manage" },
    ],
  },
  {
    key: "account",
    label: "账户",
    icon: PersonCircle,
    children: [
      { label: "Token管理", path: "/tokens", icon: PersonCircle, permission: "token:view" },
      { label: "个人设置", path: "/admin/profile", icon: Settings, permission: "profile:view" },
    ],
  },
];

const defaultAffixTags = [
  { title: "控制台", path: "/admin/dashboard", affix: true },
  { title: "Token 管理", path: "/tokens", affix: true },
];
const defaultAffixOrder = new Map(defaultAffixTags.map((tag, index) => [tag.path, index]));

const userMenuOptions = [
  { label: "个人资料", key: "profile" },
  { label: "账户设置", key: "settings" },
  { type: "divider" },
  { label: "退出登录", key: "logout" },
];

const hasPermission = (permission) => {
  if (!permission)
    return true;
  if (!Array.isArray(userPermissions.value) || userPermissions.value.length === 0)
    return true;
  return userPermissions.value.includes(permission);
};

const filterNavItemsByPermission = (items = []) => {
  const filtered = [];
  for (const item of items) {
    const hasCurrent = hasPermission(item.permission);
    if (!hasCurrent)
      continue;
    if (Array.isArray(item.children) && item.children.length > 0) {
      const children = filterNavItemsByPermission(item.children);
      if (!children.length)
        continue;
      filtered.push({ ...item, children });
    } else if (item.path) {
      filtered.push({ ...item });
    }
  }
  return filtered;
};

const flattenNavLeafItems = (items = []) => {
  const leafs = [];
  for (const item of items) {
    if (Array.isArray(item.children) && item.children.length > 0) {
      leafs.push(...flattenNavLeafItems(item.children));
    } else if (item.path) {
      leafs.push(item);
    }
  }
  return leafs;
};

const findNavItemInItems = (items = [], targetPath = "") => {
  for (const item of items) {
    if (item.path && item.path === targetPath)
      return item;
    if (Array.isArray(item.children) && item.children.length > 0) {
      const hit = findNavItemInItems(item.children, targetPath);
      if (hit)
        return hit;
    }
  }
  return null;
};

const containsPathInItems = (items = [], targetPath = "") => {
  return Boolean(findNavItemInItems(items, targetPath));
};

const navGroups = computed(() => {
  return rawNavGroups
    .map((group) => ({
      ...group,
      children: filterNavItemsByPermission(group.children),
    }))
    .filter((group) => group.children.length > 0);
});

const flatNavItems = computed(() => navGroups.value.flatMap((group) => flattenNavLeafItems(group.children)));

const tagActionOptions = computed(() => ([
  { label: "刷新当前", key: "refreshCurrent" },
  { label: "关闭其他", key: "closeOthers" },
  { label: "关闭全部", key: "closeAll" },
]));

const tagContextMenuOptions = computed(() => {
  const tag = tagContextMenuTag.value;
  if (!tag)
    return [];

  const options = [
    { label: "刷新页面", key: "refresh" },
  ];

  const isDefaultAffix = defaultAffixTags.some((item) => item.path === tag.path);
  if (!isDefaultAffix) {
    options.push({
      label: tag.affix ? "取消固定" : "固定标签",
      key: tag.affix ? "unpin" : "pin",
    });
  }

  if (!tag.affix) {
    options.push({ label: "关闭当前", key: "close" });
  }

  options.push({ type: "divider" });
  options.push({ label: "关闭其他", key: "closeOthers" });
  options.push({ label: "关闭全部", key: "closeAll" });
  return options;
});

const normalizePath = (path) => (path || "").split("?")[0];

const toStringArray = (value) => {
  if (!Array.isArray(value))
    return [];
  return value
    .filter((item) => typeof item === "string")
    .map((item) => item.trim())
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

const resolvePermissionsFromAuth = () => {
  const userInfo = authStore.userInfo || {};
  return extractPermissionsFromPayload(userInfo);
};

const resolvePermissionsFromStorage = () => {
  try {
    const savedPermissionsRaw = localStorage.getItem(LAYOUT_PERMISSION_KEY);
    const savedPermissions = savedPermissionsRaw ? JSON.parse(savedPermissionsRaw) : [];
    const list = toStringArray(savedPermissions);
    if (list.length)
      return list;
  } catch {
    // ignore local parse error
  }

  try {
    const rawUser = localStorage.getItem("user");
    if (!rawUser)
      return [];
    const parsedUser = JSON.parse(rawUser);
    const fromUser = [
      ...toStringArray(parsedUser?.permissions),
      ...toStringArray(parsedUser?.perms),
    ];
    if (fromUser.length)
      return [...new Set(fromUser)];
  } catch {
    // ignore local parse error
  }
  return [];
};

const fetchRemotePermissions = async () => {
  if (permissionFetchInFlight.value)
    return [];
  const token = authStore.token;
  if (!token)
    return [];

  permissionFetchInFlight.value = true;
  try {
    for (const endpoint of REMOTE_PERMISSION_ENDPOINTS) {
      try {
        const response = await fetch(endpoint, {
          method: "GET",
          headers: {
            Accept: "application/json",
            Authorization: `Bearer ${token}`,
          },
          credentials: "same-origin",
        });
        if (!response.ok)
          continue;
        const payload = await response.json().catch(() => null);
        const perms = extractPermissionsFromPayload(payload);
        if (perms.length) {
          return perms;
        }
      } catch {
        // keep probing next endpoint
      }
    }
  } finally {
    permissionFetchInFlight.value = false;
  }
  return [];
};

const syncLayoutPermissions = async ({ tryRemote = false } = {}) => {
  const fromAuth = resolvePermissionsFromAuth();
  if (fromAuth.length) {
    userPermissions.value = fromAuth;
    permissionSource.value = "auth-store";
    return;
  }

  if (tryRemote) {
    const fromRemote = await fetchRemotePermissions();
    if (fromRemote.length) {
      userPermissions.value = fromRemote;
      permissionSource.value = "remote-api";
      return;
    }
  }

  const fromStorage = resolvePermissionsFromStorage();
  userPermissions.value = fromStorage;
  permissionSource.value = fromStorage.length ? "local-storage" : "none";
};

const sortVisitedTags = () => {
  const withIndex = visitedTags.value.map((tag, index) => ({ tag, index }));
  withIndex.sort((a, b) => {
    if (a.tag.affix !== b.tag.affix)
      return a.tag.affix ? -1 : 1;

    const aDefault = defaultAffixOrder.has(a.tag.path)
      ? defaultAffixOrder.get(a.tag.path)
      : Number.MAX_SAFE_INTEGER;
    const bDefault = defaultAffixOrder.has(b.tag.path)
      ? defaultAffixOrder.get(b.tag.path)
      : Number.MAX_SAFE_INTEGER;

    if (aDefault !== bDefault)
      return aDefault - bDefault;

    return a.index - b.index;
  });
  visitedTags.value = withIndex.map((item) => item.tag);
};

const findNavItemByPath = (path) => {
  const normalizedPath = normalizePath(path);
  for (const group of navGroups.value) {
    const hit = findNavItemInItems(group.children, normalizedPath);
    if (hit)
      return hit;
  }
  return null;
};

const currentPageTitle = computed(() => {
  const navItem = findNavItemByPath(route.path);
  return String(route.meta?.title || navItem?.label || "控制台");
});

const breadcrumbItems = computed(() => {
  const normalizedPath = normalizePath(route.path);
  const currentTitle = currentPageTitle.value;

  if (normalizedPath === "/admin/dashboard") {
    return [{ title: "首页", path: "/admin/dashboard" }];
  }

  if (normalizedPath.startsWith("/admin")) {
    return [
      { title: "首页", path: "/admin/dashboard" },
      { title: currentTitle, path: normalizedPath },
    ];
  }

  if (normalizedPath === "/tokens") {
    return [
      { title: "首页", path: "/admin/dashboard" },
      { title: "Token 管理", path: "/tokens" },
    ];
  }

  return [{ title: currentTitle, path: normalizedPath }];
});

const currentRoleKey = computed(() => {
  const info = authStore.userInfo || {};
  const roleKeys = toStringArray(info.roleKeys);
  if (roleKeys.length)
    return roleKeys[0].toLowerCase();
  if (Array.isArray(info.roles) && info.roles.length > 0) {
    const firstRole = info.roles[0];
    if (typeof firstRole === "string")
      return firstRole.toLowerCase();
    if (firstRole && typeof firstRole === "object") {
      const roleName = String(firstRole.key || firstRole.name || "").trim().toLowerCase();
      if (roleName)
        return roleName;
    }
  }
  return "admin";
});

const currentRoleLabel = computed(() => {
  if (currentRoleKey.value === "user")
    return "user 用户";
  if (currentRoleKey.value === "viewer")
    return "viewer 只读";
  if (currentRoleKey.value === "ops")
    return "ops 运营";
  return "admin 管理";
});

const authDisplayName = computed(() => {
  const info = authStore.userInfo || {};
  return info.nickname || info.username || selectedToken?.value?.name || "未登录";
});

const permissionSourceLabel = computed(() => {
  if (permissionSource.value === "remote-api")
    return "权限来源: 接口";
  if (permissionSource.value === "auth-store")
    return "权限来源: 登录态";
  if (permissionSource.value === "local-storage")
    return "权限来源: 本地缓存";
  return "权限来源: 默认";
});

const isTagActive = (tag) => normalizePath(route.path) === tag.path;

const persistSidebarState = () => {
  localStorage.setItem(SIDEBAR_COLLAPSE_KEY, String(isSidebarCollapsed.value));
  localStorage.setItem(SIDEBAR_GROUPS_KEY, JSON.stringify(expandedGroupKeys.value));
};

const persistTags = () => {
  localStorage.setItem(VISITED_TAGS_KEY, JSON.stringify(visitedTags.value));
};

const ensureAffixTags = (tags) => {
  const map = new Map();
  for (const tag of defaultAffixTags)
    map.set(tag.path, { ...tag });

  for (const tag of tags || []) {
    if (!tag?.path)
      continue;
    const normalizedPath = normalizePath(tag.path);
    if (!map.has(normalizedPath)) {
      map.set(normalizedPath, {
        title: String(tag.title || normalizedPath),
        path: normalizedPath,
        affix: Boolean(tag.affix),
      });
    } else {
      const base = map.get(normalizedPath);
      map.set(normalizedPath, {
        ...base,
        title: String(tag.title || base.title),
        affix: base.affix || Boolean(tag.affix),
      });
    }
  }

  const normalized = [...map.values()];
  const withIndex = normalized.map((tag, index) => ({ tag, index }));
  withIndex.sort((a, b) => {
    if (a.tag.affix !== b.tag.affix)
      return a.tag.affix ? -1 : 1;
    const aDefault = defaultAffixOrder.has(a.tag.path)
      ? defaultAffixOrder.get(a.tag.path)
      : Number.MAX_SAFE_INTEGER;
    const bDefault = defaultAffixOrder.has(b.tag.path)
      ? defaultAffixOrder.get(b.tag.path)
      : Number.MAX_SAFE_INTEGER;
    if (aDefault !== bDefault)
      return aDefault - bDefault;
    return a.index - b.index;
  });
  return withIndex.map((item) => item.tag);
};

const ensureExpandedGroupForPath = (path) => {
  const normalizedPath = normalizePath(path);
  const group = navGroups.value.find((g) => containsPathInItems(g.children, normalizedPath));
  if (group && !expandedGroupKeys.value.includes(group.key)) {
    expandedGroupKeys.value = [...expandedGroupKeys.value, group.key];
    persistSidebarState();
  }
};

const addVisitedTag = (path, title, affix = false) => {
  const normalizedPath = normalizePath(path);
  if (!normalizedPath)
    return;

  const nextTitle = String(title || findNavItemByPath(normalizedPath)?.label || normalizedPath);
  const idx = visitedTags.value.findIndex((tag) => tag.path === normalizedPath);
  if (idx >= 0) {
    visitedTags.value[idx] = {
      ...visitedTags.value[idx],
      title: nextTitle,
      affix: visitedTags.value[idx].affix || affix,
    };
  } else {
    visitedTags.value.push({
      title: nextTitle,
      path: normalizedPath,
      affix,
    });
  }

  sortVisitedTags();

  if (visitedTags.value.length > 20) {
    const removableIndex = visitedTags.value.findIndex((tag) => !tag.affix);
    if (removableIndex >= 0)
      visitedTags.value.splice(removableIndex, 1);
  }

  persistTags();
};

const addCurrentRouteTag = () => {
  const path = normalizePath(route.path);
  const title = currentPageTitle.value;
  const isAffix = defaultAffixTags.some((tag) => tag.path === path);
  addVisitedTag(path, title, isAffix);
  ensureExpandedGroupForPath(path);
};

const goTo = (path) => {
  const normalizedPath = normalizePath(path);
  if (!normalizedPath || normalizePath(route.path) === normalizedPath)
    return;
  router.push(normalizedPath);
};

const refreshTagView = async (
  path = normalizePath(route.path),
  options = { silent: true },
) => {
  const normalizedPath = normalizePath(path);
  if (!normalizedPath)
    return;

  if (normalizePath(route.path) !== normalizedPath) {
    await router.push(normalizedPath);
  }

  await nextTick();
  viewRefreshSeed.value += 1;
  if (!options?.silent) {
    message.success("已刷新页面");
  }
};

const closeTag = (tag) => {
  if (tag.affix)
    return;

  const index = visitedTags.value.findIndex((item) => item.path === tag.path);
  if (index < 0)
    return;

  const isCurrent = isTagActive(tag);
  visitedTags.value.splice(index, 1);
  persistTags();

  if (isCurrent) {
    const fallback = visitedTags.value[index] || visitedTags.value[index - 1] || defaultAffixTags[0];
    goTo(fallback.path);
  }
};

const closeOtherTags = (targetPath = normalizePath(route.path)) => {
  const normalizedPath = normalizePath(targetPath);
  visitedTags.value = visitedTags.value.filter((tag) => tag.affix || tag.path === normalizedPath);
  sortVisitedTags();
  persistTags();
};

const closeAllTags = () => {
  visitedTags.value = [...defaultAffixTags];
  sortVisitedTags();
  persistTags();
  goTo("/admin/dashboard");
};

const toggleTagAffix = (tag, affix) => {
  if (!tag)
    return;

  const normalizedPath = normalizePath(tag.path);
  const isDefaultAffix = defaultAffixTags.some((item) => item.path === normalizedPath);
  if (isDefaultAffix && affix === false)
    return;

  const idx = visitedTags.value.findIndex((item) => item.path === normalizedPath);
  if (idx < 0)
    return;

  visitedTags.value[idx] = {
    ...visitedTags.value[idx],
    affix: Boolean(affix),
  };
  sortVisitedTags();
  persistTags();
};

const handleTagAction = async (key) => {
  switch (key) {
    case "refreshCurrent":
      await refreshTagView(normalizePath(route.path));
      break;
    case "closeOthers":
      closeOtherTags();
      break;
    case "closeAll":
      closeAllTags();
      break;
  }
};

const hideTagContextMenu = () => {
  tagContextMenuShow.value = false;
  tagContextMenuTag.value = null;
};

const openTagContextMenu = (tag, event) => {
  tagContextMenuTag.value = tag;
  tagContextMenuX.value = event.clientX;
  tagContextMenuY.value = event.clientY;
  tagContextMenuShow.value = true;
};

const handleTagContextAction = async (key) => {
  const tag = tagContextMenuTag.value;
  if (!tag) {
    hideTagContextMenu();
    return;
  }

  switch (key) {
    case "refresh":
      await refreshTagView(tag.path);
      break;
    case "pin":
      toggleTagAffix(tag, true);
      break;
    case "unpin":
      toggleTagAffix(tag, false);
      break;
    case "close":
      closeTag(tag);
      break;
    case "closeOthers":
      closeOtherTags(tag.path);
      goTo(tag.path);
      break;
    case "closeAll":
      closeAllTags();
      break;
  }

  hideTagContextMenu();
};

const toggleSidebar = () => {
  isSidebarCollapsed.value = !isSidebarCollapsed.value;
  persistSidebarState();
};

const isGroupExpanded = (key) => expandedGroupKeys.value.includes(key);

const toggleGroup = (key) => {
  if (isGroupExpanded(key)) {
    expandedGroupKeys.value = expandedGroupKeys.value.filter((item) => item !== key);
  } else {
    expandedGroupKeys.value = [...expandedGroupKeys.value, key];
  }
  persistSidebarState();
};

const handleUserAction = (key) => {
  switch (key) {
    case "profile":
      router.push("/admin/profile");
      break;
    case "settings":
      router.push("/admin/support-tickets");
      break;
    case "logout":
      authStore.logout();
      tokenStore.clearAllTokens();
      message.success("已退出登录");
      router.push("/login");
      break;
  }
};

const handleWindowInteraction = () => {
  if (tagContextMenuShow.value) {
    hideTagContextMenu();
  }
};

onMounted(async () => {
  await syncLayoutPermissions({ tryRemote: true });

  const savedCollapsed = localStorage.getItem(SIDEBAR_COLLAPSE_KEY);
  if (savedCollapsed !== null) {
    isSidebarCollapsed.value = savedCollapsed === "true";
  }

  const allGroupKeys = navGroups.value.map((group) => group.key);

  try {
    const savedGroupsRaw = localStorage.getItem(SIDEBAR_GROUPS_KEY);
    if (savedGroupsRaw) {
      const savedGroups = JSON.parse(savedGroupsRaw);
      if (Array.isArray(savedGroups) && savedGroups.length) {
        expandedGroupKeys.value = savedGroups.filter((groupKey) => allGroupKeys.includes(groupKey));
      }
    }
  } catch {
    expandedGroupKeys.value = allGroupKeys;
  }

  if (!expandedGroupKeys.value.length) {
    expandedGroupKeys.value = allGroupKeys;
  }

  try {
    const savedTagsRaw = localStorage.getItem(VISITED_TAGS_KEY);
    if (savedTagsRaw) {
      const savedTags = JSON.parse(savedTagsRaw);
      visitedTags.value = ensureAffixTags(Array.isArray(savedTags) ? savedTags : []);
    } else {
      visitedTags.value = [...defaultAffixTags];
    }
  } catch {
    visitedTags.value = [...defaultAffixTags];
  }

  sortVisitedTags();
  addCurrentRouteTag();
  persistSidebarState();
  persistTags();

  window.addEventListener("click", handleWindowInteraction, true);
  window.addEventListener("resize", handleWindowInteraction);
  window.addEventListener("scroll", handleWindowInteraction, true);
});

onUnmounted(() => {
  window.removeEventListener("click", handleWindowInteraction, true);
  window.removeEventListener("resize", handleWindowInteraction);
  window.removeEventListener("scroll", handleWindowInteraction, true);
});

watch(() => route.fullPath, () => {
  addCurrentRouteTag();
  hideTagContextMenu();
});

watch(
  () => authStore.userInfo,
  async () => {
    await syncLayoutPermissions({ tryRemote: false });
  },
  { deep: true },
);

watch(
  () => authStore.token,
  async () => {
    await syncLayoutPermissions({ tryRemote: true });
  },
);

watch(navGroups, (groups) => {
  const allowedKeys = new Set(groups.map((group) => group.key));
  const filtered = expandedGroupKeys.value.filter((key) => allowedKeys.has(key));
  expandedGroupKeys.value = filtered.length ? filtered : groups.map((group) => group.key);
  persistSidebarState();
}, { deep: true });
</script>

<style scoped lang="scss">
.admin-shell {
  display: flex;
  min-height: 100vh;
  background: var(--bg-secondary);
}

.sidebar {
  width: 240px;
  background: linear-gradient(180deg, var(--sidebar-bg) 0%, var(--sidebar-bg-soft) 100%);
  color: var(--sidebar-text);
  transition: width 0.2s ease;
  box-shadow: 10px 0 30px rgba(15, 23, 42, 0.12);
  z-index: 12;
}

.admin-shell.collapsed .sidebar {
  width: 76px;
}

.logo-wrap {
  height: 64px;
  padding: 0 18px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.brand-logo {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  flex: 0 0 auto;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.24);
}

.brand-text {
  color: #ffffff;
  font-weight: 700;
  white-space: nowrap;
  letter-spacing: 0.4px;
}

.menu-scroll {
  height: calc(100vh - 64px);
  padding: 12px 0 18px;
}

.menu-group {
  margin: 0 12px 10px;
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
  overflow: hidden;
}

.group-header {
  width: 100%;
  height: 44px;
  border: none;
  background: transparent;
  color: var(--sidebar-text);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;

  &:hover {
    background: rgba(255, 255, 255, 0.05);
    color: #ffffff;
  }
}

.group-title-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
}

.group-arrow {
  font-size: 14px;
  opacity: 0.72;
  transition: transform 0.15s ease;
}

.group-arrow.open {
  transform: rotate(180deg);
}

.group-body {
  padding: 2px 0 8px;
}

.side-link {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 38px;
  margin: 3px 8px;
  padding: 0 12px;
  border-radius: 8px;
  color: var(--sidebar-text);
  text-decoration: none;
  transition: all 0.15s ease;
  font-size: 13px;

  &:hover {
    background: rgba(255, 255, 255, 0.06);
    color: #ffffff;
  }

  &.active {
    color: #ffffff;
    background: linear-gradient(90deg, rgba(64, 158, 255, 0.28), rgba(64, 158, 255, 0.12));
    box-shadow: inset 3px 0 0 0 var(--sidebar-active);
  }
}

.side-link-child {
  margin-left: 20px;
}

.side-link-parent {
  color: #ffffff;
  cursor: default;
  margin-left: 20px;
  font-weight: 600;
  opacity: 0.95;
}

.side-link-grandchild {
  margin-left: 34px;
}

.subtree-wrap {
  padding-bottom: 4px;
}

.side-link-collapsed {
  justify-content: center;
  padding: 0;
  margin: 3px 10px;
}

.side-icon {
  font-size: 18px;
  flex: 0 0 auto;
}

.content-shell {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.topbar,
.breadcrumb-bar,
.tags-bar {
  background: var(--header-bg);
  backdrop-filter: blur(10px);
}

.topbar {
  height: 60px;
  border-bottom: 1px solid var(--border-light);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}

.topbar-left,
.topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.role-pill,
.perm-pill {
  height: 26px;
  border-radius: 999px;
}

.perm-pill {
  color: var(--text-secondary);
  background: var(--bg-tertiary);
}

.icon-btn {
  width: 36px;
  height: 36px;
  border: 1px solid var(--border-light);
  background: #ffffff;
  border-radius: 8px;
  cursor: pointer;
  color: var(--text-secondary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;

  &:hover {
    background: var(--bg-tertiary);
    border-color: var(--border-medium);
    color: var(--text-primary);
  }
}

.page-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid transparent;
  color: var(--text-primary);

  &:hover {
    background: var(--bg-tertiary);
    border-color: var(--border-light);
  }
}

.username {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.breadcrumb-bar {
  padding: 10px 20px;
  border-bottom: 1px solid var(--border-light);
}

.crumb-link {
  color: var(--text-secondary);
  cursor: pointer;

  &:hover {
    color: var(--primary-color);
  }
}

.tags-bar {
  height: 46px;
  border-bottom: 1px solid var(--border-light);
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px;
}

.tags-scroll {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow-x: auto;
  scrollbar-width: thin;
  flex: 1;
}

.tag-item {
  height: 30px;
  border: 1px solid var(--border-light);
  border-radius: 4px;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #ffffff;
  color: var(--text-secondary);
  cursor: pointer;
  white-space: nowrap;

  &:hover {
    border-color: var(--border-medium);
    color: var(--text-primary);
  }

  &.active {
    background: var(--primary-color);
    border-color: var(--primary-color);
    color: #ffffff;
  }
}

.tag-text {
  font-size: 12px;
}

.tag-close {
  font-size: 12px;
  border-radius: 50%;
  padding: 1px;

  &:hover {
    background: rgba(15, 23, 42, 0.12);
  }
}

.tag-action-btn {
  height: 30px;
  border: 1px solid var(--border-light);
  background: #ffffff;
  border-radius: 4px;
  padding: 0 12px;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;

  &:hover {
    color: var(--primary-color);
    border-color: rgba(64, 158, 255, 0.34);
  }
}

.page-container {
  padding: 18px 20px 24px;
  min-height: 0;
  flex: 1;
  overflow: auto;
}

.drawer-menu {
  padding: 10px;
}

.drawer-group + .drawer-group {
  margin-top: 14px;
}

.drawer-group-title {
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 0 8px 8px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.drawer-item {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 42px;
  padding: 0 12px;
  text-decoration: none;
  border-radius: 10px;
  color: var(--text-primary);

  &:hover {
    background: var(--bg-tertiary);
  }

  &.active {
    background: var(--primary-color-light);
    color: var(--primary-color);
  }
}

.drawer-subtree {
  margin: 4px 0 8px;
}

.drawer-subtitle {
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 4px 10px;
}

.drawer-item-child {
  margin-left: 10px;
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

  .breadcrumb-bar {
    display: none;
  }

  .tags-bar {
    padding: 0 10px;
  }

  .tag-action-btn {
    display: none;
  }

  .perm-pill {
    display: none;
  }

  .page-container {
    padding: 12px;
  }
}

@media (max-width: 640px) {
  .topbar {
    padding: 0 10px;
  }

  .username {
    max-width: 88px;
  }

  .role-pill {
    display: none;
  }

  .tags-bar {
    height: 38px;
  }

  .tag-item {
    height: 28px;
    padding: 0 8px;
  }
}
</style>
