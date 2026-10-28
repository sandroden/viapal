<template>
  <q-dialog v-model="aperto" maximized transition-show="slide-up" transition-hide="slide-down">
    <div v-if="voce" class="vp-dvis">
      <!-- Testata: chi è il documento, non solo il nome del file -->
      <header class="vp-dvis__testa">
        <q-btn flat round dense icon="close" color="white" aria-label="Chiudi" @click="chiudi" />
        <div class="vp-dvis__titolo">
          <div class="vp-dvis__nome">{{ voce.titolo ?? voce.tipo_display }}</div>
          <div class="vp-dvis__meta">{{ meta }}</div>
        </div>
        <DocBadgeFirma v-if="voce.versioni && pagina" :stato="pagina.stato_firma" />
        <DocBadgeStato v-if="voce.stato !== 'ok'" :stato="voce.stato" />
      </header>

      <!-- La pagina -->
      <div class="vp-dvis__foglio" :class="{ 'vp-dvis__foglio--pdf': pagina?.is_pdf }">
        <DocPagina v-if="pagina" :key="pagina.id" :pagina="pagina" />
      </div>

      <!-- Fronte e retro: due pagine dello stesso documento, non due file.
           Le versioni dei documenti firmati no: si scelgono dalla voce
           espansa nell'elenco, qui si guarda quella aperta. -->
      <div v-if="!voce.versioni && voce.pagine.length > 1" class="vp-dvis__pagine">
        <button
          v-for="(p, i) in voce.pagine"
          :key="p.id"
          class="vp-dvis__tab"
          :class="{ 'vp-dvis__tab--on': i === indice }"
          @click="indice = i"
        >
          {{ p.etichetta }}
        </button>
      </div>

      <!-- Correzione dello stato della firma (solo la proprietà): il default
           al caricamento indovina il passo, ma non sempre. -->
      <div v-if="voce.versioni && pagina && correggiFirma" class="vp-dvis__pagine">
        <button
          v-for="s in STATI_FIRMA"
          :key="s.value"
          class="vp-dvis__tab"
          :class="{ 'vp-dvis__tab--on': s.value === pagina.stato_firma }"
          :aria-pressed="s.value === pagina.stato_firma"
          @click="s.value !== pagina.stato_firma && emit('statoFirma', pagina.id, s.value)"
        >
          {{ s.label }}
        </button>
      </div>

      <!-- Azioni -->
      <footer class="vp-dvis__azioni">
        <a :href="pagina?.file" :download="pagina?.nome_file" class="vp-dvis__azione">
          <q-icon name="download" size="20px" />
          Scarica
        </a>
        <!-- Una versione nuova non sostituisce nulla: si aggiunge al giro. -->
        <button v-if="!soloLettura" class="vp-dvis__azione" @click="emit('sostituisci', voce)">
          <q-icon :name="voce.versioni ? 'upload' : 'photo_camera'" size="20px" />
          {{ voce.versioni ? 'Carica nuova versione' : 'Sostituisci' }}
        </button>
        <button
          v-if="!soloLettura && pagina?.modificabile"
          class="vp-dvis__azione vp-dvis__azione--rischio"
          @click="confermaElimina"
        >
          <q-icon name="delete_outline" size="20px" />
          Elimina
        </button>
      </footer>
    </div>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useQuasar } from 'quasar';
import DocPagina from './DocPagina.vue';
import DocBadgeStato from './DocBadgeStato.vue';
import DocBadgeFirma from './DocBadgeFirma.vue';
import type { StatoFirma, VoceFascicolo } from 'stores/fascicolo';
import { STATI_FIRMA, confermaEliminaFile } from 'src/utils/statoDocumento';
import { useFormatoData } from 'src/composables/useFormatoData';

const props = defineProps<{
  modelValue: boolean;
  /** Voce da visualizzare (con almeno una pagina). */
  voce: VoceFascicolo | null;
  /** File da mostrare all'apertura (una versione scelta dall'elenco, la
   *  pagina già aperta nel visore affiancato); assente = il primo. */
  paginaId?: number | null;
  soloLettura?: boolean;
  /** Offre la correzione dello stato della firma (lato proprietà). */
  correggiFirma?: boolean;
}>();

