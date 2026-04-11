<script setup>
import { darkTheme } from "naive-ui";
import { onErrorCaptured, onMounted, onUnmounted, ref } from "vue";

const themeOverrides = {
  common: {
    primaryColor: "#0071e3",
    primaryColorHover: "#2890ff",
    primaryColorPressed: "#005fc0",
    bodyColor: "#131313",
    cardColor: "#1b1b1b",
    modalColor: "#1b1b1b",
    popoverColor: "#17181c",
    tableColor: "#1b1b1b",
    borderColor: "rgba(255, 255, 255, 0.08)",
    baseColor: "#111214",
    inputColor: "#111214",
    actionColor: "rgba(255, 255, 255, 0.04)",
    textColorBase: "#f5f7fb",
    textColor1: "#f5f7fb",
    textColor2: "rgba(245, 247, 251, 0.72)",
    textColor3: "rgba(245, 247, 251, 0.52)",
    textColorDisabled: "rgba(245, 247, 251, 0.28)",
    placeholderColor: "rgba(245, 247, 251, 0.28)",
  },
  Input: {
    color: "#111214",
    colorFocus: "#111214",
    colorFocusError: "#111214",
    textColor: "#f5f7fb",
    placeholderColor: "rgba(245, 247, 251, 0.28)",
    border: "1px solid rgba(255, 255, 255, 0.08)",
    borderHover: "1px solid rgba(0, 113, 227, 0.48)",
    borderFocus: "1px solid #0071e3",
    boxShadowFocus: "0 0 0 2px rgba(0, 113, 227, 0.18)",
  },
  Button: {
    borderRadiusMedium: "999px",
    borderRadiusLarge: "999px",
  },
  Card: {
    color: "#1b1b1b",
    borderRadius: "20px",
  },
  Alert: {
    colorInfo: "#17181c",
    colorSuccess: "#14211a",
    colorWarning: "#241a0d",
    colorError: "#271416",
    borderInfo: "1px solid rgba(255, 255, 255, 0.08)",
    borderSuccess: "1px solid rgba(52, 211, 153, 0.24)",
    borderWarning: "1px solid rgba(245, 158, 11, 0.24)",
    borderError: "1px solid rgba(251, 113, 133, 0.24)",
  },
};

const runtimeError = ref("");

const applyRuntimeError = (value) => {
  const text = String(value || "").trim();
  const ignoredPatterns = [
    "ResizeObserver loop completed with undelivered notifications.",
    "ResizeObserver loop limit exceeded",
  ];
  if (!text || ignoredPatterns.some(pattern => text.includes(pattern)))
    return;
  if (text)
    runtimeError.value = text;
};

onErrorCaptured((error) => {
  applyRuntimeError(error instanceof Error ? error.stack || error.message : String(error));
  return false;
});

const handleWindowError = (event) => {
  applyRuntimeError(event?.error?.stack || event?.message || "Unknown runtime error");
};

const handleUnhandledRejection = (event) => {
  const reason = event?.reason;
  applyRuntimeError(reason instanceof Error ? reason.stack || reason.message : String(reason || "Unhandled rejection"));
};

onMounted(() => {
  window.addEventListener("error", handleWindowError);
  window.addEventListener("unhandledrejection", handleUnhandledRejection);
});

onUnmounted(() => {
  window.removeEventListener("error", handleWindowError);
  window.removeEventListener("unhandledrejection", handleUnhandledRejection);
});
</script>

<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">
    <n-message-provider :max="3">
      <n-loading-bar-provider>
        <n-notification-provider>
          <n-dialog-provider>
            <router-view></router-view>
            <div v-if="runtimeError" class="runtime-error-panel">
              <strong>Runtime Error</strong>
              <pre>{{ runtimeError }}</pre>
            </div>
          </n-dialog-provider>
        </n-notification-provider>
      </n-loading-bar-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<style>
html,
body,
#app {
  min-height: 100%;
}

html,
body {
  margin: 0;
  background: #131313;
  color: #f5f7fb;
}

* {
  box-sizing: border-box;
}

.runtime-error-panel {
  position: fixed;
  right: 16px;
  bottom: 16px;
  z-index: 9999;
  width: min(720px, calc(100vw - 32px));
  max-height: 40vh;
  overflow: auto;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(39, 20, 22, 0.96);
  border: 1px solid rgba(251, 113, 133, 0.34);
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.36);
  color: #ffe4e8;
  font: 12px/1.6 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.runtime-error-panel strong {
  display: block;
  margin-bottom: 8px;
}

.runtime-error-panel pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
