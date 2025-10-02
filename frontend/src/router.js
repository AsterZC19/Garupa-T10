import { createRouter, createWebHistory } from 'vue-router';
import EventView from './views/EventView.vue';
import PlayerSearchView from './views/PlayerSearchView.vue';

const routes = [
  {
    path: '/',
    name: 'Home',
    component: EventView,
  },
  {
    path: '/:eventId(\\d+)',
    name: 'Event',
    component: EventView,
    props: true, // 让 eventId 直接作为 props 传入组件
  },
  {
    path: '/player',
    name: 'Player',
    component: PlayerSearchView,
  },
  {
    path: '/player/:uid',
    name: 'PlayerDetail',
    component: PlayerSearchView,
    props: true, // uid 直接作为 props
  },
  {
    path: '/:catchAll(.*)', // 捕获所有未匹配路由，重定向到首页
    redirect: '/',
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
