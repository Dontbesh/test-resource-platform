<template>
  <main class="inventory-page">
    <section class="inventory-shell">
      <div class="header">
        <div>
          <p class="eyebrow">Resource Inventory</p>
          <h1>资源台账</h1>
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

      <n-tabs type="line" animated>
        <n-tab-pane name="pools" tab="资源池">
          <n-form
            v-if="canMaintain"
            class="pool-form"
            label-placement="top"
            :model="poolForm"
            @submit.prevent="handleCreatePool"
          >
            <n-form-item label="名称">
              <n-input v-model:value="poolForm.name" placeholder="lab-a" />
            </n-form-item>
            <n-form-item label="网络区域">
              <n-input v-model:value="poolForm.network_zone" placeholder="intranet-a" />
            </n-form-item>
            <n-form-item label="说明">
              <n-input v-model:value="poolForm.description" placeholder="用途或实验室位置" />
            </n-form-item>
            <n-form-item label=" ">
              <n-button type="primary" attr-type="submit" :loading="creatingPool">
                <template #icon>
                  <n-icon><Database24Regular /></n-icon>
                </template>
                创建资源池
              </n-button>
            </n-form-item>
          </n-form>

          <n-data-table
            :columns="poolColumns"
            :data="pools"
            :loading="loading"
            :row-key="poolRowKey"
          />
        </n-tab-pane>

        <n-tab-pane name="machines" tab="机器">
          <n-form
            v-if="canMaintain"
            class="machine-form"
            label-placement="top"
            :model="machineForm"
            @submit.prevent="handleCreateMachine"
          >
            <n-form-item label="资源编号">
              <n-input v-model:value="machineForm.resource_code" placeholder="SN-PHY-001" />
            </n-form-item>
            <n-form-item label="名称">
              <n-input v-model:value="machineForm.name" placeholder="phy-001" />
            </n-form-item>
            <n-form-item label="类型">
              <n-select v-model:value="machineForm.resource_type" :options="resourceTypeOptions" />
            </n-form-item>
            <n-form-item label="资源池">
              <n-select
                v-model:value="machineForm.pool_id"
                :options="poolOptions"
                placeholder="选择资源池"
              />
            </n-form-item>
            <n-form-item label="架构">
              <n-input v-model:value="machineForm.architecture" placeholder="x86_64" />
            </n-form-item>
            <n-form-item label="操作系统">
              <n-input v-model:value="machineForm.os_name" placeholder="Ubuntu 22.04" />
            </n-form-item>
            <n-form-item label="IP">
              <n-input v-model:value="machineForm.ip_address" placeholder="192.168.10.11" />
            </n-form-item>
            <n-form-item label="标签">
              <n-input v-model:value="tagsText" placeholder="smoke, linux" />
            </n-form-item>
            <n-form-item label=" ">
              <n-button type="primary" attr-type="submit" :loading="creatingMachine">
                <template #icon>
                  <n-icon><Desktop24Regular /></n-icon>
                </template>
                登记机器
              </n-button>
            </n-form-item>
          </n-form>

          <n-data-table
            :columns="machineColumns"
            :data="machines"
            :loading="loading"
            :row-key="machineRowKey"
          />
        </n-tab-pane>

        <n-tab-pane name="leases" tab="我的租约">
          <n-data-table
            :columns="leaseColumns"
            :data="leases"
            :loading="loading"
            :row-key="leaseRowKey"
          />
        </n-tab-pane>
      </n-tabs>

      <n-modal v-model:show="leaseModalVisible" preset="card" class="lease-modal" title="占用机器">
        <n-form label-placement="top" :model="leaseForm" @submit.prevent="handleCreateLease">
          <n-form-item label="机器">
            <n-input :value="selectedMachine?.resource_code ?? ''" disabled />
          </n-form-item>
          <n-form-item label="租期（分钟）">
            <n-input-number
              v-model:value="leaseForm.duration_minutes"
              :min="1"
              :max="1440"
              :step="30"
              class="full-width"
            />
          </n-form-item>
          <n-form-item label="用途">
            <n-input
              v-model:value="leaseForm.purpose"
              type="textarea"
              placeholder="例如：调试网络连通性"
            />
          </n-form-item>
          <n-space justify="end">
            <n-button @click="leaseModalVisible = false">取消</n-button>
            <n-button type="primary" attr-type="submit" :loading="leasing">占用</n-button>
          </n-space>
        </n-form>
      </n-modal>

      <n-modal
        v-model:show="credentialModalVisible"
        preset="card"
        class="credential-modal"
        title="配置凭据"
      >
        <n-form
          label-placement="top"
          :model="credentialForm"
          @submit.prevent="handleConfigureCredentials"
        >
          <n-form-item label="机器">
            <n-input :value="selectedCredentialMachine?.resource_code ?? ''" disabled />
          </n-form-item>
          <n-form-item label="SSH 用户">
            <n-input v-model:value="credentialForm.ssh_username" placeholder="root" />
          </n-form-item>
          <n-form-item label="SSH 密码">
            <n-input
              v-model:value="credentialForm.ssh_password"
              type="password"
              show-password-on="click"
            />
          </n-form-item>
          <n-form-item label="BMC 用户">
            <n-input v-model:value="credentialForm.bmc_username" placeholder="Administrator" />
          </n-form-item>
          <n-form-item label="BMC 密码">
            <n-input
              v-model:value="credentialForm.bmc_password"
              type="password"
              show-password-on="click"
            />
          </n-form-item>
          <n-space justify="end">
            <n-button @click="credentialModalVisible = false">取消</n-button>
            <n-button type="primary" attr-type="submit" :loading="savingCredentials">保存</n-button>
          </n-space>
        </n-form>
      </n-modal>

      <n-modal
        v-model:show="credentialViewModalVisible"
        preset="card"
        class="credential-modal"
        title="查看凭据"
      >
        <n-form v-if="credentialSecret" label-placement="top">
          <n-form-item label="机器">
            <n-input :value="credentialSecret.resource_code" disabled />
          </n-form-item>
          <n-form-item label="SSH 用户">
            <n-input :value="credentialSecret.ssh_username ?? ''" disabled />
          </n-form-item>
          <n-form-item label="SSH 密码">
            <n-input :value="credentialSecret.ssh_password ?? ''" readonly />
          </n-form-item>
          <n-form-item label="BMC 用户">
            <n-input :value="credentialSecret.bmc_username ?? ''" disabled />
          </n-form-item>
          <n-form-item label="BMC 密码">
            <n-input :value="credentialSecret.bmc_password ?? ''" readonly />
          </n-form-item>
        </n-form>
      </n-modal>

      <n-modal
        v-model:show="connectivityModalVisible"
        preset="card"
        class="connectivity-modal"
        title="连通性检查"
      >
        <n-data-table
          :columns="connectivityColumns"
          :data="connectivityChecks"
          :row-key="connectivityRowKey"
        />
      </n-modal>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue';
