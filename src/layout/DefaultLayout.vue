<template>
  <div class="shell">
    <aside class="sidebar desktop-sidebar">
      <div class="brand-block">
        <img alt="XYZW" class="brand-logo" src="/icons/xiaoyugan.png">
        <div class="brand-copy">
          <div class="brand-title">XYZW 数据台</div>
          <div class="brand-subtitle">只读前台视图</div>
        </div>
      </div>

      <nav class="nav-stack">
        <section v-for="section in navSections" :key="section.key" class="nav-section">
          <div class="section-title">{{ section.label }}</div>
          <router-link
            v-for="item in section.items"
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
        </section>
      </nav>
    </aside>

    <div class="main-shell">
      <header class="topbar">
        <div class="topbar-left">
          <button class="icon-btn mobile-only" type="button" @click="isMobileMenuOpen = true">
            <n-icon><Menu></Menu></n-icon>
          </button>
          <div class="page-meta">
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

      <main class="page-container">
        <router-view></router-view>
      </main>
    </div>

    <n-drawer
      class="mobile-drawer"
      placement="left"
      v-model:show="isMobileMenuOpen"
      :width="280"
    >
      <div class="drawer-shell">
        <div class="brand-block mobile-brand">
          <img alt="XYZW" class="brand-logo" src="/icons/xiaoyugan.png">
          <div class="brand-copy">
            <div class="brand-title">XYZW 数据台</div>
            <div class="brand-subtitle">只读前台视图</div>
          </div>
        </div>

        <nav class="nav-stack">
          <section v-for="section in navSections" :key="`drawer-${section.key}`" class="nav-section">
            <div class="section-title">{{ section.label }}</div>
            <router-link
              v-for="item in section.items"
              :key="item.path"
              active-class="active"
              class="nav-link"
              :to="item.path"
              @click="isMobileMenuOpen = false"
            >
              <n-icon class="nav-icon">
                <component :is="item.icon"></component>
              </n-icon>
              <span>{{ item.label }}</span>
            </router-link>
          </section>
        </nav>
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
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import ThemeToggle from "@/components/Common/ThemeToggle.vue";
import { useAuthStore } from "@/stores/auth";

const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();
const isMobileMenuOpen = ref(false);

const navDefinitions = [
  {
    key: "overview",
    label: "总览",
    items: [
      { label: "管理总览", path: "/admin/dashboard", icon: Home, permission: "dashboard:view", adminOnly: true },
      { label: "卡片总览", path: "/admin/card-flip-ops", icon: Cube, permission: "cardflip:view" },
      { label: "模拟盘", path: "/admin/card-flip/sim", icon: TrendingUp, permission: "cardflip:view" },
      { label: "实战盘", path: "/admin/card-flip/live", icon: TrendingUp, permission: "cardflip:view" },
      { label: "运行文档", path: "/admin/card-flip/docs", icon: ChatbubbleEllipsesSharp, permission: "cardflip:view" },
    ],
  },
  {
    key: "account",
    label: "账户",
    items: [
      { label: "账号管理", path: "/tokens", icon: PersonCircle, permission: "token:view" },
      { label: "个人设置", path: "/admin/profile", icon: PersonCircle, permission: "profile:view" },
    ],
  },
];

const navSections = computed(() =>
  navDefinitions
    .map(section => ({
      ...section,
      items: section.items.filter((item) => {
        if (item.adminOnly && !authStore.userInfo?.isAdmin)
          return false;
        return authStore.hasPermission ? authStore.hasPermission(item.permission) : true;
      }),
    }))
    .filter(section => section.items.length > 0),
);

const currentNavItem = computed(() => {
  for (const section of navSections.value) {
    for (const item of section.items) {
      if (route.path === item.path)
        return item;
    }
  }
  return null;
});

const currentRoleLabel = computed(() => {
  const roleKeys = Array.isArray(authStore.userInfo?.roleKeys) ? authStore.userInfo.roleKeys : [];
  const role = String(roleKeys[0] || "viewer").toLowerCase();
  if (role === "admin")
    return "管理员";
  if (role === "ops")
    return "运营";
  if (role === "viewer")
    return "只读";
  return role;
});

