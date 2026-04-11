<template>
  <div class="app-shell">
    <aside class="sidebar" :class="{ collapsed: isCollapsed }">
      <div class="brand">
        <div class="brand-copy" v-if="!isCollapsed">
          <strong>Console Admin</strong>
          <span>Trading Manager</span>
        </div>
        <div class="brand-mark">
          <n-icon size="18">
            <BarChartOutline></BarChartOutline>
          </n-icon>
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
          <n-icon class="nav-icon" size="18">
            <component :is="item.icon"></component>
          </n-icon>
          <span v-if="!isCollapsed" class="nav-label">{{ item.label }}</span>
        </router-link>
      </nav>

      <div v-if="!isCollapsed" class="sidebar-footer">
        <div class="footer-links">
          <button class="footer-link" type="button" @click="openUtilityPanel('settings')">
            <n-icon size="16"><SettingsOutline></SettingsOutline></n-icon>
            <span>Settings</span>
          </button>
          <button class="footer-link" type="button" @click="openUtilityPanel('support')">
            <n-icon size="16"><HelpCircleOutline></HelpCircleOutline></n-icon>
            <span>Support</span>
          </button>
        </div>

        <div class="profile-card">
          <n-avatar round size="small" class="sidebar-avatar">
            {{ displayName.slice(0, 1).toUpperCase() }}
          </n-avatar>
          <div class="profile-copy">
            <strong>{{ displayName }}</strong>
            <span>{{ currentRoleLabel }}</span>
          </div>
        </div>

        <div class="footer-label">Access</div>
        <div class="footer-value">{{ currentRoleLabel }}</div>
        <div class="footer-progress">
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
          <div class="title-group">
            <div class="topbar-title">{{ currentTitle }}</div>
            <div class="topbar-subtitle">XYZW Card Trading Console</div>
          </div>
        </div>

        <div class="topbar-right">
          <button class="quick-search desktop-only" type="button" @click="focusPrimarySearch">
            <n-icon size="16"><SearchOutline></SearchOutline></n-icon>
            <span>Search operations...</span>
          </button>
          <button class="icon-button desktop-only" type="button" @click="openUtilityPanel('alerts')">
            <n-icon size="18"><NotificationsOutline></NotificationsOutline></n-icon>
          </button>
          <n-dropdown :options="userMenuOptions" @select="handleUserAction">
            <button class="user-chip" type="button">
              <div class="user-meta desktop-only">
                <div class="user-name">{{ displayName }}</div>
                <div class="user-role">{{ currentRoleLabel }}</div>
              </div>
              <n-avatar round size="medium" class="avatar-chip">
                {{ displayName.slice(0, 1).toUpperCase() }}
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
          <div class="brand-copy">
            <strong>Console Admin</strong>
            <span>Trading Manager</span>
          </div>
          <div class="brand-mark">
            <n-icon size="18">
              <BarChartOutline></BarChartOutline>
            </n-icon>
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
            <n-icon class="nav-icon" size="18">
              <component :is="item.icon"></component>
            </n-icon>
            <span class="nav-label">{{ item.label }}</span>
          </router-link>
        </nav>
      </div>
    </n-drawer>

    <n-drawer v-model:show="showUtilityDrawer" placement="right" :width="420">
      <n-drawer-content :title="utilityTitle" closable>
        <div class="utility-stack">
          <div class="utility-hero">
            <strong>{{ utilityTitle }}</strong>
            <p>{{ utilityDescription }}</p>
          </div>

          <div class="utility-section">
            <h4>Quick Actions</h4>
            <div class="utility-actions">
              <button class="utility-action" type="button" @click="router.push('/admin/dashboard')">Open Overview</button>
              <button class="utility-action" type="button" @click="router.push('/admin/card-flip-ops')">Open Card Trading</button>
              <button class="utility-action" type="button" @click="focusPrimarySearch">Focus Search</button>
              <button class="utility-action" type="button" @click="router.go(0)">Refresh Page</button>
            </div>
          </div>

          <div class="utility-section">
            <h4>Current Context</h4>
            <div class="utility-list">
              <div class="utility-row">
                <span>User</span>
                <strong>{{ displayName }}</strong>
              </div>
              <div class="utility-row">
                <span>Role</span>
                <strong>{{ currentRoleLabel }}</strong>
              </div>
              <div class="utility-row">
                <span>Page</span>
                <strong>{{ currentTitle }}</strong>
              </div>
              <div class="utility-row">
                <span>Route</span>
                <strong>{{ route.fullPath }}</strong>
              </div>
            </div>
          </div>

          <div class="utility-section" v-if="activeUtilityPanel === 'support'">
            <h4>Support Notes</h4>
            <ul class="utility-notes">
              <li>Use the page search to filter visible rows without leaving the console.</li>
              <li>Transaction exports respect the active filters on the current page.</li>
              <li>Service buttons open live detail drawers instead of placeholder links.</li>
            </ul>
          </div>

          <div class="utility-section" v-if="activeUtilityPanel === 'alerts'">
            <h4>Notification State</h4>
            <ul class="utility-notes">
              <li>The bell is now wired to this alert panel instead of a dead button.</li>
              <li>Use it as a quick entry point before drilling into a specific page section.</li>
            </ul>
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<script setup>
import {
  BarChartOutline,
  ChevronDownOutline,
  HelpCircleOutline,
  MenuOutline,
  NotificationsOutline,
  PieChartOutline,
  SearchOutline as SearchNavOutline,
  SearchOutline,
  SettingsOutline,
} from "@vicons/ionicons5";
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const isCollapsed = ref(false);
const showMobileMenu = ref(false);
const showUtilityDrawer = ref(false);
const activeUtilityPanel = ref("settings");

