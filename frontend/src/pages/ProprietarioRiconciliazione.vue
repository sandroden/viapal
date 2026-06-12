<template>
  <q-page padding class="vp-p-rec">
    <header class="vp-p-rec__head">
      <div class="vp-p-rec__head-titolo">
        <div>
          <div class="vp-eyebrow">Bonifici ↔ addebiti</div>
          <h1 class="vp-display vp-p-rec__titolo">Riconciliazione</h1>
        </div>
        <q-btn round dense flat size="sm" icon="info_outline" color="grey-7">
          <q-tooltip>Come funziona</q-tooltip>
          <q-popup-proxy>
            <q-card class="vp-p-rec__popup-info">
              <q-card-section>
                Seleziona una transazione (Ctrl-click per aggiungerne altre,
                ad es. per pagamenti spezzati), poi gli addebiti che essa
                copre. Salva quando il residuo è a zero (o accetta
                sopra/sotto-allocazione).
              </q-card-section>
            </q-card>
          </q-popup-proxy>
        </q-btn>
      </div>
      <q-btn
        flat
        color="primary"
        icon="refresh"
        :loading="store.loadingBts || store.loadingReceivables"
        no-caps
        label="Ricarica"
        @click="ricarica"
      />
    </header>

    <section class="vp-p-rec__filtri">
      <q-input
        v-model="filtroDataDa"
        dense
        outlined
        type="date"
        label="Da"
        class="vp-p-rec__date"
      />
      <q-input
        v-model="filtroDataA"
        dense
        outlined
        type="date"
        label="A"
        class="vp-p-rec__date"
      />
    </section>
    <section class="vp-p-rec__preset">
      <span class="vp-eyebrow">Periodo rapido</span>
      <q-btn
        flat
        dense
        round
        size="sm"
        icon="chevron_left"
        :disable="!filtroDataDa || !filtroDataA"
        @click="onFrecciaIndietro"
      >
        <q-tooltip>Periodo precedente · Ctrl-click: allarga indietro</q-tooltip>
      </q-btn>
      <q-btn
        flat
        dense
        round
        size="sm"
        icon="chevron_right"
        :disable="!filtroDataDa || !filtroDataA"
        @click="onFrecciaAvanti"
      >
        <q-tooltip>Periodo successivo · Ctrl-click: allarga avanti</q-tooltip>
      </q-btn>
      <q-btn flat dense no-caps size="sm" label="Quest'anno" @click="presetQuestAnno" />
      <q-btn flat dense no-caps size="sm" label="Anno scorso" @click="presetAnnoScorso" />
      <q-btn flat dense no-caps size="sm" label="Ultimo trimestre" @click="presetUltimoTrimestre" />
      <q-btn flat dense no-caps size="sm" label="Ultimi 12 mesi" @click="presetUltimi12Mesi" />
      <q-btn flat dense no-caps size="sm" label="Tutto" @click="presetReset" />
    </section>

    <div class="vp-p-rec__grid">
      <!-- Colonna sinistra: BankTransaction -->
      <q-card flat bordered class="vp-p-rec__col">
        <q-card-section class="vp-p-rec__col-head">
          <div class="vp-p-rec__col-head-left">
            <div class="vp-eyebrow">Transazioni bancarie</div>
            <q-btn
              round
              dense
              flat
              size="sm"
              :icon="iconaStatoBt"
              :color="filtroRiconciliato === 'false' ? 'grey-7' : 'primary'"
            >
              <q-tooltip>Stato BT: {{ etichettaStatoBt }}</q-tooltip>
              <q-menu>
                <q-list dense>
                  <q-item
                    v-for="o in opzioniRiconciliato"
                    :key="o.value"
                    v-close-popup
                    clickable
                    :active="filtroRiconciliato === o.value"
                    @click="filtroRiconciliato = o.value"
                  >
                    <q-item-section>{{ o.label }}</q-item-section>
                  </q-item>
                </q-list>
              </q-menu>
            </q-btn>
            <q-btn-toggle
              v-model="filtroImportoBt"
              size="xs"
              dense
              no-caps
              unelevated
              toggle-color="primary"
              class="vp-p-rec__filtro-importo"
              :options="[
                { label: 'Tutti', value: 'tutti' },
                { label: '≥ 200€', value: 'alti' },
                { label: '< 200€', value: 'bassi' },
              ]"
            />
            <span class="vp-eyebrow vp-p-rec__resti-label">Resti</span>
            <q-btn-toggle
              v-model="sogliaMicroResidui"
              size="xs"
              dense
              no-caps
              unelevated
              toggle-color="primary"
              class="vp-p-rec__filtro-importo"
              :options="[
                { label: 'Tutti', value: 0 },
                { label: '< 1€', value: 1 },
                { label: '< 5€', value: 5 },
              ]"
            >
              <q-tooltip>
                Nasconde le BT con residuo inferiore alla soglia
                (sotto/sopra-pagamenti trascurabili)
              </q-tooltip>
            </q-btn-toggle>
            <q-btn
              round
              dense
              flat
              size="sm"
              icon="swap_horiz"
              :color="nascondiInterOwner ? 'primary' : 'grey-7'"
              @click="nascondiInterOwner = !nascondiInterOwner"
            >
              <q-tooltip>
                {{ nascondiInterOwner ? 'Mostra anche le BT inter-owner' : 'Nascondi BT inter-owner' }}
              </q-tooltip>
            </q-btn>
          </div>
          <div class="vp-p-rec__col-meta">
            <template
              v-if="
                filtroImportoBt === 'tutti'
                  && sogliaMicroResidui === 0
                  && !nascondiInterOwner
                  && !tenantPerFiltroBt
              "
            >
              {{ store.bts.length }} risultati
            </template>
            <template v-else>
              {{ btOrdinate.length }} di {{ store.bts.length }}
            </template>
            <span v-if="btSelezionate.size > 0" class="vp-p-rec__badge">
              {{ btSelezionate.size }} selezionate
            </span>
          </div>
        </q-card-section>
        <q-separator />
        <q-banner
          v-if="btFuoriFiltro.length > 0"
          dense
          class="vp-p-rec__banner-fuori"
        >
          <template #avatar>
            <q-icon name="info" color="warning" />
          </template>
          {{ btFuoriFiltro.length }} transazion{{ btFuoriFiltro.length === 1 ? 'e selezionata non è' : 'i selezionate non sono' }}
          in lista (filtri attivi).
          Le vedi nel pannello "Allocazioni" qui sotto.
          <template #action>
            <q-btn flat dense no-caps label="Mostra tutte" @click="mostraTutteBt" />
          </template>
        </q-banner>
        <q-list separator class="vp-p-rec__lista">
          <q-item
            v-for="bt in btOrdinate"
            :key="bt.id"
            v-ripple
            clickable
            :active="btSelezionate.has(bt.id)"
            active-class="vp-p-rec__item--active"
            class="vp-p-rec__item"
            @click="(e: Event) => clickBt(bt, e as MouseEvent)"
          >
            <q-item-section>
              <q-item-label class="vp-p-rec__bt-row">
                <span class="vp-p-rec__bt-data">{{ formattaData(bt.data) }}</span>
                <span class="vp-mono vp-p-rec__bt-importo">
                  {{ formattaEuro(bt.importo) }}
                </span>
              </q-item-label>
              <q-item-label caption lines="2">{{ bt.descrizione }}</q-item-label>
              <q-item-label caption class="vp-p-rec__bt-meta">
                <span
                  class="vp-p-rec__chip"
                  :class="`vp-p-rec__chip--${bt.stato_riconciliazione}`"
                >
                  {{ etichettaStato(bt.stato_riconciliazione) }}
                </span>
                <span class="vp-p-rec__chip vp-p-rec__chip--conto">
                  {{ bt.owner_nominativo }} · {{ bt.conto_banca }}
                </span>
                <span v-if="bt.is_inter_owner" class="vp-p-rec__chip vp-p-rec__chip--inter-owner">
                  inter-owner
                </span>
                <span v-if="Number(bt.residuo) !== 0" class="vp-mono">
                  residuo: {{ formattaEuro(bt.residuo) }}
                </span>
                <q-btn
                  flat
                  dense
                  round
                  size="xs"
                  icon="swap_horiz"
                  class="vp-p-rec__bt-azione"
                  :color="bt.is_inter_owner ? 'primary' : 'grey-7'"
                  @click.stop="apriDialogInterOwner(bt)"
                >
                  <q-tooltip>
                    {{ bt.is_inter_owner ? 'Modifica/disfa marcatura inter-owner' : 'Marca come inter-owner' }}
                  </q-tooltip>
                </q-btn>
              </q-item-label>
            </q-item-section>
          </q-item>
          <q-item v-if="store.bts.length === 0 && !store.loadingBts">
            <q-item-section class="text-grey-7">
              Nessuna transazione coi filtri attivi.
            </q-item-section>
          </q-item>
        </q-list>
      </q-card>

      <!-- Colonna destra: Receivable -->
      <q-card flat bordered class="vp-p-rec__col">
        <q-card-section class="vp-p-rec__col-head">
          <div class="vp-p-rec__col-head-left">
            <div class="vp-eyebrow">Addebiti</div>
            <q-btn round dense flat size="sm" icon="info_outline" color="grey-7">
              <q-tooltip>Cosa vedi qui</q-tooltip>
              <q-popup-proxy>
                <q-card class="vp-p-rec__popup-info">
                  <q-card-section>
                    Selezionando una transazione bancaria a sinistra vedi gli
                    addebiti del suo inquilino. Le icone qui accanto mostrano
                    tutti gli inquilini o anche gli addebiti già completi.
                  </q-card-section>
                </q-card>
              </q-popup-proxy>
            </q-btn>
            <q-btn
              round
              dense
              flat
              size="sm"
              :icon="iconaCausale"
              :color="filtroCausale === 'all' ? 'grey-7' : 'primary'"
            >
              <q-tooltip>Causale: {{ etichettaCausaleFiltro }}</q-tooltip>
              <q-menu>
                <q-list dense>
                  <q-item
                    v-for="o in opzioniCausale"
                    :key="o.value"
                    v-close-popup
                    clickable
                    :active="filtroCausale === o.value"
                    @click="filtroCausale = o.value"
                  >
                    <q-item-section avatar>
                      <q-icon
                        :name="
                          o.value === 'all' ? 'category' : iconaCausalePer(o.value)
                        "
                        :class="
                          o.value === 'all'
                            ? ''
                            : `vp-p-rec__causale-icon vp-p-rec__chip--c-${o.value}`
                        "
                      />
                    </q-item-section>
                    <q-item-section>{{ o.label }}</q-item-section>
                  </q-item>
                </q-list>
              </q-menu>
            </q-btn>
          </div>
          <div class="vp-p-rec__col-meta vp-p-rec__col-meta--rec">
            <template v-if="tenantInferito">
              Inquilino: <strong>{{ tenantInferito.nominativo }}</strong>
            </template>
            <template v-else-if="btSelezionate.size > 0">
              Nessun inquilino dedotto — usa l'icona "gruppi" qui sopra
            </template>
          </div>
          <div class="vp-p-rec__col-actions">
            <q-btn
              round
              dense
              flat
              icon="person"
              size="sm"
              :color="filtroTenant ? 'primary' : 'grey-7'"
            >
              <q-tooltip>
                {{ etichettaFiltroTenant }}
              </q-tooltip>
              <q-menu>
                <q-list dense>
                  <q-item
                    v-close-popup
                    clickable
                    :active="filtroTenant === null"
                    @click="filtroTenant = null"
                  >
                    <q-item-section>Tutti gli inquilini</q-item-section>
                  </q-item>
                  <q-separator />
                  <q-item
                    v-for="t in tenantsStore.tenants"
                    :key="t.id"
                    v-close-popup
                    clickable
                    :active="filtroTenant === t.id"
                    @click="filtroTenant = t.id"
                  >
                    <q-item-section>{{ t.nominativo }}</q-item-section>
                  </q-item>
                </q-list>
              </q-menu>
            </q-btn>
            <q-btn
              round
              dense
              flat
              icon="groups"
              size="sm"
              :color="mostraTuttiInquilini ? 'primary' : 'grey-7'"
              @click="mostraTuttiInquilini = !mostraTuttiInquilini"
            >
              <q-tooltip>Mostra tutti gli inquilini</q-tooltip>
            </q-btn>
            <q-btn
              round
              dense
              flat
              icon="check_circle"
              size="sm"
              :color="mostraReceivableCompleti ? 'primary' : 'grey-7'"
              @click="mostraReceivableCompleti = !mostraReceivableCompleti"
            >
              <q-tooltip>Mostra anche gli addebiti già completi</q-tooltip>
            </q-btn>
          </div>
        </q-card-section>
        <q-separator />
        <q-list separator class="vp-p-rec__lista">
          <q-item
            v-for="r in receivablesVisibili"
            :key="r.id"
            v-ripple
            clickable
            :active="receivableSelezionati.has(r.id)"
            active-class="vp-p-rec__item--active"
            class="vp-p-rec__item"
            @click="toggleReceivable(r)"
          >
            <q-item-section avatar>
              <q-checkbox
                :model-value="receivableSelezionati.has(r.id)"
                dense
                @click.stop="toggleReceivable(r)"
              />
            </q-item-section>
            <q-item-section>
              <q-item-label class="vp-p-rec__bt-row">
                <span class="vp-p-rec__rec-titolo">
                  <q-icon
                    :name="iconaCausalePer(r.causale)"
                    size="18px"
                    class="vp-p-rec__causale-icon"
                    :class="`vp-p-rec__chip--c-${r.causale}`"
                  >
                    <q-tooltip>{{ etichettaCausale(r.causale) }}</q-tooltip>
                  </q-icon>
                  {{ r.descrizione_estesa }}
                </span>
                <span class="vp-mono vp-p-rec__bt-importo">
                  {{ formattaEuro(r.importo_dovuto) }}
                </span>
              </q-item-label>
              <q-item-label caption>
                {{ r.tenant_nominativo }} —
                scadenza {{ formattaData(r.scadenza) }}
              </q-item-label>
              <q-item-label caption class="vp-p-rec__rec-coperto">
                <span
                  class="vp-mono"
                  :class="coperturaClass(r)"
                >
                  coperto {{ formattaEuro(r.importo_allocato) }} /
                  {{ formattaEuro(r.importo_dovuto) }}
                </span>
                <span v-if="Number(r.residuo) > 0.005" class="vp-mono text-negative">
                  · residuo {{ formattaEuro(r.residuo) }}
                </span>
              </q-item-label>
            </q-item-section>
          </q-item>
          <q-item
            v-if="receivablesVisibili.length === 0 && !store.loadingReceivables"
          >
            <q-item-section class="text-grey-7">
              Nessun addebito da abbinare.
            </q-item-section>
          </q-item>
        </q-list>
      </q-card>
    </div>

    <!-- Pannello allocazioni -->
    <q-card
      v-if="pannelloVisibile"
      flat
      bordered
      class="vp-p-rec__pannello"
    >
      <q-card-section class="vp-p-rec__pannello-head">
        <div class="vp-eyebrow">Allocazioni</div>
        <div class="vp-p-rec__pannello-actions">
          <q-btn
            flat
            no-caps
            color="negative"
            icon="close"
            label="Annulla"
            @click="annulla"
          />
          <q-btn
            unelevated
            no-caps
            color="primary"
            icon="save"
            :label="etichettaSalva"
            :loading="store.saving"
            :disable="!salvaAbilitato"
            @click="salva"
          />
        </div>
      </q-card-section>
      <q-separator />
      <q-banner
        v-if="allocazioni.length === 0"
        dense
        class="vp-p-rec__banner-vuoto"
      >
        <template #avatar>
          <q-icon name="warning" color="negative" />
        </template>
        Nessuna allocazione: salvando, le abbinature esistenti delle BT
        selezionate verranno <strong>cancellate</strong>.
      </q-banner>
      <q-markup-table v-else flat dense class="vp-p-rec__tabella">
        <thead>
          <tr>
            <th class="text-left">Transazione</th>
            <th class="text-left">Addebito</th>
            <th class="text-right">Dovuto</th>
            <th class="text-right">Importo da allocare</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in allocazioni" :key="`${a.bt_id}-${a.rec_id}`">
            <td>
              <span class="vp-mono">{{ formattaData(a.bt_data) }}</span>
              <br />
              <span class="vp-mono text-grey-7">
                {{ formattaEuro(a.bt_importo) }}
              </span>
            </td>
            <td>
              {{ a.rec_descrizione }}
              <br />
              <small class="text-grey-7">{{ a.rec_tenant }}</small>
            </td>
            <td class="text-right vp-mono">{{ formattaEuro(a.rec_dovuto) }}</td>
            <td class="text-right">
              <q-input
                v-model.number="a.importo"
                dense
                outlined
                type="number"
                step="0.01"
                input-class="text-right vp-mono"
                style="max-width: 130px; display: inline-block"
              />
              <q-btn
                v-if="puoEstendereAlDovuto(a)"
                flat
                dense
                round
                icon="straighten"
                size="sm"
                color="primary"
                @click="estendiAlDovuto(a)"
              >
                <q-tooltip>Porta l'importo al dovuto del Receivable</q-tooltip>
              </q-btn>
            </td>
            <td class="text-right">
              <q-btn
                flat
                dense
                round
                icon="delete"
                color="negative"
                @click="rimuoviAllocazione(a)"
              />
            </td>
          </tr>
        </tbody>
        <tfoot>
          <tr v-for="r in riepilogoBt" :key="`bt-${r.bt_id}`">
            <td colspan="3" class="text-right text-bold">
              Allocato BT {{ formattaData(r.bt_data) }}:
            </td>
            <td class="text-right vp-mono text-bold">
              {{ formattaEuro(r.allocato) }} / {{ formattaEuro(r.importo) }}
            </td>
            <td
              class="text-right vp-mono text-bold"
              :class="{
                'text-negative':
                  (r.importo >= 0 && r.residuo < -0.01)
                  || (r.importo < 0 && r.residuo > 0.01),
                'text-positive': Math.abs(r.residuo) <= 0.01,
              }"
            >
              residuo {{ formattaEuro(r.residuo) }}
            </td>
          </tr>
        </tfoot>
      </q-markup-table>
    </q-card>

    <BankTransactionLedgerDialog
      v-if="btDialogTarget"
      v-model="dialogInterOwnerAperto"
      :bt="btDialogTarget"
      @changed="ricarica"
    />
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { Notify } from 'quasar';
import { useRiconciliazioneStore, type BankTransactionFE, type ReceivableFE } from 'stores/riconciliazione';
import { useTenantsStore, type Tenant } from 'stores/tenants';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';
import BankTransactionLedgerDialog from 'src/components/BankTransactionLedgerDialog.vue';

