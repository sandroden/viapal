<template>
  <q-dialog v-model="aperto" persistent>
    <q-card class="vp-bc-dlg">
      <q-card-section class="row items-center q-pb-none">
        <div>
          <div class="vp-eyebrow">Chiusura</div>
          <div class="vp-display vp-bc-dlg__titolo">
            Bonifico di restituzione — {{ tenantNominativo }}
          </div>
          <div class="vp-bc-dlg__sub">
            Un solo movimento in uscita, imputato alla restituzione del
            deposito e a tutto ciò che viene trattenuto o accreditato.
            Netto atteso <span class="vp-mono">{{ formattaEuro(chiusura.netto) }}</span>
          </div>
        </div>
        <q-space />
        <q-btn icon="close" flat round dense @click="annulla" />
      </q-card-section>

      <q-card-section>
        <q-form class="q-gutter-md" @submit.prevent="salva">
          <q-input v-model="form.data" type="date" outlined dense label="Data del bonifico" />
          <div>
            <q-input
              v-model.number="form.importo"
              type="number"
              step="0.01"
              outlined
              dense
              label="Importo bonificato (€)"
              @focus="selezionaTutto"
            />
            <div v-if="notaImporto" class="vp-bc-dlg__nota" :class="{ 'vp-bc-dlg__nota--avviso': scarto !== 0 }">
              {{ notaImporto }}
            </div>
          </div>
          <q-select
            v-model="form.owner_account"
            :options="opzioniConti"
            option-label="label"
            option-value="value"
            emit-value
            map-options
            outlined
            dense
            label="Conto da cui è uscito"
            :rules="[(v) => !!v || 'Seleziona un conto']"
          />
          <q-input v-model="form.descrizione" outlined dense label="Descrizione movimento" maxlength="300" />
          <q-input v-model="form.note" outlined dense type="textarea" label="Note (opzionale)" autogrow />

          <q-list dense bordered class="vp-bc-dlg__lista">
            <q-item-label header>Imputazioni del bonifico</q-item-label>
            <q-item v-for="c in chiusura.componenti" :key="c.receivable_id ?? 'deposito'">
              <q-item-section>
                <q-item-label>{{ c.descrizione }}</q-item-label>
                <q-item-label caption>{{ etichettaImputazione(c) }}</q-item-label>
              </q-item-section>
              <q-item-section side>
                <span class="vp-mono">{{ formattaEuro(c.effetto) }}</span>
              </q-item-section>
            </q-item>
            <q-item v-if="chiusura.resti_bonifici !== 0">
              <q-item-section>
                <q-item-label>Resti di bonifici precedenti</q-item-label>
                <q-item-label caption>già nel saldo, non imputati qui</q-item-label>
              </q-item-section>
              <q-item-section side>
                <span class="vp-mono">{{ formattaEuro(chiusura.resti_bonifici) }}</span>
              </q-item-section>
            </q-item>
          </q-list>

          <q-banner v-if="errore" class="bg-red-1 text-red-9" rounded>{{ errore }}</q-banner>
        </q-form>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn flat color="primary" label="Annulla" no-caps @click="annulla" />
        <q-btn
          unelevated
          color="primary"
          label="Registra"
          no-caps
          :loading="salvando"
          :disable="!form.owner_account || !importoValido"
          @click="salva"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import { Notify } from 'quasar';
import { api } from 'boot/axios';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import type { BankAccountInfo } from 'stores/auth';
import type { Chiusura, ChiusuraComponente } from 'stores/tenantSituazione';

const props = defineProps<{
  modelValue: boolean;
  tenantId: number;
  tenantNominativo: string;
  chiusura: Chiusura;
  ownerAccounts: BankAccountInfo[];
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void;
  (e: 'saved'): void;
}>();

const { formattaEuro } = useFormatoEuro();

const aperto = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
});

const opzioniConti = computed(() =>
  props.ownerAccounts.map((a) => ({
    value: a.id,
    label: `${a.banca} — ${a.intestatario} (…${a.iban.slice(-4)})`,
  })),
);

const form = reactive({
  data: new Date().toISOString().slice(0, 10),
  importo: props.chiusura.netto,
  owner_account: (props.ownerAccounts.length === 1 ? props.ownerAccounts[0]?.id : null) ?? null,
  descrizione: `Restituzione deposito — ${props.tenantNominativo}`,
  note: '',
});

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      form.importo = props.chiusura.netto;
      errore.value = '';
    }
  },
);

const salvando = ref(false);
const errore = ref('');

const importoValido = computed(
  () => typeof form.importo === 'number' && !Number.isNaN(form.importo) && form.importo > 0,
);

/** Scarto rispetto al netto atteso, arrotondato al centesimo. */
const scarto = computed(() => Math.round(((form.importo || 0) - props.chiusura.netto) * 100) / 100);

const notaImporto = computed(() => {
  if (!importoValido.value) return '';
  if (scarto.value > 0) {
    return `${formattaEuro(scarto.value)} oltre il netto: resteranno sul movimento come debito dell'inquilino.`;
  }
  if (scarto.value < 0) {
    return `${formattaEuro(-scarto.value)} sotto il netto: la restituzione resterà aperta per quella parte.`;
  }
  return 'Pari al netto atteso: chiude tutte le righe.';
});

function etichettaImputazione(c: ChiusuraComponente): string {
  if (c.causale === 'deposito') return 'restituzione del deposito';
  if (c.effetto < 0) return 'trattenuto dal deposito';
  return 'accredito all\'inquilino';
}

function selezionaTutto(e: Event): void {
  (e.target as HTMLInputElement | null)?.select();
}

function annulla(): void {
  aperto.value = false;
}

async function salva(): Promise<void> {
  if (!importoValido.value || !form.owner_account) return;
  salvando.value = true;
  errore.value = '';
  try {
    await api.post(`/api/v1/tenants/${props.tenantId}/chiusura/`, {
      data: form.data,
      importo: form.importo.toFixed(2),
      owner_account: form.owner_account,
      descrizione: form.descrizione,
      note: form.note,
    });
    Notify.create({ type: 'positive', message: 'Bonifico di chiusura registrato.' });
    aperto.value = false;
    emit('saved');
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } };
    errore.value = err.response?.data?.detail ?? 'Errore nella registrazione.';
  } finally {
    salvando.value = false;
  }
}
</script>

<style lang="scss" scoped>
.vp-bc-dlg {
  width: 520px;
  max-width: 92vw;
}
.vp-bc-dlg__titolo {
  font-size: var(--vp-text-lg, 1.1rem);
}
.vp-bc-dlg__sub {
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm, 0.9rem);
  margin-top: 2px;
}
.vp-bc-dlg__nota {
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm, 0.9rem);
  margin-top: 4px;
}
.vp-bc-dlg__nota--avviso {
  color: var(--vp-terra, #b56a3b);
}
.vp-bc-dlg__lista {
  background: var(--vp-paper-1);
  border-radius: var(--vp-r-md);
}
</style>
