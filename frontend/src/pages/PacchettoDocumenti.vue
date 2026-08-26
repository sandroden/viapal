<template>
  <q-page class="pk">
    <div v-if="stato === 'caricamento'" class="pk-attesa">
      <q-spinner size="34px" />
    </div>

    <!-- Un link sbagliato, scaduto o revocato: una frase, senza dire quale
         dei tre — chi apre non deve dedurre nulla dal messaggio. -->
    <div v-else-if="stato === 'assente'" class="pk-nulla">
      <div class="pk-nulla__titolo">Questo link non è più valido</div>
      <p>
        Il collegamento potrebbe essere stato revocato o riscritto male.
        Chiedi a chi te l'ha mandato di rifarlo.
      </p>
    </div>

    <article v-else-if="pacchetto" class="pk-foglio">
      <header class="pk-testata">
        <div class="pk-testata__casa">{{ pacchetto.casa.nome }}</div>
        <h1 class="pk-testata__titolo">Documenti per {{ pacchetto.destinatario }}</h1>
        <div v-if="pacchetto.casa.indirizzo" class="pk-testata__indirizzo">
          {{ pacchetto.casa.indirizzo }}
        </div>
        <!-- La premessa spiega tutto quello che segue: sta in cima e non
             fra gli allegati numerati. Markdown reso e sanitizzato dal
             backend, come i chiarimenti. -->
        <!-- eslint-disable-next-line vue/no-v-html -->
        <div
          v-if="pacchetto.introduzione_html"
          class="pk-md pk-testata__intro"
          v-html="pacchetto.introduzione_html"
        />
      </header>

      <section v-for="(v, i) in pacchetto.voci" :key="v.id" class="pk-voce">
        <h2 class="pk-voce__titolo">
          <span class="pk-voce__n">{{ i + 1 }}</span>
          {{ v.titolo }}
        </h2>

        <!-- I chiarimenti stanno nel flusso, gli allegati si aprono lì
             dentro: una pagina sola, niente rimbalzi. -->
        <!-- eslint-disable-next-line vue/no-v-html -->
        <div v-if="v.tipo === 'testo'" class="pk-md" v-html="v.corpo_html" />

        <template v-else>
          <object
            :data="urlFile(v.id)"
            type="application/pdf"
            class="pk-pdf"
            :aria-label="v.titolo"
          >
            <div class="pk-pdf__fallback">
              Il documento non si apre qui dentro.
              <a :href="urlFile(v.id)" target="_blank" rel="noopener">Aprilo in una scheda</a>.
            </div>
          </object>
          <a class="pk-apri" :href="urlFile(v.id)" target="_blank" rel="noopener">
            Apri «{{ v.titolo }}» a schermo intero
          </a>
        </template>
      </section>

      <footer class="pk-piede">
        Questi documenti sono per la lettura: i dati delle persone che hanno
        firmato prima non ci sono. Per domande, rispondi a chi ti ha mandato
        il link.
      </footer>
    </article>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { api } from 'boot/axios';

interface VocePubblica {
  id: number;
  tipo: 'documento' | 'testo';
  titolo: string;
  corpo_html: string;
}

interface Pacchetto {
  casa: { nome: string; indirizzo: string };
  destinatario: string;
  introduzione_html: string;
  voci: VocePubblica[];
}

const route = useRoute();
const token = String(route.params.token ?? '');

const pacchetto = ref<Pacchetto | null>(null);
const stato = ref<'caricamento' | 'pronto' | 'assente'>('caricamento');

function urlFile(itemId: number): string {
  return `/api/v1/public/documenti/${token}/file/${itemId}/`;
}

onMounted(() => {
  void (async () => {
    try {
      const { data } = await api.get<Pacchetto>(`/api/v1/public/documenti/${token}/`);
      pacchetto.value = data;
      stato.value = 'pronto';
    } catch {
      stato.value = 'assente';
    }
  })();
});
</script>