interface Allocazione {
  bt_id: number;
  bt_data: string;
  bt_importo: number;
  rec_id: number;
  rec_descrizione: string;
  rec_tenant: string;
  rec_dovuto: number;
  importo: number;
}

const store = useRiconciliazioneStore();
const tenantsStore = useTenantsStore();
const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

const filtroRiconciliato = ref<'all' | 'true' | 'false'>('false');
const filtroDataDa = ref<string | null>(null);
const filtroDataA = ref<string | null>(null);
const filtroCausale = ref<'all' | 'affitto' | 'utenze' | 'extra' | 'deposito'>('all');
// Filtro inquilino client-side: usato quando si parte dai Receivable
// (nessuna BT selezionata che inferisca il tenant). Il flusso "click BT"
// inferisce comunque il tenant via tenantInferito, che ha priorità.
const filtroTenant = ref<number | null>(null);
const mostraTuttiInquilini = ref(false);
// Per default i Receivable già coperti al 100% sono nascosti dalla colonna
// destra (non servono al matching corrente). L'icona "check_circle" li
// riporta in vista per consultazione/correzione.
const mostraReceivableCompleti = ref(false);

const opzioniRiconciliato = [
  { label: 'Da abbinare', value: 'false' },
  { label: 'Tutti', value: 'all' },
  { label: 'Abbinati', value: 'true' },
] as const;

