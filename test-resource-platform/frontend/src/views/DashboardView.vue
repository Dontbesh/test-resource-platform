<template>
  <main class="dashboard-page">
    <section class="dashboard-shell">
      <div class="header">
        <div>
          <p class="eyebrow">Signed in</p>
          <h1>后台首页</h1>
        </div>
        <n-space align="center">
          <n-button secondary @click="router.push('/resources')">
            <template #icon>
              <n-icon><Server24Regular /></n-icon>
            </template>
            资源台账
          </n-button>
          <n-button v-if="auth.user?.role === 'ADMIN'" secondary @click="router.push('/users')">
            <template #icon>
              <n-icon><People24Regular /></n-icon>
            </template>
            用户管理
          </n-button>
          <n-tag type="info">{{ auth.user?.role }}</n-tag>
          <span>{{ auth.user?.username }}</span>
          <n-button secondary @click="handleLogout">登出</n-button>
        </n-space>
      </div>

      <n-alert type="success" title="登录链路已跑通">
        当前页面由 HttpOnly Cookie 会话保护，刷新页面后会通过 /api/v1/auth/me 重新确认登录状态。
      </n-alert>
    </section>
  </main>
</template>

<script setup lang="ts">
import { People24Regular, Server24Regular } from '@vicons/fluent';
import { useRouter } from 'vue-router';

import { useAuthStore } from '@/stores/auth';

const auth = useAuthStore();
const router = useRouter();

async function handleLogout() {
  await auth.logout();
  await router.push('/login');
}
</script>

<style scoped>
.dashboard-page {
  min-height: 100vh;
  background: #f4f6f8;
  color: #1f2937;
  padding: 48px 24px;
}

.dashboard-shell {
  width: min(1080px, 100%);
  margin: 0 auto;
  background: #ffffff;
  border: 1px solid #d9e1e8;
  border-radius: 8px;
  padding: 28px;
  box-shadow: 0 12px 28px rgba(31, 41, 55, 0.08);
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}

.eyebrow {
  margin: 0 0 6px;
  color: #4b728f;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0;
}

h1 {
  margin: 0;
  font-size: 28px;
  letter-spacing: 0;
}
</style>
