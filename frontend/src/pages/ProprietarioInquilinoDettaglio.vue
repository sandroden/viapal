<template>
  <q-page padding class="vp-p-id">
    <div class="vp-p-id__nav-inq">
      <q-btn
        flat
        icon="arrow_back"
        no-caps
        label="Torna agli inquilini"
        :to="linkLista"
        class="vp-p-id__back"
      />
      <div class="vp-p-id__nav-frecce">
        <q-btn
          flat
          round
          dense
          icon="navigate_before"
          aria-label="Inquilino precedente"
          :disable="!inquilinoPrecedente"
          @click="vaiInquilinoPrecedente"
        >
          <q-tooltip v-if="inquilinoPrecedente">
            {{ inquilinoPrecedente.nominativo }}
          </q-tooltip>
        </q-btn>
        <span v-if="posizioneInLista" class="vp-p-id__nav-pos">
          {{ posizioneInLista }}
        </span>
        <q-btn
          flat
          round
          dense
          icon="navigate_next"
          aria-label="Inquilino successivo"
          :disable="!inquilinoSuccessivo"
          @click="vaiInquilinoSuccessivo"
        >
          <q-tooltip v-if="inquilinoSuccessivo">
            {{ inquilinoSuccessivo.nominativo }}
          </q-tooltip>
        </q-btn>
      </div>
    </div>

    <header class="vp-p-id__head">
      <div>
        <div class="vp-eyebrow">Inquilino</div>
        <h1 class="vp-display vp-p-id__titolo">
          {{ situazione?.tenant.nominativo ?? 'Dettaglio inquilino' }}
        </h1>
        <p v-if="situazione?.tenant" class="vp-p-id__contatti">
          <span v-if="situazione.tenant.email">{{ situazione.tenant.email }}</span>
          <span v-if="situazione.tenant.email && situazione.tenant.telefono"> · </span>
          <span v-if="situazione.tenant.telefono">{{ situazione.tenant.telefono }}</span>
        </p>
      </div>

      <div class="vp-p-id__nav-anno">
        <q-btn
          flat
          round
          icon="chevron_left"
          aria-label="Anno precedente"
          :disable="!puoIndietro"
          @click="annoPrecedente"
        />
        <q-select
          v-model="annoSelezionato"
          :options="anniDisponibili"
          dense
          outlined
          label="Anno"
          class="vp-p-id__sel"
          @update:model-value="onAnnoChange"
        />
        <q-btn
          flat
          round
          icon="chevron_right"
          aria-label="Anno successivo"
          :disable="!puoAvanti"
          @click="annoSuccessivo"
        />
      </div>
    </header>

    <div v-if="store.loading && !situazione" class="vp-p-id__loader">
      <q-spinner color="primary" size="32px" />
    </div>

    <template v-else-if="situazione">
      <section class="vp-p-id__kpi">
        <div class="vp-p-id__kpi-card vp-p-id__kpi-card--accent">
          <div class="vp-p-id__kpi-head">
            <span class="vp-p-id__kpi-label">Dovuto anno</span>
            <q-icon
              name="info_outline"
              size="16px"
              class="vp-p-id__kpi-info"
              tabindex="0"
              role="button"
              aria-label="Dettaglio composizione del dovuto anno"
            >
              <q-popup-proxy>
                <q-card class="vp-p-id__popup">
                  <q-card-section>
                    <div class="vp-eyebrow">Composizione dovuto {{ situazione.anno }}</div>
                    <q-list dense>
                      <q-item>
                        <q-item-section>Affitti (mensilità)</q-item-section>
                        <q-item-section side>
                          <span class="vp-mono">{{ formattaEuro(situazione.rent.dovuto_anno) }}</span>
                        </q-item-section>
                      </q-item>
                      <q-item>
                        <q-item-section>Utenze</q-item-section>
                        <q-item-section side>
                          <span class="vp-mono">{{ formattaEuro(situazione.utility.dovuto_anno) }}</span>
                        </q-item-section>
                      </q-item>
                      <q-item>
                        <q-item-section>Addebiti extra</q-item-section>
                        <q-item-section side>
                          <span class="vp-mono">{{ formattaEuro(situazione.extra.totale_anno) }}</span>
                        </q-item-section>
                      </q-item>
                      <q-separator spaced />
                      <q-item>
                        <q-item-section><strong>Totale</strong></q-item-section>
                        <q-item-section side>
                          <strong class="vp-mono">{{ formattaEuro(situazione.totali_anno.dovuto) }}</strong>
                        </q-item-section>
                      </q-item>
                    </q-list>
                    <div class="vp-p-id__popup-nota">
                      Comprende affitti, utenze (luce, gas, TARI) e addebiti extra
                      (es. conguaglio condominiale).
                    </div>
                  </q-card-section>
                </q-card>
              </q-popup-proxy>
            </q-icon>
          </div>
          <div class="vp-p-id__kpi-value vp-display">
            {{ formattaEuro(situazione.totali_anno.dovuto) }}
          </div>
        </div>

        <KpiCard
          label="Pagato anno"
          :value="situazione.totali_anno.pagato"
          is-currency
        />
        <KpiCard
          label="Saldo"
          :value="situazione.totali_anno.saldo"
          is-currency
          :sublabel="situazione.totali_anno.saldo >= 0 ? 'In regola' : 'Da incassare'"
        />
        <KpiCard
          label="Ritardo medio"
          :value="`${situazione.ritardo_medio_giorni.toFixed(1)} gg`"
          :sublabel="situazione.ritardo_medio_giorni === 0 ? 'Mai in ritardo' : 'Sui pagati'"
        />
      </section>

      <q-tabs
        v-model="tabAttivo"
        dense
        no-caps
        align="left"
        class="vp-p-id__tabs"
        active-color="primary"
        indicator-color="primary"
      >
        <q-tab name="pagamenti" label="Pagamenti" />
        <q-tab name="profilo" label="Profilo & contratto" />
      </q-tabs>

      <q-tab-panels v-model="tabAttivo" animated class="vp-p-id__panels">
        <!-- TAB PAGAMENTI -->
        <q-tab-panel name="pagamenti" class="vp-p-id__panel">
          <div class="vp-p-id__toolbar">
            <q-btn
              round
              dense
              flat
              size="sm"
              :icon="iconaTipoPer(filtroTipo)"
              :color="filtroTipo === 'all' ? 'grey-7' : 'primary'"
              :class="
                filtroTipo === 'all'
                  ? ''
                  : `vp-p-id__filtro-attivo vp-p-id__chip--c-${filtroTipo}`
              "
            >
              <q-tooltip>Tipo: {{ etichettaTipoFiltro }}</q-tooltip>
              <q-menu>
                <q-list dense>
                  <q-item
                    v-for="o in opzioniTipo"
                    :key="o.value"
                    v-close-popup
                    clickable
                    :active="filtroTipo === o.value"
                    @click="filtroTipo = o.value"
                  >
                    <q-item-section avatar>
                      <q-icon
                        :name="iconaTipoPer(o.value)"
                        :class="
                          o.value === 'all'
                            ? ''
                            : `vp-p-id__causale-icon vp-p-id__chip--c-${o.value}`
                        "
                      />
                    </q-item-section>
                    <q-item-section>{{ o.label }}</q-item-section>
                  </q-item>
                </q-list>
              </q-menu>
            </q-btn>
            <span v-if="filtroTipo !== 'all'" class="vp-p-id__filtro-info">
              {{ righePagamentiFiltrate.length }} di {{ righePagamenti.length }} righe
            </span>
          </div>
          <q-table
            v-if="righePagamentiFiltrate.length"
            flat
            bordered
            :rows="righePagamentiFiltrate"
            :columns="colonnePagamenti"
            row-key="rowKey"
            :pagination="paginazionePagamenti"
            class="vp-p-id__table"
          >
            <template #body-cell-tipo="props">
              <q-td :props="props">
                <q-icon
                  :name="iconaPerTipo(props.row.tipo)"
                  size="18px"
                  class="vp-p-id__tipo-icon"
                  :class="[
                    `vp-p-id__chip--c-${props.row.tipo}`,
                    filtroTipo === 'all' ? 'vp-p-id__tipo-icon--clickable' : '',
                  ]"
                  @click="
                    filtroTipo === 'all' ? (filtroTipo = props.row.tipo) : null
                  "
                >
                  <q-tooltip v-if="filtroTipo === 'all'">
                    Filtra: solo {{ etichettaPerTipo(props.row.tipo) }}
                  </q-tooltip>
                </q-icon>
                {{ etichettaPerTipo(props.row.tipo) }}
              </q-td>
            </template>
            <template #body-cell-importo_dovuto="props">
              <q-td :props="props">{{ formattaEuro(props.row.importo_dovuto) }}</q-td>
            </template>
            <template #body-cell-importo_pagato="props">
              <q-td :props="props">
                {{
                  props.row.importo_pagato > 0
                    ? formattaEuro(props.row.importo_pagato)
                    : '—'
                }}
              </q-td>
            </template>
            <template #body-cell-scadenza="props">
              <q-td :props="props">
                {{ props.row.scadenza ? formattaData(props.row.scadenza) : '—' }}
              </q-td>
            </template>
            <template #body-cell-stato="props">
              <q-td :props="props">
                <SemaforoBadge
                  :livello="livelloStato(props.row.stato, props.row.giorni_ritardo)"
                  :label="props.row.stato"
                />
              </q-td>
            </template>
            <template #body-cell-data_pagamento="props">
              <q-td :props="props">
                {{ props.row.data_pagamento ? formattaData(props.row.data_pagamento) : '—' }}
              </q-td>
            </template>
          </q-table>
          <EmptyState
            v-else-if="righePagamenti.length === 0"
            icon="inbox"
            title="Nessun pagamento"
            message="Per quest'anno non sono registrati pagamenti dovuti."
          />
          <EmptyState
            v-else
            icon="filter_alt_off"
            title="Nessuna riga con questo filtro"
            :message="`Nessun pagamento di tipo ${etichettaTipoFiltro.toLowerCase()} per quest'anno.`"
          />

          <div v-if="situazione.utility.righe.length" class="vp-p-id__sotto-sezione">
            <div class="vp-eyebrow">Dettaglio voci utenze</div>
            <q-list bordered separator class="vp-p-id__lista">
              <q-expansion-item
                v-for="r in situazione.utility.righe"
                :key="r.id"
                :label="`${formattaData(r.period_da)} → ${formattaData(r.period_a)}`"
                :caption="`${formattaEuro(r.importo_totale)} · ${r.stato}`"
              >
                <q-card flat class="vp-p-id__card">
                  <q-card-section>
                    <q-list dense>
                      <q-item v-for="(ln, idx) in r.lines" :key="idx">
                        <q-item-section>
                          <q-item-label>{{ etichettaVoce(ln.voce) }}</q-item-label>
                        </q-item-section>
                        <q-item-section side>
                          <q-item-label class="vp-mono">{{ formattaEuro(ln.importo) }}</q-item-label>
                        </q-item-section>
                      </q-item>
                    </q-list>
                  </q-card-section>
                </q-card>
              </q-expansion-item>
            </q-list>
          </div>
        </q-tab-panel>

        <!-- TAB PROFILO -->
        <q-tab-panel name="profilo" class="vp-p-id__panel">
          <div class="vp-p-id__griglia">
            <q-card flat bordered class="vp-p-id__card-info">
              <q-card-section>
                <div class="vp-eyebrow">Anagrafica</div>
                <q-list dense>
                  <q-item>
                    <q-item-section>
                      <q-item-label caption>Nominativo</q-item-label>
                      <q-item-label>{{ situazione.tenant.nominativo }}</q-item-label>
                    </q-item-section>
                  </q-item>
                  <q-item v-if="situazione.tenant.codice_fiscale">
                    <q-item-section>
                      <q-item-label caption>Codice fiscale</q-item-label>
                      <q-item-label class="vp-mono">{{ situazione.tenant.codice_fiscale }}</q-item-label>
                    </q-item-section>
                  </q-item>
                  <q-item v-if="situazione.tenant.email">
                    <q-item-section>
                      <q-item-label caption>Email</q-item-label>
                      <q-item-label>{{ situazione.tenant.email }}</q-item-label>
                    </q-item-section>
                  </q-item>
                  <q-item v-if="situazione.tenant.email_alt">
                    <q-item-section>
                      <q-item-label caption>Email alternativa</q-item-label>
                      <q-item-label>{{ situazione.tenant.email_alt }}</q-item-label>
                    </q-item-section>
                  </q-item>
                  <q-item v-if="situazione.tenant.telefono">
                    <q-item-section>
                      <q-item-label caption>Telefono</q-item-label>
                      <q-item-label>{{ situazione.tenant.telefono }}</q-item-label>
                    </q-item-section>
                  </q-item>
                  <q-item v-if="situazione.tenant.username">
                    <q-item-section>
                      <q-item-label caption>Username PWA</q-item-label>
                      <q-item-label class="vp-mono">{{ situazione.tenant.username }}</q-item-label>
                    </q-item-section>
                  </q-item>
                </q-list>
              </q-card-section>
            </q-card>

            <q-card flat bordered class="vp-p-id__card-info">
              <q-card-section>
                <div class="vp-eyebrow">Preferenze pagamento</div>
                <q-list dense>
                  <q-item v-if="situazione.tenant.giorno_pagamento_affitto">
                    <q-item-section>
                      <q-item-label caption>Giorno pagamento affitto</q-item-label>
                      <q-item-label>{{ situazione.tenant.giorno_pagamento_affitto }} del mese</q-item-label>
                    </q-item-section>
                  </q-item>
                  <q-item v-if="situazione.tenant.frequenza_conguagli_display">
                    <q-item-section>
                      <q-item-label caption>Frequenza utenze</q-item-label>
                      <q-item-label>{{ situazione.tenant.frequenza_conguagli_display }}</q-item-label>
                    </q-item-section>
                  </q-item>
                  <q-item v-if="situazione.tenant.note_pagamento">
                    <q-item-section>
                      <q-item-label caption>Note pagamento</q-item-label>
                      <q-item-label>{{ situazione.tenant.note_pagamento }}</q-item-label>
                    </q-item-section>
                  </q-item>
                </q-list>
              </q-card-section>
            </q-card>

            <q-card flat bordered class="vp-p-id__card-info">
              <q-card-section>
                <div class="vp-eyebrow">Convenzione contratto</div>
                <q-list dense v-if="situazione.contract">
                  <q-item v-if="situazione.contract.default_pagatore_bollette">
                    <q-item-section>
                      <q-item-label caption>Bollette luce/gas anticipate da</q-item-label>
                      <q-item-label>{{ situazione.contract.default_pagatore_bollette }}</q-item-label>
                    </q-item-section>
                  </q-item>
                </q-list>

                <div class="vp-eyebrow q-mt-md">Quota condominio</div>
                <template v-if="situazione.quota_condominio?.corrente">
                  <q-list dense>
                    <q-item>
                      <q-item-section>
                        <q-item-label caption>In vigore</q-item-label>
                        <q-item-label class="vp-mono">
                          {{ formattaEuro(situazione.quota_condominio.corrente.importo_mensile) }}/mese
                        </q-item-label>
                        <q-item-label caption>
                          dal {{ formattaData(situazione.quota_condominio.corrente.valid_from) }}
                          <template v-if="situazione.quota_condominio.corrente.valid_to">
                            al {{ formattaData(situazione.quota_condominio.corrente.valid_to) }}
                          </template>
                        </q-item-label>
                      </q-item-section>
                    </q-item>
                  </q-list>
                  <div
                    v-if="situazione.quota_condominio.storico.length > 1"
                    class="vp-eyebrow q-mt-md"
                  >
                    Storico
                  </div>
                  <q-list
                    v-if="situazione.quota_condominio.storico.length > 1"
                    separator
                    dense
                  >
                    <q-item
                      v-for="(q, i) in situazione.quota_condominio.storico"
                      :key="i"
                    >
                      <q-item-section>
                        <q-item-label class="vp-mono">
                          {{ formattaEuro(q.importo_mensile) }}/mese
                        </q-item-label>
                        <q-item-label caption>
                          {{ formattaData(q.valid_from) }} →
                          {{ q.valid_to ? formattaData(q.valid_to) : 'in corso' }}
                        </q-item-label>
                      </q-item-section>
                    </q-item>
                  </q-list>
                </template>
                <EmptyState
                  v-else
                  icon="domain"
                  title="Quota non definita"
                  message="Nessuna quota condominio configurata sul contratto attivo."
                />
              </q-card-section>
            </q-card>

            <q-card flat bordered class="vp-p-id__card-info">
              <q-card-section>
                <div class="vp-eyebrow">Deposito (caparra)</div>
                <q-list dense>
                  <q-item>
                    <q-item-section>
                      <q-item-label caption>Versato</q-item-label>
                      <q-item-label class="vp-mono">
                        {{ formattaEuro(Number(situazione.tenant.deposito_versato || 0)) }}
                      </q-item-label>
                      <q-item-label
                        v-if="situazione.tenant.data_versamento_deposito"
                        caption
                      >
                        il {{ formattaData(situazione.tenant.data_versamento_deposito) }}
                      </q-item-label>
                    </q-item-section>
                  </q-item>
                  <q-item v-if="situazione.tenant.deposito_restituito">
                    <q-item-section>
                      <q-item-label caption>Restituito</q-item-label>
                      <q-item-label class="vp-mono">
                        {{ formattaEuro(Number(situazione.tenant.deposito_restituito)) }}
                      </q-item-label>
                      <q-item-label
                        v-if="situazione.tenant.data_restituzione_deposito"
                        caption
                      >
                        il {{ formattaData(situazione.tenant.data_restituzione_deposito) }}
                      </q-item-label>
                    </q-item-section>
                  </q-item>
                </q-list>
              </q-card-section>
            </q-card>

            <q-card flat bordered class="vp-p-id__card-info vp-p-id__card-info--full">
              <q-card-section>
                <div class="vp-eyebrow">Stanze</div>
                <q-list separator dense>
                  <q-item v-for="a in situazione.assignments" :key="a.id">
                    <q-item-section>
                      <q-item-label>{{ a.room_nome }}</q-item-label>
                      <q-item-label caption>
                        {{ formattaData(a.valid_from) }} →
                        {{ a.valid_to ? formattaData(a.valid_to) : 'in corso' }}
                        · canone {{ formattaEuro(a.canone_mensile) }}
                        <span v-if="a.data_atto_cessione">
                          · cessione {{ formattaData(a.data_atto_cessione) }}
                        </span>
                      </q-item-label>
                    </q-item-section>
                  </q-item>
                </q-list>
                <EmptyState
                  v-if="!situazione.assignments.length"
                  icon="bedroom_parent"
                  title="Nessuna stanza assegnata"
                  message="Per ora non risulta nessun assignment registrato."
                />
              </q-card-section>
            </q-card>
          </div>
        </q-tab-panel>
      </q-tab-panels>
    </template>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import type { QTableProps } from 'quasar';
