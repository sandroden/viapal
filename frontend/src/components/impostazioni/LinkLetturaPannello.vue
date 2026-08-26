<template>
  <CardSezione
    titolo="Link di lettura"
    descrizione="Un indirizzo a token da mandare a chi deve ancora firmare: apre le carte da leggere senza account. Revocabile in qualsiasi momento; nel pacchetto entra solo ciò che è esponibile."
  >
    <template v-if="puoModificare" #azioni>
      <BtnSoft etichetta="Nuovo link" data-testid="nuovo-link" @click="nuovoAperto = true" />
    </template>

    <div v-if="store.loading" class="lk-attesa"><q-spinner size="28px" /></div>
    <div v-else class="lk-elenco">
      <RigaElenco
        v-for="(l, i) in store.link"
        :key="l.id"
        :ultima="i === store.link.length - 1"
        :tenue="!l.attivo"
        data-testid="riga-link"
      >
        <template #tile><TileIcona icona="link" /></template>
        <template #titolo>Per {{ l.destinatario }}</template>
        <template #badge>
          <EtichettaStato :tono="l.attivo ? 'ok' : 'off'">
            {{ l.attivo ? aperture(l) : 'Revocato' }}
          </EtichettaStato>
          <EtichettaStato tono="line">{{ contenuto(l) }}</EtichettaStato>
        </template>
        <template #meta>
          <span class="lk-url">{{ urlBreve(l) }}</span>
        </template>
        <template #azioni>
          <BtnIcona
            v-if="l.attivo"
            icona="doc"
            :etichetta="`Copia il link per ${l.destinatario}`"
            tooltip="Copia il link"
            :data-testid="`copia-link-${l.id}`"
            @click="copia(l)"
          />
          <BtnIcona
            icona="open"
            :etichetta="`Apri il link per ${l.destinatario}`"
            tooltip="Apri come lo vede il destinatario"
            @click="apri(l)"
          />
          <BtnIcona
            v-if="puoModificare"
            icona="edit"
            :etichetta="`Componi il pacchetto per ${l.destinatario}`"
            tooltip="Componi il pacchetto"
            :data-testid="`componi-${l.id}`"
            @click="componi(l)"
          />
          <BtnIcona
            v-if="puoModificare"
            :icona="l.attivo ? 'lock' : 'refresh'"
            :etichetta="l.attivo ? 'Revoca il link' : 'Riattiva il link'"
            :tooltip="l.attivo ? 'Revoca' : 'Riattiva'"
            @click="cambiaAttivo(l)"
          />
          <BtnIcona
            v-if="puoModificare"
            icona="trash"
            pericolo
            :etichetta="`Elimina il link per ${l.destinatario}`"
            tooltip="Elimina"
            @click="conferma(l)"
          />
        </template>
      </RigaElenco>
      <div v-if="store.link.length === 0" class="lk-vuoto">
        Nessun link. Per il secondo inquilino il pacchetto si rifà in quattro
        click: i file sono già lì, non si ricarica niente.
      </div>
    </div>
  </CardSezione>

  <q-dialog v-model="nuovoAperto" @hide="destinatarioNuovo = ''">
    <q-card class="lk-nuovo">
      <q-card-section class="lk-nuovo__titolo">Nuovo link di lettura</q-card-section>
      <q-card-section>
        <q-input
          v-model="destinatarioNuovo"
          label="Pacchetto per"
          hint="Il nome compare in cima alla pagina che riceve."
          outlined
          dense
          autofocus
          data-testid="nuovo-link-destinatario"
          @keyup.enter="crea"
        />
      </q-card-section>
      <q-card-actions align="right">
        <q-btn v-close-popup flat label="Annulla" />
        <q-btn
          color="primary"
          label="Crea e componi"
          :disable="!destinatarioNuovo.trim()"
          :loading="store.salvataggio"
          data-testid="crea-link"
          @click="crea"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>

  <ComponiLinkDialog v-model="componiAperto" :link-id="linkInComposizione" />
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useQuasar, copyToClipboard } from 'quasar';
import { useLinkLetturaStore, type LinkLettura } from 'stores/linkLettura';
import { useDocumentiProprietaStore } from 'stores/documenti';
import { useFormatoData } from 'src/composables/useFormatoData';
import CardSezione from './ui/CardSezione.vue';
import RigaElenco from './ui/RigaElenco.vue';
import TileIcona from './ui/TileIcona.vue';
import EtichettaStato from './ui/EtichettaStato.vue';
import BtnIcona from './ui/BtnIcona.vue';
import BtnSoft from './ui/BtnSoft.vue';
import ComponiLinkDialog from './ComponiLinkDialog.vue';

