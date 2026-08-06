<template>
  <CardSezione titolo="Categorie di spesa">
    <template v-if="puoModificare" #azioni>
      <BtnSoft etichetta="Nuova" data-testid="nuova-categoria" @click="apriDialog(null)" />
    </template>

    <div v-if="loading" class="q-pa-md flex flex-center">
      <q-spinner size="28px" />
    </div>
    <div v-else class="imm-elenco">
      <RigaElenco
        v-for="(c, i) in categorie"
        :key="c.id"
        :ultima="i === categorie.length - 1"
        data-testid="riga-categoria"
      >
        <template #titolo>
          <span class="imm-compatto">{{ c.nome }}</span>
        </template>
        <template #meta>
          <span class="vp-mono imm-codice">
            {{ c.codice }}<template v-if="c.ripartibile_inquilini"> · ripartibile tra inquilini</template>
          </span>
        </template>
        <template #azioni>
          <AzioniRiga
            :oggetto="c.nome"
            :puo-modificare="puoModificare"
            :puo-eliminare="puoModificare"
            @modifica="apriDialog(c)"
            @elimina="elimina(c)"
          />
        </template>
      </RigaElenco>
      <div v-if="categorie.length === 0" class="imm-vuoto">Nessuna categoria configurata.</div>
    </div>
  </CardSezione>

  <!-- Dialog categoria spesa -->
  <q-dialog v-model="dialog">
    <q-card style="min-width: 380px">
      <q-card-section>
        <div class="vp-section-title">
          {{ inModifica ? 'Modifica categoria' : 'Nuova categoria' }}
        </div>
      </q-card-section>
      <q-card-section class="q-gutter-md">
        <q-input
          v-model="form.nome"
          label="Nome"
          outlined
          dense
          autofocus
          data-testid="categoria-nome"
        />
        <q-input
          v-model="form.codice"
          label="Codice (slug, es. 'manutenzione')"
          outlined
          dense
          data-testid="categoria-codice"
        />
        <q-toggle v-model="form.ripartibile_inquilini" label="Ripartibile tra inquilini" dense />
        <q-banner v-if="errore" class="vp-banner-errore" rounded dense>{{ errore }}</q-banner>
      </q-card-section>
      <q-card-actions align="right">
        <q-btn v-close-popup flat label="Annulla" />
        <q-btn
          color="primary"
          label="Salva"
          :loading="saving"
          data-testid="salva-categoria"
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

interface Categoria {
  id: number;
  nome: string;
  codice: string;
  ripartibile_inquilini: boolean;
}

defineProps<{ puoModificare: boolean }>();

const $q = useQuasar();

const categorie = ref<Categoria[]>([]);
const loading = ref(true);

function asArray<T>(data: T[] | { results: T[] } | undefined | null): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : (data.results ?? []);
}

async function carica() {
  loading.value = true;
  try {
    const { data } = await api.get<Categoria[] | { results: Categoria[] }>(
      '/api/v1/expense-categories/',
    );
    categorie.value = asArray(data);
  } catch (e: unknown) {
    $q.notify({
      type: 'negative',
      message: messaggioErrore(e, 'Caricamento categorie non riuscito.'),
    });
  } finally {
    loading.value = false;
  }
}

onMounted(carica);

const dialog = ref(false);
const inModifica = ref<Categoria | null>(null);
const form = ref({ nome: '', codice: '', ripartibile_inquilini: false });
const saving = ref(false);
const errore = ref('');

function apriDialog(c: Categoria | null) {
  inModifica.value = c;
  errore.value = '';
  form.value = {
    nome: c?.nome ?? '',
    codice: c?.codice ?? '',
    ripartibile_inquilini: c?.ripartibile_inquilini ?? false,
  };
  dialog.value = true;
}

async function salva() {
  errore.value = '';
  const f = form.value;
  if (!f.nome.trim() || !f.codice.trim()) {
    errore.value = 'Nome e codice sono obbligatori.';
    return;
  }
  saving.value = true;
  const payload = {
    nome: f.nome.trim(),
    codice: f.codice.trim(),
    ripartibile_inquilini: f.ripartibile_inquilini,
  };
  try {
    if (inModifica.value) {
      await api.patch(`/api/v1/expense-categories/${inModifica.value.id}/`, payload);
      $q.notify({ type: 'positive', message: 'Categoria aggiornata.' });
    } else {
      await api.post('/api/v1/expense-categories/', payload);
      $q.notify({ type: 'positive', message: 'Categoria creata.' });
    }
    dialog.value = false;
    await carica();
  } catch (e: unknown) {
    errore.value = messaggioErrore(e, 'Salvataggio non riuscito.');
  } finally {
    saving.value = false;
  }
}

function elimina(c: Categoria) {
  $q.dialog({
    title: 'Eliminare la categoria?',
    message: `"${c.nome}" verrà rimossa.`,
    cancel: { flat: true, label: 'Annulla' },
    ok: { color: 'negative', label: 'Elimina' },
  }).onOk(() => {
    void (async () => {
      try {
        await api.delete(`/api/v1/expense-categories/${c.id}/`);
        categorie.value = categorie.value.filter((x) => x.id !== c.id);
        $q.notify({ type: 'positive', message: 'Categoria eliminata.' });
      } catch (e: unknown) {
        $q.notify({
          type: 'negative',
          message: messaggioErrore(e, 'Eliminazione non riuscita: spese collegate.'),
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
.imm-codice {
  font-size: 11px;
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