const opzioniCausale = [
  { label: 'Tutte', value: 'all' },
  { label: 'Affitto', value: 'affitto' },
  { label: 'Utenze', value: 'utenze' },
  { label: 'Extra', value: 'extra' },
  { label: 'Deposito', value: 'deposito' },
] as const;

const iconaStatoBt = computed(() => {
  if (filtroRiconciliato.value === 'all') return 'all_inclusive';
  if (filtroRiconciliato.value === 'true') return 'done_all';
  return 'inbox'; // 'false' = da abbinare (default)
});
const etichettaStatoBt = computed(
  () =>
    opzioniRiconciliato.find((o) => o.value === filtroRiconciliato.value)
      ?.label ?? '',
);
const iconaCausale = computed(() => iconaCausalePer(filtroCausale.value));
const etichettaFiltroTenant = computed(() => {
  if (!filtroTenant.value) return 'Filtra per inquilino (filtra anche le BT per nome/cognome)';
  const t = tenantsStore.tenants.find((x) => x.id === filtroTenant.value);
  return t
    ? `Inquilino: ${t.nominativo} — filtra anche le BT per nome/cognome`
    : 'Filtra per inquilino';
});
const etichettaCausaleFiltro = computed(
  () =>
    opzioniCausale.find((o) => o.value === filtroCausale.value)?.label ?? '',
);