const currentPageTitle = computed(() =>
  String(route.meta?.title || currentNavItem.value?.label || "数据页面"),
);

const currentPageSubtitle = computed(() => {
  const path = route.path || "";
  if (path.startsWith("/admin/card-flip"))
    return "只看数据，不在前台暴露操作参数";
  if (path === "/admin/dashboard")
    return "结果、风险与服务状态的一屏总览";
  if (path === "/tokens")
    return "账号与令牌状态";
  return "简化后的管理后台";
});

const authDisplayName = computed(() => {
  const info = authStore.userInfo || {};
  return info.nickname || info.username || "未登录";
});

const userMenuOptions = [
  { label: "个人资料", key: "profile" },
  { type: "divider" },
  { label: "退出登录", key: "logout" },
];

const handleUserAction = async (key) => {
  if (key === "profile") {
    router.push("/admin/profile");
    return;
  }
  if (key === "logout") {
    await authStore.logout();
    router.push("/login");
  }
};
</script>

<style scoped lang="scss">
.shell {
  display: grid;
  grid-template-columns: 248px minmax(0, 1fr);
  min-height: 100vh;
  background: #f5f5f7;
  font-family:
    "SF Pro Display",
    "SF Pro Text",
    -apple-system,
    BlinkMacSystemFont,
    "Helvetica Neue",
    "PingFang SC",
    "Microsoft YaHei",
    sans-serif;
}

.sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  padding: 20px 16px;
  background: rgba(0, 0, 0, 0.82);
  backdrop-filter: saturate(180%) blur(20px);
  color: #fff;
}

.brand-block {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 8px 20px;
}

.brand-logo {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  flex: 0 0 auto;
}

.brand-copy {
  display: grid;
  gap: 2px;
}

.brand-title {
  color: #fff;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.1;
  letter-spacing: -0.2px;
}

.brand-subtitle {
  color: rgba(255, 255, 255, 0.62);
  font-size: 12px;
}

.nav-stack {
  display: grid;
  gap: 18px;
}

.nav-section {
  display: grid;
  gap: 8px;
}

.section-title {
  padding: 0 10px;
  color: rgba(255, 255, 255, 0.52);
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 44px;
  padding: 0 12px;
  border-radius: 12px;
  color: rgba(255, 255, 255, 0.84);
  text-decoration: none;
  transition: background 0.15s ease, color 0.15s ease, transform 0.15s ease;
}

.nav-link:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.nav-link.active {
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
}

.nav-icon {
  font-size: 18px;
}

.main-shell {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 24px;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: saturate(180%) blur(20px);
  color: #fff;
}

.topbar-left,
.topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-meta {
  display: grid;
  gap: 2px;
}

.page-title {
  color: #fff;
  font-size: 21px;
  font-weight: 600;
  letter-spacing: 0.231px;
  line-height: 1.19;
}

.page-subtitle {
  color: rgba(255, 255, 255, 0.64);
  font-size: 12px;
}

.icon-btn,
.user-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 36px;
  padding: 0 12px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
  cursor: pointer;
}

.icon-btn {
  width: 36px;
  padding: 0;
}

.user-chip {
  font-size: 14px;
}

.page-container {
  padding: 28px;
}

.mobile-only {
  display: none;
}

.drawer-shell {
  padding: 10px 4px;
}

.mobile-brand {
  padding-top: 0;
}

@media (max-width: 980px) {
  .shell {
    grid-template-columns: 1fr;
  }

  .desktop-sidebar {
    display: none;
  }

  .mobile-only {
    display: inline-flex;
  }

  .topbar {
    padding: 0 16px;
  }

  .page-container {
    padding: 18px 16px 24px;
  }
}

@media (max-width: 640px) {
  .topbar-right :deep(.n-tag) {
    display: none;
  }

  .user-chip span {
    display: none;
  }
}
</style>
