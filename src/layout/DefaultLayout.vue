<template>
  <div class="app-shell">
    <aside class="sidebar" :class="{ collapsed: isCollapsed }">
      <div class="brand">
        <div class="brand-mark">
          <n-icon size="18">
            <BarChartOutline></BarChartOutline>
          </n-icon>
        </div>
        <div v-if="!isCollapsed" class="brand-copy">
          <strong>交易中枢</strong>
          <span>Card Trading Console</span>
        </div>
      </div>

      <nav class="sidebar-nav">
        <router-link
          v-for="item in visibleNavItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          active-class="is-active"
        >
          <span class="nav-indicator"></span>
          <n-icon class="nav-icon" size="18">
            <component :is="item.icon"></component>
          </n-icon>
          <span v-if="!isCollapsed" class="nav-label">{{ item.label }}</span>
        </router-link>
      </nav>

      <div v-if="!isCollapsed" class="sidebar-footer">
        <div class="footer-label">当前角色</div>
        <div class="footer-value">{{ currentRoleLabel }}</div>
        <div class="footer-bar">
          <span></span>
        </div>
      </div>
    </aside>

    <div class="main-shell" :class="{ expanded: isCollapsed }">
      <header class="topbar">
        <div class="topbar-left">
          <button class="icon-button" type="button" @click="toggleSidebar">
            <n-icon size="20"><MenuOutline></MenuOutline></n-icon>
          </button>
          <div class="topbar-title">{{ currentTitle }}</div>
        </div>

        <div class="topbar-right">
          <button class="icon-button desktop-only" type="button">
            <n-icon size="18"><SearchOutline></SearchOutline></n-icon>
          </button>
          <button class="icon-button desktop-only" type="button">
            <n-icon size="18"><NotificationsOutline></NotificationsOutline></n-icon>
          </button>
          <div class="divider desktop-only"></div>
          <n-dropdown :options="userMenuOptions" @select="handleUserAction">
            <button class="user-chip" type="button">
              <div class="user-meta desktop-only">
                <div class="user-name">{{ displayName }}</div>
                <div class="user-role">{{ currentRoleLabel }}</div>
              </div>
              <n-avatar
                round
                size="medium"
                :style="{ backgroundColor: '#e8edf7', color: '#495c94' }"
              >
                {{ displayName.slice(0, 1) }}
              </n-avatar>
              <n-icon size="18"><ChevronDownOutline></ChevronDownOutline></n-icon>
            </button>
          </n-dropdown>
        </div>
      </header>

      <main class="page-shell">
        <router-view></router-view>
      </main>
    </div>

    <n-drawer v-model:show="showMobileMenu" placement="left" :width="248">
      <div class="mobile-drawer">
        <div class="brand mobile-brand">
          <div class="brand-mark">
            <n-icon size="18">
              <BarChartOutline></BarChartOutline>
            </n-icon>
          </div>
          <div class="brand-copy">
            <strong>交易中枢</strong>
            <span>Card Trading Console</span>
          </div>
        </div>

        <nav class="sidebar-nav">
          <router-link
            v-for="item in visibleNavItems"
            :key="`mobile-${item.path}`"
            :to="item.path"
            class="nav-item"
            active-class="is-active"
            @click="showMobileMenu = false"
          >
            <span class="nav-indicator"></span>
            <n-icon class="nav-icon" size="18">
              <component :is="item.icon"></component>
            </n-icon>
            <span class="nav-label">{{ item.label }}</span>
          </router-link>
        </nav>
      </div>
    </n-drawer>
  </div>
</template>