const navItems = [
  {
    label: "Overview",
    path: "/admin/dashboard",
    icon: BarChartOutline,
    permission: "dashboard:view",
    adminOnly: true,
  },
  {
    label: "Card Trading",
    path: "/admin/card-flip-ops",
    icon: PieChartOutline,
    permission: "cardflip:view",
  },
  {
    label: "Matching Lab",
    path: "/admin/matching-lab",
    icon: SearchNavOutline,
    permission: "cardflip:view",
  },
];

const userMenuOptions = [
  { label: "Sign Out", key: "logout" },
];

const visibleNavItems = computed(() =>
  navItems.filter((item) => {
    if (item.adminOnly && !authStore.userInfo?.isAdmin)
      return false;
    return authStore.hasPermission(item.permission);
  }),
);

const currentTitle = computed(() => String(route.meta?.title || "Card Trading"));
const currentRoleLabel = computed(() => {
  const role = String(authStore.userInfo?.roleKeys?.[0] || "viewer").toLowerCase();
  if (role === "admin")
    return "Admin";
  if (role === "ops")
    return "Ops Manager";
  return "Viewer";
});

const displayName = computed(() => {
  const username = String(authStore.userInfo?.username || "").trim();
  const nickname = String(authStore.userInfo?.nickname || "").trim();
  const genericNames = new Set([
    "server operator",
    "local operator",
    "local admin",
    "system admin",
    "operator",
    "admin",
    "管理员",
    "服务器操作员",
  ]);

  if (nickname && !genericNames.has(nickname.toLowerCase()))
    return nickname;
  if (username && !genericNames.has(username.toLowerCase()))
    return username;
  return currentRoleLabel.value;
});

const utilityTitle = computed(() => {
  if (activeUtilityPanel.value === "support")
    return "Support";
  if (activeUtilityPanel.value === "alerts")
    return "Notifications";
  return "Settings";
});

const utilityDescription = computed(() => {
  if (activeUtilityPanel.value === "support")
    return "Quick help, navigation shortcuts, and page-level operating notes.";
  if (activeUtilityPanel.value === "alerts")
    return "Topbar notification access for the current console session.";
  return "Interface controls and fast navigation for the current console session.";
});

const toggleSidebar = () => {
  if (window.innerWidth <= 992) {
    showMobileMenu.value = true;
    return;
  }
  isCollapsed.value = !isCollapsed.value;
};

