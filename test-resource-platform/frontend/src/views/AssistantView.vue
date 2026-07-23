<template>
  <main class="assistant-page">
    <section class="assistant-shell">
      <header class="assistant-header">
        <div>
          <p class="eyebrow">Resource Assistant</p>
          <h1>资源助手</h1>
        </div>
        <n-button quaternary circle title="返回后台首页" @click="router.push('/dashboard')">
          <template #icon>
            <n-icon><ArrowLeft24Regular /></n-icon>
          </template>
        </n-button>
      </header>

      <section ref="messageList" class="message-list" aria-live="polite">
        <div v-if="messages.length === 0" class="empty-message">
          <n-icon size="36"><Bot24Regular /></n-icon>
          <span>输入机器资源需求</span>
        </div>
        <article
          v-for="messageItem in messages"
          :key="messageItem.id"
          class="message-row"
          :class="messageItem.role"
        >
          <div class="message-bubble">{{ messageItem.text }}</div>
        </article>
        <article v-if="sending" class="message-row assistant">
          <div class="message-bubble pending"><n-spin size="small" /> 正在查询</div>
        </article>
      </section>

      <n-alert v-if="error" type="error" closable @close="error = ''">{{ error }}</n-alert>

      <form class="composer" @submit.prevent="sendMessage">
        <n-input
          v-model:value="draft"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 5 }"
          placeholder="例如：有没有空闲的 x86_64 机器？"
          :disabled="sending"
          @keydown.ctrl.enter.prevent="sendMessage"
        />
        <n-button type="primary" attr-type="submit" :loading="sending" :disabled="!draft.trim()">
          <template #icon>
            <n-icon><Send24Regular /></n-icon>
          </template>
          发送
        </n-button>
      </form>
    </section>
  </main>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue';
import { ArrowLeft24Regular, Bot24Regular, Send24Regular } from '@vicons/fluent';
import { useRouter } from 'vue-router';

import { sendAssistantMessage } from '@/api/assistant';

interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  text: string;
}

const router = useRouter();
const draft = ref('');
const sending = ref(false);
const error = ref('');
const messages = ref<ChatMessage[]>([]);
const messageList = ref<HTMLElement | null>(null);
let nextMessageId = 1;

async function sendMessage() {
  const text = draft.value.trim();
  if (!text || sending.value) {
    return;
  }
  messages.value.push({ id: nextMessageId++, role: 'user', text });
  draft.value = '';
  error.value = '';
  sending.value = true;
  await scrollToBottom();
  try {
    const response = await sendAssistantMessage(text);
    messages.value.push({ id: nextMessageId++, role: 'assistant', text: response.text });
  } catch (err) {
    error.value = err instanceof Error ? err.message : '助手请求失败';
  } finally {
    sending.value = false;
    await scrollToBottom();
  }
}

async function scrollToBottom() {
  await nextTick();
  if (messageList.value) {
    messageList.value.scrollTop = messageList.value.scrollHeight;
  }
}
</script>

<style scoped>
.assistant-page {
  min-height: 100vh;
  background: #f3f5f7;
  color: #1f2937;
  padding: 32px 20px;
}

.assistant-shell {
  width: min(920px, 100%);
  min-height: calc(100vh - 64px);
  margin: 0 auto;
  display: grid;
  grid-template-rows: auto minmax(320px, 1fr) auto auto;
  gap: 16px;
  background: #ffffff;
  border: 1px solid #d8e0e7;
  border-radius: 8px;
  padding: 24px;
}

.assistant-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.eyebrow {
  margin: 0 0 4px;
  color: #52748b;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0;
}

h1 {
  margin: 0;
  font-size: 26px;
  letter-spacing: 0;
}

.message-list {
  min-height: 0;
  overflow-y: auto;
  padding: 20px;
  background: #f8fafb;
  border: 1px solid #e0e6eb;
  border-radius: 6px;
}

.empty-message {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #6b7c89;
}

.message-row {
  display: flex;
  margin-bottom: 14px;
}

.message-row.user {
  justify-content: flex-end;
}

.message-bubble {
  max-width: min(680px, 86%);
  padding: 11px 14px;
  border-radius: 6px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.6;
  background: #e8edf1;
}

.message-row.user .message-bubble {
  color: #ffffff;
  background: #176b87;
}

.message-bubble.pending {
  display: flex;
  align-items: center;
  gap: 8px;
}

.composer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 12px;
}

@media (max-width: 640px) {
  .assistant-page {
    padding: 0;
  }

  .assistant-shell {
    min-height: 100vh;
    border: 0;
    border-radius: 0;
    padding: 16px;
  }

  .composer {
    grid-template-columns: 1fr;
  }
}
</style>
