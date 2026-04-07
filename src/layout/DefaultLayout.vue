<template>
  <div class="layout-shell" :class="{ collapsed: isCollapsed }">
    <aside class="sidebar">
      <div class="sidebar-logo">
        <img alt="XYZW" class="logo-image" src="/icons/xiaoyugan.png">
        <div v-if="!isCollapsed" class="logo-copy">
          <strong>XYZW 后台</strong>
          <span>卡片倒卖数据看板</span>
        </div>
      </div>

      <nav class="sidebar-menu">
        <router-link
          v-for="item in visibleNavItems"
          :key="item.path"
          :to="item.path"
          class="menu-item"
          active-class="is-active"
        >
          <n-icon class="menu-icon">
            <component :is="item.icon"></component>
          </n-icon>
          <span v-if="!isCollapsed">{{ item.label }}</span>
        </router-link>
      </nav>
    </aside>

    <div class="layout-main">
      <header class="layout-header">
        <div class="header-left">
          <button class="icon-button" type="button" @click="toggleSidebar">
            <n-icon><MenuOutline></MenuOutline></n-icon>
          </button>
          <div class="header-meta">
            <div class="header-title">{{ currentTitle }}</div>
            <n-breadcrumb class="header-breadcrumb">
              <n-breadcrumb-item>后台</n-breadcrumb-item>
              <n-breadcrumb-item>{{ currentTitle }}</n-breadcrumb-item>
            </n-breadcrumb>
          </div>
        </div>

        <div class="header-right">
          <n-tag size="small" type="info">{{ currentRoleLabel }}</n-tag>
          <n-dropdown :options="userMenuOptions" @select="handleUserAction">
            <button class="user-button" type="button">
              <n-avatar round size="small">{{ displayName.slice(0, 1) }}</n-avatar>
              <span>{{ displayName }}</span>
              <n-icon><ChevronDownOutline></ChevronDownOutline></n-icon>
            </button>
          </n-dropdown>
        </div>
      </header>

      <main class="layout-content">
        <router-view></router-view>
      </main>
    </div>

    <n-drawer v-model:show="showMobileMenu" placement="left" :width="220">
      <div class="mobile-menu">
        <router-link
          v-for="item in visibleNavItems"
          :key="`mobile-${item.path}`"
          :to="item.path"
          class="mobile-menu-item"
          active-class="is-active"
          @click="showMobileMenu = false"
        >
          <n-icon class="menu-icon">
            <component :is="item.icon"></component>
          </n-icon>
          <span>{{ item.label }}</span>
        </router-link>
      </div>
    </n-drawer>
  </div>
</template>

<script setup>
import {
  BarChartOutline,
  ChevronDownOutline,
  MenuOutline,
  PieChartOutline,
} from "@vicons/ionicons5";
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const isCollapsed = ref(false);
const showMobileMenu = ref(false);

const navItems = [
  {
    label: "管理总览",
    path: "/admin/dashboard",
    icon: BarChartOutline,
    permission: "dashboard:view",
    adminOnly: true,
  },
  {
    label: "卡片倒卖",
    path: "/admin/card-flip-ops",
    icon: PieChartOutline,
    permission: "cardflip:view",
  },
];

const userMenuOptions = [
  { label: "退出登录", key: "logout" },
];

const visibleNavItems = computed(() =>
  navItems.filter((item) => {
    if (item.adminOnly && !authStore.userInfo?.isAdmin)
      return false;
    return authStore.hasPermission(item.permission);
  }),
);

const currentTitle = computed(() => String(route.meta?.title || "卡片倒卖"));
const displayName = computed(() =>
  String(authStore.userInfo?.nickname || authStore.userInfo?.username || "管理员"),
);
const currentRoleLabel = computed(() => {
  const role = String(authStore.userInfo?.roleKeys?.[0] || "viewer").toLowerCase();
  if (role === "admin")
    return "管理员";
  if (role === "ops")
    return "运营";
  return "只读";
});

const toggleSidebar = () => {
  if (window.innerWidth <= 992) {
    showMobileMenu.value = true;
    return;
  }
  isCollapsed.value = !isCollapsed.value;
};

const handleUserAction = async (key) => {
  if (key !== "logout")
    return;
  await authStore.logout();
  router.push("/login");
};
</script>

<style scoped lang="scss">
.layout-shell {
  display: flex;
  min-height: 100vh;
  background: var(--bg-secondary);
}

.sidebar {
  width: 210px;
  background: var(--sidebar-bg);
  color: var(--sidebar-text);
  transition: width 0.28s ease;
  box-shadow: 2px 0 6px rgba(0, 21, 41, 0.08);
}

.layout-shell.collapsed .sidebar {
  width: 64px;
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 60px;
  padding: 0 16px;
  overflow: hidden;
}

.logo-image {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  flex: 0 0 auto;
}

.logo-copy {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.logo-copy strong {
  font-size: 15px;
  color: #fff;
  white-space: nowrap;
}

.logo-copy span {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.65);
  white-space: nowrap;
}

.sidebar-menu {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
}

.menu-item,
.mobile-menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 46px;
  padding: 0 14px;
  border-radius: 4px;
  color: inherit;
  text-decoration: none;
  transition: background 0.2s ease, color 0.2s ease;
}

.menu-item:hover,
.mobile-menu-item:hover {
  background: rgba(255, 255, 255, 0.08);
}

.menu-item.is-active,
.mobile-menu-item.is-active {
  background: #263445;
  color: #409eff;
}

.layout-shell.collapsed .menu-item {
  justify-content: center;
  padding: 0;
}

.menu-icon {
  font-size: 18px;
  flex: 0 0 auto;
}

.layout-main {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
}

.layout-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
  padding: 0 20px;
  background: var(--header-bg);
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 4px;
  font-size: 18px;
  color: #606266;
  transition: background 0.2s ease;
}

.icon-button:hover {
  background: #f5f7fa;
}

.header-meta {
  display: grid;
  gap: 4px;
}

.header-title {
  color: #303133;
  font-size: 18px;
  font-weight: 600;
}

.header-breadcrumb {
  color: #909399;
}

.user-button {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: #303133;
  font-size: 14px;
}

.layout-content {
  flex: 1;
  padding: 20px;
  overflow: auto;
}

.mobile-menu {
  display: grid;
  gap: 6px;
  padding: 12px;
}

@media (max-width: 992px) {
  .sidebar {
    display: none;
  }

  .layout-content {
    padding: 16px;
  }
}

@media (max-width: 640px) {
  .layout-header {
    padding: 0 12px;
  }

  .header-breadcrumb,
  .user-button span {
    display: none;
  }
}
</style>