<script setup>
import {
  BarChartOutline,
  ChevronDownOutline,
  MenuOutline,
  NotificationsOutline,
  PieChartOutline,
  SearchOutline,
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
    label: "总览",
    path: "/admin/dashboard",
    icon: BarChartOutline,
    permission: "dashboard:view",
    adminOnly: true,
  },
  {
    label: "卡片交易",
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

const currentTitle = computed(() => String(route.meta?.title || "卡片交易"));
const currentRoleLabel = computed(() => {
  const role = String(authStore.userInfo?.roleKeys?.[0] || "viewer").toLowerCase();
  if (role === "admin")
    return "管理员";
  if (role === "ops")
    return "运营";
  return "查看";
});

const displayName = computed(() => {
  const username = String(authStore.userInfo?.username || "").trim();
  const nickname = String(authStore.userInfo?.nickname || "").trim();
  const genericNames = new Set([
    "服务器操作员",
    "本地操作员",
    "Local Admin",
    "System Admin",
    "operator",
    "admin",
  ]);

  if (nickname && !genericNames.has(nickname))
    return nickname;
  if (username && !genericNames.has(username))
    return username;
  return currentRoleLabel.value;
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
.app-shell {
  min-height: 100vh;
  background: var(--bg-primary);
}

.sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 30;
  width: 248px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 18px 16px;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--surface-line);
}

.sidebar.collapsed {
  width: 88px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 4px 12px;
}

.brand-mark {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  color: #fff;
  background: linear-gradient(180deg, #306bf3, #0051d5);
  box-shadow: 0 10px 22px rgba(0, 81, 213, 0.24);
}

.brand-copy {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.brand-copy strong {
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 800;
  letter-spacing: -0.03em;
  white-space: nowrap;
}

.brand-copy span {
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  white-space: nowrap;
}

.sidebar-nav {
  display: grid;
  gap: 4px;
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 48px;
  padding: 0 14px;
  border-radius: 12px;
  color: var(--sidebar-text);
  transition: background 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.nav-item:hover {
  background: rgba(0, 81, 213, 0.04);
  color: var(--text-primary);
}

.nav-item.is-active {
  background: var(--sidebar-active-bg);
  color: var(--sidebar-active-text);
}

.nav-indicator {
  position: absolute;
  left: -16px;
  top: 10px;
  bottom: 10px;
  width: 4px;
  border-radius: 999px;
  background: transparent;
}

.nav-item.is-active .nav-indicator {
  background: var(--primary-color);
}

.nav-label {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
}

.sidebar-footer {
  margin-top: auto;
  padding: 16px;
  border-radius: 14px;
  background: var(--surface-soft);
  border: 1px solid var(--surface-line);
}

.footer-label {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.footer-value {
  margin-top: 8px;
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 800;
}

.footer-bar {
  height: 6px;
  margin-top: 12px;
  border-radius: 999px;
  background: rgba(73, 92, 148, 0.12);
  overflow: hidden;
}

.footer-bar span {
  display: block;
  width: 78%;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #306bf3, #0051d5);
}

.main-shell {
  min-height: 100vh;
  margin-left: 248px;
}

.main-shell.expanded {
  margin-left: 88px;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  padding: 0 28px;
  background: var(--header-bg);
  backdrop-filter: blur(14px);
  border-bottom: 1px solid var(--surface-line);
}

.topbar-left,
.topbar-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.topbar-title {
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.icon-button {
  width: 38px;
  height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  color: var(--text-secondary);
  background: transparent;
  transition: background 0.18s ease, color 0.18s ease;
}

.icon-button:hover {
  background: rgba(0, 81, 213, 0.06);
  color: var(--primary-color);
}

.divider {
  width: 1px;
  height: 28px;
  background: var(--surface-line);
}

.user-chip {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  color: var(--text-primary);
}

.user-meta {
  display: grid;
  gap: 2px;
  text-align: right;
}

.user-name {
  font-size: 14px;
  font-weight: 700;
}

.user-role {
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.page-shell {
  padding: 28px;
}

.mobile-drawer {
  display: grid;
  gap: 20px;
}

.mobile-brand {
  padding-bottom: 4px;
}

@media (max-width: 992px) {
  .sidebar {
    display: none;
  }

  .main-shell,
  .main-shell.expanded {
    margin-left: 0;
  }

  .topbar {
    padding: 0 16px;
  }

  .page-shell {
    padding: 20px 16px 28px;
  }
}

@media (max-width: 640px) {
  .desktop-only,
  .user-meta {
    display: none;
  }

  .topbar {
    padding: 0 12px;
  }
}
</style>