function pad2(n: number): string {
  return n < 10 ? `0${n}` : `${n}`;
}
function isoDate(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}
function presetQuestAnno() {
  const oggi = new Date();
  filtroDataDa.value = `${oggi.getFullYear()}-01-01`;
  filtroDataA.value = `${oggi.getFullYear()}-12-31`;
}
function presetAnnoScorso() {
  const oggi = new Date();
  filtroDataDa.value = `${oggi.getFullYear() - 1}-01-01`;
  filtroDataA.value = `${oggi.getFullYear() - 1}-12-31`;
}
function presetUltimoTrimestre() {
  const oggi = new Date();
  const inizio = new Date(oggi);
  inizio.setMonth(inizio.getMonth() - 3);
  filtroDataDa.value = isoDate(inizio);
  filtroDataA.value = isoDate(oggi);
}
function presetUltimi12Mesi() {
  const oggi = new Date();
  const inizio = new Date(oggi);
  inizio.setFullYear(inizio.getFullYear() - 1);
  filtroDataDa.value = isoDate(inizio);
  filtroDataA.value = isoDate(oggi);
}
function presetReset() {
  filtroDataDa.value = null;
  filtroDataA.value = null;
}
function aggiungiGiorni(iso: string, giorni: number): string {
  const d = new Date(iso);
  d.setDate(d.getDate() + giorni);
  return isoDate(d);
}
function navigaPeriodo(direzione: -1 | 1, allarga: boolean) {
  if (!filtroDataDa.value || !filtroDataA.value) return;
  const da = new Date(filtroDataDa.value);
  const a = new Date(filtroDataA.value);
  const span = Math.round((a.getTime() - da.getTime()) / 86400000) + 1;
  if (allarga) {
    if (direzione === -1) {
      filtroDataDa.value = aggiungiGiorni(filtroDataDa.value, -span);
    } else {
      filtroDataA.value = aggiungiGiorni(filtroDataA.value, span);
    }
  } else {
    filtroDataDa.value = aggiungiGiorni(filtroDataDa.value, span * direzione);
    filtroDataA.value = aggiungiGiorni(filtroDataA.value, span * direzione);
  }
}
function onFrecciaIndietro(e: Event) {
  const m = e as MouseEvent;
  navigaPeriodo(-1, m.ctrlKey || m.metaKey);
}
function onFrecciaAvanti(e: Event) {
  const m = e as MouseEvent;
  navigaPeriodo(1, m.ctrlKey || m.metaKey);
}
function mostraTutteBt() {
  filtroRiconciliato.value = 'all';
  filtroImportoBt.value = 'tutti';
  sogliaMicroResidui.value = 0;
  nascondiInterOwner.value = false;
}

// Selezione: una o più BT, e per ognuna gli addebiti abbinati.
// btSelezionate = unione di btEsplicite (cliccate dall'utente a sinistra)
//                 + le BT auto-caricate dal click su un Receivable (flusso simmetrico).
// Il "modo creazione abbinamento" è attivo quando btEsplicite ha almeno un elemento.
const btSelezionate = reactive<Set<number>>(new Set());
const btEsplicite = reactive<Set<number>>(new Set());
const receivableSelezionati = reactive<Set<number>>(new Set());
const allocazioni = ref<Allocazione[]>([]);

// Filtro client-side per importo BT: 'tutti' (default) | 'alti' (≥200€) |
// 'bassi' (<200€). Affianca i filtri server (stato/causale/periodo/tenant)
// per separare visivamente bonifici-affitto (alti) da bonifici-utenze (bassi)
// senza richiedere un nuovo round-trip.
const filtroImportoBt = ref<'tutti' | 'alti' | 'bassi'>('tutti');

// Soglia per nascondere BT con residuo trascurabile (sotto/sopra-pagamenti
// di pochi centesimi). 0 = mostra tutto.
const sogliaMicroResidui = ref<0 | 1 | 5>(1);

// Filtro client-side: nasconde le BT marcate come transazioni inter-owner
// (giroconti tra fratelli). Default attivo: nella riconciliazione le BT
// inter-owner sono rumore — non sono pagamenti inquilino.
const nascondiInterOwner = ref(true);

// Stato del dialog "marca BT come inter-owner".
const dialogInterOwnerAperto = ref(false);
const btDialogTarget = ref<BankTransactionFE | null>(null);
function apriDialogInterOwner(bt: BankTransactionFE) {
  btDialogTarget.value = bt;
  dialogInterOwnerAperto.value = true;
}

// Tokens "significativi" del nominativo (nome/cognome con len>=3, lowercase):
// usato sia per inferire l'inquilino dalla descrizione di una BT, sia per
// filtrare le BT quando l'utente seleziona un inquilino dal menu.
function tenantTokens(t: Tenant): string[] {
  return t.nominativo
    .split(/\s+/)
    .filter((tok) => tok.length >= 3)
    .map((tok) => tok.toLowerCase());
}

function btTestoMatchTenant(descr: string, t: Tenant): boolean {
  const tokens = tenantTokens(t);
  if (tokens.length === 0) return true;
  const lower = descr.toLowerCase();
  return tokens.some((tok) => lower.includes(tok));
}

const tenantPerFiltroBt = computed<Tenant | null>(() => {
  if (mostraTuttiInquilini.value) return null;
  if (!filtroTenant.value) return null;
  return tenantsStore.tenants.find((t) => t.id === filtroTenant.value) ?? null;
});

// BT con allocations verso un receivable di questo tenant: vanno sempre mostrate
// (anche se la descrizione non contiene nome/cognome — es. pagamento fatto da
// terzi e già abbinato manualmente).
function btHaAllocAlTenant(bt: BankTransactionFE, tenantId: number): boolean {
  for (const alloc of bt.allocations) {
    const r = store.receivables.find((rr) => rr.id === alloc.receivable);
    if (r && r.tenant_id === tenantId) return true;
  }
  return false;
}

