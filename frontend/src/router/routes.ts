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
      { path: '', name: 'p-home', component: () => import('pages/ProprietarioHome.vue') },
      {
        path: 'ritardi',
        name: 'p-ritardi',
        component: () => import('pages/ProprietarioRitardi.vue'),
      },
      {
        path: 'inquilini',
        name: 'p-inquilini',
        component: () => import('pages/ProprietarioInquilini.vue'),
      },
      {
        path: 'inquilini/:id',
        name: 'p-inquilino-dettaglio',
        component: () => import('pages/ProprietarioInquilinoDettaglio.vue'),
      },
      {
        path: 'quadro-annuale',
        name: 'p-quadro',
        component: () => import('pages/ProprietarioQuadro.vue'),
      },
      {
        path: 'spese',
        name: 'p-spese',
        component: () => import('pages/ProprietarioSpese.vue'),
      },
      {
        path: 'quick-add',
        name: 'p-quick-add',
        component: () => import('pages/ProprietarioQuickAdd.vue'),
      },
      {
        path: 'bilancio/:ownerId',
        name: 'p-bilancio-dettaglio',
        component: () => import('pages/ProprietarioBilancioDettaglio.vue'),
      },
      {
        path: ':catchAll(.*)*',
        component: () => import('pages/ErrorNotFound.vue'),
      },
    ],
  },
  {
    path: '/i',
    component: () => import('layouts/InquilinoLayout.vue'),
    meta: { role: 'inquilino' },
    children: [
      { path: '', name: 'i-home', component: () => import('pages/InquilinoHome.vue') },
      {
        path: 'paga/:tipo/:id',
        name: 'i-paga',
        component: () => import('pages/InquilinoPaga.vue'),
      },
      {
        path: 'pagamenti',
        name: 'i-pagamenti',
        component: () => import('pages/InquilinoPagamenti.vue'),
      },
      {
        path: 'utenze/:id',
        name: 'i-utenze',
        component: () => import('pages/InquilinoConguaglio.vue'),
      },
      {
        path: 'profilo',
        name: 'i-profilo',
        component: () => import('pages/InquilinoProfilo.vue'),
      },
      {
        path: ':catchAll(.*)*',
        component: () => import('pages/ErrorNotFound.vue'),
      },
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
