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
        <!-- La premessa spiega tutto quello che segue: sta in cima alla
             pagina, prima degli allegati, e si scrive nello stesso editor
             dei chiarimenti. -->
        <div class="lk-premessa">
          <div class="lk-premessa__testa">
            <span class="lk-premessa__eti">Premessa</span>
            <BtnSoft
              :etichetta="link?.introduzione ? 'Modifica' : 'Scrivi la premessa'"
              :icona="link?.introduzione ? 'edit' : 'plus'"
              variante="ghost"
              data-testid="modifica-premessa"
              @click="void apriPremessa()"
            />
          </div>
          <!-- eslint-disable-next-line vue/no-v-html -->
          <div
            v-if="link?.introduzione_html"
            class="lk-md lk-premessa__corpo"
            v-html="link.introduzione_html"
          />
          <div v-else class="lk-premessa__vuota">
            Nessuna premessa: la pagina si apre direttamente con gli allegati.
          </div>
        </div>

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
            <span v-if="v.tipo === 'testo'" class="lk-voce__tag">testo</span>
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
            Nessun allegato: aggiungi le carte da leggere. La spiegazione sta
            nella premessa, qui sopra.
          </div>
        </div>

        <div class="lk-aggiungi">
          <BtnSoft
            etichetta="Aggiungi documento"
            :disabilitato="esponibiliDisponibili.length === 0 && daEsporre.length === 0"
            data-testid="aggiungi-documento"
            @click="aggiuntaAperta = true"
          />
          <BtnSoft
            etichetta="Testo fra gli allegati"
            icona="message"
            variante="ghost"
            data-testid="aggiungi-testo"
            @click="apriTesto(null)"
          />
        </div>
        <div
          v-if="esponibiliDisponibili.length === 0 && daEsporre.length === 0"
          class="lk-nota"
        >
          Non c'è altro da aggiungere. Per mandare una carta che nomina
          qualcuno serve prima la sua copia oscurata, in «Documenti fac-simile
          senza dati personali».
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
      <q-card-section class="lk-scelta__corpo">
        <q-select
          v-if="esponibiliDisponibili.length"
          v-model="documentoDaAggiungere"
          :options="esponibiliDisponibili"
          label="Documento senza dati personali"
          outlined
          dense
          emit-value
          map-options
          autofocus
          data-testid="scelta-documento"
        />
        <div v-else class="lk-scelta__vuoto">
          Nessun documento pronto: o è già tutto nel pacchetto, o va prima
          preparata una copia oscurata.
        </div>

        <!-- Le carte della casa che non nominano nessuno non hanno bisogno
             di una copia: basta dire che possono uscire. Prima quella spunta
             stava solo in «Altri documenti», e da qui non c'era modo di
             sapere che esisteva. -->
        <template v-if="daEsporre.length">
          <div class="lk-scelta__eti">Carte della casa non ancora esponibili</div>
          <div class="lk-scelta__nota">
            Escono <strong>così come sono</strong>, senza copia oscurata:
            aggiungile solo se non nominano nessuno.
          </div>
          <div v-for="d in daEsporre" :key="d.id" class="lk-scelta__riga">
            <VpIcon name="doc" :size="14" />
            <span class="lk-scelta__nome">{{ etichetta(d) }}</span>
            <BtnSoft
              etichetta="Esponi e aggiungi"
              icona="link"
              variante="ghost"
              :disabilitato="store.salvataggio"
              :data-testid="`esponi-e-aggiungi-${d.id}`"
              @click="void esponiEAggiungi(d)"
            />
          </div>
        </template>
      </q-card-section>
      <q-card-actions align="right">
        <q-btn v-close-popup flat label="Annulla" />
        <!-- Senza il select non c'è niente da confermare: le carte da
             esporre si aggiungono dal loro bottone. -->
        <q-btn
          v-if="esponibiliDisponibili.length"
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
        {{ titoloEditor }}
      </q-card-section>
      <q-card-section class="lk-testo__corpo">
        <!-- Chi apre questo dialog cercando «il testo» ha in mente la
             premessa: dire subito che questo va altrove costa una riga. -->
        <div v-if="!modificaLaPremessa" class="lk-testo__dove">
          Va <strong>nell'elenco</strong>, in mezzo agli allegati, e si sposta
          con le frecce. La spiegazione che apre la pagina è la premessa.
        </div>
        <!-- La premessa non ha titolo: è il cappello della pagina, non
             una voce dell'elenco. -->
        <q-input
          v-if="!modificaLaPremessa"
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
            input-style="height: 100%"
            data-testid="corpo-markdown"
            @update:model-value="chiediAnteprima"
          />
          <!-- Solo a campo vuoto: rimettere la proposta su un testo già
               scritto vorrebbe dire cancellarlo. -->
          <BtnSoft
            v-if="modificaLaPremessa && !corpoMd.trim()"
            etichetta="Parti dal testo proposto"
            icona="refresh"
            variante="ghost"
            data-testid="testo-proposto"
            @click="void proponi()"
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
/** Da quale link viene il valore che sta nella casella. Senza, se il dialog
 *  si apre prima che lo store abbia il link, la casella conserva il testo di
 *  un'apertura precedente e il primo blur lo scrive addosso a questo. */
