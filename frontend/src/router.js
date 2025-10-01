import { createRouter, createWebHistory } from 'vue-router';
import EventView from './views/EventView.vue';
import PlayerSearch from './components/PlayerSearch.vue';

const routes = [
  {
    path: '/',
    name: 'Home',
    component: EventView,
  },
  {
    path: '/:eventId(\d+)',
    name: 'Event',
    component: EventView,
  },
  {
    path: '/player',
    name: 'Player',
    component: PlayerSearch,
  },
  {
    path: '/player/:uid(\d+)',
    name: 'PlayerDetail',
    component: PlayerSearch,
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
