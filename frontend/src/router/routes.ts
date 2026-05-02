import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    component: () => import('layouts/AuthLayout.vue'),
    meta: { public: true },
    children: [
      { path: '', component: () => import('pages/LoginPage.vue') },
    ],
  },
  {
    path: '/p',
    component: () => import('layouts/ProprietarioLayout.vue'),
    meta: { role: 'proprietario' },
    children: [
      { path: '', component: () => import('pages/ProprietarioHome.vue') },
    ],
  },
  {
    path: '/i',
    component: () => import('layouts/InquilinoLayout.vue'),
    meta: { role: 'inquilino' },
    children: [
      { path: '', component: () => import('pages/InquilinoHome.vue') },
    ],
  },
  {
    path: '/',
    redirect: '/login',
  },
  {
    path: '/:catchAll(.*)*',
    component: () => import('pages/ErrorNotFound.vue'),
  },
];

export default routes;