const destinatarioDi = ref<number | null>(null);

watch(
  () => [props.linkId, aperto.value] as const,
  () => {
    if (!aperto.value || !link.value) {
      destinatarioDi.value = null;
      destinatario.value = '';
      return;
    }
    destinatario.value = link.value.destinatario;
    destinatarioDi.value = link.value.id;
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
/** Le carte della casa che potrebbero uscire ma non sono ancora spuntate.
 *  Solo quelle **senza contratto**: contratto firmato, side letter e
 *  ricevuta di registrazione nominano le persone che hanno firmato, e per
 *  quelle serve una copia oscurata — non una spunta. */
const daEsporre = computed(() => {
  const giaDentro = new Set((link.value?.voci ?? []).map((v) => v.documento));
  return documenti.documenti.filter(
    (d) =>
      !d.esponibile &&
      !d.esponibile_per_natura &&
      !d.copia_di &&
      !d.contract &&
      !giaDentro.has(d.id),
  );
});

async function esponiEAggiungi(d: DocumentoFE) {
  if (!link.value) return;
  if (!(await documenti.impostaEsponibile(d.id, true))) {
    $q.notify({ type: 'negative', message: documenti.errore ?? 'Non riuscito.' });
    return;
  }
  const ok = await store.aggiungiVoce({ share: link.value.id, documento: d.id });
  if (!ok) {
    $q.notify({ type: 'negative', message: store.errore ?? 'Voce non aggiunta.' });
    return;
  }
  aggiuntaAperta.value = false;
}

function etichetta(d: DocumentoFE): string {
  const nome = d.titolo || d.descrizione || d.tipo_display;
  if (!d.copia_di || /copia/i.test(nome)) return nome;
  return `${nome} (copia oscurata)`;
}

async function salvaTestata() {
  if (!link.value || destinatarioDi.value !== link.value.id) return;
  if (destinatario.value === link.value.destinatario) return;
  if (!destinatario.value.trim()) {
    destinatario.value = link.value.destinatario;
    return;
  }
  await store.aggiorna(link.value.id, { destinatario: destinatario.value });
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
/** L'editor serve a due cose: la premessa del pacchetto e i chiarimenti fra
 *  un allegato e l'altro. Cambia solo dove si salva. */
const modificaLaPremessa = ref(false);
const titoloTesto = ref('');
const corpoMd = ref('');
const anteprima = ref('');
let timerAnteprima: ReturnType<typeof setTimeout> | null = null;

/** Apre l'editor. Su una voce nuova parte dalla proposta del backend, che è
 *  quella che si scrive quasi sempre: da lì si ritocca per questo link. Su
 *  una voce esistente non si tocca niente — quello che c'è è già stato
 *  deciso. */
/** Un testo fra gli allegati si apre in bianco, e su una voce esistente con
 *  quello che c'è dentro. La proposta è della premessa e solo di quella: è
 *  lì che va la spiegazione generale, e vederla comparire anche qui faceva
 *  sembrare i due bottoni la stessa cosa. */
function apriTesto(v: VoceLink | null) {
  modificaLaPremessa.value = false;
  voceInModifica.value = v;
  testoAperto.value = true;
  if (v) {
    titoloTesto.value = v.titolo;
    corpoMd.value = v.corpo_md;
    anteprima.value = v.corpo_html;
    return;
  }
  titoloTesto.value = '';
  corpoMd.value = '';
  anteprima.value = '';
}

/** La premessa: stesso editor, e su una premessa vuota parte dalla
 *  proposta — è lì che il testo che si scrive quasi sempre va a finire. */
async function apriPremessa() {
  modificaLaPremessa.value = true;
  voceInModifica.value = null;
  testoAperto.value = true;
  titoloTesto.value = '';
  corpoMd.value = link.value?.introduzione ?? '';
  anteprima.value = link.value?.introduzione_html ?? '';
  if (!corpoMd.value) await proponi();
}

/** Riempie l'editor con la proposta e ne calcola l'anteprima. */
async function proponi() {
  const proposta = await store.testoPredefinito();
  if (!proposta.corpo_md) return;
  titoloTesto.value = titoloTesto.value || proposta.titolo;
  corpoMd.value = proposta.corpo_md;
  anteprima.value = await store.anteprimaMarkdown(proposta.corpo_md);
}

function svuotaTesto() {
  voceInModifica.value = null;
  titoloTesto.value = '';
  corpoMd.value = '';
  anteprima.value = '';
}

const titoloEditor = computed(() => {
  if (modificaLaPremessa.value) return 'Premessa del pacchetto';
  return voceInModifica.value ? 'Modifica il testo' : 'Testo fra gli allegati';
});

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
  const ok = modificaLaPremessa.value
    ? await store.aggiorna(link.value.id, { introduzione: corpoMd.value })
    : voceInModifica.value
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
.lk-premessa {
  border: 1px solid var(--vp-paper-3);
  border-radius: 9px;
  padding: 8px 11px 10px;
}
.lk-premessa__testa {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.lk-premessa__eti {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--vp-ink-3);
}
.lk-premessa__corpo {
  margin-top: 6px;
  max-height: 190px;
  overflow: auto;
  font-size: 13px;
}
.lk-premessa__vuota {
  margin-top: 4px;
  font-size: 12.5px;
  color: var(--vp-ink-3);
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
  width: 520px;
  max-width: 93vw;
}
.lk-scelta__corpo {
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.lk-scelta__vuoto {
  font-size: 13px;
  color: var(--vp-ink-3);
  line-height: 1.5;
}
.lk-scelta__eti {
  margin-top: 6px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--vp-ink-3);
}
.lk-scelta__nota {
  font-size: 12px;
  color: var(--vp-ink-3);
  line-height: 1.45;
}
.lk-scelta__riga {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
  padding: 3px 0;
}
.lk-scelta__nome {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* Ci si scrive dentro un testo lungo: nasce grande e si allarga a mano
   (l'angolo in basso a destra). ``resize`` vuole ``overflow`` diverso da
   visible, e il q-dialog non impone una larghezza propria. */
.lk-testo {
  width: min(1120px, 94vw);
  max-width: 96vw;
  height: min(760px, 88vh);
  max-height: 92vh;
  resize: both;
  overflow: auto;
  display: flex;
  flex-direction: column;
}
.lk-testo__corpo {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  min-height: 0;
}
.lk-testo__dove {
  font-size: 12.5px;
  line-height: 1.45;
  color: var(--vp-ink-3);
}
.lk-testo__due {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  flex: 1;
  min-height: 0;
}
/* Le due colonne seguono l'altezza del dialog invece di restare alte
   quanto il testo: allargandolo si guadagna spazio per scrivere. */
.lk-testo__due :deep(.q-field),
.lk-testo__due :deep(.q-field__control),
.lk-testo__due :deep(.q-field__native) {
  height: 100%;
}
.lk-testo__due :deep(.q-field__native) {
  resize: none;
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
  min-height: 0;
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
