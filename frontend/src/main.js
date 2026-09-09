import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import Shops from './Shops.vue'
import ShopWorkspace from './ShopWorkspace.vue'
import Store from './Store.vue'
import './style.css'
const router = createRouter({ history: createWebHashHistory(), scrollBehavior: () => ({ top: 0 }), routes: [
  { path: '/', component: Store },
  { path: '/store', component: Store },
  { path: '/shop', component: Shops },
  { path: '/shop/:shop', name: 'shop-workspace', component: ShopWorkspace },
  { path: '/:pathMatch(.*)*', redirect: '/' },
] })
createApp(App).use(router).mount('#lc-app')
