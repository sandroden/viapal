<template>
  <q-page padding class="vp-i-sit">
    <header class="vp-i-sit__head">
      <div class="vp-i-sit__head-txt">
        <div class="vp-eyebrow">La tua situazione</div>
        <h1 class="vp-display vp-i-sit__titolo">
          {{ situazione?.tenant.nominativo ?? nominativoFallback }}
        </h1>
      </div>

      <div class="vp-i-sit__nav-anno">
        <q-btn
          flat
          round
          dense
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
          class="vp-i-sit__sel"
          @update:model-value="onAnnoChange"
        />
        <q-btn
          flat
          round
          dense
          icon="chevron_right"
          aria-label="Anno successivo"
          :disable="!puoAvanti"
          @click="annoSuccessivo"
        />
      </div>
    </header>

    <div v-if="store.loading && !situazione" class="vp-i-sit__loader">
      <q-spinner color="primary" size="32px" />
    </div>

    <EmptyState
      v-else-if="!tenantId && !store.loading"
      icon="error_outline"
      title="Profilo non disponibile"
      message="Non risulta un profilo inquilino collegato al tuo account. Contatta il proprietario."
    />

    <template v-else-if="situazione">
      <section class="vp-i-sit__kpi">
        <KpiCard
          label="Dovuto anno"
          :value="situazione.totali_anno.dovuto"
          is-currency
          accent
          info-tooltip="Composizione del dovuto"
        >
          <template #dettaglio>
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
              <q-item v-if="situazione.deposito && situazione.deposito.righe.length">
                <q-item-section>Deposito</q-item-section>
                <q-item-section side>
                  <span class="vp-mono">{{ formattaEuro(situazione.deposito.dovuto_anno) }}</span>
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
            <div class="vp-i-sit__nota">
              Comprende affitti, utenze (luce, gas, TARI) e addebiti extra
              (es. conguaglio condominiale). Il deposito è incluso solo dopo
              la restituzione.
            </div>
          </template>
        </KpiCard>

        <KpiCard label="Pagato anno" :value="situazione.totali_anno.pagato" is-currency />
        <KpiCard
          :label="`Saldo ${situazione.anno}`"
          :value="situazione.saldi.anno"
          is-currency
          :sublabel="situazione.saldi.anno >= 0 ? 'In regola' : 'Da saldare'"
        />
        <KpiCard
          label="Saldo totale"
          :value="situazione.saldi.totale"
          is-currency
          :sublabel="situazione.saldi.totale >= 0 ? 'In regola' : 'Da saldare'"
        />
        <!--
          Card "Ritardo medio" nascosta: dato poco significativo e spesso
          fuorviante (vedi nota in ProprietarioInquilinoDettaglio.vue e in
          dashboard_views.py). Riattivabile solo con ritardo misurato rispetto
          alla scadenza reale *dell'addebito*. Backend invariato.
        <KpiCard
          label="Ritardo medio"
          :value="`${situazione.ritardo_medio_giorni.toFixed(1)} gg`"
          :sublabel="situazione.ritardo_medio_giorni === 0 ? 'Mai in ritardo' : 'Su tutte le scadenze'"
        />
        -->
      </section>

      <q-tabs
        v-model="tabAttivo"
        dense
        no-caps
        align="left"
        class="vp-i-sit__tabs"
        active-color="primary"
        indicator-color="primary"
      >
        <q-tab name="pagamenti" label="Pagamenti" />
        <q-tab name="profilo" label="Profilo & contratto" />
      </q-tabs>

      <q-tab-panels v-model="tabAttivo" animated class="vp-i-sit__panels">
        <!-- PAGAMENTI -->
        <q-tab-panel name="pagamenti" class="vp-i-sit__panel">
          <div class="vp-i-sit__toolbar">
            <q-btn
              round
              dense
              flat
              size="sm"
              :icon="iconaTipoPer(filtroTipo)"
              :color="filtroTipo === 'all' ? 'grey-7' : 'primary'"
              :class="filtroTipo === 'all' ? '' : `vp-i-sit__chip--c-${filtroTipo}`"
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
                        :class="o.value === 'all' ? '' : `vp-i-sit__chip--c-${o.value}`"
                      />
                    </q-item-section>
                    <q-item-section>{{ o.label }}</q-item-section>
                  </q-item>
                </q-list>
              </q-menu>
            </q-btn>
            <span v-if="filtroTipo !== 'all'" class="vp-i-sit__filtro-info">
              {{ righeFiltrate.length }} di {{ righe.length }} righe
            </span>
          </div>

          <q-table
            v-if="righeFiltrate.length"
            flat
            bordered
            :rows="righeFiltrate"
            :columns="colonne"
            row-key="rowKey"
            :pagination="paginazione"
            :grid="$q.screen.lt.md"
            hide-pagination
            class="vp-i-sit__table"
          >
            <template #body-cell-tipo="props">
              <q-td :props="props">
                <q-icon
                  :name="iconaPerTipo(props.row.tipo)"
                  size="18px"
                  class="vp-i-sit__tipo-icon"
                  :class="`vp-i-sit__chip--c-${props.row.tipo}`"
                />
                {{ etichettaPerTipo(props.row.tipo) }}
              </q-td>
            </template>
            <template #body-cell-importo_dovuto="props">
              <q-td :props="props">{{ formattaEuro(props.row.importo_dovuto) }}</q-td>
            </template>
            <template #body-cell-importo_pagato="props">
              <q-td :props="props">
                {{ props.row.importo_pagato > 0 ? formattaEuro(props.row.importo_pagato) : '—' }}
              </q-td>
            </template>
            <template #body-cell-scadenza="props">
              <q-td :props="props">
                {{ props.row.scadenza ? formattaData(props.row.scadenza) : '—' }}
              </q-td>
            </template>
            <template #body-cell-stato="props">
              <q-td :props="props">
                <StatoPagamentoBadge
                  :importo-dovuto="props.row.importo_dovuto"
                  :importo-pagato="props.row.importo_pagato"
                  :stato="props.row.stato"
                  :giorni-ritardo="props.row.giorni_ritardo"
                />
              </q-td>
            </template>
            <template #body-cell-data_pagamento="props">
              <q-td :props="props">
                {{ props.row.data_pagamento ? formattaData(props.row.data_pagamento) : '—' }}
              </q-td>
            </template>

            <!-- Card layout su mobile -->
            <template #item="props">
              <div class="vp-i-sit__card-row">
                <q-card flat bordered class="vp-i-sit__pcard">
                  <q-card-section class="vp-i-sit__pcard-top">
                    <div class="vp-i-sit__pcard-tipo">
                      <q-icon
                        :name="iconaPerTipo(props.row.tipo)"
                        size="18px"
                        :class="`vp-i-sit__chip--c-${props.row.tipo}`"
                      />
                      <span>{{ props.row.descrizione }}</span>
                    </div>
                    <StatoPagamentoBadge
                      :importo-dovuto="props.row.importo_dovuto"
                      :importo-pagato="props.row.importo_pagato"
                      :stato="props.row.stato"
                      :giorni-ritardo="props.row.giorni_ritardo"
                    />
                  </q-card-section>
                  <q-separator />
                  <q-card-section class="vp-i-sit__pcard-grid">
                    <div>
                      <div class="vp-i-sit__pcard-lbl">Dovuto</div>
                      <div class="vp-mono">{{ formattaEuro(props.row.importo_dovuto) }}</div>
                    </div>
                    <div>
                      <div class="vp-i-sit__pcard-lbl">Pagato</div>
                      <div class="vp-mono">
                        {{ props.row.importo_pagato > 0 ? formattaEuro(props.row.importo_pagato) : '—' }}
                      </div>
                    </div>
                    <div>
                      <div class="vp-i-sit__pcard-lbl">Scadenza</div>
                      <div>{{ props.row.scadenza ? formattaData(props.row.scadenza) : '—' }}</div>
                    </div>
                    <div>
                      <div class="vp-i-sit__pcard-lbl">Pagato il</div>
                      <div>
                        {{ props.row.data_pagamento ? formattaData(props.row.data_pagamento) : '—' }}
                      </div>
                    </div>
                  </q-card-section>
                </q-card>
              </div>
            </template>
          </q-table>

          <EmptyState
            v-else-if="righe.length === 0"
            icon="inbox"
            title="Nessun pagamento"
            message="Per quest'anno non risultano pagamenti dovuti."
          />
          <EmptyState
            v-else
            icon="filter_alt_off"
            title="Nessuna riga con questo filtro"
            :message="`Nessun pagamento di tipo ${etichettaTipoFiltro.toLowerCase()} per quest'anno.`"
          />

          <div v-if="situazione.utility.righe.length" class="vp-i-sit__sotto">
            <div class="vp-eyebrow">Dettaglio voci utenze</div>
            <q-list bordered separator class="vp-i-sit__lista">
              <q-expansion-item
                v-for="r in situazione.utility.righe"
                :key="r.id"
                :label="`${formattaData(r.period_da)} → ${formattaData(r.period_a)}`"
                :caption="`${formattaEuro(r.importo_totale)} · ${r.stato}`"
              >
                <q-card flat class="vp-i-sit__card-inner">
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

        <!-- PROFILO -->
        <q-tab-panel name="profilo" class="vp-i-sit__panel">
          <div class="vp-i-sit__griglia">
            <q-card flat bordered class="vp-i-sit__card-info">
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
                  <q-item v-if="situazione.tenant.telefono">
                    <q-item-section>
                      <q-item-label caption>Telefono</q-item-label>
                      <q-item-label>{{ situazione.tenant.telefono }}</q-item-label>
                    </q-item-section>
                  </q-item>
                </q-list>
              </q-card-section>
            </q-card>

            <q-card flat bordered class="vp-i-sit__card-info">
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

            <q-card flat bordered class="vp-i-sit__card-info">
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

            <q-card flat bordered class="vp-i-sit__card-info">
              <q-card-section>
                <div class="vp-eyebrow">Deposito</div>
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
                  <q-item v-if="situazione.tenant.data_restituzione_prevista">
                    <q-item-section>
                      <q-item-label caption>
                        {{ restituzioneEffettuata ? 'Restituito' : 'Restituzione dovuta' }}
                      </q-item-label>
                      <q-item-label class="vp-mono">
                        {{ formattaEuro(importoDaRestituire) }}
                      </q-item-label>
                      <q-item-label caption>
                        {{ restituzioneEffettuata ? 'il' : 'dovuta il' }}
                        {{ formattaData(situazione.tenant.data_restituzione_prevista) }}
                      </q-item-label>
                    </q-item-section>
                  </q-item>
                </q-list>

                <template v-if="simulazioneUscita">
                  <q-separator spaced />
                  <div class="vp-eyebrow">
                    {{ simulazioneUscita.giaRestituito ? 'Chiusura deposito' : 'Simulazione uscita' }}
                  </div>
                  <q-list dense>
                    <q-item>
                      <q-item-section>Deposito versato</q-item-section>
                      <q-item-section side>
                        <span class="vp-mono">{{ formattaEuro(simulazioneUscita.versato) }}</span>
                      </q-item-section>
                    </q-item>
                    <q-item v-if="simulazioneUscita.daRestituire !== simulazioneUscita.versato">
                      <q-item-section>
                        Importo da rendere
                        <q-item-label caption>override su versato</q-item-label>
                      </q-item-section>
                      <q-item-section side>
                        <span class="vp-mono">{{ formattaEuro(simulazioneUscita.daRestituire) }}</span>
                      </q-item-section>
                    </q-item>
                    <q-item>
                      <q-item-section>
                        Saldo totale corrente
                        <q-item-label caption>
                          {{ simulazioneUscita.saldo >= 0 ? 'a tuo favore' : 'a tuo debito' }}
                        </q-item-label>
                      </q-item-section>
                      <q-item-section side>
                        <span class="vp-mono">{{ formattaEuro(simulazioneUscita.saldo) }}</span>
                      </q-item-section>
                    </q-item>
                    <q-separator spaced />
                    <q-item>
                      <q-item-section>
                        <strong>
                          {{ simulazioneUscita.giaRestituito ? 'Deposito già restituito' : 'Netto da restituire' }}
                        </strong>
                      </q-item-section>
                      <q-item-section side>
                        <strong class="vp-mono vp-i-sit__sim-netto">
                          {{ formattaEuro(simulazioneUscita.netto) }}
                        </strong>
                      </q-item-section>
                    </q-item>
                    <q-item v-if="simulazioneUscita.residuoDebito > 0">
                      <q-item-section class="vp-i-sit__sim-warn">
                        Il deposito non copre il debito: resterebbe a tuo carico
                        un residuo di
                        {{ formattaEuro(simulazioneUscita.residuoDebito) }}.
                      </q-item-section>
                    </q-item>
                  </q-list>
                  <div class="vp-i-sit__nota">
                    {{
                      simulazioneUscita.giaRestituito
                        ? 'Il deposito è stato restituito: nulla da trattenere. Il saldo residuo resta da regolare a parte.'
                        : 'Stima alla data odierna: deposito versato al netto del saldo totale cumulativo (affitti, utenze, extra). Non include addebiti di fine locazione non ancora registrati.'
                    }}
                  </div>
                </template>
              </q-card-section>
            </q-card>

            <q-card flat bordered class="vp-i-sit__card-info vp-i-sit__card-info--full">
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
import { useDashboardStore } from 'stores/dashboard';
import { useAuthStore } from 'stores/auth';
import KpiCard from 'src/components/KpiCard.vue';
import StatoPagamentoBadge from 'src/components/StatoPagamentoBadge.vue';
import EmptyState from 'src/components/EmptyState.vue';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';