import { NButton, NIcon, NPopconfirm, NSpace, NTag, useMessage, type DataTableColumns } from 'naive-ui';
import {
  ArrowLeft24Regular,
  Database24Regular,
  Desktop24Regular,
  DismissCircle24Regular,
  PlayCircle24Regular
} from '@vicons/fluent';
import { useRouter } from 'vue-router';

import {
  createMachine,
  createResourcePool,
  disableMachine,
  disableResourcePool,
  enableMachine,
  enableResourcePool,
  listMachines,
  listResourcePools,
  type MachineResourcePublic,
  type ResourcePoolPublic,
  type ResourceType
} from '@/api/resourceInventory';
import {
  createResourceLease,
  listMyLeases,
  releaseResourceLease,
  type ResourceLeasePublic
} from '@/api/resourceLeases';
import {
  configureMachineCredentials,
  getMachineCredentials,
  type MachineCredentialSecret
} from '@/api/machineCredentials';
import {
  runMachineConnectivityCheck,
  type ConnectivityCheckResult
} from '@/api/connectivityChecks';
import { useAuthStore } from '@/stores/auth';

const auth = useAuthStore();
const router = useRouter();
const message = useMessage();

const pools = ref<ResourcePoolPublic[]>([]);
const machines = ref<MachineResourcePublic[]>([]);
const leases = ref<ResourceLeasePublic[]>([]);
const loading = ref(false);
const creatingPool = ref(false);
const creatingMachine = ref(false);
const leasing = ref(false);
const releasingLeaseId = ref<string | null>(null);
const leaseModalVisible = ref(false);
const selectedMachine = ref<MachineResourcePublic | null>(null);
const credentialModalVisible = ref(false);
const credentialViewModalVisible = ref(false);
const connectivityModalVisible = ref(false);
const selectedCredentialMachine = ref<MachineResourcePublic | null>(null);
const credentialSecret = ref<MachineCredentialSecret | null>(null);
const connectivityChecks = ref<ConnectivityCheckResult[]>([]);
const savingCredentials = ref(false);
const viewingCredentialCode = ref<string | null>(null);
const checkingConnectivityCode = ref<string | null>(null);
const tagsText = ref('');

