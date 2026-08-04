<template>
  <q-dialog v-model="aperto" @before-show="carica">
    <div class="vp-gen">
      <header class="vp-gen__testa">
        <div>
          <span class="vp-eyebrow">Genera documento</span>
          <div class="vp-gen__titolo">{{ anteprima?.documento_display ?? titoloAtteso }}</div>
        </div>
        <q-btn flat round dense icon="close" aria-label="Chiudi" @click="aperto = false" />
      </header>

      <div class="vp-gen__corpo">
        <q-inner-loading :showing="caricamento" />

        <div v-if="errore" class="vp-banner vp-banner--late">
          <q-icon name="error_outline" size="19px" />
          <div>{{ errore }}</div>
        </div>

        <!-- Dati mancanti: non li chiediamo qui, diciamo dove compilarli -->
        <template v-else-if="anteprima && !anteprima.completo">
          <p class="vp-gen__intro">
            Mancano {{ anteprima.mancanti.length }}
            {{ anteprima.mancanti.length === 1 ? 'dato' : 'dati' }}. Si compilano
            dove stanno di casa, non qui: da lì torni e generi.
          </p>
          <ul class="vp-gen__mancanti">
            <li v-for="m in anteprima.mancanti" :key="m.campo + m.etichetta">
              <div class="vp-gen__mtesto">
                <div class="vp-gen__metichetta">{{ m.etichetta }}</div>
                <div class="vp-gen__mdove">{{ m.dove }}</div>
              </div>
              <button class="vp-btn vp-btn--soft vp-gen__mvai" @click="vai(m)">
                Vai
                <q-icon v-if="m.esterno" name="open_in_new" size="13px" />
              </button>
            </li>
          </ul>
        </template>

        <!-- Pronto: si rilegge cosa finirà nel documento -->
        <template v-else-if="anteprima">
          <div v-if="anteprima.esistente" class="vp-banner vp-gen__avviso">
            <q-icon name="history" size="19px" />
            <div>
              Ne esiste già uno {{ anteprima.esistente.descrizione }}: verrà
              sostituito. Le copie firmate caricate a mano restano dove sono.
            </div>
          </div>

          <dl class="vp-gen__riepilogo">
            <template v-for="riga in righeRiepilogo" :key="riga.etichetta">
              <dt>{{ riga.etichetta }}</dt>
              <dd>{{ riga.valore }}</dd>
            </template>
          </dl>
        </template>
      </div>

      <footer class="vp-gen__azioni">
        <button class="vp-btn vp-btn--ghost" @click="aperto = false">Annulla</button>
        <button
          class="vp-btn vp-btn--primary"
          :disabled="!anteprima?.completo || generazione"
          @click="genera"
        >
          <q-icon v-if="!generazione" name="picture_as_pdf" size="15px" />
          <q-spinner v-else size="15px" />
          {{ anteprima?.esistente ? 'Rigenera PDF' : 'Genera PDF' }}
        </button>
      </footer>
    </div>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useQuasar } from 'quasar';
import { useRouter } from 'vue-router';
import { useFascicoloStore, type AnteprimaDocumento, type DatoMancante } from 'stores/fascicolo';
import { useFormatoData } from 'src/composables/useFormatoData';
import { messaggioErrore } from 'src/utils/apiErrors';

const props = defineProps<{
  modelValue: boolean;
  tenantId: number;
  /** Codice del generatore (``voce.generabile``). */
  documento: string | null;
  /** Titolo mostrato prima che l'anteprima arrivi. */
  titoloAtteso?: string;
}>();

const emit = defineEmits<{
  'update:modelValue': [valore: boolean];
  generato: [];
}>();

const $q = useQuasar();
const router = useRouter();
const { formattaData } = useFormatoData();
const fascicoloStore = useFascicoloStore();

const anteprima = ref<AnteprimaDocumento | null>(null);
const caricamento = ref(false);
const generazione = ref(false);
const errore = ref<string | null>(null);

const aperto = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
});