type TipoPagamento = 'rent' | 'utility' | 'extra' | 'deposito';
type FiltroTipo = TipoPagamento | 'all';

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
const dashboard = useDashboardStore();
const auth = useAuthStore();
const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

const nominativoFallback = computed(
  () =>
    [auth.user?.first_name, auth.user?.last_name].filter(Boolean).join(' ') ||
    auth.user?.username ||
    'La tua situazione',
);

// Il tenant_id dell'inquilino loggato arriva dalla dashboard inquilino.
const tenantId = computed<number | null>(
  () => dashboard.inquilinoData?.tenant.id ?? null,
);

const annoCorrente = new Date().getFullYear();
const annoMin = annoCorrente - 5;

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
  if (s === 'rent' || s === 'utility' || s === 'extra' || s === 'deposito') return s;
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
  { label: 'Deposito', value: 'deposito' as const },
];

const situazione = computed(() =>
  tenantId.value ? store.get(tenantId.value, annoSelezionato.value) : null,
);

const rigaRestituzione = computed(() => {
  const r = situazione.value?.deposito?.righe ?? [];
  return r.find((x) => x.importo < 0) ?? null;
});
const restituzioneEffettuata = computed(
  () => rigaRestituzione.value?.stato === 'pagato',
);
const importoDaRestituire = computed(() => {
  const t = situazione.value?.tenant;
  if (!t) return 0;
  const override = Number(t.deposito_da_restituire || 0);
  if (override > 0) return override;
  return Number(t.deposito_versato || 0);
});
const simulazioneUscita = computed(() => {
  const s = situazione.value;
  if (!s) return null;
  const versato = Number(s.tenant.deposito_versato || 0);
  const daRestituire = importoDaRestituire.value;
  if (versato <= 0 && daRestituire <= 0) return null;
  const saldo = s.saldi.totale;
  const restituito = restituzioneEffettuata.value;
  const netto = restituito ? 0 : daRestituire + saldo;
  return {
    versato,
    daRestituire,
    saldo,
    netto: Math.max(netto, 0),
    residuoDebito: !restituito && netto < 0 ? -netto : 0,
    giaRestituito: restituito,
  };
});

