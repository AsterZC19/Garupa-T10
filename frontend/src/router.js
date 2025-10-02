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
    path: '/:eventId',
    name: 'Event',
    component: EventView,
  },
  {
    path: '/player',
    name: 'Player',
    component: PlayerSearchView, // Corrected
  },
  {
    path: '/player/:uid',
    name: 'PlayerDetail',
    component: PlayerSearchView, // Corrected
  },];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
