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
      <q-btn
        flat
        round
        dense
        icon="theater_comedy"
        color="primary"
        :loading="impersonando"
        aria-label="Vedi come questo inquilino"
        class="vp-p-id__impersona"
        @click="vediComeInquilino"
      >
        <q-tooltip>Vedi come {{ situazione?.tenant.nominativo ?? 'inquilino' }}</q-tooltip>
      </q-btn>
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
                    <div class="vp-p-id__popup-nota">
                      Comprende affitti, utenze (luce, gas, TARI) e addebiti extra
                      (es. conguaglio condominiale). Il deposito è incluso
                      solo dopo la restituzione.
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
          :label="`Saldo ${situazione.anno}`"
          :value="situazione.saldi.anno"
          is-currency
          :sublabel="situazione.saldi.anno >= 0 ? 'In regola' : 'Da incassare'"
        />
        <KpiCard
          label="Saldo totale"
          :value="situazione.saldi.totale"
          is-currency
          :sublabel="situazione.saldi.totale >= 0 ? 'In regola' : 'Da incassare'"
        />
        <!--
          Card "Ritardo medio" nascosta: il dato è poco significativo e spesso
          fuorviante in questa realtà. La media backend considera solo i ritardi
          positivi (gli anticipi non la compensano), e `data_pagamento` =
          Max(data BT allocata): un residuo di matching o le scadenze utenze
          troppo strette generano ritardi fittizi. Riattivabile in futuro solo
          se il ritardo è misurato rispetto alla scadenza reale *dell'addebito*
          (prima di quella data è anticipo, non ritardo). Backend invariato.
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
        class="vp-p-id__tabs"
        active-color="primary"
        indicator-color="primary"
      >
        <q-tab name="pagamenti" label="Pagamenti" />
        <q-tab name="profilo" label="Profilo & contratto" />
        <q-route-tab
          name="rendiconto"
          label="Rendiconto"
          icon="description"
          inline-label
          :to="{
            name: 'p-inquilino-rendiconto',
            params: { id: tenantId },
          }"
        />
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
                  props.row.importo_pagato
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
                <span class="vp-p-id__stato-wrap">
                  <span
                    v-if="props.row.stato !== 'pagato'"
                    class="vp-p-id__stato-click"
                    @click="aprireRegistraPagamento(props.row)"
                  >
                    <StatoPagamentoBadge
                      :importo-dovuto="props.row.importo_dovuto"
                      :importo-pagato="props.row.importo_pagato"
                      :stato="props.row.stato"
                      :giorni-ritardo="props.row.giorni_ritardo"
                    />
                    <q-icon name="payments" size="14px" class="vp-p-id__stato-icon" />
                    <q-tooltip>Registra pagamento</q-tooltip>
                  </span>
                  <StatoPagamentoBadge
                    v-else
                    :importo-dovuto="props.row.importo_dovuto"
                    :importo-pagato="props.row.importo_pagato"
                    :stato="props.row.stato"
                    :giorni-ritardo="props.row.giorni_ritardo"
                  />
                  <q-icon
                    name="swap_horiz"
                    size="14px"
                    class="vp-p-id__stato-icon vp-p-id__stato-icon--link"
                    @click.stop="vaiARiconciliazione"
                  >
                    <q-tooltip>Apri riconciliazione (tenant + anno pre-filtrati)</q-tooltip>
                  </q-icon>
                </span>
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
                        <template v-if="!situazione.tenant.deposito_da_restituire">
                          · pari al versato
                        </template>
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
                    <q-item
                      v-if="simulazioneUscita.daRestituire !== simulazioneUscita.versato"
                    >
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
                          {{ simulazioneUscita.saldo >= 0 ? 'a favore inquilino' : 'a debito inquilino' }}
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
                        <strong class="vp-mono vp-p-id__sim-netto">
                          {{ formattaEuro(simulazioneUscita.netto) }}
                        </strong>
                      </q-item-section>
                    </q-item>
                    <q-item v-if="simulazioneUscita.residuoDebito > 0">
                      <q-item-section class="vp-p-id__sim-warn">
                        Il deposito non copre il debito: resta a carico
                        dell'inquilino un residuo di
                        {{ formattaEuro(simulazioneUscita.residuoDebito) }}.
                      </q-item-section>
                    </q-item>
                  </q-list>
                  <div class="vp-p-id__popup-nota">
                    {{
                      simulazioneUscita.giaRestituito
                        ? 'Il deposito è stato restituito: nulla da trattenere. Il saldo residuo resta da incassare a parte.'
                        : 'Stima alla data odierna: deposito versato al netto del saldo totale cumulativo (affitti, utenze, extra). Non include addebiti di fine locazione non ancora registrati.'
                    }}
                  </div>
                </template>

                <q-btn
                  v-if="puoCrearePrevisionale"
                  flat
                  dense
                  no-caps
                  size="sm"
                  color="primary"
                  icon="bolt"
                  label="Crea addebito previsionale utenze"
                  class="vp-p-id__rendiconto-btn"
                  @click="dialogPrevisionale = true"
                />
                <q-btn
                  v-if="previsionaleApertoId"
                  flat
                  dense
                  no-caps
                  size="sm"
                  color="primary"
                  icon="balance"
                  label="Conguaglia previsionale con utenze reali"
                  class="vp-p-id__rendiconto-btn"
                  @click="dialogConguaglio = true"
                />
                <q-btn
                  flat
                  dense
                  no-caps
                  size="sm"
                  color="primary"
                  icon="description"
                  label="Rendiconto stampabile"
                  class="vp-p-id__rendiconto-btn"
                  :to="{
                    name: 'p-inquilino-rendiconto',
                    params: { id: tenantId },
                  }"
                />
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
                    <q-item-section v-if="puoModificare && a.valid_to === null" side>
                      <q-btn
                        flat
                        dense
                        no-caps
                        size="sm"
                        color="primary"
                        icon="swap_horiz"
                        label="Cessione…"
                        data-testid="apri-cessione"
                        @click="apriDialogCessione(a)"
                      />
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

    <RegistraPagamentoDialog
      v-if="receivableSelezionato"
      v-model="dialogPagamento"
      :receivable="receivableSelezionato"
      :owner-accounts="contiUtente"
      :default-owner-account-id="contoDiDefaultUtente"
      @saved="dopoSalvataggioPagamento"
    />

    <PrevisionaleUtenzeDialog
      v-if="assignmentAttivoId"
      v-model="dialogPrevisionale"
      :tenant-id="tenantId"
      :assignment-id="assignmentAttivoId"
      :data-target="dataTargetPrevisionale"
      @saved="dopoSalvataggioPagamento"
    />

    <ConguagliaPrevisionaleDialog
      v-if="previsionaleApertoId"
      v-model="dialogConguaglio"
      :tenant-id="tenantId"
      :previsionale-id="previsionaleApertoId"
      @saved="dopoSalvataggioPagamento"
    />

    <!-- Dialog cessione stanza -->
    <q-dialog v-model="dialogCessione">
      <q-card style="min-width: 440px">
        <q-card-section>
          <div class="vp-p-id__dialog-titolo">
            Cessione {{ assignmentCessione?.room_nome ?? 'stanza' }}
          </div>
          <div class="vp-p-id__popup-nota">
            Chiude l'assegnazione corrente alla data indicata e apre dal giorno
            dopo una nuova assegnazione per il nuovo inquilino.
          </div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input
            v-model="formCessione.data_fine"
            label="Data fine occupazione"
            type="date"
            outlined
            dense
            data-testid="cessione-data-fine"
          />
          <q-select
            v-model="formCessione.nuovo_tenant"
            :options="opzioniNuovoTenant"
            label="Nuovo inquilino"
            outlined
            dense
            emit-value
            map-options
            :loading="loadingCandidati"
            data-testid="cessione-nuovo-tenant"
          />
          <q-input
            v-model="formCessione.canone_mensile"
            label="Canone mensile"
            type="number"
            min="0"
            step="0.01"
            suffix="€"
            outlined
            dense
            data-testid="cessione-canone"
          />
          <q-input
            v-model="formCessione.costo_cessione"
            label="Costo cessione (facoltativo)"
            type="number"
            min="0"
            step="0.01"
            suffix="€"
            outlined
            dense
            clearable
          />
          <q-input
            v-model="formCessione.data_atto_cessione"
            label="Data atto di cessione (facoltativa)"
            type="date"
            outlined
            dense
            clearable
          />
          <q-banner v-if="erroreCessione" class="vp-p-id__banner-errore" rounded dense>
            {{ erroreCessione }}
          </q-banner>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn v-close-popup flat label="Annulla" />
          <q-btn
            color="primary"
            label="Esegui cessione"
            :loading="salvandoCessione"
            data-testid="cessione-esegui"
            @click="eseguiCessione"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { isAxiosError } from 'axios';
