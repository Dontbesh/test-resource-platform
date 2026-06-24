<template>
  <main class="page">
    <section class="shell">
      <div class="header">
        <div>
          <p class="eyebrow">Phase 1 Tracer</p>
          <h1>测试资源平台</h1>
        </div>
        <n-button type="primary" :loading="health.loading" @click="health.load">刷新</n-button>
      </div>

      <n-alert v-if="health.error" type="error" title="API 连接失败">
        {{ health.error }}
      </n-alert>

      <n-grid v-else :cols="4" :x-gap="16" :y-gap="16" responsive="screen">
        <n-grid-item>
          <n-statistic label="API 状态" :value="health.data?.status ?? '-'" />
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="数据库" :value="health.data?.database.status ?? '-'" />
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="版本" :value="health.data?.version ?? '-'" />
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="Request ID" :value="health.data?.request_id ?? '-'" />
        </n-grid-item>
      </n-grid>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';

import { useHealthStore } from '@/stores/health';

const health = useHealthStore();

onMounted(() => {
  void health.load();
});
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f4f6f8;
  color: #1f2937;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 48px 24px;
}

.shell {
  width: min(1080px, 100%);
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
  font-weight: 700;
  letter-spacing: 0;
}
</style>
