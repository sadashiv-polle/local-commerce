import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import Shops from './Shops.vue'
import Store from './Store.vue'
import './style.css'
const router = createRouter({ history: createWebHashHistory(), routes: [
  { path: '/', component: Store },
  { path: '/store', component: Store },
  { path: '/shop', component: Shops },
  { path: '/:pathMatch(.*)*', redirect: '/' },
] })
createApp(App).use(router).mount('#lc-app')
