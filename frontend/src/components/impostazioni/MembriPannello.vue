<template>
  <q-card flat bordered class="vp-card q-mb-md" style="max-width: 720px">
    <q-card-section>
      <div class="row items-center">
        <div class="vp-section-title">Membri</div>
        <q-space />
        <q-btn
          v-if="sonoProprietario"
          dense
          color="primary"
          icon="person_add"
          label="Invita"
          @click="dialogInvito = true"
          data-testid="apri-invito"
        />
      </div>

      <q-list separator class="q-mt-sm">
        <q-item v-for="m in membri" :key="m.id" data-testid="riga-membro">
          <q-item-section>
            <q-item-label>{{ m.nominativo }}</q-item-label>
            <q-item-label caption>{{ m.email || m.username }}</q-item-label>
          </q-item-section>
          <q-item-section side>
            <div class="row items-center q-gutter-sm">
              <q-btn
                v-if="puoAnagrafica(m)"
                flat
                dense
                round
                icon="edit"
                :aria-label="`Anagrafica di ${m.nominativo}`"
                data-testid="modifica-anagrafica-membro"
                @click="apriAnagrafica(m.owner_profile!)"
              >
                <q-tooltip>Anagrafica</q-tooltip>
              </q-btn>
              <q-select
                v-if="sonoProprietario"
                :model-value="m.ruolo"
                :options="OPZIONI_RUOLO"
                dense
                outlined
                emit-value
                map-options
                style="min-width: 150px"
                @update:model-value="(r: RuoloProperty) => cambiaRuolo(m, r)"
              />
              <q-chip v-else dense outline>{{ etichettaRuolo(m.ruolo) }}</q-chip>
              <q-btn
                v-if="sonoProprietario"
                flat
                dense
                round
                icon="delete_outline"
                color="negative"
                :aria-label="`Rimuovi ${m.nominativo}`"
                @click="rimuovi(m)"
              />
            </div>
          </q-item-section>
        </q-item>
      </q-list>
    </q-card-section>
  </q-card>

  <!-- Dialog invito -->
  <q-dialog v-model="dialogInvito">
    <q-card style="min-width: 380px">
      <q-card-section>
        <div class="vp-section-title">Invita un membro</div>
      </q-card-section>
      <q-card-section class="q-gutter-md">
        <q-input
          v-model="invitoEmail"
          label="Email"
          type="email"
          outlined
          dense
          autofocus
          data-testid="invito-email"
        />
        <q-input
          v-model="invitoNominativo"
          label="Nome e cognome (facoltativo)"
          outlined
          dense
          data-testid="invito-nominativo"
        />
        <q-select
          v-model="invitoRuolo"
          :options="OPZIONI_RUOLO"
          label="Ruolo"
          outlined
          dense
          emit-value
          map-options
        />
        <q-banner v-if="invitoErrore" class="vp-banner-errore" rounded dense>
          {{ invitoErrore }}
        </q-banner>
      </q-card-section>
      <q-card-actions align="right">
        <q-btn v-close-popup flat label="Annulla" />
        <q-btn
          color="primary"
          label="Invia invito"
          :loading="invitoSaving"
          @click="invia"
          data-testid="invito-invia"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>

  <!-- Dialog anagrafica del membro (deep-link dai "dati mancanti") -->
  <AnagraficaOwnerDialog
    v-model="dialogAnagrafica"
    :owner-id="anagraficaOwnerId"
    :campo="anagraficaCampo"
    @salvato="anagraficaSalvata"
  />
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useQuasar } from 'quasar';
import { messaggioErrore } from 'src/utils/apiErrors';
import { useAuthStore, type RuoloProperty } from 'stores/auth';
import {
  OPZIONI_RUOLO,
  etichettaRuolo,
  usePropertiesStore,
  type Membro,
} from 'stores/properties';
import { useOwnersStore } from 'stores/owners';
import AnagraficaOwnerDialog from 'components/impostazioni/AnagraficaOwnerDialog.vue';