import { useQuasar, type QTableProps } from 'quasar';
import { api } from 'boot/axios';
import {
  useTenantSituazioneStore,
  type AssignmentRiga,
} from 'stores/tenantSituazione';
import { useTenantsStore, type Tenant } from 'stores/tenants';
import { useAuthStore } from 'stores/auth';
import { usePropertiesStore } from 'stores/properties';
import { useOwnerBankAccountsStore } from 'stores/ownerBankAccounts';
import KpiCard from 'src/components/KpiCard.vue';
import StatoPagamentoBadge from 'src/components/StatoPagamentoBadge.vue';
import EmptyState from 'src/components/EmptyState.vue';
import RegistraPagamentoDialog from 'src/components/RegistraPagamentoDialog.vue';
import PrevisionaleUtenzeDialog from 'src/components/PrevisionaleUtenzeDialog.vue';
import ConguagliaPrevisionaleDialog from 'src/components/ConguagliaPrevisionaleDialog.vue';

type CausaleReceivable = 'affitto' | 'utenze' | 'extra' | 'deposito';

interface ReceivableInput {
  id: number;
  causale: CausaleReceivable;
  importo_dovuto: number;
  importo_pagato: number;
  descrizione: string;
  tenant_nominativo: string;
  scadenza: string;
  bank_account_destinazione_id: number | null;
}
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';