import { useTenantSituazioneStore } from 'stores/tenantSituazione';
import { useTenantsStore, type Tenant } from 'stores/tenants';
import KpiCard from 'src/components/KpiCard.vue';
import SemaforoBadge from 'src/components/SemaforoBadge.vue';
import type { SemaforoLivello } from 'src/types/semaforo';
import EmptyState from 'src/components/EmptyState.vue';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';

type TipoPagamento = 'rent' | 'utility' | 'extra';

interface RigaPagamento {
  rowKey: string;
  tipo: TipoPagamento;
  descrizione: string;
  importo_dovuto: number;
  importo_pagato: number;
  scadenza: string | null;
  stato: string;
  giorni_ritardo: number;
  data_pagamento: string | null;
}

const route = useRoute();
const router = useRouter();
const store = useTenantSituazioneStore();
const tenantsStore = useTenantsStore();
const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

const tenantId = computed(() => Number(route.params.id));

const annoCorrente = new Date().getFullYear();
const annoMin = annoCorrente - 5;

type FiltroTipo = TipoPagamento | 'all';

function parseAnno(v: unknown): number {
  const n = Number(Array.isArray(v) ? v[0] : v);
  if (Number.isFinite(n) && n >= annoMin && n <= annoCorrente) return n;
  return annoCorrente;
}
function parseTab(v: unknown): 'pagamenti' | 'profilo' {
  const s = Array.isArray(v) ? v[0] : v;
  return s === 'profilo' ? 'profilo' : 'pagamenti';
}
function parseTipo(v: unknown): FiltroTipo {
  const s = Array.isArray(v) ? v[0] : v;
  if (s === 'rent' || s === 'utility' || s === 'extra') return s;
  return 'all';
}

