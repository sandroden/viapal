<template>
  <q-dialog v-model="aperto" @hide="chiudiTutto">
    <q-card class="lk-comp">
      <q-card-section class="lk-comp__head">
        <div class="lk-comp__titolo">Pacchetto di lettura</div>
        <BtnIcona icona="x" etichetta="Chiudi" @click="aperto = false" />
      </q-card-section>

      <q-card-section class="lk-comp__corpo">
        <q-input
          v-model="destinatario"
          label="Pacchetto per"
          outlined
          dense
          autofocus
          data-testid="link-destinatario"
          @blur="salvaTestata"
        />
        <q-input
          v-model="introduzione"
          label="Due righe di introduzione"
          type="textarea"
          autogrow
          outlined
          dense
          @blur="salvaTestata"
        />

        <div v-if="link" class="lk-voci">
          <div
            v-for="(v, i) in link.voci"
            :key="v.id"
            class="lk-voce"
            data-testid="voce-link"
          >
            <span class="lk-voce__n">{{ i + 1 }}.</span>
            <VpIcon :name="v.tipo === 'documento' ? 'doc' : 'message'" :size="14" />
            <span class="lk-voce__titolo">{{ v.titolo_effettivo || 'Senza titolo' }}</span>
            <span v-if="v.tipo === 'testo'" class="lk-voce__tag">chiarimento</span>
            <span class="lk-voce__spazio" />
            <BtnIcona
              icona="up"
              etichetta="Sposta su"
              tooltip="Su"
              :disabilitato="i === 0"
              @click="sposta(i, -1)"
            />
            <BtnIcona
              icona="down"
              etichetta="Sposta giù"
              tooltip="Giù"
              :disabilitato="i === link.voci.length - 1"
              @click="sposta(i, 1)"
            />
            <BtnIcona
              v-if="v.tipo === 'testo'"
              icona="edit"
              etichetta="Modifica il testo"
              tooltip="Modifica"
              @click="apriTesto(v)"
            />
            <BtnIcona
              icona="trash"
              pericolo
              etichetta="Togli dal pacchetto"
              tooltip="Togli"
              @click="togli(v)"
            />
          </div>
          <div v-if="link.voci.length === 0" class="lk-vuoto">
            Pacchetto vuoto: aggiungi le carte da leggere e, se serve, un
            chiarimento scritto.
          </div>
        </div>

        <div class="lk-aggiungi">
          <BtnSoft
            etichetta="Aggiungi documento"
            :disabilitato="esponibiliDisponibili.length === 0"
            data-testid="aggiungi-documento"
            @click="aggiuntaAperta = true"
          />
          <BtnSoft
            etichetta="Scrivi un testo"
            icona="message"
            data-testid="aggiungi-testo"
            @click="apriTesto(null)"
          />
        </div>
        <div v-if="esponibiliDisponibili.length === 0" class="lk-nota">
          Nel link entra solo ciò che è esponibile: carica una copia per la
          lettura, o spunta «esponibile» su un documento che non nomina
          nessuno (le regole di convivenza).
        </div>

        <q-banner v-if="store.errore" class="vp-banner-errore" rounded dense>
          {{ store.errore }}
        </q-banner>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn flat label="Chiudi" @click="aperto = false" />
      </q-card-actions>
    </q-card>
  </q-dialog>

  <!-- Scelta del documento da aggiungere: solo l'esponibile è in elenco,
       quindi non c'è modo di scegliere un originale per sbaglio. -->
  <q-dialog v-model="aggiuntaAperta">
    <q-card class="lk-scelta">
      <q-card-section class="lk-comp__titolo">Aggiungi un documento</q-card-section>
      <q-card-section>
        <q-select
          v-model="documentoDaAggiungere"
          :options="esponibiliDisponibili"
          label="Documento esponibile"
          outlined
          dense
          emit-value
          map-options
          autofocus
          data-testid="scelta-documento"
        />
      </q-card-section>
      <q-card-actions align="right">
        <q-btn v-close-popup flat label="Annulla" />
        <q-btn
          color="primary"
          label="Aggiungi"
          :disable="!documentoDaAggiungere"
          :loading="store.salvataggio"
          @click="aggiungiDocumento"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>

  <!-- Il testo di chiarimento: markdown a sinistra, com'è reso a destra.
       L'anteprima la produce il backend, con lo stesso sanitizzatore della
       pagina pubblica: un renderer JS a parte la farebbe mentire. -->
  <q-dialog v-model="testoAperto" @hide="svuotaTesto">
    <q-card class="lk-testo">
      <q-card-section class="lk-comp__titolo">
        {{ voceInModifica ? 'Modifica il chiarimento' : 'Scrivi un chiarimento' }}
      </q-card-section>
      <q-card-section class="lk-testo__corpo">
        <q-input
          v-model="titoloTesto"
          label="Titolo"
          outlined
          dense
          autofocus
          data-testid="titolo-testo"
        />
        <div class="lk-testo__due">
          <q-input
            v-model="corpoMd"
            type="textarea"
            outlined
            label="Testo (markdown)"
            hint="**grassetto**, - elenchi, ## titoli, tabelle"
            input-style="min-height: 190px"
            data-testid="corpo-markdown"
            @update:model-value="chiediAnteprima"
          />
          <div class="lk-testo__prev">
            <div class="lk-testo__prev-eti">Anteprima</div>
            <!-- eslint-disable-next-line vue/no-v-html -->
            <div class="lk-md" v-html="anteprima" />
          </div>
        </div>
      </q-card-section>
      <q-card-actions align="right">
        <q-btn v-close-popup flat label="Annulla" />
        <q-btn
          color="primary"
          label="Salva"
          :disable="!corpoMd.trim()"
          :loading="store.salvataggio"
          data-testid="salva-testo"
          @click="salvaTesto"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useQuasar } from 'quasar';
