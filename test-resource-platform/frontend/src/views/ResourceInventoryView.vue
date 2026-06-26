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
      </n-tabs>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue';
import { NTag, useMessage, type DataTableColumns } from 'naive-ui';
import {
  ArrowLeft24Regular,
  Database24Regular,
  Desktop24Regular
} from '@vicons/fluent';
import { useRouter } from 'vue-router';

import {
  createMachine,
  createResourcePool,
  listMachines,
  listResourcePools,
  type MachineResourcePublic,
  type ResourcePoolPublic,
  type ResourceType
} from '@/api/resourceInventory';
import { useAuthStore } from '@/stores/auth';

const auth = useAuthStore();
const router = useRouter();
const message = useMessage();

const pools = ref<ResourcePoolPublic[]>([]);
const machines = ref<MachineResourcePublic[]>([]);
const loading = ref(false);
const creatingPool = ref(false);
const creatingMachine = ref(false);
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
  { title: '说明', key: 'description' }
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
      return h(NTag, { type: row.admin_status === 'ACTIVE' ? 'success' : 'warning' }, { default: () => row.admin_status });
    }
  },
  { title: 'IP', key: 'ip_address' },
  {
    title: '标签',
    key: 'tags',
    render(row) {
      return row.tags.join(', ');
    }
  }
];

function poolRowKey(row: ResourcePoolPublic) {
  return row.id;
}

function machineRowKey(row: MachineResourcePublic) {
  return row.id;
}

function poolName(poolId: number) {
  return pools.value.find((pool) => pool.id === poolId)?.name ?? `#${poolId}`;
}

async function loadInventory() {
  loading.value = true;
  try {
    const [nextPools, nextMachines] = await Promise.all([listResourcePools(), listMachines()]);
    pools.value = nextPools;
    machines.value = nextMachines;
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
