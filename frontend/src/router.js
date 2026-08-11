import { createRouter, createWebHistory } from 'vue-router';
import EventView from './views/EventView.vue';
import MonthlyView from './views/MonthlyView.vue';
import PlayerSearchView from './views/PlayerSearchView.vue';
import NotFoundView from './views/NotFoundView.vue';

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
    path: '/monthly',
    name: 'Monthly',
    component: MonthlyView,
  },
  {
    path: '/monthly/:monthlyId(\\d+)',
    name: 'MonthlyDetail',
    component: MonthlyView,
    props: true, // monthlyId 直接作为 props
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
    path: '/page/404',
    name: 'NotFound',
    component: NotFoundView,
  },
  {
    path: '/:catchAll(.*)', // 未匹配路径（含无效活动 ID）→ 主题化 404 页面
    redirect: { name: 'NotFound' },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
