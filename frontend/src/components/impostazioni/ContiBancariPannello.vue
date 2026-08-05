<template>
  <q-card flat bordered class="vp-card q-mb-md" style="max-width: 720px">
    <q-card-section>
      <div class="row items-center">
        <div class="vp-section-title">Conti bancari</div>
        <q-space />
        <q-btn
          dense
          color="primary"
          icon="add"
          label="Nuovo conto"
          data-testid="nuovo-conto"
          @click="apriDialogConto(null)"
        />
      </div>
      <div class="vp-hint q-mt-xs">
        I conti dei membri: da qui si sceglie quello su cui gli inquilini
        versano. Ognuno può modificare solo i propri.
      </div>
      <q-list separator class="q-mt-sm">
        <q-item v-for="c in conti" :key="c.id" data-testid="riga-conto">
          <q-item-section>
            <q-item-label>
              {{ c.intestatario }} — {{ c.banca }}
              <q-chip v-if="c.id === contoUtenzeId" dense outline class="q-ml-xs">
                incassi e utenze
              </q-chip>
            </q-item-label>
            <q-item-label caption>
              {{ c.iban }}
              <template v-if="!c.attivo"> · non attivo</template>
            </q-item-label>
          </q-item-section>
          <q-item-section side>
            <div class="row items-center q-gutter-xs">
              <q-btn
                v-if="c.owner === mioOwnerProfileId || sonoSuperuser"
                flat
                dense
                round
                icon="edit"
                :aria-label="`Modifica conto ${c.banca}`"
                @click="apriDialogConto(c)"
              />
              <q-btn
                v-if="c.owner === mioOwnerProfileId || sonoSuperuser"
                flat
                dense
                round
                icon="delete_outline"
                color="negative"
                :aria-label="`Elimina conto ${c.banca}`"
                @click="eliminaConto(c)"
              />
            </div>
          </q-item-section>
        </q-item>
        <q-item v-if="conti.length === 0">
          <q-item-section class="text-grey">
            Nessun conto registrato: senza, gli inquilini non hanno un
            IBAN su cui versare.
          </q-item-section>
        </q-item>
      </q-list>
    </q-card-section>
  </q-card>

  <!-- Dialog conto bancario -->
  <q-dialog v-model="dialogConto">
    <q-card style="min-width: 420px">
      <q-card-section>
        <div class="vp-section-title">
          {{ contoInModifica ? 'Modifica conto' : 'Nuovo conto' }}
        </div>
        <div class="vp-hint">
          {{
            sonoSuperuser
              ? 'Da superuser puoi gestire i conti di tutti i membri.'
              : 'Il conto è tuo: gli altri membri lo vedono ma non lo modificano.'
          }}
        </div>
      </q-card-section>
      <q-card-section class="q-gutter-md">
        <q-select
          v-if="sonoSuperuser && !contoInModifica"
          v-model="formContoOwner"
          :options="opzioniIntestatario"
          label="Membro intestatario"
          outlined
          dense
          emit-value
          map-options
          data-testid="conto-owner"
          @update:model-value="precompilaIntestatario"
        />
        <q-input
          v-model="formConto.banca"
          label="Banca"
          outlined
          dense
          autofocus
          data-testid="conto-banca"
        />
        <q-input
          v-model="formConto.intestatario"
          label="Intestatario"
          outlined
          dense
          data-testid="conto-intestatario"
        />
        <q-input
          v-model="formConto.iban"
          label="IBAN"
          outlined
          dense
          data-testid="conto-iban"
        />
        <q-toggle v-model="formConto.attivo" label="Attivo" />
        <q-banner v-if="erroreConto" class="vp-banner-errore" rounded dense>
          {{ erroreConto }}
        </q-banner>
      </q-card-section>
      <q-card-actions align="right">
        <q-btn v-close-popup flat label="Annulla" />
        <q-btn
          color="primary"
          label="Salva"
          :loading="savingConto"
          data-testid="salva-conto"
          @click="salvaConto"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { api } from 'boot/axios';
import { messaggioErrore } from 'src/utils/apiErrors';
import { useAuthStore } from 'stores/auth';
import { useOwnerBankAccountsStore, type BankAccountFull } from 'stores/ownerBankAccounts';
import { type Membro } from 'stores/properties';

const props = defineProps<{
  /** Il conto scelto in "Dati" come conto per incassi e utenze (chip). */
  contoUtenzeId: number | null;
  membri: Membro[];
}>();

const $q = useQuasar();
const auth = useAuthStore();
const contiStore = useOwnerBankAccountsStore();