const annoSelezionato = ref<number>(parseAnno(route.query.anno));
const anniDisponibili = computed<number[]>(() => {
  const lista: number[] = [];
  for (let a = annoCorrente; a >= annoMin; a -= 1) lista.push(a);
  return lista;
});
const puoIndietro = computed(() => annoSelezionato.value > annoMin);
const puoAvanti = computed(() => annoSelezionato.value < annoCorrente);

const tabAttivo = ref<'pagamenti' | 'profilo'>(parseTab(route.query.tab));

const filtroTipo = ref<FiltroTipo>(parseTipo(route.query.tipo));
const opzioniTipo = [
  { label: 'Tutti', value: 'all' as const },
  { label: 'Affitto', value: 'rent' as const },
  { label: 'Utenze', value: 'utility' as const },
  { label: 'Extra', value: 'extra' as const },
];

const situazione = computed(() => store.get(tenantId.value, annoSelezionato.value));

const righePagamenti = computed<RigaPagamento[]>(() => {
  if (!situazione.value) return [];
  const out: RigaPagamento[] = [];
  for (const r of situazione.value.rent.righe) {
    const competenza = `${formattaData(r.competenza_da)} → ${formattaData(r.competenza_a)}`;
    out.push({
      rowKey: `rent-${r.id}`,
      tipo: 'rent',
      descrizione: r.is_aggiustamento ? `Affitto (aggiust.) ${competenza}` : `Affitto ${competenza}`,
      importo_dovuto: r.importo_dovuto,
      importo_pagato: r.importo_pagato,
      scadenza: r.scadenza,
      stato: r.stato,
      giorni_ritardo: r.giorni_ritardo,
      data_pagamento: r.data_pagamento,
    });
  }
  for (const c of situazione.value.utility.righe) {
    out.push({
      rowKey: `utility-${c.id}`,
      tipo: 'utility',
      descrizione: `Utenze ${formattaData(c.period_da)} → ${formattaData(c.period_a)}`,
      importo_dovuto: c.importo_totale,
      importo_pagato: c.importo_pagato,
      scadenza: c.scadenza,
      stato: c.stato,
      giorni_ritardo: c.scadenza ? giorniRitardo(c.scadenza) : 0,
      data_pagamento: c.data_pagamento,
    });
  }
  for (const e of situazione.value.extra.righe) {
    out.push({
      rowKey: `extra-${e.id}`,
      tipo: 'extra',
      descrizione: e.descrizione,
      importo_dovuto: e.importo,
      importo_pagato: 0,
      scadenza: e.scadenza,
      stato: e.stato,
      giorni_ritardo: e.scadenza ? giorniRitardo(e.scadenza) : 0,
      data_pagamento: null,
    });
  }
  out.sort((a, b) => (a.scadenza ?? '').localeCompare(b.scadenza ?? ''));
  return out;
});