const righe = computed<RigaPagamento[]>(() => {
  const s = situazione.value;
  if (!s) return [];
  const out: RigaPagamento[] = [];
  for (const r of s.rent.righe) {
    const comp = `${formattaData(r.competenza_da)} → ${formattaData(r.competenza_a)}`;
    out.push({
      rowKey: `rent-${r.id}`,
      tipo: 'rent',
      descrizione: r.is_aggiustamento ? `Affitto (aggiust.) ${comp}` : `Affitto ${comp}`,
      importo_dovuto: r.importo_dovuto,
      importo_pagato: r.importo_pagato,
      scadenza: r.scadenza,
      stato: r.stato,
      giorni_ritardo: r.giorni_ritardo,
      data_pagamento: r.data_pagamento,
    });
  }
  for (const c of s.utility.righe) {
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
  for (const e of s.extra.righe) {
    out.push({
      rowKey: `extra-${e.id}`,
      tipo: 'extra',
      descrizione: e.descrizione,
      importo_dovuto: e.importo,
      importo_pagato: e.importo_pagato ?? 0,
      scadenza: e.scadenza,
      stato: e.stato,
      giorni_ritardo: e.scadenza ? giorniRitardo(e.scadenza) : 0,
      data_pagamento: e.data_pagamento,
    });
  }
  for (const d of s.deposito?.righe ?? []) {
    out.push({
      rowKey: `deposito-${d.id}`,
      tipo: 'deposito',
      descrizione: d.descrizione,
      importo_dovuto: d.importo,
      importo_pagato: d.importo_pagato ?? 0,
      scadenza: d.scadenza,
      stato: d.stato,
      giorni_ritardo: d.scadenza ? giorniRitardo(d.scadenza) : 0,
      data_pagamento: d.data_pagamento,
    });
  }
  out.sort((a, b) => (a.scadenza ?? '').localeCompare(b.scadenza ?? ''));
  return out;
});

const righeFiltrate = computed<RigaPagamento[]>(() =>
  filtroTipo.value === 'all'
    ? righe.value
    : righe.value.filter((r) => r.tipo === filtroTipo.value),
);

const etichettaTipoFiltro = computed(
  () => opzioniTipo.find((o) => o.value === filtroTipo.value)?.label ?? '',
);

const colonne: QTableProps['columns'] = [
  { name: 'tipo', label: 'Tipo', field: 'tipo', align: 'left', sortable: true },
  { name: 'descrizione', label: 'Descrizione', field: 'descrizione', align: 'left', sortable: true },
  { name: 'importo_dovuto', label: 'Dovuto', field: 'importo_dovuto', align: 'right', sortable: true },
  { name: 'importo_pagato', label: 'Pagato', field: 'importo_pagato', align: 'right', sortable: true },
  { name: 'scadenza', label: 'Scadenza', field: 'scadenza', align: 'left', sortable: true },
  { name: 'stato', label: 'Stato', field: 'stato', align: 'center' },
  { name: 'data_pagamento', label: 'Data pagamento', field: 'data_pagamento', align: 'left' },
];
const paginazione = { rowsPerPage: 0, sortBy: 'scadenza' };

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
  deposito: 'Deposito',
};
const ICONE_TIPO: Record<TipoPagamento, string> = {
  rent: 'home',
  utility: 'bolt',
  extra: 'receipt',
  deposito: 'savings',
};
function etichettaPerTipo(t: TipoPagamento): string {
  return ETICHETTE_TIPO[t];
}
function iconaPerTipo(t: TipoPagamento): string {
  return ICONE_TIPO[t];
}
function iconaTipoPer(t: FiltroTipo): string {
  if (t === 'all') return 'category';
  return ICONE_TIPO[t];
}