const conti = ref<BankAccountFull[]>([]);
const dialogConto = ref(false);
const contoInModifica = ref<BankAccountFull | null>(null);
const formConto = ref({ banca: '', intestatario: '', iban: '', attivo: true });
/** Solo superuser: profilo proprietario per cui si crea il conto. */
const formContoOwner = ref<number | null>(null);
const savingConto = ref(false);
const erroreConto = ref('');

const mioOwnerProfileId = computed(() => auth.user?.owner_profile_id ?? null);
const sonoSuperuser = computed(() => !!auth.user?.is_superuser);
/** I membri con profilo proprietario: gli intestatari possibili quando il
 *  superuser crea un conto a nome altrui. */
const opzioniIntestatario = computed(() =>
  props.membri
    .filter((m) => m.owner_profile !== null)
    .map((m) => ({ label: m.nominativo, value: m.owner_profile as number })),
);

async function caricaConti() {
  const { data } = await api.get<BankAccountFull[] | { results: BankAccountFull[] }>(
    '/api/v1/bank-accounts/',
  );
  conti.value = Array.isArray(data) ? data : (data.results ?? []);
}

function apriDialogConto(c: BankAccountFull | null) {
  contoInModifica.value = c;
  erroreConto.value = '';
  formConto.value = {
    banca: c?.banca ?? '',
    intestatario: c?.intestatario ?? '',
    iban: c?.iban ?? '',
    attivo: c?.attivo ?? true,
  };
  formContoOwner.value = c?.owner ?? mioOwnerProfileId.value;
  dialogConto.value = true;
}

/** Alla scelta del membro, propone il suo nominativo come intestatario
 *  (se il campo non è già stato compilato a mano). */
function precompilaIntestatario(ownerId: number | null) {
  if (formConto.value.intestatario.trim()) return;
  const scelto = opzioniIntestatario.value.find((o) => o.value === ownerId);
  if (scelto) formConto.value.intestatario = scelto.label;
}

async function salvaConto() {
  erroreConto.value = '';
  const f = formConto.value;
  if (!f.banca.trim() || !f.intestatario.trim() || !f.iban.trim()) {
    erroreConto.value = 'Banca, intestatario e IBAN sono obbligatori.';
    return;
  }
  if (sonoSuperuser.value && !contoInModifica.value && !formContoOwner.value) {
    erroreConto.value = 'Scegli il membro intestatario del conto.';
    return;
  }
  savingConto.value = true;
  const payload: Record<string, unknown> = {
    banca: f.banca.trim(),
    intestatario: f.intestatario.trim(),
    iban: f.iban.replace(/\s+/g, '').toUpperCase(),
    attivo: f.attivo,
  };
  // Il backend accetta l'owner esplicito solo dal superuser; per gli altri
  // il conto è sempre il proprio.
  if (sonoSuperuser.value && !contoInModifica.value) {
    payload.owner = formContoOwner.value;
  }
  try {
    if (contoInModifica.value) {
      await api.patch(`/api/v1/bank-accounts/${contoInModifica.value.id}/`, payload);
    } else {
      await api.post('/api/v1/bank-accounts/', payload);
    }
    dialogConto.value = false;
    await caricaConti();
    // Il select del conto dell'immobile pesca dallo store: va riallineato.
    await contiStore.ensureLoaded(true);
    $q.notify({ type: 'positive', message: 'Conto salvato.' });
  } catch (e: unknown) {
    erroreConto.value = messaggioErrore(e, 'Salvataggio non riuscito.');
  } finally {
    savingConto.value = false;
  }
}

function eliminaConto(c: BankAccountFull) {
  $q.dialog({
    title: 'Eliminare il conto?',
    message: `${c.intestatario} — ${c.banca} verrà rimosso.`,
    cancel: { flat: true, label: 'Annulla' },
    ok: { color: 'negative', label: 'Elimina' },
  }).onOk(() => {
    void (async () => {
      try {
        await api.delete(`/api/v1/bank-accounts/${c.id}/`);
        await caricaConti();
        await contiStore.ensureLoaded(true);
        $q.notify({ type: 'positive', message: 'Conto eliminato.' });
      } catch (e: unknown) {
        $q.notify({
          type: 'negative',
          message: messaggioErrore(e, 'Eliminazione non riuscita: ha movimenti collegati.'),
        });
      }
    })();
  });
}

onMounted(caricaConti);
</script>

<style scoped>
.vp-section-title {
  font-weight: 600;
  font-size: 16px;
  color: var(--vp-ink-1);
}
.vp-hint {
  color: var(--vp-ink-3);
  font-size: 13px;
}
.vp-banner-errore {
  background: var(--vp-clay-soft, #fbeae5);
  color: var(--vp-clay-deep, #8c3b21);
}
</style>
