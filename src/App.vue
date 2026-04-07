<template>
  <n-config-provider :theme="naiveTheme">
    <n-message-provider :max="3">
      <n-loading-bar-provider>
        <n-notification-provider>
          <n-dialog-provider>
            <router-view></router-view>
          </n-dialog-provider>
        </n-notification-provider>
      </n-loading-bar-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup>
import { darkTheme } from "naive-ui";
import { computed, onMounted, onUnmounted } from "vue";

import { useTheme } from "@/composables/useTheme";

const { isDark, initTheme, setupSystemThemeListener, updateReactiveState } = useTheme();

const naiveTheme = computed(() => (isDark.value ? darkTheme : null));

const handleThemeChange = () => {
  updateReactiveState();
  window.setTimeout(() => {
    updateReactiveState();
  }, 50);
};

onMounted(() => {
  initTheme();
  setupSystemThemeListener();
  window.addEventListener("theme-change", handleThemeChange);
  updateReactiveState();
});

onUnmounted(() => {
  window.removeEventListener("theme-change", handleThemeChange);
});
</script>

<style>
html.dark,
html[data-theme="dark"] {
  color-scheme: dark;
}

html.dark .n-input__input-el,
html.dark .n-input__textarea-el,
html[data-theme="dark"] .n-input__input-el,
html[data-theme="dark"] .n-input__textarea-el {
  color: var(--text-primary) !important;
}

html.dark .n-input__placeholder,
html.dark ::placeholder,
html[data-theme="dark"] .n-input__placeholder,
html[data-theme="dark"] ::placeholder {
  color: var(--text-tertiary) !important;
}
</style>