const btOrdinate = computed<BankTransactionFE[]>(() => {
  const tenantBt = tenantPerFiltroBt.value;
  const filtrate = store.bts.filter((bt) => {
    if (nascondiInterOwner.value && bt.is_inter_owner) return false;
    if (filtroImportoBt.value !== 'tutti') {
      const imp = Math.abs(Number(bt.importo));
      const passaImporto =
        filtroImportoBt.value === 'alti' ? imp >= 200 : imp < 200;
      if (!passaImporto) return false;
    }
    if (sogliaMicroResidui.value > 0) {
      // Esclude solo le BT parzialmente riconciliate con residuo trascurabile.
      // Le BT "vuote" (residuo == importo) restano sempre visibili, anche
      // se l'importo è < soglia (es. piccoli bonifici da abbinare).
      const residuo = Number(bt.residuo);
      const importo = Number(bt.importo);
      if (residuo > 0 && residuo < sogliaMicroResidui.value && residuo < importo) {
        return false;
      }
    }
    if (tenantBt && !btSelezionate.has(bt.id)) {
      // BT già selezionata (esplicita o auto): sempre visibile.
      // Altrimenti: match testuale su nome/cognome OPPURE allocations al tenant.
      if (
        !btTestoMatchTenant(bt.descrizione, tenantBt)
        && !btHaAllocAlTenant(bt, tenantBt.id)
      ) {
        return false;
      }
    }
    return true;
  });
  return filtrate.sort((a, b) => (a.data < b.data ? 1 : -1));
});

// Inquilino dedotto: priorità (1) allocations esistenti, (2) match
// testuale sul nominativo nella descrizione del bonifico (es. "Bon. da Rossi").
function inquilinoDaDescrizione(descr: string) {
  for (const t of tenantsStore.tenants) {
    if (btTestoMatchTenant(descr, t)) return t;
  }
  return null;
}

const tenantInferito = computed(() => {
  if (mostraTuttiInquilini.value) return null;
  // Il filtro manuale ha priorità sul testo della BT.
  if (filtroTenant.value) {
    return (
      tenantsStore.tenants.find((t) => t.id === filtroTenant.value) ?? null
    );
  }
  for (const id of btSelezionate) {
    const bt = store.bts.find((b) => b.id === id);
    if (!bt) continue;
    const alloc = bt.allocations[0];
    if (alloc) {
      const r = store.receivables.find((rr) => rr.id === alloc.receivable);
      if (r) {
        const t = tenantsStore.tenants.find((tt) => tt.id === r.tenant_id);
        if (t) return t;
      }
    }
    const dalTesto = inquilinoDaDescrizione(bt.descrizione);
    if (dalTesto) return dalTesto;
  }
  return null;
});

const receivablesVisibili = computed<ReceivableFE[]>(() => {
  // Quando una BT è selezionata e ha allocations già esistenti, i recv coperti
  // devono essere SEMPRE visibili, anche se non rispettano filtri causale/tenant
  // (l'utente vuole vedere/correggere le componenti dell'abbinamento esistente).
  const recIdsCoinvolti = new Set(allocazioni.value.map((a) => a.rec_id));
  function bypass(r: ReceivableFE): boolean {
    return recIdsCoinvolti.has(r.id);
  }

  let lista = store.receivables;
  // Filtro tenant: solo se inferito da una BT selezionata.
  if (!mostraTuttiInquilini.value && tenantInferito.value) {
    lista = lista.filter(
      (r) => bypass(r) || r.tenant_id === tenantInferito.value!.id,
    );
  }
  // Filtro causale
  if (filtroCausale.value !== 'all') {
    lista = lista.filter((r) => bypass(r) || r.causale === filtroCausale.value);
  }
  // Filtro completamente coperti (default: nascosti)
  if (!mostraReceivableCompleti.value) {
    lista = lista.filter((r) => bypass(r) || !receivableCompleto(r));
  }
  return lista;
});

function receivableCompleto(r: ReceivableFE): boolean {
  // Segno-aware: per Receivable positivi serve allocato ≥ dovuto; per
  // negativi (restituzione caparra) serve allocato ≤ dovuto (entrambi
  // negativi). Confronto in valore assoluto con tolleranza.
  const dovuto = Number(r.importo_dovuto);
  const allocato = Number(r.importo_allocato) || 0;
  if (dovuto === 0) return true;
  if (Math.sign(dovuto) !== Math.sign(allocato) && allocato !== 0) return false;
  return Math.abs(allocato) + 0.01 >= Math.abs(dovuto);
}

const btFuoriFiltro = computed(() =>
  Array.from(btSelezionate).filter(
    (id) => !btOrdinate.value.some((b) => b.id === id),
  ),
);

const riepilogoBt = computed(() =>
  Array.from(btSelezionate).map((bt_id) => {
    const bt = store.bts.find((b) => b.id === bt_id);
    // Fallback: la BT potrebbe non essere in store.bts perché filtrata
    // (es. abbinata, mentre il filtro è su "da abbinare"); recupero data/importo
    // dalle allocations già caricate (vedi caricaAllocazioniDaReceivable).
    const fromAlloc = allocazioni.value.find((a) => a.bt_id === bt_id);
    const importo = Number(bt?.importo ?? fromAlloc?.bt_importo ?? 0);
    const data = bt?.data ?? fromAlloc?.bt_data ?? '';
    const allocato = allocazioni.value
      .filter((a) => a.bt_id === bt_id)
      .reduce((s, a) => s + (Number.isFinite(a.importo) ? a.importo : 0), 0);
    return {
      bt_id,
      bt_data: data,
      importo,
      allocato,
      residuo: importo - allocato,
    };
  }),
);

const pannelloVisibile = computed(
  () => allocazioni.value.length > 0 || btEsplicite.size > 0,
);

const etichettaSalva = computed(() =>
  allocazioni.value.length === 0 && btEsplicite.size > 0
    ? 'Cancella abbinamenti'
    : 'Salva',
);

const salvaAbilitato = computed(() => {
  // Caso "scollega": nessuna allocazione, ma BT esplicitamente selezionate →
  // salvataggio cancella le allocations esistenti sul backend.
  if (allocazioni.value.length === 0) return btEsplicite.size > 0;
  // Invariante per ogni BT: somma algebrica delle allocations dello stesso
  // segno della BT (o nulla) e |Σ| ≤ |BT.importo|. Allocations miste sono
  // permesse purché la somma rispetti questi vincoli.
  const tutteBtOk = riepilogoBt.value.every((r) => {
    const somma = Number(r.importo) - Number(r.residuo);
    if (r.importo > 0 && somma < -0.01) return false;
    if (r.importo < 0 && somma > 0.01) return false;
    if (r.importo >= 0) return r.residuo >= -0.01;
    return r.residuo <= 0.01;
  });
  // Per ogni allocation: il segno deve concordare col Receivable a cui è
  // legata (l'invariante BT↔alloc è stata rilassata, quella alloc↔Rec resta).
  const tutteAllocOk = allocazioni.value.every((a) => {
    if (a.rec_dovuto > 0) return a.importo > 0;
    if (a.rec_dovuto < 0) return a.importo < 0;
    return a.importo !== 0;
  });
  return tutteBtOk && tutteAllocOk;
});