const righePagamentiFiltrate = computed<RigaPagamento[]>(() =>
  filtroTipo.value === 'all'
    ? righePagamenti.value
    : righePagamenti.value.filter((r) => r.tipo === filtroTipo.value),
);

const etichettaTipoFiltro = computed(
  () => opzioniTipo.find((o) => o.value === filtroTipo.value)?.label ?? '',
);

function iconaTipoPer(t: FiltroTipo): string {
  if (t === 'all') return 'category';
  return ICONE_TIPO[t];
}

const colonnePagamenti: QTableProps['columns'] = [
  { name: 'tipo', label: 'Tipo', field: 'tipo', align: 'left', sortable: true },
  { name: 'descrizione', label: 'Descrizione', field: 'descrizione', align: 'left', sortable: true },
  { name: 'importo_dovuto', label: 'Dovuto', field: 'importo_dovuto', align: 'right', sortable: true },
  { name: 'importo_pagato', label: 'Pagato', field: 'importo_pagato', align: 'right', sortable: true },
  { name: 'scadenza', label: 'Scadenza', field: 'scadenza', align: 'left', sortable: true },
  { name: 'stato', label: 'Stato', field: 'stato', align: 'center' },
  { name: 'data_pagamento', label: 'Data pagamento', field: 'data_pagamento', align: 'left' },
];

