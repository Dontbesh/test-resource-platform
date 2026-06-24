import { defineStore } from 'pinia';

import { fetchHealth, type HealthResponse } from '@/api/health';

type HealthState = {
  data: HealthResponse | null;
  loading: boolean;
  error: string | null;
};

export const useHealthStore = defineStore('health', {
  state: (): HealthState => ({
    data: null,
    loading: false,
    error: null
  }),
  actions: {
    async load() {
      this.loading = true;
      this.error = null;
      try {
        this.data = await fetchHealth();
      } catch (error) {
        this.error = error instanceof Error ? error.message : '未知错误';
      } finally {
        this.loading = false;
      }
    }
  }
});
