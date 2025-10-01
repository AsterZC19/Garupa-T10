import { createApp } from 'vue'
import App from './App.vue'
import './index.css'  // 如果使用 tailwind

// Dynamically inject Umami tracking script in production
if (import.meta.env.PROD) {
  const script = document.createElement('script');
  script.defer = true;
  script.src = 'https://umami.starminus.uk/script.js';
  script.setAttribute('data-website-id', 'e6d36d29-e496-4bed-9fcf-c599a6f3f621');
  document.head.appendChild(script);
}

createApp(App).mount('#app')
