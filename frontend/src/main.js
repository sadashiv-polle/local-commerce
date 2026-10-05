import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
const AdminDashboard = () => import('./AdminDashboard.vue')
const Shops = () => import('./Shops.vue')
const ShopWorkspace = () => import('./ShopWorkspace.vue')
const Store = () => import('./Store.vue')
const StoreCategories = () => import('./StoreCategories.vue')
const StoreSettings = () => import('./StoreSettings.vue')
const CustomerShop = () => import('./CustomerShop.vue')
const Orders = () => import('./Orders.vue')
const Signup = () => import('./Signup.vue')
const Login = () => import('./Login.vue')
const ResetPassword = () => import('./ResetPassword.vue')
const Account = () => import('./Account.vue')
const Favourites = () => import('./Favourites.vue')
const Delivery = () => import('./Delivery.vue')
import './style.css'
import './responsive.css'
const router = createRouter({ history: createWebHashHistory(), scrollBehavior: (to, from, saved) => saved || (to.path === from.path ? false : { top: 0 }), routes: [
  { path: '/', component: Store },
  { path: '/store', component: Store },
  { path: '/store/map', component: () => import('./ShopMap.vue') },
  { path: '/categories', component: StoreCategories },
  { path: '/store-settings', component: StoreSettings },
  { path: '/store/:shop', name: 'customer-shop', component: CustomerShop },
  { path: '/orders', component: Orders },
  { path: '/orders/verify/:order', component: () => import('./VerifyOrder.vue') },
  { path: '/signup', component: Signup },
  { path: '/login', component: Login },
  { path: '/reset-password', component: ResetPassword },
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
