import { defineRouter } from '#q-app/wrappers';
import {
  createMemoryHistory,
  createRouter,
  createWebHashHistory,
  createWebHistory,
} from 'vue-router';
import routes from './routes';
import { useAuthStore } from 'stores/auth';
import { usePropertiesStore } from 'stores/properties';

export default defineRouter((/* { store, ssrContext } */) => {
  const createHistory = process.env.SERVER
    ? createMemoryHistory
    : (process.env.VUE_ROUTER_MODE === 'history' ? createWebHistory : createWebHashHistory);

  const Router = createRouter({
    scrollBehavior: () => ({ left: 0, top: 0 }),
    routes,
    history: createHistory(process.env.VUE_ROUTER_BASE),
  });

  Router.beforeEach(async (to) => {
    const auth = useAuthStore();
    if (!auth.loaded) {
      await auth.fetchMe();
    }
    // Multiproprietà: valida/ripiega l'immobile attivo persistito (vale
    // anche dopo il login, quando fetchMe è già avvenuto fuori dal guard).
    usePropertiesStore().sincronizza();

    const isPublic = to.meta.public === true;

    if (!auth.isAuthenticated && !isPublic) {
      return { path: '/login', query: { next: to.fullPath } };
    }

    if (auth.isAuthenticated && to.path === '/login') {
      return auth.homePath;
    }

    const requiredRole = to.meta.role as string | undefined;
    if (requiredRole && auth.role !== requiredRole) {
      return auth.homePath;
    }

    return true;
  });

  // Recupero da deploy: se una navigazione fallisce perché il chunk lazy della
  // rotta non esiste più (hash cambiato dopo un deploy, vecchio file → 404),
  // ricarichiamo a pagina piena sulla destinazione così il browser scarica il
  // bundle nuovo. Doppia rete rispetto al reload-on-controllerchange del SW.
  // La guardia in sessionStorage evita loop se il reload non risolve.
  const CHUNK_ERR =
    /Failed to fetch dynamically imported module|error loading dynamically imported module|Importing a module script failed/i;
  Router.onError((error, to) => {
    if (!CHUNK_ERR.test(error?.message ?? '')) return;
    if (sessionStorage.getItem('vp-chunk-reload') === to.fullPath) return;
    sessionStorage.setItem('vp-chunk-reload', to.fullPath);
    window.location.assign(to.fullPath);
  });
  // Navigazione andata a buon fine: azzera la guardia per i deploy futuri.
  Router.afterEach(() => {
    sessionStorage.removeItem('vp-chunk-reload');
  });

  return Router;
});