function caricaAllocazioniEsistenti(bt: BankTransactionFE) {
  for (const alloc of bt.allocations) {
    if (allocazioni.value.some((a) => a.bt_id === bt.id && a.rec_id === alloc.receivable)) {
      continue;
    }
    const rec = store.receivables.find((r) => r.id === alloc.receivable);
    allocazioni.value.push({
      bt_id: bt.id,
      bt_data: bt.data,
      bt_importo: Number(bt.importo),
      rec_id: alloc.receivable,
      rec_descrizione: rec?.descrizione_estesa ?? alloc.receivable_descrizione,
      rec_tenant: rec?.tenant_nominativo ?? '',
      rec_dovuto: Number(rec?.importo_dovuto ?? 0),
      importo: Number(alloc.importo),
    });
    receivableSelezionati.add(alloc.receivable);
  }
}

function clickBt(bt: BankTransactionFE, e: MouseEvent) {
  const additivo = e.ctrlKey || e.metaKey;
  if (additivo) {
    // Ctrl/Cmd+Click: toggle nella selezione multipla.
    if (btEsplicite.has(bt.id)) {
      btEsplicite.delete(bt.id);
      btSelezionate.delete(bt.id);
      const recIdsRimossi = allocazioni.value
        .filter((a) => a.bt_id === bt.id)
        .map((a) => a.rec_id);
      allocazioni.value = allocazioni.value.filter((a) => a.bt_id !== bt.id);
      for (const rid of recIdsRimossi) {
        if (!allocazioni.value.some((x) => x.rec_id === rid)) {
          receivableSelezionati.delete(rid);
        }
      }
    } else {
      btSelezionate.add(bt.id);
      btEsplicite.add(bt.id);
      caricaAllocazioniEsistenti(bt);
    }
    return;
  }
  // Click semplice: sostituisce la selezione corrente.
  if (btEsplicite.size === 1 && btEsplicite.has(bt.id)) {
    // Riclick sull'unica BT esplicita: deseleziona tutto.
    btSelezionate.clear();
    btEsplicite.clear();
    allocazioni.value = [];
    receivableSelezionati.clear();
    return;
  }
  btSelezionate.clear();
  btEsplicite.clear();
  allocazioni.value = [];
  receivableSelezionati.clear();
  btSelezionate.add(bt.id);
  btEsplicite.add(bt.id);
  caricaAllocazioniEsistenti(bt);
}

function caricaAllocazioniDaReceivable(r: ReceivableFE) {
  // Popola il pannello con le allocazioni esistenti del receivable.
  // Auto-seleziona le BT che lo coprono (anche se non sono in store.bts
  // perché filtrate fuori dalla lista a sinistra: il pannello in basso le mostra).
  for (const alloc of r.allocations) {
    if (allocazioni.value.some((a) => a.bt_id === alloc.bank_transaction && a.rec_id === r.id)) {
      continue;
    }
    allocazioni.value.push({
      bt_id: alloc.bank_transaction,
      bt_data: alloc.bt_data,
      bt_importo: Number(alloc.bt_importo),
      rec_id: r.id,
      rec_descrizione: r.descrizione_estesa,
      rec_tenant: r.tenant_nominativo,
      rec_dovuto: Number(r.importo_dovuto),
      importo: Number(alloc.importo),
    });
    btSelezionate.add(alloc.bank_transaction);
  }
  receivableSelezionati.add(r.id);
}

function toggleReceivable(r: ReceivableFE) {
  // Caso A: l'utente NON ha cliccato esplicitamente alcuna BT → modalità
  // "vedere chi paga il receivable". Click su un altro recv = sostituisce.
  if (btEsplicite.size === 0) {
    if (receivableSelezionati.has(r.id)) {
      // Riclick: deseleziona e svuota il pannello.
      receivableSelezionati.delete(r.id);
      allocazioni.value = allocazioni.value.filter((a) => a.rec_id !== r.id);
      pulisciBtAuto();
      return;
    }
    // Click su un nuovo recv: rimpiazza il contesto attuale.
    allocazioni.value = [];
    receivableSelezionati.clear();
    btSelezionate.clear();
    if (r.allocations.length === 0) {
      Notify.create({
        type: 'info',
        message: 'Questo addebito non ha pagamenti. Seleziona una transazione per abbinarlo.',
      });
      return;
    }
    caricaAllocazioniDaReceivable(r);
    return;
  }
  // Caso B: BT esplicita già selezionata → flusso di creazione/modifica abbinamento.
  if (receivableSelezionati.has(r.id)) {
    receivableSelezionati.delete(r.id);
    allocazioni.value = allocazioni.value.filter((a) => a.rec_id !== r.id);
    pulisciBtAuto();
  } else {
    aggiungiAllocazione(r);
  }
}

function aggiungiAllocazione(r: ReceivableFE) {
  // Le allocations devono avere lo stesso segno del Receivable a cui sono
  // legate (invariante alloc↔Rec). Il segno della BT può differire: questo
  // serve al pattern "restituzione deposito + previsionale utenze" dove una
  // BT in uscita copre un Rec negativo e uno positivo nella stessa BT.
  const dovuto = Number(r.importo_dovuto);
  const segnoDovuto = Math.sign(dovuto);
  if (riepilogoBt.value.length === 0) {
    Notify.create({
      type: 'warning',
      message: 'Seleziona prima una transazione bancaria.',
    });
    return;
  }
  // Scegliamo la BT con più capacità residua nel verso del Rec: per Rec
  // positivo preferiamo BT con `residuo` algebrico più alto (più positivo),
  // per Rec negativo quelle con residuo più basso (più negativo). Se nessuna
  // BT ha residuo nel verso giusto, prendiamo quella con maggior capacità
  // totale (|importo|) — utile per il pattern misto.
  const ordinate = [...riepilogoBt.value].sort((a, b) =>
    segnoDovuto >= 0 ? b.residuo - a.residuo : a.residuo - b.residuo,
  );
  const target =
    ordinate.find((b) =>
      segnoDovuto > 0 ? b.residuo > 0.005 : b.residuo < -0.005,
    ) ?? ordinate[0];
  if (!target) return;
  const allocato = Number(r.importo_allocato);
  // Residuo dell'addebito col segno corretto (≥0 per dovuto>0, ≤0 per dovuto<0).
  const residuoRecRaw = dovuto - allocato;
  const residuoRec =
    segnoDovuto >= 0
      ? Math.max(residuoRecRaw, 0)
      : Math.min(residuoRecRaw, 0);
  // Capacità ancora disponibile sulla BT nel verso del Rec: importo già
  // allocato escluso, così una BT con resto parziale propone il resto (non
  // il suo importo pieno) e non sfora il salvataggio. Se non c'è capacità in
  // questo verso (es. pattern a segni discordi) si ricade sull'importo pieno.
  const capacitaResidua =
    segnoDovuto >= 0 ? Math.max(target.residuo, 0) : Math.min(target.residuo, 0);
  const capAbs = Math.abs(capacitaResidua) || Math.abs(target.importo);
  // Quota da allocare: il residuo del Rec, capped alla capacità residua della BT.
  const quotaAbs = Math.min(
    capAbs,
    Math.abs(residuoRec) || capAbs,
  );
  const importo = segnoDovuto < 0 ? -quotaAbs : quotaAbs;
  const bt = store.bts.find((b) => b.id === target.bt_id)!;
  allocazioni.value.push({
    bt_id: target.bt_id,
    bt_data: bt.data,
    bt_importo: Number(bt.importo),
    rec_id: r.id,
    rec_descrizione: r.descrizione_estesa,
    rec_tenant: r.tenant_nominativo,
    rec_dovuto: dovuto,
    importo: Number(importo.toFixed(2)),
  });
  receivableSelezionati.add(r.id);
}

