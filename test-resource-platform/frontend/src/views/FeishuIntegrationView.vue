<template>
  <main class="feishu-page">
    <section class="feishu-shell">
      <div class="header">
        <div>
          <p class="eyebrow">Integrations</p>
          <h1>飞书接入</h1>
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

      <div class="setup-grid">
        <section class="setup-panel">
          <div class="panel-header">
            <div>
              <h2>扫码配置应用</h2>
              <p>用飞书手机端扫码后，平台会保存应用凭据。</p>
            </div>
            <n-button type="primary" :loading="phase === 'loading'" @click="startSetup">
              <template #icon>
                <n-icon><QrCode24Regular /></n-icon>
              </template>
              开始扫码
            </n-button>
          </div>

          <div v-if="phase === 'idle'" class="empty-state">
            <n-icon size="42"><PlugConnected24Regular /></n-icon>
            <span>点击开始后生成飞书授权二维码。</span>
          </div>

          <div v-else-if="setupSession" class="qr-area">
            <div class="qr-frame">
              <img :src="qrImageUrl" alt="Feishu setup QR code" />
            </div>
            <n-space vertical size="small" class="qr-info">
              <n-tag :type="phaseTagType">{{ phaseText }}</n-tag>
              <span>过期时间：{{ formatDateTime(setupSession.expires_at) }}</span>
              <n-button tag="a" :href="setupSession.qr_url" target="_blank" secondary>
                打开扫码链接
              </n-button>
              <n-input :value="setupSession.qr_url" readonly />
            </n-space>
          </div>

          <n-alert v-if="error" type="error" title="配置失败" class="status-alert">
            {{ error }}
          </n-alert>
          <n-alert v-if="savedApp" type="success" title="应用已保存" class="status-alert">
            {{ savedApp.name }} 已保存，后续可以继续开发 WebSocket 长连接和飞书命令。
          </n-alert>
        </section>

        <section class="apps-panel">
          <div class="panel-header">
            <div>
              <h2>已配置应用</h2>
              <p>当前版本只保存应用配置，暂不启动长连接。</p>
            </div>
            <n-button secondary :loading="loadingApps" @click="loadApps">刷新</n-button>
          </div>
          <n-data-table :columns="columns" :data="apps" :loading="loadingApps" :row-key="rowKey" />
        </section>
      </div>

      <section class="bindings-panel">
        <div class="panel-header">
          <div>
            <h2>用户绑定</h2>
            <p>把飞书 open_id 绑定到平台用户后，飞书资源命令才能执行。</p>
          </div>
          <n-button secondary :loading="loadingBindings" :disabled="!selectedAppId" @click="loadBindings">
            刷新
          </n-button>
        </div>
        <div class="binding-form">
          <n-select
            v-model:value="selectedAppId"
            :options="appOptions"
            placeholder="选择飞书应用"
            @update:value="loadBindings"
          />
          <n-input v-model:value="bindingForm.open_id" placeholder="飞书 open_id" />
          <n-input v-model:value="bindingForm.platform_username" placeholder="平台用户名" />
          <n-input v-model:value="bindingForm.display_name" placeholder="显示名（可选）" />
          <n-button type="primary" :loading="savingBinding" :disabled="!selectedAppId" @click="saveBinding">
            保存绑定
          </n-button>
        </div>
        <n-data-table
          :columns="bindingColumns"
          :data="bindings"
          :loading="loadingBindings"
          :row-key="bindingRowKey"
        />
      </section>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, h, onBeforeUnmount, onMounted, ref } from 'vue';
import { NButton, NTag, useMessage, type DataTableColumns } from 'naive-ui';
import { ArrowLeft24Regular, PlugConnected24Regular, QrCode24Regular } from '@vicons/fluent';
import { useRouter } from 'vue-router';