function giorniRitardo(scadenza: string): number {
  const oggi = new Date();
  oggi.setHours(0, 0, 0, 0);
  const s = new Date(scadenza);
  s.setHours(0, 0, 0, 0);
  return Math.round((oggi.getTime() - s.getTime()) / 86400000);
}

function aggiornaQuery(): void {
  const q: Record<string, string> = {
    anno: String(annoSelezionato.value),
    tab: tabAttivo.value,
  };
  if (filtroTipo.value !== 'all') q.tipo = filtroTipo.value;
  void router.replace({ query: q });
}

function caricaSituazione(force = false): void {
  if (tenantId.value) {
    void store.loadSituazione(tenantId.value, annoSelezionato.value, force);
  }
}

onMounted(async () => {
  await dashboard.loadInquilino();
  caricaSituazione();
  aggiornaQuery();
});

watch(tenantId, (id) => {
  if (id) caricaSituazione();
});
watch(tabAttivo, aggiornaQuery);
watch(filtroTipo, aggiornaQuery);

function onAnnoChange(v: number) {
  annoSelezionato.value = v;
  caricaSituazione();
  aggiornaQuery();
}
function annoPrecedente() {
  if (puoIndietro.value) {
    annoSelezionato.value -= 1;
    caricaSituazione();
    aggiornaQuery();
  }
}
function annoSuccessivo() {
  if (puoAvanti.value) {
    annoSelezionato.value += 1;
    caricaSituazione();
    aggiornaQuery();
  }
}
</script>

