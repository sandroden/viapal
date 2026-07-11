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
    path: '/password-dimenticata',
    component: () => import('layouts/AuthLayout.vue'),
    meta: { public: true },
    children: [
      {
        path: '',
        name: 'password-dimenticata',
        component: () => import('pages/PasswordDimenticata.vue'),
      },
    ],
  },
  {
    // Usata sia per il primo set-password (invito) sia per il reset password.
    path: '/imposta-password/:uid/:token',
    component: () => import('layouts/AuthLayout.vue'),
    meta: { public: true },
    children: [
      {
        path: '',
        name: 'imposta-password',
        component: () => import('pages/ImpostaPassword.vue'),
      },
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
        path: 'inquilini/:id/rendiconto',
        name: 'p-inquilino-rendiconto',
        component: () => import('pages/ProprietarioRendiconto.vue'),
      },
      {
        path: 'da-incassare',
        name: 'p-da-incassare',
        component: () => import('pages/ProprietarioDaIncassare.vue'),
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
        path: 'riconciliazione',
        name: 'p-riconciliazione',
        component: () => import('pages/ProprietarioRiconciliazione.vue'),
      },
      {
        path: 'saldi-fratelli',
        name: 'p-saldi-fratelli',
        component: () => import('pages/ProprietarioSaldiFratelli.vue'),
      },
      {
        path: 'conto-economico',
        name: 'p-conto-economico',
        component: () => import('pages/ProprietarioContoEconomico.vue'),
      },
      {
        path: 'utenze',
        name: 'p-utenze',
        component: () => import('pages/ProprietarioUtenze.vue'),
      },
      {
        path: 'proprieta/nuova',
        name: 'p-property-nuova',
        component: () => import('pages/ProprietarioPropertyNuova.vue'),
      },
      {
        path: 'impostazioni/proprieta',
        name: 'p-impostazioni-proprieta',
        component: () => import('pages/ProprietarioImpostazioniProprieta.vue'),
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
        path: 'situazione',
        name: 'i-situazione',
        component: () => import('pages/InquilinoSituazione.vue'),
      },
      {
        path: 'rendiconto',
        name: 'i-rendiconto',
        // documento tabellare: esce dal cap stretto del layout inquilino
        meta: { wide: true },
        component: () => import('pages/InquilinoRendiconto.vue'),
      },
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
        path: 'utenze',
        name: 'i-utenze-list',
        component: () => import('pages/InquilinoUtenze.vue'),
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
        path: 'documenti',
        name: 'i-documenti',
        component: () => import('pages/InquilinoDocumenti.vue'),
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