const paginazionePagamenti = { rowsPerPage: 0, sortBy: 'scadenza' };

const listaInquiliniAnno = computed<Tenant[]>(() =>
  tenantsStore.tenantsAnno(annoSelezionato.value),
);
const indiceCorrente = computed<number>(() =>
  listaInquiliniAnno.value.findIndex((t) => t.id === tenantId.value),
);
const inquilinoPrecedente = computed<Tenant | null>(() => {
  const i = indiceCorrente.value;
  if (i <= 0) return null;
  return listaInquiliniAnno.value[i - 1] ?? null;
});
const inquilinoSuccessivo = computed<Tenant | null>(() => {
  const i = indiceCorrente.value;
  const lista = listaInquiliniAnno.value;
  if (i < 0 || i >= lista.length - 1) return null;
  return lista[i + 1] ?? null;
});
const posizioneInLista = computed<string>(() => {
  const i = indiceCorrente.value;
  if (i < 0) return '';
  return `${i + 1}/${listaInquiliniAnno.value.length}`;
});

const linkLista = computed(() => ({
  path: '/p/inquilini',
  query: { anno: String(annoSelezionato.value) },
}));

function aggiornaQuery(): void {
  const q: Record<string, string> = {
    anno: String(annoSelezionato.value),
    tab: tabAttivo.value,
  };
  if (filtroTipo.value !== 'all') q.tipo = filtroTipo.value;
  void router.replace({ query: q });
}

