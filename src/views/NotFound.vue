<template>
  <div class="not-found-page">
    <div class="not-found-card">
      <div class="code">404</div>
      <h1>页面不存在</h1>
      <p>你访问的地址已经下线，或者当前后台不再保留这个入口。</p>
      <div class="actions">
        <n-button type="primary" @click="router.push('/admin/dashboard')">回到总览</n-button>
        <n-button @click="router.push('/login')">回到登录</n-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from "vue-router";

const router = useRouter();
</script>

<style scoped lang="scss">
.not-found-page {
  display: flex;
  min-height: 100vh;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: #f0f2f5;
}

.not-found-card {
  width: min(480px, 100%);
  padding: 40px 32px;
  text-align: center;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}

.code {
  color: #409eff;
  font-size: 72px;
  font-weight: 700;
  line-height: 1;
}

h1 {
  margin: 16px 0 12px;
  color: #303133;
  font-size: 28px;
  font-weight: 600;
}

p {
  margin: 0;
  color: #606266;
  line-height: 1.7;
}

.actions {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 24px;
}

@media (max-width: 640px) {
  .not-found-card {
    padding: 28px 20px;
  }

  .actions {
    flex-direction: column;
  }
}
</style>
