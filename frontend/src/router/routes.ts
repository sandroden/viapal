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
    // Galleria pubblica dell'immobile (annuncio affitto). Nessuna
    // autenticazione: l'editing in-place appare solo se un proprietario è
    // loggato.
    path: '/g/:slug',
    component: () => import('layouts/PublicLayout.vue'),
    meta: { public: true },
    children: [
      {
        path: '',
        name: 'galleria-pubblica',
        component: () => import('pages/GalleriaPubblica.vue'),
      },
    ],
  },
  {
    // Privacy/cookie per i visitatori anonimi (link dal footer della
    // galleria pubblica). L'informativa completa per gli inquilini resta
    // in /i/privacy.
    path: '/privacy',
    component: () => import('layouts/PublicLayout.vue'),
    meta: { public: true },
    children: [
      {
        path: '',
        name: 'privacy-pubblica',
        component: () => import('pages/PrivacyPubblica.vue'),
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
        path: 'spese',
        name: 'p-spese',
        component: () => import('pages/ProprietarioSpese.vue'),
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
        path: 'saldi-proprietari',
        name: 'p-saldi-proprietari',
        component: () => import('pages/ProprietarioSaldiProprietari.vue'),
      },
      // Nome storico della pagina (quando i proprietari erano solo i tre
      // fratelli): i segnalibri devono continuare ad aprirla.
      { path: 'saldi-fratelli', redirect: { name: 'p-saldi-proprietari' } },
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
        path: 'notifiche',
        name: 'p-notifiche',
        component: () => import('pages/ProprietarioNotifiche.vue'),
      },
      // La pagina si chiamava "riepilogo addebiti": i link già in giro
      // (email, segnalibri) devono continuare ad aprirla.
      { path: 'riepilogo', redirect: { name: 'p-notifiche' } },
      {
        path: 'proprieta/nuova',
        name: 'p-property-nuova',
        component: () => import('pages/ProprietarioPropertyNuova.vue'),
      },
      {
        path: 'impostazioni',
        name: 'p-impostazioni',
        component: () => import('pages/ProprietarioImpostazioni.vue'),
      },
      // Le due vecchie pagine ("Immobile e membri" e "La casa") sono fuse
      // nella pagina a tab qui sopra: segnalibri e link nei documenti già
      // generati devono continuare ad aprirla. Il tab di default va iniettato
      // preservando i param dei deep link (campo, contratto); lo spread dopo
      // il default fa vincere un eventuale ?tab= esplicito.
      {
        path: 'impostazioni/proprieta',
        redirect: (to) => ({ name: 'p-impostazioni', query: { tab: 'dati', ...to.query } }),
      },
      {
        path: 'impostazioni/casa',
        redirect: (to) => ({ name: 'p-impostazioni', query: { tab: 'stanze', ...to.query } }),
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
        path: 'privacy',
        name: 'i-privacy',
        component: () => import('pages/InquilinoPrivacy.vue'),
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
