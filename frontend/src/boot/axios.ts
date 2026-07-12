import { defineBoot } from '#q-app/wrappers';
import axios, { type AxiosInstance } from 'axios';

declare module 'vue' {
  interface ComponentCustomProperties {
    $axios: AxiosInstance;
    $api: AxiosInstance;
  }
}

// Stessa-origine in produzione (nginx fa proxy verso il backend).
// In dev il proxy di Quasar inoltra /api -> http://localhost:8000.
const api = axios.create({
  baseURL: '/',
  withCredentials: true,
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
});

// Multiproprietà: ogni richiesta dichiara l'immobile attivo. La chiave
// localStorage è condivisa con stores/properties.ts (STORAGE_KEY); si legge
// qui direttamente per non dipendere da Pinia in fase di boot. Il backend
// verifica comunque la membership: l'header è una dichiarazione, non fiducia.
api.interceptors.request.use((config) => {
  const raw = localStorage.getItem('vp-property-id');
  if (raw && !config.headers.has('X-Property-Id')) {
    config.headers.set('X-Property-Id', raw);
  }
  return config;
});

export default defineBoot(({ app }) => {
  app.config.globalProperties.$axios = axios;
  app.config.globalProperties.$api = api;
});

export { api };