const openUtilityPanel = (panel) => {
  activeUtilityPanel.value = panel;
  showUtilityDrawer.value = true;
};

const focusPrimarySearch = () => {
  if (route.path.includes("/card-flip-ops")) {
    window.dispatchEvent(new CustomEvent("focus-card-trading-search"));
    showUtilityDrawer.value = false;
    return;
  }
  router.push("/admin/card-flip-ops");
  showUtilityDrawer.value = false;
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
  gap: 24px;
  padding: 24px 16px;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--surface-line);
}

.sidebar.collapsed {
  width: 92px;
}

.brand {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 8px;
}

.brand-mark {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  border-radius: 14px;
  color: #fff;
  background: linear-gradient(180deg, #2890ff, #0071e3);
  box-shadow: 0 16px 32px rgba(0, 113, 227, 0.26);
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
  letter-spacing: -0.04em;
}

.brand-copy span {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.sidebar-nav {
  display: grid;
  gap: 8px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 48px;
  padding: 0 14px;
  border-radius: var(--radius-full);
  color: var(--sidebar-text);
  transition: background 0.18s ease, color 0.18s ease;
}

.nav-item:hover {
  color: rgba(255, 255, 255, 0.82);
  background: rgba(255, 255, 255, 0.05);
}

.nav-item.is-active {
  color: var(--sidebar-active-text);
  background: var(--sidebar-active-bg);
}

.nav-label {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.sidebar-footer {
  margin-top: auto;
  padding: 18px;
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--surface-line);
}

.footer-links {
  display: grid;
  gap: 6px;
}

.footer-link {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 36px;
  padding: 0 10px;
  border-radius: 12px;
  color: var(--text-secondary);
}

.footer-link:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.05);
}

.profile-card {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 18px 0 14px;
  padding-top: 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.sidebar-avatar {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary);
}

.profile-copy {
  display: grid;
  gap: 2px;
}

.profile-copy strong {
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 700;
}

.profile-copy span {
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 700;
}

.footer-label {
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.footer-value {
  margin-top: 8px;
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 800;
}

.footer-progress {
  height: 6px;
  margin-top: 14px;
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.08);
  overflow: hidden;
}

.footer-progress span {
  display: block;
  width: 76%;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2890ff, #0071e3);
}

.main-shell {
  min-height: 100vh;
  margin-left: 248px;
}

.main-shell.expanded {
  margin-left: 92px;
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
  backdrop-filter: blur(18px);
  border-bottom: 1px solid var(--surface-line);
}

.topbar-left,
.topbar-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.title-group {
  display: grid;
  gap: 2px;
}

.topbar-title {
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.topbar-subtitle {
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.icon-button {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-full);
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.04);
  transition: background 0.18s ease, color 0.18s ease;
}

.icon-button:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.08);
}

.quick-search {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 220px;
  height: 40px;
  padding: 0 14px;
  border-radius: var(--radius-full);
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.quick-search span {
  font-size: 13px;
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

.avatar-chip {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary);
}

.page-shell {
  width: min(1440px, 100%);
  padding: 32px 28px 40px;
  margin: 0 auto;
}

.utility-stack {
  display: grid;
  gap: 20px;
}

.utility-hero {
  padding: 18px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.04);
}

.utility-hero strong {
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 700;
}

.utility-hero p {
  margin-top: 8px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.utility-section h4 {
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 12px;
}

.utility-actions {
  display: grid;
  gap: 10px;
}

.utility-action {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  border-radius: 12px;
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.05);
}

.utility-action:hover {
  background: rgba(255, 255, 255, 0.08);
}

.utility-list {
  display: grid;
  gap: 10px;
}

.utility-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.04);
}

.utility-row span {
  color: var(--text-secondary);
}

.utility-row strong {
  color: var(--text-primary);
}

.utility-notes {
  display: grid;
  gap: 10px;
  padding-left: 18px;
  color: var(--text-secondary);
}

.utility-notes li {
  line-height: 1.6;
}

.mobile-drawer {
  display: grid;
  gap: 24px;
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
    padding: 24px 16px 32px;
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
