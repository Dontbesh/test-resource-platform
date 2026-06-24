import { createApp } from 'vue';
import naive from 'naive-ui';
import { createPinia } from 'pinia';

import App from './App.vue';
import router from './router';
import './style.css';

createApp(App).use(createPinia()).use(router).use(naive).mount('#app');
