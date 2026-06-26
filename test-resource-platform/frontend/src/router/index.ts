import { createRouter, createWebHistory } from 'vue-router';

import DashboardView from '@/views/DashboardView.vue';
import HealthView from '@/views/HealthView.vue';
import LoginView from '@/views/LoginView.vue';
import ResourceInventoryView from '@/views/ResourceInventoryView.vue';
import UserManagementView from '@/views/UserManagementView.vue';
import { useAuthStore } from '@/stores/auth';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/dashboard'
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: DashboardView,
      meta: { requiresAuth: true }
    },
    {
      path: '/users',
      name: 'users',
      component: UserManagementView,
      meta: { requiresAuth: true, roles: ['ADMIN'] }
    },
    {
      path: '/resources',
      name: 'resources',
      component: ResourceInventoryView,
      meta: { requiresAuth: true }
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView
    },
    {
      path: '/health',
      name: 'health',
      component: HealthView
    }
  ]
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  await auth.initialize();

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } };
  }

  const allowedRoles = to.meta.roles as string[] | undefined;
  if (allowedRoles && (!auth.user || !allowedRoles.includes(auth.user.role))) {
    return { name: 'dashboard' };
  }

  if (to.name === 'login' && auth.isAuthenticated) {
    return { name: 'dashboard' };
  }

  return true;
});

export default router;