function vaiInquilino(t: Tenant | null): void {
  if (!t) return;
  const q: Record<string, string> = {
    anno: String(annoSelezionato.value),
    tab: tabAttivo.value,
  };
  if (filtroTipo.value !== 'all') q.tipo = filtroTipo.value;
  void router.push({
    name: 'p-inquilino-dettaglio',
    params: { id: t.id },
    query: q,
  });
}

function vaiInquilinoPrecedente(): void {
  vaiInquilino(inquilinoPrecedente.value);
}
function vaiInquilinoSuccessivo(): void {
  vaiInquilino(inquilinoSuccessivo.value);
}

onMounted(() => {
  void store.loadSituazione(tenantId.value, annoSelezionato.value);
  void tenantsStore.fetchTenantsAnno(annoSelezionato.value);
  aggiornaQuery();
});

watch(tenantId, (id) => {
  if (id) {
    void store.loadSituazione(id, annoSelezionato.value);
    aggiornaQuery();
  }
});

watch(tabAttivo, aggiornaQuery);
watch(filtroTipo, aggiornaQuery);

function onAnnoChange(v: number) {
  void store.loadSituazione(tenantId.value, v);
  void tenantsStore.fetchTenantsAnno(v);
  aggiornaQuery();
}
function annoPrecedente() {
  if (puoIndietro.value) {
    annoSelezionato.value -= 1;
    void store.loadSituazione(tenantId.value, annoSelezionato.value);
    void tenantsStore.fetchTenantsAnno(annoSelezionato.value);
    aggiornaQuery();
  }
}
function annoSuccessivo() {
  if (puoAvanti.value) {
    annoSelezionato.value += 1;
    void store.loadSituazione(tenantId.value, annoSelezionato.value);
    void tenantsStore.fetchTenantsAnno(annoSelezionato.value);
    aggiornaQuery();
  }
}