import {
  beginFeishuSetup,
  checkFeishuAppConnection,
  createFeishuUserBinding,
  deleteFeishuUserBinding,
  listFeishuApps,
  listFeishuUserBindings,
  pollFeishuSetup,
  saveFeishuSetup,
  type FeishuAppPublic,
  type FeishuSetupBeginResponse,
  type FeishuSetupStatus,
  type FeishuUserBindingPublic
} from '@/api/feishuIntegration';
import { useAuthStore } from '@/stores/auth';

type Phase = 'idle' | 'loading' | 'scanning' | 'saving' | 'completed' | 'denied' | 'expired' | 'error';

const auth = useAuthStore();
const router = useRouter();
const message = useMessage();

const phase = ref<Phase>('idle');
const setupSession = ref<FeishuSetupBeginResponse | null>(null);
const baseUrl = ref<string | undefined>();
const intervalSeconds = ref(5);
const error = ref('');
const savedApp = ref<FeishuAppPublic | null>(null);
const apps = ref<FeishuAppPublic[]>([]);
const loadingApps = ref(false);
const checkingAppIds = ref(new Set<number>());
const selectedAppId = ref<number | null>(null);
const bindings = ref<FeishuUserBindingPublic[]>([]);
const loadingBindings = ref(false);
const savingBinding = ref(false);
const deletingBindingIds = ref(new Set<number>());
const bindingForm = ref({
  open_id: '',
  platform_username: '',
  display_name: ''
});
let pollTimer: number | undefined;

const qrImageUrl = computed(() => {
  const url = setupSession.value?.qr_url ?? '';
  return `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(url)}`;
});

const phaseText = computed(() => {
  switch (phase.value) {
    case 'loading':
      return '正在生成二维码';
    case 'scanning':
      return '等待扫码确认';
    case 'saving':
      return '正在保存应用配置';
    case 'completed':
      return '配置完成';
    case 'denied':
      return '用户已拒绝授权';
    case 'expired':
      return '二维码已过期';
    case 'error':
      return '配置出错';
    default:
      return '未开始';
  }
});

const phaseTagType = computed(() => {
  if (phase.value === 'completed') {
    return 'success';
  }
  if (phase.value === 'denied' || phase.value === 'expired' || phase.value === 'error') {
    return 'error';
  }
  return 'info';
});

const appOptions = computed(() =>
  apps.value.map((app) => ({
    label: `${app.name} (${app.app_id})`,
    value: app.id
  }))
);

