import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import Shops from './Shops.vue'
import ShopWorkspace from './ShopWorkspace.vue'
import Store from './Store.vue'
import CustomerShop from './CustomerShop.vue'
import Orders from './Orders.vue'
import Signup from './Signup.vue'
import Login from './Login.vue'
import Account from './Account.vue'
import Delivery from './Delivery.vue'
import './style.css'
const router = createRouter({ history: createWebHashHistory(), scrollBehavior: () => ({ top: 0 }), routes: [
  { path: '/', component: Store },
  { path: '/store', component: Store },
  { path: '/store/:shop', name: 'customer-shop', component: CustomerShop },
  { path: '/orders', component: Orders },
  { path: '/signup', component: Signup },
  { path: '/login', component: Login },
  { path: '/account', component: Account },
  { path: '/delivery', component: Delivery },
  { path: '/shop', component: Shops },
  { path: '/shop/:shop', name: 'shop-workspace', component: ShopWorkspace },
  { path: '/:pathMatch(.*)*', redirect: '/' },
] })
createApp(App).use(router).mount('#lc-app')