import { useLinkLetturaStore, type LinkLettura, type VoceLink } from 'stores/linkLettura';
import { useDocumentiProprietaStore, type DocumentoFE } from 'stores/documenti';
import VpIcon from 'components/utenze/VpIcon.vue';
import BtnIcona from './ui/BtnIcona.vue';
import BtnSoft from './ui/BtnSoft.vue';

const props = defineProps<{ linkId: number | null }>();
const aperto = defineModel<boolean>({ required: true });

const $q = useQuasar();
const store = useLinkLetturaStore();
const documenti = useDocumentiProprietaStore();

const link = computed<LinkLettura | null>(
  () => store.link.find((l) => l.id === props.linkId) ?? null,
);

const destinatario = ref('');
const introduzione = ref('');

watch(
  () => [props.linkId, aperto.value] as const,
  () => {
    if (!aperto.value || !link.value) return;
    destinatario.value = link.value.destinatario;
    introduzione.value = link.value.introduzione;
  },
  { immediate: true },
);

/** «Aggiungi documento» propone solo ciò che è esponibile: l'originale non
 *  è in elenco, quindi non c'è nessun modo di sceglierlo per sbaglio. */
const esponibiliDisponibili = computed(() => {
  const giaDentro = new Set((link.value?.voci ?? []).map((v) => v.documento));
  return documenti.documenti
    .filter((d) => d.esponibile && !giaDentro.has(d.id))
    .map((d) => ({ label: etichetta(d), value: d.id }));
});

/** La descrizione proposta dal server finisce già con «— copia oscurata»:
 *  ripeterlo darebbe «… — copia oscurata (copia oscurata)». Il marcatore
 *  serve solo quando chi ha caricato ha scritto un'altra descrizione. */
function etichetta(d: DocumentoFE): string {
  const nome = d.titolo || d.descrizione || d.tipo_display;
  if (!d.copia_di || /copia/i.test(nome)) return nome;
  return `${nome} (copia per la lettura)`;
}

async function salvaTestata() {
  if (!link.value) return;
  if (
    destinatario.value === link.value.destinatario &&
    introduzione.value === link.value.introduzione
  ) {
    return;
  }
  if (!destinatario.value.trim()) {
    destinatario.value = link.value.destinatario;
    return;
  }
  await store.aggiorna(link.value.id, {
    destinatario: destinatario.value,
    introduzione: introduzione.value,
  });
}

// ── Voci documento ────────────────────────────────────────────────────────

const aggiuntaAperta = ref(false);
const documentoDaAggiungere = ref<number | null>(null);

async function aggiungiDocumento() {
  if (!link.value || !documentoDaAggiungere.value) return;
  const ok = await store.aggiungiVoce({
    share: link.value.id,
    documento: documentoDaAggiungere.value,
  });
  if (!ok) {
    $q.notify({ type: 'negative', message: store.errore ?? 'Voce non aggiunta.' });
    return;
  }
  documentoDaAggiungere.value = null;
  aggiuntaAperta.value = false;
}

async function togli(v: VoceLink) {
  const ok = await store.eliminaVoce(v);
  if (!ok) $q.notify({ type: 'negative', message: store.errore ?? 'Non rimossa.' });
}

async function sposta(indice: number, delta: number) {
  if (!link.value) return;
  const ids = link.value.voci.map((v) => v.id);
  const altro = indice + delta;
  if (altro < 0 || altro >= ids.length) return;
  const a = ids[indice];
  const b = ids[altro];
  if (a === undefined || b === undefined) return;
  ids[indice] = b;
  ids[altro] = a;
  await store.riordina(link.value.id, ids);
}

// ── Voci di testo ─────────────────────────────────────────────────────────