function pulisciBtAuto() {
  // Rimuove dalla btSelezionate le BT che (a) non sono state cliccate
  // esplicitamente dall'utente e (b) non hanno più allocations nel pannello.
  // Le BT esplicite restano selezionate anche con pannello vuoto.
  for (const id of Array.from(btSelezionate)) {
    if (btEsplicite.has(id)) continue;
    if (!allocazioni.value.some((a) => a.bt_id === id)) {
      btSelezionate.delete(id);
    }
  }
}

function puoEstendereAlDovuto(a: Allocazione): boolean {
  // Mostra il bottone solo se l'importo allocato corrente è ancora "lontano"
  // dal dovuto del Rec (in valore assoluto, oltre 1 €).
  if (!a.rec_dovuto) return false;
  return Math.abs(Math.abs(a.rec_dovuto) - Math.abs(a.importo)) > 1;
}

function estendiAlDovuto(a: Allocazione) {
  a.importo = Number(a.rec_dovuto.toFixed(2));
}

function rimuoviAllocazione(a: Allocazione) {
  // Rimuovere l'allocazione è una modifica esplicita dell'utente: promuoviamo
  // la BT a "esplicita" (anche se era stata auto-aggiunta dal flusso
  // "vedi chi paga"), così il pannello resta visibile col bottone Salva
  // — altrimenti sparirebbe senza che il backend venga aggiornato.
  btEsplicite.add(a.bt_id);
  btSelezionate.add(a.bt_id);
  allocazioni.value = allocazioni.value.filter(
    (x) => !(x.bt_id === a.bt_id && x.rec_id === a.rec_id),
  );
  // Se il receivable non ha più nessuna allocation, deselezionalo.
  if (!allocazioni.value.some((x) => x.rec_id === a.rec_id)) {
    receivableSelezionati.delete(a.rec_id);
  }
  pulisciBtAuto();
}

function annulla() {
  allocazioni.value = [];
  receivableSelezionati.clear();
  btSelezionate.clear();
  btEsplicite.clear();
}

async function salva() {
  const replace_for_transactions = Array.from(btSelezionate);
  const items = allocazioni.value.map((a) => ({
    bank_transaction: a.bt_id,
    receivable: a.rec_id,
    importo: a.importo.toFixed(2),
  }));
  try {
    await store.saveBulk({ replace_for_transactions, items });
    Notify.create({
      type: 'positive',
      message: 'Riconciliazione salvata.',
      icon: 'check_circle',
    });
    annulla();
    await ricarica();
  } catch (e: unknown) {
    const msg =
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      || 'Salvataggio non riuscito';
    Notify.create({ type: 'negative', message: msg });
  }
}

function etichettaStato(s: string): string {
  if (s === 'pieno') return 'abbinato';
  if (s === 'parziale') return 'parziale';
  return 'da abbinare';
}

function etichettaCausale(c: string): string {
  if (c === 'affitto') return 'Affitto';
  if (c === 'utenze') return 'Utenze';
  if (c === 'extra') return 'Extra';
  if (c === 'deposito') return 'Deposito';
  return c;
}

function iconaCausalePer(c: string): string {
  if (c === 'affitto') return 'home';
  if (c === 'utenze') return 'bolt';
  if (c === 'extra') return 'more_horiz';
  if (c === 'deposito') return 'savings';
  return 'category';
}

function coperturaClass(r: ReceivableFE): string {
  // Segno-aware: per dovuto<0 (restituzione caparra) allocato deve essere
  // <= dovuto (cioè più negativo o uguale).
  const allocato = Number(r.importo_allocato) || 0;
  const dovuto = Number(r.importo_dovuto);
  if (dovuto === 0) return 'vp-p-rec__cop--pieno';
  const stessoSegno = Math.sign(allocato) === Math.sign(dovuto) || allocato === 0;
  if (stessoSegno && Math.abs(allocato) + 0.01 >= Math.abs(dovuto)) {
    return 'vp-p-rec__cop--pieno';
  }
  if (Math.abs(allocato) > 0.005) return 'vp-p-rec__cop--parziale';
  return 'vp-p-rec__cop--vuoto';
}

async function ricarica() {
  // Dimensione pagina: lo store segue tutte le pagine DRF (vedi
  // fetchAllPaginated), quindi non c'è un cap rigido — questo è solo il numero
  // di record per richiesta (200 = max_limit del backend).
  const PAGE_LIMIT = 200;
  await Promise.all([
    store.fetchBankTransactions({
      data_da: filtroDataDa.value,
      data_a: filtroDataA.value,
      riconciliato: filtroRiconciliato.value,
      tenant: null,
      limit: PAGE_LIMIT,
    }),
    store.fetchReceivables({
      tenant: null,
      riconciliato: 'all',
      data_da: filtroDataDa.value,
      data_a: filtroDataA.value,
      limit: PAGE_LIMIT,
    }),
  ]);
}

const route = useRoute();

onMounted(async () => {
  await tenantsStore.fetchTenants(false);
  // Pre-filtri da query string: ?tenant=<id>&anno=YYYY&riconciliato=all|true|false.
  // Usati dalle scorciatoie da altre pagine (dettaglio inquilino).
  const tenantQ = Number(route.query.tenant);
  if (Number.isFinite(tenantQ) && tenantQ > 0) {
    filtroTenant.value = tenantQ;
    // Esplicitamente NON attiviamo mostraTuttiInquilini: con la scorciatoia
    // vogliamo proprio filtrare BT+Receivable sul tenant.
    mostraTuttiInquilini.value = false;
  }
  const annoQ = Number(route.query.anno);
  if (Number.isFinite(annoQ) && annoQ > 2000) {
    filtroDataDa.value = `${annoQ}-01-01`;
    filtroDataA.value = `${annoQ}-12-31`;
  }
  const riconciliatoQ = route.query.riconciliato;
  if (riconciliatoQ === 'all' || riconciliatoQ === 'true' || riconciliatoQ === 'false') {
    filtroRiconciliato.value = riconciliatoQ;
  }
  await ricarica();
});

