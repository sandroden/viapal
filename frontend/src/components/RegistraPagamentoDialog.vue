<template>
  <q-dialog v-model="aperto" persistent>
    <q-card class="vp-rp-dlg">
      <q-card-section class="row items-center q-pb-none">
        <div>
          <div class="vp-eyebrow">Registra pagamento</div>
          <div class="vp-display vp-rp-dlg__titolo">
            {{ titoloDialog }}
          </div>
          <div class="vp-rp-dlg__sub">
            Dovuto <span class="vp-mono">{{ formattaEuro(receivable.importo_dovuto) }}</span>
            <span v-if="residuo !== receivable.importo_dovuto">
              · Residuo
              <span class="vp-mono">{{ formattaEuro(residuo) }}</span>
            </span>
          </div>
        </div>
        <q-space />
        <q-btn icon="close" flat round dense @click="annulla" />
      </q-card-section>

      <q-card-section>
        <q-form class="q-gutter-md" @submit.prevent="salva">
          <q-input
            v-model="form.data"
            type="date"
            outlined
            dense
            label="Data del bonifico"
          />
          <q-input
            v-model.number="form.importo"
            type="number"
            step="0.01"
            outlined
            dense
            label="Importo (€)"
          />
          <q-select
            v-model="form.owner_account"
            :options="opzioniConti"
            option-label="label"
            option-value="value"
            emit-value
            map-options
            outlined
            dense
            label="Conto destinazione"
            :rules="[(v) => !!v || 'Seleziona un conto']"
          />
          <q-input
            v-model="form.descrizione"
            outlined
            dense
            label="Descrizione bonifico"
            maxlength="300"
          />
          <q-input
            v-model="form.note"
            outlined
            dense
            type="textarea"
            label="Note (opzionale)"
            autogrow
          />
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

export type CausaleReceivable = 'affitto' | 'utenze' | 'extra' | 'deposito';

export interface ReceivableInput {
  id: number;
  causale: CausaleReceivable;
  importo_dovuto: number;
  importo_pagato: number;
  descrizione: string;
  tenant_nominativo: string;
  scadenza: string;
  bank_account_destinazione_id: number | null;
}

const props = defineProps<{
  modelValue: boolean;
  receivable: ReceivableInput;
  ownerAccounts: BankAccountInfo[];
  defaultOwnerAccountId: number | null;
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

const residuo = computed(() => {
  const d = props.receivable.importo_dovuto - props.receivable.importo_pagato;
  // se dovuto>0 → residuo positivo restante; se dovuto<0 (restituzione
  // deposito) → residuo negativo; in entrambi i casi fallback su dovuto.
  if (props.receivable.importo_dovuto >= 0) {
    return d > 0 ? d : props.receivable.importo_dovuto;
  }
  return d < 0 ? d : props.receivable.importo_dovuto;
});

const opzioniConti = computed(() =>
  props.ownerAccounts.map((a) => ({
    value: a.id,
    label: `${a.banca} — ${a.intestatario} (…${a.iban.slice(-4)})`,
  })),
);

const CAUSALE_LABEL: Record<CausaleReceivable, string> = {
  affitto: 'Affitto',
  utenze: 'Utenze',
  extra: 'Extra',
  deposito: 'Deposito',
};
const MESI_ABBR = [
  '',
  'Gen',
  'Feb',
  'Mar',
  'Apr',
  'Mag',
  'Giu',
  'Lug',
  'Ago',
  'Set',
  'Ott',
  'Nov',
  'Dic',
];

const titoloDialog = computed(
  () =>
    `${CAUSALE_LABEL[props.receivable.causale]} — ${props.receivable.tenant_nominativo}`,
);

function descrizioneSuggerita(): string {
  const r = props.receivable;
  const d = new Date(r.scadenza);
  const mese = MESI_ABBR[d.getMonth() + 1];
  const anno = d.getFullYear();
  return `Bonifico ${r.tenant_nominativo} — ${CAUSALE_LABEL[r.causale]} ${mese} ${anno}`;
}

function contoDiDefault(): number | null {
  if (props.receivable.bank_account_destinazione_id) {
    if (
      props.ownerAccounts.some(
        (a) => a.id === props.receivable.bank_account_destinazione_id,
      )
    ) {
      return props.receivable.bank_account_destinazione_id;
    }
  }
  if (
    props.defaultOwnerAccountId &&
    props.ownerAccounts.some((a) => a.id === props.defaultOwnerAccountId)
  ) {
    return props.defaultOwnerAccountId;
  }
  if (props.ownerAccounts.length === 1) {
    return props.ownerAccounts[0]!.id;
  }
  return null;
}

interface FormPagamento {
  data: string;
  importo: number;
  owner_account: number | null;
  descrizione: string;
  note: string;
}

const form = reactive<FormPagamento>({
  data: new Date().toISOString().slice(0, 10),
  importo: residuo.value,
  owner_account: contoDiDefault(),
  descrizione: descrizioneSuggerita(),
  note: '',
});

const salvando = ref(false);
const errore = ref('');

const importoValido = computed(() => {
  const imp = form.importo;
  if (!imp || Number.isNaN(imp)) return false;
  // segno coerente col dovuto (restituzione deposito: dovuto<0 → importo<0)
  return props.receivable.importo_dovuto >= 0 ? imp > 0 : imp < 0;
});

watch(
  () => props.modelValue,
  (apertoNuovo) => {
    if (apertoNuovo) {
      // reset alla riapertura per riflettere il receivable corrente
      form.data = new Date().toISOString().slice(0, 10);
      form.importo = residuo.value;
      form.owner_account = contoDiDefault();
      form.descrizione = descrizioneSuggerita();
      form.note = '';
      errore.value = '';
    }
  },
);

function annulla() {
  aperto.value = false;
}

async function salva() {
  if (!form.owner_account) {
    errore.value = 'Seleziona un conto destinazione.';
    return;
  }
  if (!importoValido.value) {
    errore.value =
      props.receivable.importo_dovuto < 0
        ? "L'importo deve essere negativo (restituzione)."
        : "L'importo deve essere maggiore di zero.";
    return;
  }
  salvando.value = true;
  errore.value = '';
  try {
    await api.post(
      `/api/v1/receivables/${props.receivable.id}/registra-pagamento/`,
      {
        data: form.data,
        importo: String(form.importo),
        owner_account: form.owner_account,
        descrizione: form.descrizione,
        note: form.note,
      },
    );
    Notify.create({ type: 'positive', message: 'Pagamento registrato.' });
    aperto.value = false;
    emit('saved');
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } };
    errore.value =
      err.response?.data?.detail ?? 'Errore nella registrazione del pagamento.';
  } finally {
    salvando.value = false;
  }
}
</script>

<style lang="scss" scoped>
.vp-rp-dlg {
  min-width: 480px;
  max-width: 92vw;
}
.vp-rp-dlg__titolo {
  font-size: var(--vp-text-lg, 1.1rem);
}
.vp-rp-dlg__sub {
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm, 0.9rem);
  margin-top: 2px;
}
</style>
