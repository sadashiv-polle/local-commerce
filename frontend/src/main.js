import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import AdminDashboard from './AdminDashboard.vue'
import Shops from './Shops.vue'
import ShopWorkspace from './ShopWorkspace.vue'
import Store from './Store.vue'
import StoreCategories from './StoreCategories.vue'
import StoreSettings from './StoreSettings.vue'
import CustomerShop from './CustomerShop.vue'
import Orders from './Orders.vue'
import Signup from './Signup.vue'
import Login from './Login.vue'
import Account from './Account.vue'
import Favourites from './Favourites.vue'
import Delivery from './Delivery.vue'
import './style.css'
import './responsive.css'
const router = createRouter({ history: createWebHashHistory(), scrollBehavior: (to, from, saved) => saved || (to.path === from.path ? false : { top: 0 }), routes: [
  { path: '/', component: Store },
  { path: '/store', component: Store },
  { path: '/categories', component: StoreCategories },
  { path: '/store-settings', component: StoreSettings },
  { path: '/store/:shop', name: 'customer-shop', component: CustomerShop },
  { path: '/orders', component: Orders },
  { path: '/signup', component: Signup },
  { path: '/login', component: Login },
  { path: '/account', component: Account },
  { path: '/favourites', component: Favourites },
  { path: '/delivery', component: Delivery },
  { path: '/admin', component: AdminDashboard },
  { path: '/admin/:section', component: AdminDashboard },
  { path: '/shop', component: Shops },
  { path: '/shop/:shop', name: 'shop-workspace', component: ShopWorkspace },
  { path: '/:pathMatch(.*)*', redirect: '/' },
] })
createApp(App).use(router).mount('#lc-app')