<style scoped>
.pk {
  background: var(--vp-paper-1, #faf8f5);
  padding: 26px 16px 60px;
}
.pk-attesa {
  display: flex;
  justify-content: center;
  padding-top: 80px;
}
.pk-nulla {
  max-width: 460px;
  margin: 80px auto;
  text-align: center;
  color: var(--vp-ink-2, #5a5550);
  line-height: 1.55;
}
.pk-nulla__titolo {
  font-family: var(--vp-serif, Georgia, serif);
  font-size: 21px;
  color: var(--vp-ink-1, #2e2b28);
  margin-bottom: 8px;
}
.pk-foglio {
  max-width: 780px;
  margin: 0 auto;
}
.pk-testata {
  padding-bottom: 18px;
  border-bottom: 1px solid var(--vp-paper-3, #e5ded4);
  margin-bottom: 26px;
}
.pk-testata__casa {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.09em;
  color: var(--vp-terra, #b4703f);
}
.pk-testata__titolo {
  font-family: var(--vp-serif, Georgia, serif);
  font-size: 27px;
  line-height: 1.2;
  margin: 6px 0 4px;
  font-weight: 500;
}
.pk-testata__indirizzo {
  font-size: 13.5px;
  color: var(--vp-ink-3, #857e76);
}
.pk-testata__intro {
  margin-top: 16px;
}
.pk-voce {
  margin-bottom: 34px;
}
.pk-voce__titolo {
  font-family: var(--vp-serif, Georgia, serif);
  font-size: 19px;
  font-weight: 500;
  line-height: 1.3;
  margin: 0 0 12px;
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.pk-voce__n {
  font-size: 12px;
  color: var(--vp-terra, #b4703f);
  font-variant-numeric: tabular-nums;
  border: 1px solid var(--vp-paper-3, #e5ded4);
  border-radius: 50%;
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.pk-pdf {
  width: 100%;
  height: 70vh;
  min-height: 380px;
  border: 1px solid var(--vp-paper-3, #e5ded4);
  border-radius: 10px;
  background: #fff;
}
.pk-pdf__fallback {
  padding: 22px;
  font-size: 14px;
}
.pk-apri {
  display: inline-block;
  margin-top: 8px;
  font-size: 13px;
  color: var(--vp-terra, #b4703f);
}
.pk-md {
  font-size: 15px;
  line-height: 1.62;
  color: var(--vp-ink-1, #2e2b28);
}
/* I titoli del markdown sono dentro il flusso di una voce, non titoli di
   pagina: senza una scala esplicita ereditano gli h1/h2 globali di Quasar e
   un «## In sintesi» diventa più grande del titolo del pacchetto. */
.pk-md :deep(h1),
.pk-md :deep(h2),
.pk-md :deep(h3),
.pk-md :deep(h4) {
  font-family: var(--vp-serif, Georgia, serif);
  font-weight: 600;
  margin: 18px 0 7px;
  line-height: 1.3;
  letter-spacing: 0;
}
.pk-md :deep(h1) {
  font-size: 19.5px;
}
.pk-md :deep(h2) {
  font-size: 17.5px;
}
.pk-md :deep(h3),
.pk-md :deep(h4) {
  font-size: 15.5px;
}
.pk-md :deep(p) {
  margin: 0 0 11px;
}
.pk-md :deep(ul),
.pk-md :deep(ol) {
  margin: 0 0 11px;
  padding-left: 22px;
}
.pk-md :deep(li) {
  margin-bottom: 4px;
}
.pk-md :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin-bottom: 12px;
}
.pk-md :deep(th),
.pk-md :deep(td) {
  border: 1px solid var(--vp-paper-3, #e5ded4);
  padding: 6px 9px;
  text-align: left;
}
.pk-md :deep(blockquote) {
  margin: 0 0 11px;
  padding-left: 13px;
  border-left: 3px solid var(--vp-paper-3, #e5ded4);
  color: var(--vp-ink-2, #5a5550);
}
.pk-piede {
  margin-top: 40px;
  padding-top: 16px;
  border-top: 1px solid var(--vp-paper-3, #e5ded4);
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--vp-ink-3, #857e76);
}
</style>