<style scoped>
.vp-i-sit {
  background: var(--vp-paper);
  min-height: 100%;
}
.vp-i-sit__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: var(--vp-gap-3);
  margin-bottom: var(--vp-gap-4);
}
.vp-i-sit__head-txt {
  min-width: 0;
}
.vp-i-sit__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 0;
  color: var(--vp-ink);
}
.vp-i-sit__nav-anno {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-1);
}
.vp-i-sit__sel {
  min-width: 110px;
}
.vp-i-sit__loader {
  display: flex;
  justify-content: center;
  padding: var(--vp-gap-7);
}
.vp-i-sit__kpi {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--vp-gap-3);
  margin-bottom: var(--vp-gap-5);
}
.vp-i-sit__nota {
  margin-top: var(--vp-gap-2);
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm);
}
.vp-i-sit__tabs {
  border-bottom: 1px solid var(--vp-paper-3);
  margin-bottom: var(--vp-gap-3);
}
.vp-i-sit__panels {
  background: transparent;
}
.vp-i-sit__panel {
  padding: 0;
}
.vp-i-sit__toolbar {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-2);
  margin-bottom: var(--vp-gap-2);
}
.vp-i-sit__filtro-info {
  font-size: var(--vp-text-sm);
  color: var(--vp-ink-3);
}
.vp-i-sit__table,
.vp-i-sit__lista {
  background: var(--vp-cream);
  border-color: var(--vp-paper-3) !important;
  border-radius: var(--vp-r-lg);
  overflow: hidden;
}
.vp-i-sit__tipo-icon {
  margin-right: var(--vp-gap-1);
}
.vp-i-sit__chip--c-rent {
  color: var(--vp-salvia, #4f6e3f);
}
.vp-i-sit__chip--c-utility {
  color: var(--vp-miele, #b08a1f);
}
.vp-i-sit__chip--c-extra {
  color: var(--vp-terra, #b56a3b);
}
.vp-i-sit__chip--c-deposito {
  color: var(--vp-ink-2, #5b6470);
}
.vp-i-sit__sotto {
  margin-top: var(--vp-gap-5);
}
.vp-i-sit__card-inner {
  background: var(--vp-paper-1);
}
.vp-i-sit__griglia {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--vp-gap-3);
}
.vp-i-sit__card-info {
  background: var(--vp-cream);
  border-color: var(--vp-paper-3) !important;
}
.vp-i-sit__card-info--full {
  grid-column: 1 / -1;
}
.vp-i-sit__sim-netto {
  font-size: var(--vp-text-lg);
}
.vp-i-sit__sim-warn {
  color: var(--vp-terra, #b56a3b);
  font-size: var(--vp-text-sm);
}
/* Card layout (q-table grid mode su mobile) */
.vp-i-sit__card-row {
  width: 100%;
  padding: 4px 0;
}
.vp-i-sit__pcard {
  background: var(--vp-cream);
  border-color: var(--vp-paper-3) !important;
  border-radius: var(--vp-r-lg);
}
.vp-i-sit__pcard-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--vp-gap-2);
  padding-bottom: var(--vp-gap-2);
}
.vp-i-sit__pcard-tipo {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
  font-size: var(--vp-text-sm);
}
.vp-i-sit__pcard-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--vp-gap-2) var(--vp-gap-4);
}
.vp-i-sit__pcard-lbl {
  font-size: 10px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--vp-ink-3);
}
</style>
