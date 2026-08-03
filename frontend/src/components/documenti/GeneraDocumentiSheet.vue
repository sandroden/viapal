<template>
  <q-dialog
    v-model="aperto"
    :position="$q.screen.lt.sm ? 'bottom' : 'standard'"
    @before-show="carica"
  >
    <div class="vp-gsheet">
      <div class="vp-gsheet__maniglia" />
      <h2 class="vp-display vp-gsheet__titolo">Genera un documento</h2>
      <p class="vp-gsheet__intro">
        Li compila l'applicazione dai dati che hai già — contratto, immobile,
        anagrafiche. Nessuno è dovuto: generi quello che ti serve, quando serve.
      </p>

      <div class="vp-gsheet__corpo">
        <q-inner-loading :showing="caricamento" />

        <div v-if="errore" class="vp-banner vp-banner--late">
          <q-icon name="error_outline" size="19px" />
          <div>{{ errore }}</div>
        </div>

        <button
          v-for="d in documenti"
          :key="d.codice"
          class="vp-gsheet__voce"
          @click="scegli(d)"
        >
          <div class="vp-gsheet__ic">
            <q-icon name="picture_as_pdf" size="19px" />
          </div>
          <div class="vp-gsheet__txt">
            <div class="vp-gsheet__nome">{{ d.titolo }}</div>
            <div class="vp-gsheet__nota">{{ nota(d) }}</div>
          </div>
          <q-icon name="chevron_right" size="18px" class="vp-gsheet__chevron" />
        </button>
      </div>
    </div>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useFascicoloStore, type DocumentoGenerabile } from 'stores/fascicolo';
import { useFormatoData } from 'src/composables/useFormatoData';

const props = defineProps<{
  modelValue: boolean;
  tenantId: number;
}>();

const emit = defineEmits<{
  'update:modelValue': [valore: boolean];
  /** Documento scelto: il dialog di generazione lo prende da qui. */
  scelto: [documento: DocumentoGenerabile];
}>();

const { formattaData } = useFormatoData();
const fascicoloStore = useFascicoloStore();

const documenti = ref<DocumentoGenerabile[]>([]);
const caricamento = ref(false);
const errore = ref<string | null>(null);

const aperto = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
});

/** Distinzione che conta prima di cliccare: sto creando o rifacendo? Le
 *  copie caricate a mano non contano — una rigenerazione non le tocca, e
 *  il dialog lo ripete prima di sostituire alcunché. */
function nota(d: DocumentoGenerabile): string {
  if (!d.esistente) return 'non ancora generato';
  return `già generato il ${formattaData(d.esistente.created_at)}`;
}

async function carica() {
  caricamento.value = true;
  errore.value = null;
  try {
    documenti.value = await fascicoloStore.generabili(props.tenantId);
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } };
    errore.value = err?.response?.data?.detail ?? 'Impossibile leggere l’elenco.';
  } finally {
    caricamento.value = false;
  }
}

function scegli(d: DocumentoGenerabile) {
  aperto.value = false;
  emit('scelto', d);
}
</script>

<style scoped>
.vp-gsheet {
  width: 100%;
  max-width: 480px;
  background: var(--vp-paper);
  border-radius: var(--vp-r-lg);
  padding: var(--vp-gap-4);
}
.vp-gsheet__maniglia {
  width: 36px;
  height: 4px;
  border-radius: var(--vp-r-pill);
  background: var(--vp-paper-3);
  margin: 0 auto var(--vp-gap-3);
}
.vp-gsheet__titolo {
  font-size: var(--vp-text-xl);
  margin: 0 0 var(--vp-gap-2);
}
.vp-gsheet__intro {
  margin: 0 0 var(--vp-gap-4);
  font-size: var(--vp-text-sm);
  color: var(--vp-ink-3);
  line-height: 1.5;
}
.vp-gsheet__corpo {
  position: relative;
  min-height: 80px;
}
.vp-gsheet__voce {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-3);
  width: 100%;
  padding: var(--vp-gap-3);
  margin-bottom: var(--vp-gap-2);
  text-align: left;
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-md);
  cursor: pointer;
}
.vp-gsheet__voce:hover {
  border-color: var(--vp-terra);
}
.vp-gsheet__ic {
  flex: none;
  width: 38px;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--vp-r-sm);
  background: var(--vp-terra-soft);
  color: var(--vp-terra-deep);
}
.vp-gsheet__txt {
  flex: 1;
  min-width: 0;
}
.vp-gsheet__nome {
  font-size: var(--vp-text-md);
  font-weight: 500;
  color: var(--vp-ink);
}
.vp-gsheet__nota {
  font-size: 12.5px;
  color: var(--vp-ink-3);
  margin-top: 2px;
}
.vp-gsheet__chevron {
  flex: none;
  color: var(--vp-ink-4);
}
</style>