watch([filtroRiconciliato, filtroDataDa, filtroDataA], () => {
  void ricarica();
});
</script>

<style scoped>
.vp-p-rec__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: var(--vp-gap-3);
  flex-wrap: wrap;
  margin-bottom: var(--vp-gap-4);
}
.vp-p-rec__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 0;
}
.vp-p-rec__head-titolo {
  display: flex;
  align-items: flex-start;
  gap: var(--vp-gap-2);
}
.vp-p-rec__popup-info {
  max-width: 480px;
  padding: var(--vp-gap-1);
  color: var(--vp-ink-2);
}
.vp-p-rec__filtri {
  display: flex;
  flex-wrap: wrap;
  gap: var(--vp-gap-3);
  align-items: flex-end;
  margin-bottom: var(--vp-gap-4);
}
.vp-p-rec__date {
  width: 160px;
}
.vp-p-rec__col-meta--rec {
  flex: 1 1 auto;
}
.vp-p-rec__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--vp-gap-4);
  margin-bottom: var(--vp-gap-4);
}
@media (max-width: 900px) {
  .vp-p-rec__grid {
    grid-template-columns: 1fr;
  }
}
.vp-p-rec__col {
  background: var(--vp-cream);
  display: flex;
  flex-direction: column;
  max-height: 60vh;
}
.vp-p-rec__col-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--vp-gap-2);
}
.vp-p-rec__col-head-left {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-2);
  flex-wrap: wrap;
}
.vp-p-rec__filtro-importo {
  font-size: 0.7rem;
}
.vp-p-rec__resti-label {
  margin-left: var(--vp-gap-1);
}
.vp-p-rec__col-actions {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}
.vp-p-rec__col-meta {
  color: var(--vp-ink-2);
  font-size: 0.85rem;
}
.vp-p-rec__badge {
  margin-left: var(--vp-gap-2);
  padding: 2px 8px;
  border-radius: var(--vp-r-sm);
  background: var(--vp-terra-soft);
  color: var(--vp-terra-deep);
  font-weight: 500;
}
.vp-p-rec__lista {
  overflow-y: auto;
  flex: 1;
}
.vp-p-rec__item {
  cursor: pointer;
}
.vp-p-rec__item--active {
  background: var(--vp-terra-soft);
}
.vp-p-rec__bt-row {
  display: flex;
  justify-content: space-between;
  gap: var(--vp-gap-2);
}
.vp-p-rec__bt-data {
  font-weight: 500;
}
.vp-p-rec__bt-importo {
  font-weight: 600;
}
.vp-p-rec__bt-meta {
  display: flex;
  gap: var(--vp-gap-2);
  align-items: center;
  flex-wrap: wrap;
  margin-top: var(--vp-gap-1);
}
.vp-p-rec__chip {
  padding: 1px 8px;
  border-radius: var(--vp-r-sm);
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background: var(--vp-paper-2);
  color: var(--vp-ink-2);
}
.vp-p-rec__chip--vuoto {
  background: var(--vp-argilla-chiaro, #f3d9c8);
  color: var(--vp-ink);
}
.vp-p-rec__chip--parziale {
  background: var(--vp-miele, #f6e1a3);
  color: var(--vp-ink);
}
.vp-p-rec__chip--pieno {
  background: var(--vp-salvia, #c6d6c6);
  color: var(--vp-ink);
}
.vp-p-rec__chip--conto {
  text-transform: none;
  letter-spacing: normal;
}
.vp-p-rec__chip--inter-owner {
  background: var(--vp-terra-soft, #ead0bd);
  color: var(--vp-terra-deep, #6c3a18);
  font-weight: 500;
}
.vp-p-rec__bt-azione {
  margin-left: auto;
}
.vp-p-rec__chip--causale {
  margin-right: var(--vp-gap-1);
  font-weight: 600;
}
.vp-p-rec__chip--c-affitto {
  background: var(--vp-salvia, #c6d6c6);
  color: var(--vp-ink);
}
.vp-p-rec__chip--c-utenze {
  background: var(--vp-miele, #f6e1a3);
  color: var(--vp-ink);
}
.vp-p-rec__chip--c-extra {
  background: var(--vp-terra-soft, #ead0bd);
  color: var(--vp-terra-deep, #6c3a18);
}
.vp-p-rec__chip--c-deposito {
  background: var(--vp-argilla, #e6dccb);
  color: var(--vp-ink);
}
.vp-p-rec__causale-icon {
  flex-shrink: 0;
  background: transparent;
}
.vp-p-rec__causale-icon.vp-p-rec__chip--c-affitto {
  background: transparent;
  color: var(--vp-salvia, #4f6e3f);
}
.vp-p-rec__causale-icon.vp-p-rec__chip--c-utenze {
  background: transparent;
  color: var(--vp-miele, #b08a1f);
}
.vp-p-rec__causale-icon.vp-p-rec__chip--c-extra {
  background: transparent;
  color: var(--vp-terra, #b56a3b);
}
.vp-p-rec__causale-icon.vp-p-rec__chip--c-deposito {
  background: transparent;
  color: var(--vp-argilla-deep, #8a7748);
}
.vp-p-rec__rec-titolo {
  display: inline-flex;
  align-items: center;
  gap: var(--vp-gap-1);
}
.vp-p-rec__rec-coperto {
  margin-top: 2px;
  display: flex;
  gap: var(--vp-gap-1);
  align-items: center;
  flex-wrap: wrap;
}
.vp-p-rec__cop--pieno {
  color: var(--vp-salvia-deep, #4f6b4d);
  font-weight: 500;
}
.vp-p-rec__cop--parziale {
  color: var(--vp-miele-deep, #8a6b1f);
  font-weight: 500;
}
.vp-p-rec__cop--vuoto {
  color: var(--vp-ink-2);
}
.vp-p-rec__preset {
  display: flex;
  flex-wrap: wrap;
  gap: var(--vp-gap-1);
  align-items: center;
  margin-bottom: var(--vp-gap-3);
  padding: var(--vp-gap-2);
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-md);
}
.vp-p-rec__banner-fuori {
  background: var(--vp-miele, #f6e1a3);
  color: var(--vp-ink);
  font-size: 0.85rem;
}
.vp-p-rec__banner-vuoto {
  background: var(--vp-argilla-chiaro, #f3d9c8);
  color: var(--vp-ink);
  font-size: 0.85rem;
}
.vp-p-rec__pannello {
  background: var(--vp-cream);
  margin-bottom: var(--vp-gap-4);
}
.vp-p-rec__pannello-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--vp-gap-2);
}
.vp-p-rec__pannello-actions {
  display: flex;
  gap: var(--vp-gap-2);
}
.vp-p-rec__tabella {
  background: var(--vp-cream);
}
.vp-mono {
  font-variant-numeric: tabular-nums;
}
</style>