const testoAperto = ref(false);
const voceInModifica = ref<VoceLink | null>(null);
const titoloTesto = ref('');
const corpoMd = ref('');
const anteprima = ref('');
let timerAnteprima: ReturnType<typeof setTimeout> | null = null;

function apriTesto(v: VoceLink | null) {
  voceInModifica.value = v;
  titoloTesto.value = v?.titolo ?? '';
  corpoMd.value = v?.corpo_md ?? '';
  anteprima.value = v?.corpo_html ?? '';
  testoAperto.value = true;
}

function svuotaTesto() {
  voceInModifica.value = null;
  titoloTesto.value = '';
  corpoMd.value = '';
  anteprima.value = '';
}

function chiediAnteprima() {
  if (timerAnteprima) clearTimeout(timerAnteprima);
  timerAnteprima = setTimeout(() => {
    void store.anteprimaMarkdown(corpoMd.value).then((html) => {
      anteprima.value = html;
    });
  }, 350);
}

async function salvaTesto() {
  if (!link.value) return;
  const payload = { titolo: titoloTesto.value, corpo_md: corpoMd.value };
  const ok = voceInModifica.value
    ? await store.aggiornaVoce(voceInModifica.value, payload)
    : await store.aggiungiVoce({ share: link.value.id, ...payload });
  if (!ok) {
    $q.notify({ type: 'negative', message: store.errore ?? 'Salvataggio non riuscito.' });
    return;
  }
  testoAperto.value = false;
}

function chiudiTutto() {
  aggiuntaAperta.value = false;
  testoAperto.value = false;
}
</script>

<style scoped>
.lk-comp {
  width: 620px;
  max-width: 95vw;
}
.lk-comp__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 4px;
}
.lk-comp__titolo {
  font-family: var(--vp-serif, Georgia, serif);
  font-size: 18px;
}
.lk-comp__corpo {
  display: flex;
  flex-direction: column;
  gap: 13px;
}
.lk-voci {
  border: 1px solid var(--vp-paper-3);
  border-radius: 9px;
  padding: 4px 8px;
}
.lk-voce {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 2px;
  border-bottom: 1px solid var(--vp-paper-3);
  font-size: 13.5px;
}
.lk-voce:last-child {
  border-bottom: none;
}
.lk-voce__n {
  color: var(--vp-ink-3);
  font-variant-numeric: tabular-nums;
}
.lk-voce__titolo {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.lk-voce__tag {
  font-size: 11.5px;
  color: var(--vp-ink-3);
  background: var(--vp-paper-2);
  border-radius: 5px;
  padding: 1px 6px;
}
.lk-voce__spazio {
  flex: 1;
}
.lk-vuoto {
  font-size: 13px;
  color: var(--vp-ink-3);
  padding: 12px 2px;
  line-height: 1.5;
}
.lk-aggiungi {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.lk-nota {
  font-size: 12px;
  color: var(--vp-ink-3);
  line-height: 1.45;
}
.lk-scelta {
  width: 460px;
  max-width: 92vw;
}
.lk-testo {
  width: 760px;
  max-width: 96vw;
}
.lk-testo__corpo {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.lk-testo__due {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
@media (max-width: 720px) {
  .lk-testo__due {
    grid-template-columns: 1fr;
  }
}
.lk-testo__prev {
  border: 1px solid var(--vp-paper-3);
  border-radius: 8px;
  padding: 10px 12px;
  overflow: auto;
  max-height: 300px;
}
.lk-testo__prev-eti {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--vp-ink-3);
  margin-bottom: 6px;
}
/* Stessa scala della pagina pubblica: l'anteprima deve somigliare a quello
   che il destinatario vedrà, non agli h1 globali di Quasar. */
.lk-md :deep(h1),
.lk-md :deep(h2),
.lk-md :deep(h3),
.lk-md :deep(h4) {
  font-family: var(--vp-serif, Georgia, serif);
  font-weight: 500;
  margin: 10px 0 5px;
  line-height: 1.25;
  letter-spacing: 0;
}
.lk-md :deep(h1) {
  font-size: 17px;
}
.lk-md :deep(h2) {
  font-size: 15.5px;
}
.lk-md :deep(h3),
.lk-md :deep(h4) {
  font-size: 14px;
}
.lk-md :deep(p) {
  margin: 0 0 8px;
  line-height: 1.5;
}
.lk-md :deep(ul),
.lk-md :deep(ol) {
  margin: 0 0 8px;
  padding-left: 20px;
}
.lk-md :deep(table) {
  border-collapse: collapse;
  width: 100%;
}
.lk-md :deep(th),
.lk-md :deep(td) {
  border: 1px solid var(--vp-paper-3);
  padding: 4px 7px;
  text-align: left;
}
</style>
