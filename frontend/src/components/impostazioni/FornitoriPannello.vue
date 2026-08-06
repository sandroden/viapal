<template>
  <CardSezione titolo="Fornitori">
    <template v-if="puoModificare" #azioni>
      <BtnSoft etichetta="Nuovo" data-testid="nuovo-fornitore" @click="apriDialog(null)" />
    </template>

    <div v-if="loading" class="q-pa-md flex flex-center">
      <q-spinner size="28px" />
    </div>
    <div v-else class="imm-elenco">
      <RigaElenco
        v-for="(f, i) in fornitori"
        :key="f.id"
        :ultima="i === fornitori.length - 1"
        data-testid="riga-fornitore"
      >
        <template #titolo>
          <span class="imm-compatto">{{ f.nome }}</span>
        </template>
        <template #meta>{{ dettaglio(f) }}</template>
        <template #azioni>
          <AzioniRiga
            :oggetto="f.nome"
            :puo-modificare="puoModificare"
            :puo-eliminare="puoModificare"
            @modifica="apriDialog(f)"
            @elimina="elimina(f)"
          />
        </template>
      </RigaElenco>
      <div v-if="fornitori.length === 0" class="imm-vuoto">Nessun fornitore registrato.</div>
    </div>
  </CardSezione>

  <!-- Dialog fornitore -->
  <q-dialog v-model="dialog">
    <q-card style="min-width: 380px">
      <q-card-section>
        <div class="vp-section-title">
          {{ inModifica ? 'Modifica fornitore' : 'Nuovo fornitore' }}
        </div>
      </q-card-section>
      <q-card-section class="q-gutter-md">
        <q-input
          v-model="form.nome"
          label="Nome"
          outlined
          dense
          autofocus
          data-testid="fornitore-nome"
        />
        <q-select
          v-model="form.tipo"
          :options="OPZIONI_TIPO"
          label="Tipo"
          outlined
          dense
          emit-value
          map-options
          data-testid="fornitore-tipo"
        />
        <q-input v-model="form.partita_iva" label="Partita IVA" outlined dense />
        <q-input v-model="form.contatto" label="Contatto" type="textarea" autogrow outlined dense />
        <q-banner v-if="errore" class="vp-banner-errore" rounded dense>{{ errore }}</q-banner>
      </q-card-section>
      <q-card-actions align="right">
        <q-btn v-close-popup flat label="Annulla" />
        <q-btn
          color="primary"
          label="Salva"
          :loading="saving"
          data-testid="salva-fornitore"
          @click="salva"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { api } from 'boot/axios';
import { messaggioErrore } from 'src/utils/apiErrors';
import CardSezione from './ui/CardSezione.vue';
import RigaElenco from './ui/RigaElenco.vue';
import BtnSoft from './ui/BtnSoft.vue';
import AzioniRiga from './ui/AzioniRiga.vue';

type TipoFornitore = 'energia' | 'gas' | 'acqua' | 'condominio' | 'altro';

interface Fornitore {
  id: number;
  nome: string;
  tipo: TipoFornitore;
  tipo_display?: string;
  partita_iva: string;
  contatto: string;
}

defineProps<{ puoModificare: boolean }>();

const $q = useQuasar();

const OPZIONI_TIPO = [
  { label: 'Energia elettrica', value: 'energia' },
  { label: 'Gas', value: 'gas' },
  { label: 'Acqua', value: 'acqua' },
  { label: 'Condominio', value: 'condominio' },
  { label: 'Altro', value: 'altro' },
];

const fornitori = ref<Fornitore[]>([]);
const loading = ref(true);

function etichettaTipo(tipo: TipoFornitore): string {
  return OPZIONI_TIPO.find((o) => o.value === tipo)?.label ?? tipo;
}

function dettaglio(f: Fornitore): string {
  const parti = [f.tipo_display || etichettaTipo(f.tipo)];
  if (f.partita_iva) parti.push(`P.IVA ${f.partita_iva}`);
  if (f.contatto) parti.push(f.contatto);
  return parti.join(' · ');
}

function asArray<T>(data: T[] | { results: T[] } | undefined | null): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : (data.results ?? []);
}

async function carica() {
  loading.value = true;
  try {
    const { data } = await api.get<Fornitore[] | { results: Fornitore[] }>('/api/v1/suppliers/');
    fornitori.value = asArray(data);
  } catch (e: unknown) {
    $q.notify({
      type: 'negative',
      message: messaggioErrore(e, 'Caricamento fornitori non riuscito.'),
    });
  } finally {
    loading.value = false;
  }
}

onMounted(carica);

const dialog = ref(false);
const inModifica = ref<Fornitore | null>(null);

interface FormFornitore {
  nome: string;
  tipo: TipoFornitore;
  partita_iva: string;
  contatto: string;
}

const form = ref<FormFornitore>({ nome: '', tipo: 'altro', partita_iva: '', contatto: '' });
const saving = ref(false);
const errore = ref('');

function apriDialog(f: Fornitore | null) {
  inModifica.value = f;
  errore.value = '';
  form.value = {
    nome: f?.nome ?? '',
    tipo: f?.tipo ?? 'altro',
    partita_iva: f?.partita_iva ?? '',
    contatto: f?.contatto ?? '',
  };
  dialog.value = true;
}

async function salva() {
  errore.value = '';
  const f = form.value;
  if (!f.nome.trim()) {
    errore.value = 'Il nome è obbligatorio.';
    return;
  }
  saving.value = true;
  const payload = {
    nome: f.nome.trim(),
    tipo: f.tipo,
    partita_iva: f.partita_iva.trim(),
    contatto: f.contatto.trim(),
  };
  try {
    if (inModifica.value) {
      await api.patch(`/api/v1/suppliers/${inModifica.value.id}/`, payload);
      $q.notify({ type: 'positive', message: 'Fornitore aggiornato.' });
    } else {
      await api.post('/api/v1/suppliers/', payload);
      $q.notify({ type: 'positive', message: 'Fornitore creato.' });
    }
    dialog.value = false;
    await carica();
  } catch (e: unknown) {
    errore.value = messaggioErrore(e, 'Salvataggio non riuscito.');
  } finally {
    saving.value = false;
  }
}

function elimina(f: Fornitore) {
  $q.dialog({
    title: 'Eliminare il fornitore?',
    message: `"${f.nome}" verrà rimosso.`,
    cancel: { flat: true, label: 'Annulla' },
    ok: { color: 'negative', label: 'Elimina' },
  }).onOk(() => {
    void (async () => {
      try {
        await api.delete(`/api/v1/suppliers/${f.id}/`);
        fornitori.value = fornitori.value.filter((x) => x.id !== f.id);
        $q.notify({ type: 'positive', message: 'Fornitore eliminato.' });
      } catch (e: unknown) {
        $q.notify({
          type: 'negative',
          message: messaggioErrore(e, 'Eliminazione non riuscita: dati collegati.'),
        });
      }
    })();
  });
}
</script>

<style scoped>
.imm-elenco {
  margin-top: 4px;
}
.imm-vuoto {
  font-size: 13px;
  color: var(--vp-ink-3);
  padding: 10px 2px;
}
.imm-compatto {
  font-size: 13.5px;
}
.vp-section-title {
  font-weight: 600;
  font-size: 16px;
  color: var(--vp-ink-1);
}
.vp-banner-errore {
  background: var(--vp-clay-soft, #fbeae5);
  color: var(--vp-clay-deep, #8c3b21);
}
</style>