type TipoPagamento = 'rent' | 'utility' | 'extra' | 'deposito';

const TIPO_TO_CAUSALE: Record<TipoPagamento, CausaleReceivable> = {
  rent: 'affitto',
  utility: 'utenze',
  extra: 'extra',
  deposito: 'deposito',
};

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
  receivable_id: number;
  bank_account_destinazione_id: number | null;
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

const situazione = computed(() => store.get(tenantId.value, annoSelezionato.value));

// Riga Receivable di restituzione deposito (importo negativo). Esposta dal
// backend solo quando data_restituzione_prevista è valorizzata.
const rigaRestituzione = computed(() => {
  const righe = situazione.value?.deposito?.righe ?? [];
  return righe.find((r) => r.importo < 0) ?? null;
});
// "Effettuata" = il Receivable di restituzione risulta pagato. Altrimenti
// la data_restituzione è solo la scadenza in cui la restituzione è DOVUTA.
const restituzioneEffettuata = computed(
  () => rigaRestituzione.value?.stato === 'pagato',
);

// Importo lordo da rendere all'uscita: override esplicito se valorizzato,
// altrimenti pari al deposito versato (allineato alla logica del backend).
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
  const saldo = s.saldi.totale; // < 0 = inquilino a debito
  // Se il deposito è già stato effettivamente restituito non c'è più nulla
  // da trattenere: il netto da restituire si azzera.
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
      receivable_id: r.id,
      bank_account_destinazione_id: r.bank_account_destinazione_id,
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
      receivable_id: c.id,
      bank_account_destinazione_id: c.bank_account_destinazione_id,
    });
  }
  for (const e of situazione.value.extra.righe) {
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
      receivable_id: e.id,
      bank_account_destinazione_id: e.bank_account_destinazione_id,
    });
  }
  for (const c of situazione.value.deposito?.righe ?? []) {
    out.push({
      rowKey: `deposito-${c.id}`,
      tipo: 'deposito',
      descrizione: c.descrizione,
      importo_dovuto: c.importo,
      importo_pagato: c.importo_pagato ?? 0,
      scadenza: c.scadenza,
      stato: c.stato,
      giorni_ritardo: c.scadenza ? giorniRitardo(c.scadenza) : 0,
      data_pagamento: c.data_pagamento,
      receivable_id: c.id,
      bank_account_destinazione_id: c.bank_account_destinazione_id,
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
  // force=true così, rientrando in pagina dopo aver modificato
  // riconciliazioni/pagamenti altrove, vediamo subito lo stato aggiornato.
  void store.loadSituazione(tenantId.value, annoSelezionato.value, true);
  void tenantsStore.fetchTenantsAnno(annoSelezionato.value);
  void contiStore.ensureLoaded();
  aggiornaQuery();
});

function vaiARiconciliazione(): void {
  void router.push({
    path: '/p/riconciliazione',
    query: {
      tenant: String(tenantId.value),
      anno: String(annoSelezionato.value),
      riconciliato: 'all',
    },
  });
}

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

// --- Registra pagamento (modale su righe in stato atteso) -----------------

const auth = useAuthStore();
const $q = useQuasar();
const contiStore = useOwnerBankAccountsStore();

// --- Impersonation ("vedi come inquilino") --------------------------------
const impersonando = ref(false);
async function vediComeInquilino() {
  impersonando.value = true;
  try {
    // impersonate() fa hard reload verso /i/.
    await auth.impersonate(tenantId.value);
  } catch {
    $q.notify({ type: 'negative', message: 'Impossibile impersonare questo inquilino.' });
    impersonando.value = false;
  }
}
const tenantCorrente = computed(() => situazione.value?.tenant ?? null);

const dialogPagamento = ref(false);
const receivableSelezionato = ref<ReceivableInput | null>(null);

const dialogPrevisionale = ref(false);
const dialogConguaglio = ref(false);
// Giorni prima della fine occupazione in cui ha senso preparare i conti
// (previsionale) anche se la restituzione del deposito non è ancora stata
// fissata. Allineato alla finestra "in scadenza" del backend.
const FINESTRA_PREVISIONALE_GIORNI = 14;
// Assignment più recente: l'ordinamento backend è -valid_from, quindi il
// primo è quello da cui dedurre fine occupazione e data target.
const assignmentRecente = computed<AssignmentRiga | null>(
  () => situazione.value?.assignments?.[0] ?? null,
);
const assignmentAttivoId = computed<number | null>(
  () => assignmentRecente.value?.id ?? null,
);
// True quando oggi è entro le ultime due settimane prima della fine
// occupazione (o oltre): finestra in cui preparare il previsionale.
const inFinestraUscita = computed(() => {
  const vt = assignmentRecente.value?.valid_to;
  if (!vt) return false;
  const fine = new Date(`${vt}T00:00:00`).getTime();
  const oggi = new Date();
  oggi.setHours(0, 0, 0, 0);
  return oggi.getTime() >= fine - FINESTRA_PREVISIONALE_GIORNI * 86_400_000;
});
// Data fino a cui stimare il previsionale: la restituzione prevista se già
// fissata, altrimenti la fine occupazione (così si può preparare in anticipo
// senza dover prima generare il Receivable di restituzione).
const dataTargetPrevisionale = computed<string | null>(
  () =>
    situazione.value?.tenant?.data_restituzione_prevista ??
    assignmentRecente.value?.valid_to ??
    null,
);

// Cerca un Receivable EXTRA marcato come previsionale e non ancora
// conguagliato. Usa la situazione dell'anno corrente; in futuro si potrebbe
// estendere su più anni se necessario.
const previsionaleApertoId = computed<number | null>(() => {
  const righe = situazione.value?.extra?.righe ?? [];
  const aperto = righe.find(
    (r: { is_previsionale?: boolean; previsionale_conguagliato?: boolean; id: number }) =>
      r.is_previsionale && !r.previsionale_conguagliato,
  );
  return aperto?.id ?? null;
});

const puoCrearePrevisionale = computed(
  () =>
    (!!situazione.value?.tenant?.data_restituzione_prevista ||
      inFinestraUscita.value) &&
    !restituzioneEffettuata.value &&
    assignmentAttivoId.value !== null &&
    previsionaleApertoId.value === null,
);

function aprireRegistraPagamento(riga: RigaPagamento): void {
  if (riga.stato === 'pagato') return;
  const t = tenantCorrente.value;
  if (!t) return;
  receivableSelezionato.value = {
    id: riga.receivable_id,
    causale: TIPO_TO_CAUSALE[riga.tipo],
    importo_dovuto: riga.importo_dovuto,
    importo_pagato: riga.importo_pagato,
    descrizione: riga.descrizione,
    tenant_nominativo: t.nominativo,
    scadenza: riga.scadenza ?? new Date().toISOString().slice(0, 10),
    bank_account_destinazione_id: riga.bank_account_destinazione_id,
  };
  dialogPagamento.value = true;
}

async function dopoSalvataggioPagamento(): Promise<void> {
  await store.loadSituazione(tenantId.value, annoSelezionato.value, true);
}

// --- Cessione stanza (assignment attivo, solo ruoli operativi) -------------

const propStore = usePropertiesStore();
const puoModificare = computed(
  () => propStore.mioRuolo === 'proprietario' || propStore.mioRuolo === 'gestore',
);

const dialogCessione = ref(false);
const assignmentCessione = ref<AssignmentRiga | null>(null);
const salvandoCessione = ref(false);
const erroreCessione = ref('');
const loadingCandidati = ref(false);
const candidatiCessione = ref<Tenant[]>([]);
const formCessione = ref({
  data_fine: '',
  nuovo_tenant: null as number | null,
  canone_mensile: '',
  costo_cessione: '',
  data_atto_cessione: '',
});

const opzioniNuovoTenant = computed(() =>
  candidatiCessione.value
    .filter((t) => t.id !== tenantId.value)
    .map((t) => ({ label: t.nominativo, value: t.id })),
);

function messaggioErroreCessione(e: unknown, fallback: string): string {
  if (isAxiosError(e)) {
    const data = e.response?.data as Record<string, unknown> | undefined;
    if (data && typeof data === 'object') {
      if (typeof data.detail === 'string') return data.detail;
      for (const valore of Object.values(data)) {
        if (typeof valore === 'string') return valore;
        if (Array.isArray(valore) && typeof valore[0] === 'string') return valore[0];
      }
    }
  }
  return fallback;
}

function apriDialogCessione(a: AssignmentRiga): void {
  assignmentCessione.value = a;
  erroreCessione.value = '';
  formCessione.value = {
    data_fine: new Date().toISOString().slice(0, 10),
    nuovo_tenant: null,
    canone_mensile: String(a.canone_mensile),
    costo_cessione: '',
    data_atto_cessione: '',
  };
  dialogCessione.value = true;
  void caricaCandidatiCessione();
}

async function caricaCandidatiCessione(): Promise<void> {
  loadingCandidati.value = true;
  try {
    const { data } = await api.get<Tenant[] | { results: Tenant[] }>(
      '/api/v1/tenants/',
      { params: { solo_attivi: 0 } },
    );
    const lista = Array.isArray(data) ? data : (data.results ?? []);
    candidatiCessione.value = [...lista].sort((a, b) =>
      a.nominativo.localeCompare(b.nominativo),
    );
  } catch {
    candidatiCessione.value = [];
    $q.notify({
      type: 'negative',
      message: 'Caricamento inquilini non riuscito.',
    });
  } finally {
    loadingCandidati.value = false;
  }
}

async function eseguiCessione(): Promise<void> {
  erroreCessione.value = '';
  const a = assignmentCessione.value;
  if (!a) return;
  const f = formCessione.value;
  if (!f.data_fine) {
    erroreCessione.value = 'La data di fine occupazione è obbligatoria.';
    return;
  }
  if (!f.nuovo_tenant) {
    erroreCessione.value = 'Selezionare il nuovo inquilino.';
    return;
  }
  if (f.canone_mensile === '' || Number(f.canone_mensile) < 0) {
    erroreCessione.value = 'Indicare il canone mensile del nuovo inquilino.';
    return;
  }
  salvandoCessione.value = true;
  try {
    await api.post(`/api/v1/room-assignments/${a.id}/cessione/`, {
      data_fine: f.data_fine,
      nuovo_tenant: f.nuovo_tenant,
      canone_mensile: f.canone_mensile,
      costo_cessione: f.costo_cessione !== '' ? f.costo_cessione : null,
      data_atto_cessione: f.data_atto_cessione || null,
    });
    dialogCessione.value = false;
    $q.notify({ type: 'positive', message: 'Cessione registrata.' });
    await store.loadSituazione(tenantId.value, annoSelezionato.value, true);
  } catch (e: unknown) {
    erroreCessione.value = messaggioErroreCessione(e, 'Cessione non riuscita.');
  } finally {
    salvandoCessione.value = false;
  }
}

const contiUtente = computed(() =>
  contiStore.accounts.length > 0
    ? contiStore.accounts
    : (auth.user?.bank_accounts ?? []),
);
const contoDiDefaultUtente = computed(
  () => auth.user?.bank_accounts?.[0]?.id ?? null,
);
</script>

<style scoped>
.vp-p-id__nav-inq {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-3);
  margin-bottom: var(--vp-gap-3);
  flex-wrap: wrap;
}
.vp-p-id__impersona {
  margin-left: auto;
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
/* icona del tab "Rendiconto" inline col testo (non impilata sopra) */
.vp-p-id__tabs :deep(.q-tab__content) {
  flex-direction: row;
  gap: 6px;
}
.vp-p-id__tabs :deep(.q-tab__icon) {
  font-size: 18px;
  margin: 0;
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
.vp-p-id__chip--c-deposito {
  color: var(--vp-ink-2, #5b6470);
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
.vp-p-id__sim-netto {
  font-size: var(--vp-text-lg);
}
.vp-p-id__rendiconto-btn {
  margin-top: var(--vp-gap-3);
}
.vp-p-id__sim-warn {
  color: var(--vp-terra, #b56a3b);
  font-size: var(--vp-text-sm);
}
.vp-p-id__dialog-titolo {
  font-weight: 600;
  font-size: 16px;
  color: var(--vp-ink-1);
}
.vp-p-id__banner-errore {
  background: var(--vp-clay-soft, #fbeae5);
  color: var(--vp-clay-deep, #8c3b21);
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
.vp-p-id__stato-wrap {
  display: inline-flex;
  align-items: center;
  gap: var(--vp-gap-1);
}
.vp-p-id__stato-click {
  display: inline-flex;
  align-items: center;
  gap: var(--vp-gap-1);
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 4px;
  transition: background-color 120ms;
}
.vp-p-id__stato-click:hover {
  background: var(--vp-paper-2, rgba(0, 0, 0, 0.04));
}
.vp-p-id__stato-icon {
  color: var(--vp-ink-3);
  opacity: 0.6;
}
.vp-p-id__stato-click:hover .vp-p-id__stato-icon {
  opacity: 1;
  color: var(--vp-salvia, #4f6e3f);
}
.vp-p-id__stato-icon--link {
  cursor: pointer;
  padding: 2px;
  border-radius: 4px;
}
.vp-p-id__stato-icon--link:hover {
  opacity: 1;
  color: var(--vp-terra, #b56a3b);
  background: var(--vp-paper-2, rgba(0, 0, 0, 0.04));
}
</style>