const canMaintain = computed(() => auth.user?.role === 'ADMIN' || auth.user?.role === 'TSE');

const poolForm = reactive({
  name: '',
  description: '',
  location: '',
  network_zone: ''
});

const machineForm = reactive({
  resource_code: '',
  name: '',
  resource_type: 'PHYSICAL' as ResourceType,
  pool_id: null as number | null,
  architecture: '',
  os_name: '',
  ip_address: ''
});

const leaseForm = reactive({
  duration_minutes: 60,
  purpose: ''
});

const credentialForm = reactive({
  ssh_username: '',
  ssh_password: '',
  bmc_username: '',
  bmc_password: ''
});

const resourceTypeOptions = [
  { label: '物理机', value: 'PHYSICAL' },
  { label: '虚拟机', value: 'VIRTUAL' }
];

const poolOptions = computed(() =>
  pools.value.map((pool) => ({
    label: pool.name,
    value: pool.id
  }))
);

const poolColumns: DataTableColumns<ResourcePoolPublic> = [
  { title: 'ID', key: 'id', width: 80 },
  { title: '名称', key: 'name' },
  { title: '网络区域', key: 'network_zone' },
  { title: '说明', key: 'description' },
  {
    title: '状态',
    key: 'is_active',
    width: 110,
    render(row) {
      return h(
        NTag,
        { type: row.is_active ? 'success' : 'error' },
        { default: () => (row.is_active ? '启用' : '停用') }
      );
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 130,
    render(row) {
      if (!canMaintain.value) {
        return null;
      }
      return renderToggleButton(
        row.is_active,
        `确认停用资源池 ${row.name}？`,
        () => handleDisablePool(row),
        () => handleEnablePool(row)
      );
    }
  }
];

const machineColumns: DataTableColumns<MachineResourcePublic> = [
  { title: 'ID', key: 'id', width: 80 },
  { title: '资源编号', key: 'resource_code' },
  { title: '名称', key: 'name' },
  {
    title: '类型',
    key: 'resource_type',
    width: 110,
    render(row) {
      return h(NTag, null, { default: () => (row.resource_type === 'PHYSICAL' ? '物理机' : '虚拟机') });
    }
  },
  {
    title: '资源池',
    key: 'pool_id',
    render(row) {
      return poolName(row.pool_id);
    }
  },
  {
    title: '状态',
    key: 'admin_status',
    width: 110,
    render(row) {
      const pool = findPool(row.pool_id);
      if (pool && !pool.is_active) {
        return h(NTag, { type: 'error' }, { default: () => '资源池停用' });
      }
      return h(
        NTag,
        { type: row.admin_status === 'ACTIVE' ? 'success' : 'warning' },
        { default: () => row.admin_status }
      );
    }
  },
  {
    title: '占用状态',
    key: 'occupancy_status',
    width: 110,
    render(row) {
      return h(
        NTag,
        { type: row.occupancy_status === 'OCCUPIED' ? 'warning' : 'success' },
        { default: () => (row.occupancy_status === 'OCCUPIED' ? '已占用' : '空闲') }
      );
    }
  },
  {
    title: '使用人',
    key: 'leased_by_username',
    width: 120,
    render(row) {
      return row.leased_by_username ?? '-';
    }
  },
  { title: 'IP', key: 'ip_address' },
  {
    title: '标签',
    key: 'tags',
    render(row) {
      return row.tags.join(', ');
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 360,
    render(row) {
      const actions = [
        renderLeaseButton(row),
        renderCredentialViewButton(row),
        renderConnectivityButton(row)
      ];
      if (canMaintain.value) {
        actions.push(renderCredentialConfigButton(row));
        actions.push(
          renderToggleButton(
            row.admin_status !== 'DISABLED',
            `确认停用机器 ${row.resource_code}？`,
            () => handleDisableMachine(row),
            () => handleEnableMachine(row),
            isMachinePoolDisabled(row)
          )
        );
      }
      return h(NSpace, { size: 8 }, { default: () => actions });
    }
  }
];

const leaseColumns: DataTableColumns<ResourceLeasePublic> = [
  { title: '租约编号', key: 'lease_id', minWidth: 180 },
  {
    title: '机器',
    key: 'machine',
    render(row) {
      return row.machine.resource_code;
    }
  },
  { title: '用途', key: 'purpose', ellipsis: { tooltip: true } },
  {
    title: '状态',
    key: 'status',
    width: 110,
    render(row) {
      const tagType =
        row.status === 'ACTIVE' ? 'success' : row.status === 'EXPIRED' ? 'warning' : 'default';
      return h(NTag, { type: tagType }, { default: () => row.status });
    }
  },
  {
    title: '开始时间',
    key: 'started_at',
    render(row) {
      return formatDateTime(row.started_at);
    }
  },
  {
    title: '结束时间',
    key: 'expires_at',
    render(row) {
      return formatDateTime(row.expires_at);
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    render(row) {
      if (row.status !== 'ACTIVE') {
        return null;
      }
      return h(
        NPopconfirm,
        {
          onPositiveClick: () => handleReleaseLease(row)
        },
        {
          trigger: () =>
            h(
              NButton,
              {
                size: 'small',
                type: 'error',
                secondary: true,
                loading: releasingLeaseId.value === row.lease_id
              },
              { default: () => '释放' }
            ),
          default: () => `确认释放租约 ${row.lease_id}？`
        }
      );
    }
  }
];

const connectivityColumns: DataTableColumns<ConnectivityCheckResult> = [
  { title: '目标', key: 'target', width: 120 },
  { title: '地址', key: 'host' },
  { title: '端口', key: 'port', width: 90 },
  {
    title: '状态',
    key: 'status',
    width: 110,
    render(row) {
      return h(
        NTag,
        { type: row.status === 'REACHABLE' ? 'success' : 'error' },
        { default: () => (row.status === 'REACHABLE' ? '可达' : '不可达') }
      );
    }
  },
  {
    title: '耗时',
    key: 'latency_ms',
    width: 100,
    render(row) {
      return row.latency_ms === null ? '-' : `${row.latency_ms} ms`;
    }
  },
  {
    title: '错误',
    key: 'error',
    ellipsis: { tooltip: true },
    render(row) {
      return row.error ?? '-';
    }
  }
];

function renderLeaseButton(machine: MachineResourcePublic) {
  const disabled = !isMachineLeasable(machine) || machine.occupancy_status === 'OCCUPIED';
  return h(
    NButton,
    {
      size: 'small',
      type: 'primary',
      secondary: true,
      disabled,
      onClick: () => openLeaseModal(machine)
    },
    {
      icon: () => h(NIcon, null, { default: () => h(PlayCircle24Regular) }),
      default: () => (machine.occupancy_status === 'OCCUPIED' ? '已占用' : '占用')
    }
  );
}

function renderCredentialViewButton(machine: MachineResourcePublic) {
  return h(
    NButton,
    {
      size: 'small',
      secondary: true,
      loading: viewingCredentialCode.value === machine.resource_code,
      onClick: () => handleViewCredentials(machine)
    },
    { default: () => '查看凭据' }
  );
}

function renderCredentialConfigButton(machine: MachineResourcePublic) {
  return h(
    NButton,
    {
      size: 'small',
      secondary: true,
      onClick: () => openCredentialModal(machine)
    },
    { default: () => '配置凭据' }
  );
}

function renderConnectivityButton(machine: MachineResourcePublic) {
  return h(
    NButton,
    {
      size: 'small',
      secondary: true,
      loading: checkingConnectivityCode.value === machine.resource_code,
      onClick: () => handleConnectivityCheck(machine)
    },
    { default: () => '连通性' }
  );
}

function renderToggleButton(
  isEnabled: boolean,
  confirmText: string,
  disableAction: () => Promise<void>,
  enableAction: () => Promise<void>,
  disableEnableAction = false
) {
  if (!isEnabled) {
    return h(
      NButton,
      {
        size: 'small',
        secondary: true,
        disabled: disableEnableAction,
        onClick: enableAction
      },
      {
        icon: () => h(NIcon, null, { default: () => h(PlayCircle24Regular) }),
        default: () => '恢复'
      }
    );
  }
  return h(
    NPopconfirm,
    {
      onPositiveClick: disableAction
    },
    {
      trigger: () =>
        h(
          NButton,
          {
            size: 'small',
            type: 'error',
            secondary: true
          },
          {
            icon: () => h(NIcon, null, { default: () => h(DismissCircle24Regular) }),
            default: () => '停用'
          }
        ),
      default: () => confirmText
    }
  );
}

function poolRowKey(row: ResourcePoolPublic) {
  return row.id;
}

function machineRowKey(row: MachineResourcePublic) {
  return row.id;
}

function leaseRowKey(row: ResourceLeasePublic) {
  return row.lease_id;
}

function connectivityRowKey(row: ConnectivityCheckResult) {
  return `${row.target}-${row.host}-${row.port}`;
}

function poolName(poolId: number) {
  return findPool(poolId)?.name ?? `#${poolId}`;
}

function findPool(poolId: number) {
  return pools.value.find((pool) => pool.id === poolId);
}

function isMachinePoolDisabled(machine: MachineResourcePublic) {
  const pool = findPool(machine.pool_id);
  return Boolean(pool && !pool.is_active);
}

function isMachineLeasable(machine: MachineResourcePublic) {
  return machine.admin_status === 'ACTIVE' && !isMachinePoolDisabled(machine);
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString();
}

async function loadInventory() {
  loading.value = true;
  try {
    const [nextPools, nextMachines, nextLeases] = await Promise.all([
      listResourcePools(),
      listMachines(),
      listMyLeases()
    ]);
    pools.value = nextPools;
    machines.value = nextMachines;
    leases.value = nextLeases;
  } catch (error) {
    message.error(error instanceof Error ? error.message : '加载资源台账失败');
  } finally {
    loading.value = false;
  }
}

async function handleCreatePool() {
  creatingPool.value = true;
  try {
    await createResourcePool({
      name: poolForm.name,
      description: poolForm.description || null,
      location: poolForm.location || null,
      network_zone: poolForm.network_zone || null
    });
    poolForm.name = '';
    poolForm.description = '';
    poolForm.location = '';
    poolForm.network_zone = '';
    message.success('资源池已创建');
    await loadInventory();
  } catch (error) {
    message.error(error instanceof Error ? error.message : '创建资源池失败');
  } finally {
    creatingPool.value = false;
  }
}

async function handleCreateMachine() {
  if (!machineForm.pool_id) {
    message.error('请选择资源池');
    return;
  }
  creatingMachine.value = true;
  try {
    await createMachine({
      resource_code: machineForm.resource_code,
      name: machineForm.name,
      resource_type: machineForm.resource_type,
      pool_id: machineForm.pool_id,
      architecture: machineForm.architecture || null,
      os_name: machineForm.os_name || null,
      ip_address: machineForm.ip_address || null,
      tags: tagsText.value
        .split(',')
        .map((tag) => tag.trim())
        .filter(Boolean)
    });
    machineForm.resource_code = '';
    machineForm.name = '';
    machineForm.resource_type = 'PHYSICAL';
    machineForm.pool_id = null;
    machineForm.architecture = '';
    machineForm.os_name = '';
    machineForm.ip_address = '';
    tagsText.value = '';
    message.success('机器已登记');
    await loadInventory();
  } catch (error) {
    message.error(error instanceof Error ? error.message : '登记机器失败');
  } finally {
    creatingMachine.value = false;
  }
}

function openLeaseModal(machine: MachineResourcePublic) {
  selectedMachine.value = machine;
  leaseForm.duration_minutes = 60;
  leaseForm.purpose = '';
  leaseModalVisible.value = true;
}

async function handleCreateLease() {
  if (!selectedMachine.value) {
    return;
  }
  if (!leaseForm.purpose.trim()) {
    message.error('请填写用途');
    return;
  }
  leasing.value = true;
  try {
    await createResourceLease({
      resource_code: selectedMachine.value.resource_code,
      duration_minutes: leaseForm.duration_minutes,
      purpose: leaseForm.purpose.trim()
    });
    leaseModalVisible.value = false;
    selectedMachine.value = null;
    message.success('机器已占用');
    await loadInventory();
  } catch (error) {
    message.error(error instanceof Error ? error.message : '占用机器失败');
  } finally {
    leasing.value = false;
  }
}

async function handleReleaseLease(lease: ResourceLeasePublic) {
  releasingLeaseId.value = lease.lease_id;
  try {
    await releaseResourceLease(lease.lease_id);
    message.success('租约已释放');
    await loadInventory();
  } catch (error) {
    message.error(error instanceof Error ? error.message : '释放租约失败');
  } finally {
    releasingLeaseId.value = null;
  }
}

function openCredentialModal(machine: MachineResourcePublic) {
  selectedCredentialMachine.value = machine;
  credentialForm.ssh_username = '';
  credentialForm.ssh_password = '';
  credentialForm.bmc_username = '';
  credentialForm.bmc_password = '';
  credentialModalVisible.value = true;
}

async function handleConfigureCredentials() {
  if (!selectedCredentialMachine.value) {
    return;
  }
  savingCredentials.value = true;
  try {
    await configureMachineCredentials(selectedCredentialMachine.value.resource_code, {
      ssh_username: credentialForm.ssh_username || null,
      ssh_password: credentialForm.ssh_password || null,
      bmc_username: credentialForm.bmc_username || null,
      bmc_password: credentialForm.bmc_password || null
    });
    credentialModalVisible.value = false;
    selectedCredentialMachine.value = null;
    message.success('凭据已保存');
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存凭据失败');
  } finally {
    savingCredentials.value = false;
  }
}

async function handleViewCredentials(machine: MachineResourcePublic) {
  viewingCredentialCode.value = machine.resource_code;
  try {
    credentialSecret.value = await getMachineCredentials(machine.resource_code);
    credentialViewModalVisible.value = true;
  } catch (error) {
    message.error(error instanceof Error ? error.message : '查看凭据失败');
  } finally {
    viewingCredentialCode.value = null;
  }
}

async function handleConnectivityCheck(machine: MachineResourcePublic) {
  checkingConnectivityCode.value = machine.resource_code;
  try {
    const response = await runMachineConnectivityCheck(machine.resource_code);
    connectivityChecks.value = response.checks;
    connectivityModalVisible.value = true;
  } catch (error) {
    message.error(error instanceof Error ? error.message : '连通性检查失败');
  } finally {
    checkingConnectivityCode.value = null;
  }
}

async function handleDisablePool(pool: ResourcePoolPublic) {
  try {
    await disableResourcePool(pool.id);
    message.success('资源池已停用');
    await loadInventory();
  } catch (error) {
    message.error(error instanceof Error ? error.message : '停用资源池失败');
  }
}

async function handleEnablePool(pool: ResourcePoolPublic) {
  try {
    await enableResourcePool(pool.id);
    message.success('资源池已恢复');
    await loadInventory();
  } catch (error) {
    message.error(error instanceof Error ? error.message : '恢复资源池失败');
  }
}

async function handleDisableMachine(machine: MachineResourcePublic) {
  try {
    await disableMachine(machine.resource_code);
    message.success('机器已停用');
    await loadInventory();
  } catch (error) {
    message.error(error instanceof Error ? error.message : '停用机器失败');
  }
}

async function handleEnableMachine(machine: MachineResourcePublic) {
  try {
    await enableMachine(machine.resource_code);
    message.success('机器已恢复');
    await loadInventory();
  } catch (error) {
    message.error(error instanceof Error ? error.message : '恢复机器失败');
  }
}

onMounted(loadInventory);
</script>

<style scoped>
.inventory-page {
  min-height: 100vh;
  background: #f4f6f8;
  color: #1f2937;
  padding: 48px 24px;
}

.inventory-shell {
  width: min(1180px, 100%);
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

.pool-form,
.machine-form {
  display: grid;
  gap: 16px;
  align-items: end;
  margin-bottom: 24px;
}

.pool-form {
  grid-template-columns: minmax(160px, 1fr) minmax(160px, 1fr) minmax(220px, 2fr) auto;
}

.machine-form {
  grid-template-columns: repeat(4, minmax(150px, 1fr)) auto;
}

.lease-modal {
  width: min(520px, calc(100vw - 32px));
}

.credential-modal {
  width: min(560px, calc(100vw - 32px));
}

.connectivity-modal {
  width: min(760px, calc(100vw - 32px));
}

.full-width {
  width: 100%;
}

@media (max-width: 980px) {
  .inventory-page {
    padding: 24px 12px;
  }

  .inventory-shell {
    padding: 20px;
  }

  .header {
    align-items: flex-start;
    flex-direction: column;
  }

  .pool-form,
  .machine-form {
    grid-template-columns: 1fr;
  }
}
</style>