function giorniRitardo(scadenza: string): number {
  const oggi = new Date();
  oggi.setHours(0, 0, 0, 0);
  const s = new Date(scadenza);
  s.setHours(0, 0, 0, 0);
  return Math.round((oggi.getTime() - s.getTime()) / 86400000);
}

const ETICHETTE_VOCE: Record<string, string> = {
  luce: 'Luce',
  gas: 'Gas',
  tari: 'TARI',
  altro: 'Altro',
};
function etichettaVoce(v: string): string {
  return ETICHETTE_VOCE[v] ?? v;
}

const ETICHETTE_TIPO: Record<TipoPagamento, string> = {
  rent: 'Affitto',
  utility: 'Utenze',
  extra: 'Extra',
};
const ICONE_TIPO: Record<TipoPagamento, string> = {
  rent: 'home',
  utility: 'bolt',
  extra: 'receipt',
};
function etichettaPerTipo(t: TipoPagamento): string {
  return ETICHETTE_TIPO[t];
}
function iconaPerTipo(t: TipoPagamento): string {
  return ICONE_TIPO[t];
}

function livelloStato(stato: string, giorni_ritardo: number): SemaforoLivello {
  if (stato === 'pagato') return 'salvia';
  if (giorni_ritardo > 7) return 'argilla_scuro';
  if (giorni_ritardo > 0) return 'argilla_chiaro';
  if (giorni_ritardo > -7) return 'miele';
  return 'salvia';
}
</script>