const props = defineProps<{
  propertyId: number;
  membri: Membro[];
  sonoProprietario: boolean;
}>();

const emit = defineEmits<{
  (e: 'aggiornati', membri: Membro[]): void;
}>();

const $q = useQuasar();
const propStore = usePropertiesStore();
const authStore = useAuthStore();
const ownersStore = useOwnersStore();

const dialogAnagrafica = ref(false);
const anagraficaOwnerId = ref<number | null>(null);
const anagraficaCampo = ref<string | null>(null);

/** Stesso gate del backend: il titolare modifica la propria anagrafica,
 *  i proprietari (e i superuser) quella di tutti i membri. */
function puoAnagrafica(m: Membro): boolean {
  if (!m.owner_profile) return false;
  if (props.sonoProprietario || authStore.isSuperuser) return true;
  return m.user === authStore.user?.id;
}

function apriAnagrafica(ownerId: number, campo: string | null = null) {
  anagraficaOwnerId.value = ownerId;
  anagraficaCampo.value = campo;
  dialogAnagrafica.value = true;
}

async function anagraficaSalvata() {
  // Il nominativo compare nella lista membri e nelle select intestatario:
  // ricarichiamo entrambe le fonti.
  await ownersStore.fetchOwners(true);
  emit('aggiornati', await propStore.caricaMembri(props.propertyId));
}

defineExpose({ apriAnagrafica });

const dialogInvito = ref(false);
const invitoEmail = ref('');
const invitoNominativo = ref('');
const invitoRuolo = ref<RuoloProperty>('proprietario');
const invitoSaving = ref(false);
const invitoErrore = ref('');

async function invia() {
  invitoSaving.value = true;
  invitoErrore.value = '';
  try {
    await propStore.invitaMembro(props.propertyId, {
      email: invitoEmail.value.trim(),
      ruolo: invitoRuolo.value,
      nominativo: invitoNominativo.value.trim(),
    });
    dialogInvito.value = false;
    invitoEmail.value = '';
    invitoNominativo.value = '';
    $q.notify({ type: 'positive', message: 'Invito inviato via email.' });
    emit('aggiornati', await propStore.caricaMembri(props.propertyId));
  } catch (e: unknown) {
    invitoErrore.value = messaggioErrore(e, 'Invito non riuscito.');
  } finally {
    invitoSaving.value = false;
  }
}

async function cambiaRuolo(m: Membro, ruolo: RuoloProperty) {
  if (m.ruolo === ruolo) return;
  try {
    await propStore.cambiaRuoloMembro(props.propertyId, m.id, ruolo);
    emit(
      'aggiornati',
      props.membri.map((x) => (x.id === m.id ? { ...x, ruolo } : x)),
    );
    $q.notify({ type: 'positive', message: `Ruolo di ${m.nominativo} aggiornato.` });
  } catch (e: unknown) {
    $q.notify({ type: 'negative', message: messaggioErrore(e, 'Cambio ruolo non riuscito.') });
    emit('aggiornati', await propStore.caricaMembri(props.propertyId));
  }
}

function rimuovi(m: Membro) {
  $q.dialog({
    title: 'Rimuovere il membro?',
    message: `${m.nominativo} non avrà più accesso a questo immobile.`,
    cancel: { flat: true, label: 'Annulla' },
    ok: { color: 'negative', label: 'Rimuovi' },
  }).onOk(() => {
    void (async () => {
      try {
        await propStore.rimuoviMembro(props.propertyId, m.id);
        emit(
          'aggiornati',
          props.membri.filter((x) => x.id !== m.id),
        );
      } catch (e: unknown) {
        $q.notify({
          type: 'negative',
          message: messaggioErrore(e, 'Rimozione non riuscita.'),
        });
      }
    })();
  });
}
</script>

<style scoped>
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
