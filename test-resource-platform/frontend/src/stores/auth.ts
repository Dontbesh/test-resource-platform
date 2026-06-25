import { defineStore } from 'pinia';

import {
  fetchCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
  type LoginRequest,
  type UserPublic
} from '@/api/auth';

type AuthState = {
  user: UserPublic | null;
  initialized: boolean;
  loading: boolean;
  error: string | null;
};

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    user: null,
    initialized: false,
    loading: false,
    error: null
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.user)
  },
  actions: {
    async initialize() {
      if (this.initialized) {
        return;
      }
      this.loading = true;
      try {
        this.user = await fetchCurrentUser();
      } catch {
        this.user = null;
      } finally {
        this.initialized = true;
        this.loading = false;
      }
    },
    async login(body: LoginRequest) {
      this.loading = true;
      this.error = null;
      try {
        this.user = await loginRequest(body);
        this.initialized = true;
      } catch (error) {
        this.user = null;
        this.error = error instanceof Error ? error.message : '登录失败';
        throw error;
      } finally {
        this.loading = false;
      }
    },
    async logout() {
      await logoutRequest();
      this.user = null;
      this.initialized = true;
    }
  }
});