defineProps<{ puoModificare: boolean }>();

const $q = useQuasar();
const { formattaData } = useFormatoData();
const store = useLinkLetturaStore();
const documenti = useDocumentiProprietaStore();

const nuovoAperto = ref(false);
const destinatarioNuovo = ref('');
const componiAperto = ref(false);
const linkInComposizione = ref<number | null>(null);

onMounted(() => {
  void store.fetch();
  // Il compositore propone i documenti esponibili: se la pagina si apre
  // direttamente qui, l'elenco deve esserci già. Il pannello «Altri
  // documenti» sta sopra e li carica per primo: senza il controllo su
  // ``loading`` questa sarebbe una seconda richiesta identica in volo.
  if (!documenti.loading && documenti.documenti.length === 0) {
    void documenti.fetch();
  }
});

function aperture(l: LinkLettura): string {
  if (l.visite === 0) return 'Mai aperto';
  const quante = l.visite === 1 ? 'aperto 1 volta' : `aperto ${l.visite} volte`;
  return l.ultima_visita ? `${quante} · l'ultima il ${formattaData(l.ultima_visita)}` : quante;
}

function contenuto(l: LinkLettura): string {
  const n = l.voci.length;
  if (n === 0) return 'Pacchetto vuoto';
  return n === 1 ? '1 voce' : `${n} voci`;
}

function urlBreve(l: LinkLettura): string {
  return l.url_pubblico.replace(/^https?:\/\//, '').replace(/\/d\/(.{6}).*$/, '/d/$1…');
}

function apri(l: LinkLettura) {
  window.open(l.url_pubblico, '_blank', 'noopener');
}

function copia(l: LinkLettura) {
  void copyToClipboard(l.url_pubblico).then(
    () => $q.notify({ type: 'positive', message: 'Link copiato.' }),
    () => $q.notify({ type: 'negative', message: l.url_pubblico }),
  );
}

function componi(l: LinkLettura) {
  linkInComposizione.value = l.id;
  componiAperto.value = true;
}

async function crea() {
  if (!destinatarioNuovo.value.trim()) return;
  const creato = await store.crea({ destinatario: destinatarioNuovo.value.trim() });
  if (!creato) {
    $q.notify({ type: 'negative', message: store.errore ?? 'Creazione non riuscita.' });
    return;
  }
  nuovoAperto.value = false;
  componi(creato);
}

async function cambiaAttivo(l: LinkLettura) {
  const ok = await store.cambiaAttivo(l.id, !l.attivo);
  if (!ok) {
    $q.notify({ type: 'negative', message: store.errore ?? 'Operazione non riuscita.' });
    return;
  }
  $q.notify({
    type: 'positive',
    message: l.attivo ? 'Il link non funziona più.' : 'Il link funziona di nuovo.',
  });
}

function conferma(l: LinkLettura) {
  $q.dialog({
    title: 'Eliminare il link?',
    message: `Il pacchetto per ${l.destinatario} sparisce e con lui la traccia di cosa gli era stato mandato. Per disattivarlo senza perdere la traccia, usa «Revoca».`,
    cancel: { flat: true, label: 'Annulla' },
    ok: { color: 'negative', label: 'Elimina' },
  }).onOk(() => {
    void (async () => {
      const ok = await store.elimina(l.id);
      $q.notify(
        ok
          ? { type: 'positive', message: 'Link eliminato.' }
          : { type: 'negative', message: store.errore ?? 'Eliminazione non riuscita.' },
      );
    })();
  });
}
</script>

<style scoped>
.lk-attesa {
  padding: 16px;
  display: flex;
  justify-content: center;
}
.lk-elenco {
  margin-top: 4px;
}
.lk-url {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  color: var(--vp-ink-3);
}
.lk-vuoto {
  font-size: 13px;
  color: var(--vp-ink-3);
  padding: 10px 2px;
  line-height: 1.5;
}
.lk-nuovo {
  width: 440px;
  max-width: 92vw;
}
.lk-nuovo__titolo {
  font-family: var(--vp-serif, Georgia, serif);
  font-size: 18px;
}
</style>
