<template>
  <main class="users-page">
    <section class="users-shell">
      <div class="header">
        <div>
          <p class="eyebrow">Administration</p>
          <h1>用户管理</h1>
        </div>
        <n-space align="center">
          <n-button secondary @click="router.push('/dashboard')">
            <template #icon>
              <n-icon><ArrowLeft24Regular /></n-icon>
            </template>
            返回
          </n-button>
          <n-tag type="info">{{ auth.user?.role }}</n-tag>
          <span>{{ auth.user?.username }}</span>
        </n-space>
      </div>

      <n-form
        class="create-form"
        label-placement="top"
        :model="createForm"
        @submit.prevent="handleCreate"
      >
        <n-form-item label="用户名">
          <n-input v-model:value="createForm.username" placeholder="alice" />
        </n-form-item>
        <n-form-item label="初始密码">
          <n-input
            v-model:value="createForm.password"
            placeholder="至少 8 位"
            type="password"
            show-password-on="click"
          />
        </n-form-item>
        <n-form-item label="角色">
          <n-select v-model:value="createForm.role" :options="roleOptions" />
        </n-form-item>
        <n-form-item label=" ">
          <n-button type="primary" attr-type="submit" :loading="creating">
            <template #icon>
              <n-icon><PeopleAdd24Regular /></n-icon>
            </template>
            创建
          </n-button>
        </n-form-item>
      </n-form>

      <n-data-table
        :columns="columns"
        :data="users"
        :loading="loading"
        :row-key="rowKey"
      />

      <n-modal
        v-model:show="resetModalVisible"
        preset="dialog"
        title="重置密码"
        positive-text="保存"
        negative-text="取消"
        :positive-button-props="{ disabled: resetPassword.length < 8, loading: resetting }"
        @positive-click="handleResetPassword"
      >
        <n-space vertical>
          <span>{{ resetTarget?.username }}</span>
          <n-input
            v-model:value="resetPassword"
            type="password"
            show-password-on="click"
            placeholder="输入新密码"
          />
        </n-space>
      </n-modal>
    </section>
  </main>
</template>

<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue';
import { NButton, NIcon, NPopconfirm, NSpace, NTag, useMessage, type DataTableColumns } from 'naive-ui';
import {
  ArrowLeft24Regular,
  ArrowReset24Regular,
  DismissCircle24Regular,
  PeopleAdd24Regular
} from '@vicons/fluent';
import { useRouter } from 'vue-router';

import type { UserPublic, UserRole } from '@/api/auth';
import { createUser, disableUser, listUsers, resetUserPassword } from '@/api/users';
import { useAuthStore } from '@/stores/auth';

const auth = useAuthStore();
const router = useRouter();
const message = useMessage();

const users = ref<UserPublic[]>([]);
const loading = ref(false);
const creating = ref(false);
const resetting = ref(false);
const resetModalVisible = ref(false);
const resetTarget = ref<UserPublic | null>(null);
const resetPassword = ref('');

const createForm = reactive({
  username: '',
  password: '',
  role: 'TE' as UserRole
});

const roleOptions = [
  { label: 'TE', value: 'TE' },
  { label: 'TSE', value: 'TSE' },
  { label: 'ADMIN', value: 'ADMIN' }
];

const columns: DataTableColumns<UserPublic> = [
  {
    title: 'ID',
    key: 'id',
    width: 80
  },
  {
    title: '用户名',
    key: 'username'
  },
  {
    title: '角色',
    key: 'role',
    width: 120,
    render(row) {
      return h(NTag, { type: row.role === 'ADMIN' ? 'info' : 'default' }, { default: () => row.role });
    }
  },
  {
    title: '状态',
    key: 'is_active',
    width: 120,
    render(row) {
      return h(
        NTag,
        { type: row.is_active ? 'success' : 'error' },
        { default: () => (row.is_active ? '启用' : '禁用') }
      );
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 220,
    render(row) {
      return h(
        NSpace,
        { size: 8 },
        {
          default: () => [
            h(
              NButton,
              {
                size: 'small',
                secondary: true,
                onClick: () => openResetModal(row)
              },
              {
                icon: () => h(NIcon, null, { default: () => h(ArrowReset24Regular) }),
                default: () => '重置'
              }
            ),
            h(
              NPopconfirm,
              {
                disabled: !row.is_active,
                onPositiveClick: () => handleDisable(row)
              },
              {
                trigger: () =>
                  h(
                    NButton,
                    {
                      size: 'small',
                      type: 'error',
                      secondary: true,
                      disabled: !row.is_active
                    },
                    {
                      icon: () => h(NIcon, null, { default: () => h(DismissCircle24Regular) }),
                      default: () => '禁用'
                    }
                  ),
                default: () => `确认禁用用户 ${row.username}？`
              }
            )
          ]
        }
      );
    }
  }
];

function rowKey(row: UserPublic) {
  return row.id;
}

async function loadUsers() {
  loading.value = true;
  try {
    users.value = await listUsers();
  } catch (error) {
    message.error(error instanceof Error ? error.message : '加载用户失败');
  } finally {
    loading.value = false;
  }
}

async function handleCreate() {
  creating.value = true;
  try {
    await createUser({ ...createForm });
    createForm.username = '';
    createForm.password = '';
    createForm.role = 'TE';
    message.success('用户已创建');
    await loadUsers();
  } catch (error) {
    message.error(error instanceof Error ? error.message : '创建用户失败');
  } finally {
    creating.value = false;
  }
}

async function handleDisable(user: UserPublic) {
  try {
    await disableUser(user.id);
    message.success('用户已禁用');
    await loadUsers();
  } catch (error) {
    message.error(error instanceof Error ? error.message : '禁用用户失败');
  }
}

function openResetModal(user: UserPublic) {
  resetTarget.value = user;
  resetPassword.value = '';
  resetModalVisible.value = true;
}

async function handleResetPassword() {
  if (!resetTarget.value) {
    return false;
  }
  resetting.value = true;
  try {
    await resetUserPassword(resetTarget.value.id, { password: resetPassword.value });
    message.success('密码已重置');
    resetModalVisible.value = false;
    return true;
  } catch (error) {
    message.error(error instanceof Error ? error.message : '重置密码失败');
    return false;
  } finally {
    resetting.value = false;
  }
}

onMounted(loadUsers);
</script>

<style scoped>
.users-page {
  min-height: 100vh;
  background: #f4f6f8;
  color: #1f2937;
  padding: 48px 24px;
}

.users-shell {
  width: min(1120px, 100%);
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

.create-form {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) minmax(180px, 1fr) 140px auto;
  gap: 16px;
  align-items: end;
  margin-bottom: 24px;
}

@media (max-width: 820px) {
  .users-page {
    padding: 24px 12px;
  }

  .users-shell {
    padding: 20px;
  }

  .header {
    align-items: flex-start;
    flex-direction: column;
  }

  .create-form {
    grid-template-columns: 1fr;
  }
}
</style>
