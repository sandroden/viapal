import { defineRouter } from '#q-app/wrappers';
import {
  createMemoryHistory,
  createRouter,
  createWebHashHistory,
  createWebHistory,
} from 'vue-router';
import routes from './routes';
import { useAuthStore } from 'stores/auth';

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

  return Router;
});