const columns: DataTableColumns<FeishuAppPublic> = [
  { title: 'ID', key: 'id', width: 80 },
  { title: '名称', key: 'name' },
  {
    title: '平台',
    key: 'platform_type',
    width: 110,
    render(row) {
      return h(NTag, null, { default: () => row.platform_type });
    }
  },
  { title: 'App ID', key: 'app_id' },
  {
    title: '状态',
    key: 'status',
    width: 120,
    render(row) {
      const type = row.status === 'ERROR' ? 'error' : row.status === 'CONNECTED' ? 'success' : 'default';
      return h(NTag, { type }, { default: () => row.status });
    }
  },
  {
    title: '创建时间',
    key: 'created_at',
    render(row) {
      return formatDateTime(row.created_at);
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 130,
    render(row) {
      return h(
        NButton,
        {
          size: 'small',
          secondary: true,
          loading: checkingAppIds.value.has(row.id),
          onClick: () => checkConnection(row.id)
        },
        { default: () => '检查连接' }
      );
    }
  }
];

const bindingColumns: DataTableColumns<FeishuUserBindingPublic> = [
  { title: 'Open ID', key: 'open_id' },
  {
    title: '平台用户',
    key: 'platform_user',
    render(row) {
      return `${row.platform_user.username} (${row.platform_user.role})`;
    }
  },
  {
    title: '显示名',
    key: 'display_name',
    render(row) {
      return row.display_name ?? '-';
    }
  },
  {
    title: '创建时间',
    key: 'created_at',
    render(row) {
      return formatDateTime(row.created_at);
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    render(row) {
      return h(
        NButton,
        {
          size: 'small',
          tertiary: true,
          type: 'error',
          loading: deletingBindingIds.value.has(row.id),
          onClick: () => deleteBinding(row.id)
        },
        { default: () => '删除' }
      );
    }
  }
];

function rowKey(row: FeishuAppPublic) {
  return row.id;
}

function bindingRowKey(row: FeishuUserBindingPublic) {
  return row.id;
}

async function startSetup() {
  clearPollTimer();
  phase.value = 'loading';
  error.value = '';
  savedApp.value = null;
  try {
    setupSession.value = await beginFeishuSetup();
    intervalSeconds.value = setupSession.value.interval || 5;
    baseUrl.value = undefined;
    phase.value = 'scanning';
    schedulePoll();
  } catch (err) {
    phase.value = 'error';
    error.value = err instanceof Error ? err.message : '生成二维码失败';
  }
}

function schedulePoll() {
  clearPollTimer();
  pollTimer = window.setTimeout(pollSetup, intervalSeconds.value * 1000);
}

async function pollSetup() {
  if (!setupSession.value || phase.value !== 'scanning') {
    return;
  }
  try {
    const response = await pollFeishuSetup(setupSession.value.device_code, baseUrl.value);
    baseUrl.value = response.base_url;
    if (response.slow_down) {
      intervalSeconds.value += 5;
    }
    await handlePollStatus(response.status, response);
  } catch (err) {
    phase.value = 'error';
    error.value = err instanceof Error ? err.message : '轮询扫码状态失败';
  }
}

async function handlePollStatus(status: FeishuSetupStatus, response: Awaited<ReturnType<typeof pollFeishuSetup>>) {
  if (status === 'PENDING') {
    schedulePoll();
    return;
  }
  clearPollTimer();
  if (status === 'DENIED') {
    phase.value = 'denied';
    return;
  }
  if (status === 'EXPIRED') {
    phase.value = 'expired';
    return;
  }
  if (status === 'ERROR') {
    phase.value = 'error';
    error.value = response.error ?? '飞书返回未知错误';
    return;
  }
  if (!response.app_id || !response.app_secret || !response.platform) {
    phase.value = 'error';
    error.value = '飞书返回的应用凭据不完整';
    return;
  }
  phase.value = 'saving';
  savedApp.value = await saveFeishuSetup({
    name: '飞书资源助手',
    platform_type: response.platform,
    app_id: response.app_id,
    app_secret: response.app_secret,
    owner_open_id: response.owner_open_id,
    tenant_brand: response.platform.toLowerCase()
  });
  phase.value = 'completed';
  message.success('飞书应用配置已保存');
  await loadApps();
}

async function loadApps() {
  loadingApps.value = true;
  try {
    apps.value = await listFeishuApps();
    if (!selectedAppId.value && apps.value.length > 0) {
      selectedAppId.value = apps.value[0].id;
      await loadBindings();
    }
  } catch (err) {
    message.error(err instanceof Error ? err.message : '加载飞书应用失败');
  } finally {
    loadingApps.value = false;
  }
}

async function loadBindings() {
  if (!selectedAppId.value) {
    bindings.value = [];
    return;
  }
  loadingBindings.value = true;
  try {
    bindings.value = await listFeishuUserBindings(selectedAppId.value);
  } catch (err) {
    message.error(err instanceof Error ? err.message : '加载飞书用户绑定失败');
  } finally {
    loadingBindings.value = false;
  }
}

async function saveBinding() {
  if (!selectedAppId.value) {
    return;
  }
  if (!bindingForm.value.open_id.trim() || !bindingForm.value.platform_username.trim()) {
    message.error('请填写飞书 open_id 和平台用户名');
    return;
  }
  savingBinding.value = true;
  try {
    await createFeishuUserBinding(selectedAppId.value, {
      open_id: bindingForm.value.open_id.trim(),
      platform_username: bindingForm.value.platform_username.trim(),
      display_name: bindingForm.value.display_name.trim() || null
    });
    bindingForm.value = { open_id: '', platform_username: '', display_name: '' };
    message.success('飞书用户绑定已保存');
    await loadBindings();
  } catch (err) {
    message.error(err instanceof Error ? err.message : '保存飞书用户绑定失败');
  } finally {
    savingBinding.value = false;
  }
}

async function deleteBinding(bindingId: number) {
  deletingBindingIds.value = new Set(deletingBindingIds.value).add(bindingId);
  try {
    await deleteFeishuUserBinding(bindingId);
    message.success('飞书用户绑定已删除');
    await loadBindings();
  } catch (err) {
    message.error(err instanceof Error ? err.message : '删除飞书用户绑定失败');
  } finally {
    const next = new Set(deletingBindingIds.value);
    next.delete(bindingId);
    deletingBindingIds.value = next;
  }
}

async function checkConnection(appId: number) {
  checkingAppIds.value = new Set(checkingAppIds.value).add(appId);
  try {
    const updated = await checkFeishuAppConnection(appId);
    apps.value = apps.value.map((app) => (app.id === appId ? updated : app));
    message.success('飞书应用连接检查通过');
  } catch (err) {
    message.error(err instanceof Error ? err.message : '飞书应用连接检查失败');
    await loadApps();
  } finally {
    const next = new Set(checkingAppIds.value);
    next.delete(appId);
    checkingAppIds.value = next;
  }
}

function clearPollTimer() {
  if (pollTimer !== undefined) {
    window.clearTimeout(pollTimer);
    pollTimer = undefined;
  }
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString();
}

onMounted(loadApps);
onBeforeUnmount(clearPollTimer);
</script>

<style scoped>
.feishu-page {
  min-height: 100vh;
  background: #f4f6f8;
  color: #1f2937;
  padding: 48px 24px;
}

.feishu-shell {
  width: min(1180px, 100%);
  margin: 0 auto;
  background: #ffffff;
  border: 1px solid #d9e1e8;
  border-radius: 8px;
  padding: 28px;
  box-shadow: 0 12px 28px rgba(31, 41, 55, 0.08);
}

.header,
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.header {
  margin-bottom: 24px;
}

.eyebrow {
  margin: 0 0 6px;
  color: #4b728f;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0;
}

h1,
h2,
p {
  letter-spacing: 0;
}

h1 {
  margin: 0;
  font-size: 28px;
}

h2 {
  margin: 0 0 6px;
  font-size: 18px;
}

p {
  margin: 0;
  color: #607083;
}

.setup-grid {
  display: grid;
  grid-template-columns: minmax(320px, 420px) minmax(0, 1fr);
  gap: 20px;
}

.setup-panel,
.apps-panel,
.bindings-panel {
  border: 1px solid #d9e1e8;
  border-radius: 8px;
  padding: 20px;
}

.bindings-panel {
  margin-top: 20px;
}

.binding-form {
  display: grid;
  grid-template-columns: minmax(180px, 1.2fr) minmax(160px, 1fr) minmax(140px, 0.8fr) minmax(140px, 0.8fr) auto;
  gap: 12px;
  margin: 18px 0;
}

.empty-state,
.qr-area {
  margin-top: 22px;
}

.empty-state {
  min-height: 260px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 12px;
  color: #607083;
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
}

.qr-area {
  display: grid;
  gap: 16px;
}

.qr-frame {
  display: flex;
  justify-content: center;
  padding: 18px;
  border: 1px solid #d9e1e8;
  border-radius: 8px;
  background: #ffffff;
}

.qr-frame img {
  width: 220px;
  height: 220px;
}

.qr-info {
  word-break: break-all;
}

.status-alert {
  margin-top: 16px;
}

@media (max-width: 980px) {
  .feishu-page {
    padding: 24px 12px;
  }

  .feishu-shell {
    padding: 20px;
  }

  .header,
  .panel-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .setup-grid {
    grid-template-columns: 1fr;
  }

  .binding-form {
    grid-template-columns: 1fr;
  }
}
</style>