const emit = defineEmits<{
  'update:modelValue': [valore: boolean];
  sostituisci: [voce: VoceFascicolo];
  elimina: [id: number];
  statoFirma: [id: number, stato: StatoFirma];
}>();

const $q = useQuasar();
const { formattaData } = useFormatoData();

const aperto = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
});

const indice = ref(0);
watch(
  () => [props.voce, props.paginaId] as const,
  ([voce, id]) => {
    const i = voce && id != null ? voce.pagine.findIndex((p) => p.id === id) : -1;
    indice.value = Math.max(i, 0);
  },
  { immediate: true },
);

const pagina = computed(() => props.voce?.pagine[indice.value] ?? null);

const meta = computed(() => {
  const voce = props.voce;
  if (!voce) return '';
  const parti: string[] = [];
  // Per le versioni lo stato sta nel badge: qui la data di quella aperta.
  if (voce.versioni && pagina.value) {
    const verbo = pagina.value.generato ? 'generata' : 'caricata';
    parti.push(`${verbo} il ${formattaData(pagina.value.created_at)}`);
    if (voce.pagine.length > 1) parti.push(`${voce.pagine.length} versioni`);
    return parti.join(' · ');
  }
  if (voce.pagine.length > 1 && pagina.value) parti.push(pagina.value.etichetta);
  if (voce.data_scadenza) {
    parti.push(
      (voce.stato === 'scaduto' ? 'scaduto il ' : 'scade il ') +
        formattaData(voce.data_scadenza),
    );
  } else if (voce.caricato_il) {
    parti.push(`caricato il ${formattaData(voce.caricato_il)}`);
  }
  return parti.join(' · ');
});

function chiudi() {
  aperto.value = false;
}

function confermaElimina() {
  const corrente = pagina.value;
  if (!corrente || !props.voce) return;
  confermaEliminaFile($q, props.voce, corrente, () => emit('elimina', corrente.id));
}
</script>

<style scoped>
/* Fondo scuro: il documento è la cosa illuminata, il resto sparisce. */
.vp-dvis {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: oklch(0.24 0.02 55);
  color: var(--vp-cream);
}
.vp-dvis__testa {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-3);
  padding: var(--vp-gap-3) var(--vp-gap-4);
  padding-top: max(var(--vp-gap-3), env(safe-area-inset-top));
}
.vp-dvis__titolo {
  flex: 1;
  min-width: 0;
}
.vp-dvis__nome {
  font-size: var(--vp-text-md);
  font-weight: 500;
}
.vp-dvis__meta {
  font-size: var(--vp-text-xs);
  color: oklch(0.78 0.015 70);
}
.vp-dvis__foglio {
  flex: 1;
  min-height: 0;
  padding: var(--vp-gap-1) var(--vp-gap-5) 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
/* Il PDF ha già i suoi margini interni: gli si dà tutta la finestra. */
.vp-dvis__foglio--pdf {
  padding: 0;
}
.vp-dvis__pagine {
  display: flex;
  justify-content: center;
  gap: var(--vp-gap-2);
  padding: var(--vp-gap-4) 0 var(--vp-gap-1);
}
.vp-dvis__tab {
  height: 28px;
  padding: 0 12px;
  border: none;
  border-radius: var(--vp-r-pill);
  cursor: pointer;
  font-family: var(--vp-font-ui);
  font-size: 12.5px;
  background: oklch(0.34 0.02 55);
  color: oklch(0.8 0.015 70);
}
.vp-dvis__tab--on {
  background: var(--vp-cream);
  color: var(--vp-ink);
}
.vp-dvis__tab--on {
  font-weight: 500;
  cursor: default;
}
.vp-dvis__azioni {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: 1fr;
  gap: 1px;
  background: oklch(0.32 0.018 55);
  border-top: 1px solid oklch(0.32 0.018 55);
  padding-bottom: env(safe-area-inset-bottom);
}
.vp-dvis__azione {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--vp-gap-1);
  padding: 14px 0 10px;
  border: none;
  background: oklch(0.24 0.02 55);
  color: var(--vp-cream);
  font-family: var(--vp-font-ui);
  font-size: var(--vp-text-xs);
  text-align: center;
  text-decoration: none;
  cursor: pointer;
}
.vp-dvis__azione--rischio {
  color: oklch(0.76 0.09 28);
}
</style>
