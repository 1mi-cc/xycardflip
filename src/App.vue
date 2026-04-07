<template>
  <n-config-provider>
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

<style>
html,
body,
#app {
  min-height: 100%;
}

html,
body {
  margin: 0;
  background: #f0f2f5;
  color: #303133;
}

* {
  box-sizing: border-box;
}

body {
  font-family:
    "Helvetica Neue",
    Helvetica,
    "PingFang SC",
    "Hiragino Sans GB",
    "Microsoft YaHei",
    Arial,
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

a {
  color: inherit;
}

::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: #f0f2f5;
}

::-webkit-scrollbar-thumb {
  background: #c0c4cc;
  border-radius: 999px;
}

::-webkit-scrollbar-thumb:hover {
  background: #909399;
}
</style>