// Ogni documento dichiara il proprio riepilogo: le righe che non gli
// appartengono non arrivano affatto (la cessione di fabbricato non parla di
// canoni, l'atto di subentro non ripete l'indirizzo).
const righeRiepilogo = computed(() => {
  const r = anteprima.value?.riepilogo;
  if (!r) return [];
  const righe: { etichetta: string; valore: string }[] = [];
  if (r.stanza) righe.push({ etichetta: 'Stanza', valore: r.stanza });
  if (r.decorrenza) {
    righe.push({ etichetta: 'Decorrenza', valore: formattaData(r.decorrenza) });
  }
  if (r.data_cessione) {
    righe.push({
      etichetta: 'Data della cessione',
      valore: formattaData(r.data_cessione),
    });
  }
  if (r.canone) righe.push({ etichetta: 'Canone mensile', valore: `${r.canone} €` });
  if (r.oneri_accessori) {
    righe.push({ etichetta: 'Oneri accessori', valore: `${r.oneri_accessori} €` });
  }
  if (r.deposito) {
    righe.push({
      etichetta: 'Deposito',
      valore: `${r.deposito} € in ${r.rate_deposito} ${r.rate_deposito === 1 ? 'rata' : 'rate'}`,
    });
  }
  if (r.uscente) righe.push({ etichetta: 'Inquilino uscente', valore: r.uscente });
  if (r.firmatario) righe.push({ etichetta: 'Firma come cedente', valore: r.firmatario });
  if (r.comproprietari?.length) {
    righe.push({ etichetta: 'Comproprietari', valore: r.comproprietari.join(', ') });
  }
  if (r.contratto) righe.push({ etichetta: 'Contratto', valore: r.contratto });
  if (r.fabbricato) righe.push({ etichetta: 'Fabbricato', valore: r.fabbricato });
  return righe;
});

async function carica() {
  if (!props.documento) return;
  caricamento.value = true;
  errore.value = null;
  anteprima.value = null;
  try {
    anteprima.value = await fascicoloStore.anteprima(props.tenantId, props.documento);
  } catch (e: unknown) {
    errore.value = messaggioErrore(e, 'Impossibile preparare il documento.');
  } finally {
    caricamento.value = false;
  }
}

/** I dati di competenza dell'admin Django escono dalla PWA: solo quelli
 *  aprono una nuova scheda. Tutto il resto resta dentro l'app. */
function vai(mancante: DatoMancante) {
  if (mancante.esterno) {
    window.open(mancante.link, '_blank');
    return;
  }
  aperto.value = false;
  void router.push(mancante.link);
}

async function genera() {
  if (!props.documento) return;
  generazione.value = true;
  try {
    await fascicoloStore.genera(props.tenantId, props.documento);
    $q.notify({ type: 'positive', message: 'Documento generato.' });
    aperto.value = false;
    emit('generato');
  } catch (e: unknown) {
    $q.notify({
      type: 'negative',
      message: messaggioErrore(e, 'Errore nella generazione.'),
    });
  } finally {
    generazione.value = false;
  }
}
</script>

<style scoped>
.vp-gen {
  width: 100%;
  max-width: 560px;
  background: var(--vp-paper);
  border-radius: var(--vp-r-lg);
  display: flex;
  flex-direction: column;
  max-height: 86vh;
}
.vp-gen__testa {
  display: flex;
  align-items: flex-start;
  gap: var(--vp-gap-3);
  padding: var(--vp-gap-4) var(--vp-gap-4) var(--vp-gap-3);
  border-bottom: 1px solid var(--vp-paper-3);
}
.vp-gen__testa > div:first-child {
  flex: 1;
}
.vp-gen__titolo {
  font-size: var(--vp-text-lg);
  margin-top: 2px;
}
.vp-gen__corpo {
  position: relative;
  flex: 1;
  min-height: 120px;
  overflow-y: auto;
  padding: var(--vp-gap-4);
}
.vp-gen__avviso {
  margin-bottom: var(--vp-gap-4);
}
.vp-gen__intro {
  margin: 0 0 var(--vp-gap-3);
  font-size: var(--vp-text-sm);
  color: var(--vp-ink-3);
  line-height: 1.5;
}
.vp-gen__mancanti {
  list-style: none;
  margin: 0;
  padding: 0;
}
.vp-gen__mancanti li {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-3);
  padding: var(--vp-gap-2) 0;
  border-bottom: 1px solid var(--vp-paper-3);
}
.vp-gen__mancanti li:last-child {
  border-bottom: none;
}
.vp-gen__mtesto {
  flex: 1;
  min-width: 0;
}
.vp-gen__metichetta {
  font-size: var(--vp-text-sm);
}
.vp-gen__mdove {
  font-size: 12.5px;
  color: var(--vp-ink-3);
  margin-top: 1px;
}
.vp-gen__mvai {
  height: 30px;
  padding: 0 12px;
  font-size: 12.5px;
  gap: 4px;
}
.vp-gen__riepilogo {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: var(--vp-gap-2) var(--vp-gap-4);
  margin: 0;
  font-size: var(--vp-text-sm);
}
.vp-gen__riepilogo dt {
  color: var(--vp-ink-3);
}
.vp-gen__riepilogo dd {
  margin: 0;
}
.vp-gen__azioni {
  display: flex;
  justify-content: flex-end;
  gap: var(--vp-gap-2);
  padding: var(--vp-gap-3) var(--vp-gap-4);
  border-top: 1px solid var(--vp-paper-3);
}
.vp-gen__azioni .vp-btn {
  height: 36px;
  font-size: var(--vp-text-sm);
  gap: 6px;
}
</style>
