<template>
  <q-dialog v-model="aperto" @before-show="riempi">
    <q-card style="width: 520px; max-width: min(560px, 92vw)">
      <q-card-section>
        <div class="vp-section-title">Modifica documento</div>
        <div class="vp-hint">{{ nomeFile }}</div>
      </q-card-section>

      <q-card-section class="q-gutter-md">
        <q-select
          v-model="form.tipo"
          :options="tipi"
          label="Tipo"
          outlined
          dense
          emit-value
          map-options
          data-testid="modifica-doc-tipo"
        />

        <q-input
          v-model="form.descrizione"
          label="Descrizione"
          outlined
          dense
          hint="Facoltativa: distingue due file dello stesso tipo"
          data-testid="modifica-doc-descrizione"
        />

        <!-- Lo stesso campo del foglio di caricamento: è l'unica cosa che
             decide se il documento sta sulla riga del contratto o fra i
             documenti generali della casa. -->
        <q-select
          v-model="form.contract"
          :options="opzioniDestinazione"
          label="Collega a"
          outlined
          dense
          emit-value
          map-options
          :hint="notaDestinazione"
          data-testid="modifica-doc-contratto"
        />

        <q-toggle v-model="form.visibile" dense>
          <span class="imm-mod__vis">Visibile agli inquilini</span>
        </q-toggle>

        <q-banner v-if="ambitoIncoerente" class="imm-mod__errore" rounded dense>
          Scegli il contratto: una carta di contratto fra i documenti generali
          della casa sarebbe visibile agli inquilini di ogni contratto.
        </q-banner>

        <q-banner v-else-if="errore" class="imm-mod__errore" rounded dense>
          {{ errore }}
        </q-banner>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn v-close-popup flat no-caps label="Annulla" />
        <q-btn
          color="primary"
          unelevated
          no-caps
          label="Salva"
          :loading="salvataggio"
          :disable="ambitoIncoerente"
          data-testid="modifica-doc-salva"
          @click="salva"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useQuasar } from 'quasar';
import {
  richiedeContratto,
  type DocumentiStore,
  type DocumentoFE,
  type TipoDocumentoOption,
} from 'stores/documenti';

const props = withDefaults(
  defineProps<{
    store: DocumentiStore;
    documento: DocumentoFE | null;
    tipi: TipoDocumentoOption[];
    contratti?: { id: number; nome: string; data_decorrenza: string }[];
  }>(),
  { contratti: () => [] },
);

const emit = defineEmits<{ (e: 'salvato'): void }>();

const $q = useQuasar();
const aperto = defineModel<boolean>({ default: false });

const salvataggio = ref(false);
const errore = ref('');
const form = ref({
  tipo: 'altro',
  descrizione: '',
  contract: null as number | null,
  visibile: false,
});

const nomeFile = computed(() => {
  const url = props.documento?.file ?? '';
  // Gli URL firmati portano la querystring: senza toglierla il nome è
  // illeggibile e due file diversi sembrano lo stesso.
  const senzaQuery = url.split('?')[0] ?? '';
  return decodeURIComponent(senzaQuery.split('/').pop() ?? '');
});

const opzioniDestinazione = computed(() => [
  { label: 'La casa (documento generale)', value: null },
  ...props.contratti.map((c) => ({
    label: `Contratto · ${c.nome || `dal ${c.data_decorrenza}`}`,
    value: c.id,
  })),
]);

/** Il backend lo rifiuta comunque, ma dirlo prima evita un errore di
 *  validazione grezzo su un'azione che si può correggere in un click. */
const ambitoIncoerente = computed(
  () => form.value.contract === null && richiedeContratto(form.value.tipo),
);

const notaDestinazione = computed(() => {
  if (form.value.contract !== null) {
    return 'Compare sulla riga del contratto; se visibile, solo agli inquilini che vi stanno dentro.';
  }
  return richiedeContratto(form.value.tipo)
    ? 'Un documento di questo tipo è la carta di un contratto: indica quale.'
    : 'Compare fra i documenti generali della casa.';
});

function riempi() {
  const d = props.documento;
  errore.value = '';
  form.value = {
    tipo: d?.tipo ?? 'altro',
    descrizione: d?.descrizione ?? '',
    contract: d?.contract ?? null,
    visibile: !!d?.visibile_inquilini,
  };
}

async function salva() {
  const d = props.documento;
  if (!d) return;
  errore.value = '';
  salvataggio.value = true;
  const ok = await props.store.aggiorna(d.id, {
    tipo: form.value.tipo,
    descrizione: form.value.descrizione,
    contract: form.value.contract,
    visibile_inquilini: form.value.visibile,
  });
  salvataggio.value = false;
  if (!ok) {
    errore.value = props.store.errore ?? 'Salvataggio non riuscito.';
    return;
  }
  $q.notify({ type: 'positive', message: 'Documento aggiornato.' });
  aperto.value = false;
  emit('salvato');
}
</script>

<style scoped>
.imm-mod__vis {
  font-size: 13px;
}
.imm-mod__errore {
  background: var(--vp-clay-soft, #fbeae5);
  color: var(--vp-clay-deep, #8c3b21);
  font-size: 12.5px;
}
</style>