<style scoped>
.vp-p-id__nav-inq {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-3);
  margin-bottom: var(--vp-gap-3);
  flex-wrap: wrap;
}
.vp-p-id__back {
  margin: 0;
}
.vp-p-id__nav-frecce {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-1);
}
.vp-p-id__nav-pos {
  font-size: var(--vp-text-sm);
  color: var(--vp-ink-3);
  min-width: 2.5rem;
  text-align: center;
  font-variant-numeric: tabular-nums;
}
.vp-p-id__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: var(--vp-gap-3);
  margin-bottom: var(--vp-gap-5);
}
.vp-p-id__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 var(--vp-gap-1);
}
.vp-p-id__contatti {
  color: var(--vp-ink-2);
  margin: 0;
}
.vp-p-id__nav-anno {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-2);
}
.vp-p-id__sel {
  min-width: 140px;
}
.vp-p-id__loader {
  display: flex;
  justify-content: center;
  padding: var(--vp-gap-7);
}
.vp-p-id__kpi {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--vp-gap-4);
  margin-bottom: var(--vp-gap-5);
}
.vp-p-id__kpi-card {
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
  padding: var(--vp-gap-5);
  box-shadow: var(--vp-shadow-1);
  display: flex;
  flex-direction: column;
  gap: var(--vp-gap-2);
}
.vp-p-id__kpi-card--accent {
  background: var(--vp-terra-soft);
  border-color: transparent;
}
.vp-p-id__kpi-head {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-1);
}
.vp-p-id__kpi-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--vp-ink-3);
}
.vp-p-id__kpi-info {
  cursor: help;
  color: var(--vp-ink-3);
}
.vp-p-id__kpi-info:hover,
.vp-p-id__kpi-info:focus {
  color: var(--vp-primary, var(--vp-ink));
  outline: none;
}
.vp-p-id__kpi-value {
  font-family: var(--vp-font-display);
  font-size: var(--vp-text-3xl);
  color: var(--vp-ink);
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}
.vp-p-id__popup {
  min-width: 280px;
  background: var(--vp-cream);
}
.vp-p-id__popup-nota {
  margin-top: var(--vp-gap-2);
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm);
}
.vp-p-id__tabs {
  border-bottom: 1px solid var(--vp-paper-3);
  margin-bottom: var(--vp-gap-3);
}
.vp-p-id__panels {
  background: transparent;
}
.vp-p-id__panel {
  padding: 0;
}
.vp-p-id__table,
.vp-p-id__lista {
  background: var(--vp-cream);
  border-color: var(--vp-paper-3) !important;
  border-radius: var(--vp-r-lg);
  overflow: hidden;
}
.vp-p-id__sotto-sezione {
  margin-top: var(--vp-gap-5);
}
.vp-p-id__tipo-icon {
  margin-right: var(--vp-gap-1);
  color: var(--vp-ink-3);
}
.vp-p-id__tipo-icon--clickable {
  cursor: pointer;
}
.vp-p-id__tipo-icon--clickable:hover {
  filter: brightness(0.9);
}
.vp-p-id__chip--c-rent {
  color: var(--vp-salvia, #4f6e3f);
}
.vp-p-id__chip--c-utility {
  color: var(--vp-miele, #b08a1f);
}
.vp-p-id__chip--c-extra {
  color: var(--vp-terra, #b56a3b);
}
.vp-p-id__causale-icon {
  flex-shrink: 0;
}
.vp-p-id__toolbar {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-2);
  margin-bottom: var(--vp-gap-2);
}
.vp-p-id__filtro-info {
  font-size: var(--vp-text-sm);
  color: var(--vp-ink-3);
}
.vp-p-id__card {
  background: var(--vp-paper-1);
}
.vp-p-id__griglia {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: var(--vp-gap-4);
}
.vp-p-id__card-info {
  background: var(--vp-cream);
  border-color: var(--vp-paper-3) !important;
}
.vp-p-id__card-info--full {
  grid-column: 1 / -1;
}
</style>
