<template>
  <main class="login-page">
    <section class="login-panel">
      <div class="brand">
        <p class="eyebrow">Test Resource Platform</p>
        <h1>登录测试资源平台</h1>
      </div>

      <n-alert v-if="auth.error" type="error" title="登录失败">
        {{ auth.error }}
      </n-alert>

      <n-form :model="form" label-placement="top" @submit.prevent="submit">
        <n-form-item label="用户名">
          <n-input v-model:value="form.username" placeholder="请输入用户名" />
        </n-form-item>
        <n-form-item label="密码">
          <n-input
            v-model:value="form.password"
            placeholder="请输入密码"
            type="password"
            show-password-on="click"
          />
        </n-form-item>
        <n-button block type="primary" :loading="auth.loading" @click="submit">登录</n-button>
      </n-form>
    </section>
  </main>
</template>

<script setup lang="ts">
import { reactive } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useAuthStore } from '@/stores/auth';

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

const form = reactive({
  username: 'admin',
  password: ''
});

async function submit() {
  await auth.login({ username: form.username, password: form.password });
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/dashboard';
  await router.push(redirect);
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  background: #eef3f7;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.login-panel {
  width: min(420px, 100%);
  background: #ffffff;
  border: 1px solid #d8e1e8;
  border-radius: 8px;
  padding: 28px;
  box-shadow: 0 14px 34px rgba(31, 41, 55, 0.1);
}

.brand {
  margin-bottom: 24px;
}

.eyebrow {
  margin: 0 0 8px;
  color: #4b728f;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0;
}

h1 {
  margin: 0;
  font-size: 26px;
  letter-spacing: 0;
}
</style>
