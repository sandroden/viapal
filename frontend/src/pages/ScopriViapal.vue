<template>
  <q-page padding class="vp-scopri">
    <div class="vp-eyebrow">Presentazione</div>
    <h1 class="vp-display vp-scopri__titolo">Viapal in tre minuti</h1>
    <p class="vp-scopri__occhiello">
      Viapal gestisce l'affitto di una casa, intera o divisa in stanze: per chi la possiede e per
      chi ci abita. Il video lo mostra all'opera, dal lato di entrambi.
    </p>

    <!-- Il video sta in MEDIA_ROOT/scopri/, caricato a mano: non è nel
         repository. `playsinline` evita che iPhone lo apra a schermo intero
         al primo tocco; `preload="metadata"` non scarica 10 MB a chi non
         preme play. -->
    <div class="vp-scopri__video">
      <video
        controls
        playsinline
        preload="metadata"
        :poster="`${CARTELLA}/copertina.jpg`"
        data-testid="scopri-video"
      >
        <source :src="`${CARTELLA}/viapal-demo.mp4`" type="video/mp4" />
        Il tuo browser non riproduce il video:
        <a :href="`${CARTELLA}/viapal-demo.mp4`">scaricalo qui</a>.
      </video>
    </div>
    <div class="vp-scopri__hd">
      <a :href="`${CARTELLA}/viapal-demo-hd.mp4`" download class="vp-hint">
        Scarica il video in alta qualità (1080p, 75 MB)
      </a>
    </div>

    <div class="vp-scopri__viste">
      <div v-for="v in VISTE" :key="v.titolo" class="vp-card vp-scopri__vista">
        <div class="vp-scopri__vista-testa">
          <q-icon :name="v.icona" size="22px" class="vp-scopri__icona" />
          <h2>{{ v.titolo }}</h2>
        </div>
        <ul>
          <li v-for="voce in v.voci" :key="voce">{{ voce }}</li>
        </ul>
      </div>
    </div>

    <div class="vp-card vp-scopri__prova" data-testid="scopri-contatto">
      <h2 class="vp-display">Prova Viapal gratis.</h2>
      <div class="vp-scopri__contatto">viapal.e-den.it</div>
    </div>

    <div class="vp-scopri__fine">
      <q-btn
        flat
        no-caps
        color="primary"
        icon="login"
        :label="auth.isAuthenticated ? 'Vai all\'app' : 'Hai già un accesso? Entra'"
        @click="vaiAllApp"
      />
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';
import { useAuthStore } from 'stores/auth';

const auth = useAuthStore();
const router = useRouter();

const CARTELLA = '/media/scopri';

// Le stesse voci del cartello introduttivo del video (video/src/manifest.ts),
// con quello che il video mostra dopo.
const VISTE = [
  {
    titolo: 'Per chi affitta',
    icona: 'real_estate_agent',
    voci: [
      'Incassi e ritardi, abbinati ai bonifici',
      'Bollette divise per presenza',
      'Spese e conti fra comproprietari',
      'Annuncio pubblico e documenti generati',
    ],
  },
  {
    titolo: 'Per chi abita',
    icona: 'person',
    voci: [
      'Quanto deve e perché',
      'Paga con un QR',
      'I suoi documenti',
      'Avvisi sul telefono',
    ],
  },
];

function vaiAllApp() {
  void router.push(auth.isAuthenticated ? auth.homePath : { path: '/login' });
}
</script>

<style scoped>
.vp-scopri {
  max-width: 880px;
  margin: 0 auto;
}
.vp-scopri__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 var(--vp-gap-3);
}
.vp-scopri__occhiello {
  font-size: var(--vp-text-sm);
  line-height: 1.55;
  color: var(--vp-ink-2);
  margin: 0 0 var(--vp-gap-5);
  max-width: 60ch;
}

.vp-scopri__video {
  border-radius: 12px;
  overflow: hidden;
  background: #000;
  aspect-ratio: 16 / 9;
  box-shadow: 0 8px 28px rgba(60, 40, 20, 0.18);
}
.vp-scopri__video video {
  display: block;
  width: 100%;
  height: 100%;
}
.vp-scopri__hd {
  margin-top: var(--vp-gap-2);
  text-align: right;
}

.vp-scopri__viste {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: var(--vp-gap-4);
  margin-top: var(--vp-gap-6);
}
.vp-scopri__vista {
  padding: var(--vp-gap-4);
}
.vp-scopri__vista-testa {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-3);
}
.vp-scopri__vista-testa h2 {
  font-size: var(--vp-text-lg);
  font-weight: 600;
  margin: 0;
}
.vp-scopri__icona {
  color: var(--vp-terra);
}
.vp-scopri__vista ul {
  margin: var(--vp-gap-3) 0 0;
  padding-left: 1.2em;
  font-size: var(--vp-text-sm);
  line-height: 1.7;
  color: var(--vp-ink-2);
}

.vp-scopri__prova {
  margin-top: var(--vp-gap-6);
  padding: var(--vp-gap-5) var(--vp-gap-4);
  text-align: center;
}
.vp-scopri__prova h2 {
  font-size: var(--vp-text-xl);
  margin: 0 0 var(--vp-gap-2);
}
.vp-scopri__contatto {
  font-size: var(--vp-text-lg);
  font-weight: 600;
  color: var(--vp-terra-deep);
  letter-spacing: 0.01em;
}

.vp-scopri__fine {
  margin: var(--vp-gap-5) 0 var(--vp-gap-6);
  text-align: center;
}
</style>
