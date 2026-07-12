<template>
  <q-page padding class="vp-page">
    <div class="vp-page-head row items-center q-gutter-sm">
      <h1 class="vp-h1">La casa</h1>
    </div>

    <q-tabs
      v-model="tabAttivo"
      dense
      no-caps
      align="left"
      class="vp-casa__tabs"
      active-color="primary"
      indicator-color="primary"
      data-testid="tabs-casa"
    >
      <q-tab name="stanze" label="Stanze" />
      <q-tab name="contratti" label="Contratti" />
      <q-tab name="spese" label="Spese" />
      <q-tab name="tari" label="TARI" />
    </q-tabs>

    <q-tab-panels v-model="tabAttivo" animated class="vp-casa__panels">
      <!-- STANZE -->
      <q-tab-panel name="stanze" class="vp-casa__panel">
        <q-card flat bordered class="vp-card" style="max-width: 720px">
          <q-card-section>
            <div class="row items-center">
              <div class="vp-section-title">Stanze</div>
              <q-space />
              <q-btn
                v-if="puoModificare"
                dense
                color="primary"
                icon="add"
                label="Nuova stanza"
                data-testid="nuova-stanza"
                @click="apriDialogStanza(null)"
              />
            </div>
            <q-table
              flat
              :rows="stanze"
              :columns="colonneStanze"
              row-key="id"
              :loading="loadingStanze"
              :pagination="{ rowsPerPage: 0, sortBy: 'ordinamento' }"
              hide-pagination
              no-data-label="Nessuna stanza configurata."
              class="q-mt-sm"
            >
              <template #body-cell-azioni="props">
                <q-td :props="props" auto-width>
                  <q-btn
                    v-if="puoModificare"
                    flat
                    dense
                    round
                    icon="edit"
                    :aria-label="`Modifica ${props.row.nome}`"
                    @click="apriDialogStanza(props.row)"
                  />
                  <q-btn
                    v-if="puoModificare"
                    flat
                    dense
                    round
                    icon="delete_outline"
                    color="negative"
                    :aria-label="`Elimina ${props.row.nome}`"
                    @click="eliminaStanza(props.row)"
                  />
                </q-td>
              </template>
            </q-table>
          </q-card-section>
        </q-card>
      </q-tab-panel>

      <!-- CONTRATTI -->
      <q-tab-panel name="contratti" class="vp-casa__panel">
        <q-card flat bordered class="vp-card" style="max-width: 720px">
          <q-card-section>
            <div class="row items-center">
              <div class="vp-section-title">Contratti</div>
              <q-space />
              <q-btn
                v-if="puoModificare"
                dense
                color="primary"
                icon="add"
                label="Nuovo contratto"
                data-testid="nuovo-contratto"
                @click="apriDialogContratto(null)"
              />
            </div>
            <q-list separator class="q-mt-sm">
              <q-item v-for="c in contratti" :key="c.id" data-testid="riga-contratto">
                <q-item-section>
                  <q-item-label>{{ nomeContratto(c) }}</q-item-label>
                  <q-item-label caption>
                    decorrenza {{ c.data_decorrenza }} · {{ c.durata_anni }}
                    {{ c.durata_anni === 1 ? 'anno' : 'anni' }}
                    · {{ c.regime_fiscale_display || c.regime_fiscale }}
                    <template v-if="c.termine"> · terminato il {{ c.termine }}</template>
                    <template v-if="c.default_pagatore_bollette">
                      · bollette: {{ nominativoOwner(c.default_pagatore_bollette) }}
                    </template>
                  </q-item-label>
                </q-item-section>
                <q-item-section side>
                  <div class="row items-center q-gutter-xs">
                    <q-chip v-if="c.asseverato" dense outline>Asseverato</q-chip>
                    <q-btn
                      v-if="puoModificare"
                      flat
                      dense
                      round
                      icon="edit"
                      :aria-label="`Modifica ${nomeContratto(c)}`"
                      @click="apriDialogContratto(c)"
                    />
                    <q-btn
                      v-if="puoModificare"
                      flat
                      dense
                      round
                      icon="delete_outline"
                      color="negative"
                      :aria-label="`Elimina ${nomeContratto(c)}`"
                      @click="eliminaContratto(c)"
                    />
                  </div>
                </q-item-section>
              </q-item>
              <q-item v-if="!loadingContratti && contratti.length === 0">
                <q-item-section class="text-grey">
                  Nessun contratto registrato.
                </q-item-section>
              </q-item>
            </q-list>
          </q-card-section>
        </q-card>
      </q-tab-panel>

      <!-- SPESE -->
      <q-tab-panel name="spese" class="vp-casa__panel">
        <q-card flat bordered class="vp-card q-mb-md" style="max-width: 720px">
          <q-card-section>
            <div class="row items-center">
              <div class="vp-section-title">Categorie di spesa</div>
              <q-space />
              <q-btn
                v-if="puoModificare"
                dense
                color="primary"
                icon="add"
                label="Nuova categoria"
                data-testid="nuova-categoria"
                @click="apriDialogCategoria(null)"
              />
            </div>
            <q-list separator class="q-mt-sm">
              <q-item v-for="c in categorie" :key="c.id" data-testid="riga-categoria">
                <q-item-section>
                  <q-item-label>{{ c.nome }}</q-item-label>
                  <q-item-label caption>
                    codice {{ c.codice }}
                    <template v-if="c.ripartibile_inquilini"> · ripartibile tra inquilini</template>
                  </q-item-label>
                </q-item-section>
                <q-item-section side>
                  <div class="row items-center q-gutter-xs">
                    <q-btn
                      v-if="puoModificare"
                      flat
                      dense
                      round
                      icon="edit"
                      :aria-label="`Modifica ${c.nome}`"
                      @click="apriDialogCategoria(c)"
                    />
                    <q-btn
                      v-if="puoModificare"
                      flat
                      dense
                      round
                      icon="delete_outline"
                      color="negative"
                      :aria-label="`Elimina ${c.nome}`"
                      @click="eliminaCategoria(c)"
                    />
                  </div>
                </q-item-section>
              </q-item>
              <q-item v-if="!loadingCategorie && categorie.length === 0">
                <q-item-section class="text-grey">
                  Nessuna categoria configurata.
                </q-item-section>
              </q-item>
            </q-list>
          </q-card-section>
        </q-card>

        <q-card flat bordered class="vp-card" style="max-width: 720px">
          <q-card-section>
            <div class="row items-center">
              <div class="vp-section-title">Fornitori</div>
              <q-space />
              <q-btn
                v-if="puoModificare"
                dense
                color="primary"
                icon="add"
                label="Nuovo fornitore"
                data-testid="nuovo-fornitore"
                @click="apriDialogFornitore(null)"
              />
            </div>
            <q-list separator class="q-mt-sm">
              <q-item v-for="f in fornitori" :key="f.id" data-testid="riga-fornitore">
                <q-item-section>
                  <q-item-label>{{ f.nome }}</q-item-label>
                  <q-item-label caption>
                    {{ f.tipo_display || etichettaTipoFornitore(f.tipo) }}
                    <template v-if="f.partita_iva"> · P.IVA {{ f.partita_iva }}</template>
                    <template v-if="f.contatto"> · {{ f.contatto }}</template>
                  </q-item-label>
                </q-item-section>
                <q-item-section side>
                  <div class="row items-center q-gutter-xs">
                    <q-btn
                      v-if="puoModificare"
                      flat
                      dense
                      round
                      icon="edit"
                      :aria-label="`Modifica ${f.nome}`"
                      @click="apriDialogFornitore(f)"
                    />
                    <q-btn
                      v-if="puoModificare"
                      flat
                      dense
                      round
                      icon="delete_outline"
                      color="negative"
                      :aria-label="`Elimina ${f.nome}`"
                      @click="eliminaFornitore(f)"
                    />
                  </div>
                </q-item-section>
              </q-item>
              <q-item v-if="!loadingFornitori && fornitori.length === 0">
                <q-item-section class="text-grey">
                  Nessun fornitore registrato.
                </q-item-section>
              </q-item>
            </q-list>
          </q-card-section>
        </q-card>
      </q-tab-panel>

      <!-- TARI / COSTI ANNUALI -->
      <q-tab-panel name="tari" class="vp-casa__panel">
        <q-card flat bordered class="vp-card" style="max-width: 720px">
          <q-card-section>
            <div class="row items-center">
              <div class="vp-section-title">Costi annuali (TARI e altro)</div>
              <q-space />
              <q-btn
                v-if="puoModificare"
                dense
                color="primary"
                icon="add"
                label="Nuovo costo"
                data-testid="nuovo-costo"
                @click="apriDialogCosto(null)"
              />
            </div>
            <div class="vp-hint q-mt-xs">
              Costi annuali spalmati sui conguagli utenze (es. tassa rifiuti).
            </div>
            <q-list separator class="q-mt-sm">
              <q-item v-for="c in costiAnnuali" :key="c.id" data-testid="riga-costo">
                <q-item-section>
                  <q-item-label>
                    {{ c.voce_display || etichettaVoce(c.voce) }} {{ c.anno }}
                  </q-item-label>
                  <q-item-label caption>
                    {{ formattaImporto(c.importo_annuale) }}/anno
                    · dal {{ c.valid_from }}
                    <template v-if="c.valid_to"> al {{ c.valid_to }}</template>
                    <template v-if="c.note"> · {{ c.note }}</template>
                  </q-item-label>
                </q-item-section>
                <q-item-section side>
                  <div class="row items-center q-gutter-xs">
                    <q-btn
                      v-if="puoModificare"
                      flat
                      dense
                      round
                      icon="edit"
                      :aria-label="`Modifica costo ${c.anno}`"
                      @click="apriDialogCosto(c)"
                    />
                    <q-btn
                      v-if="puoModificare"
                      flat
                      dense
                      round
                      icon="delete_outline"
                      color="negative"
                      :aria-label="`Elimina costo ${c.anno}`"
                      @click="eliminaCosto(c)"
                    />
                  </div>
                </q-item-section>
              </q-item>
              <q-item v-if="!loadingCosti && costiAnnuali.length === 0">
                <q-item-section class="text-grey">
                  Nessun costo annuale configurato.
                </q-item-section>
              </q-item>
            </q-list>
          </q-card-section>
        </q-card>
      </q-tab-panel>
    </q-tab-panels>

    <!-- Dialog stanza -->
    <q-dialog v-model="dialogStanza">
      <q-card style="min-width: 380px">
        <q-card-section>
          <div class="vp-section-title">
            {{ stanzaInModifica ? 'Modifica stanza' : 'Nuova stanza' }}
          </div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input
            v-model="formStanza.nome"
            label="Nome"
            outlined
            dense
            autofocus
            data-testid="stanza-nome"
          />
          <q-input
            v-model="formStanza.superficie_mq"
            label="Superficie (mq)"
            type="number"
            min="0"
            step="0.01"
            outlined
            dense
            data-testid="stanza-superficie"
          />
          <q-input
            v-model="formStanza.ordinamento"
            label="Ordinamento"
            type="number"
            min="0"
            outlined
            dense
            data-testid="stanza-ordinamento"
          />
          <q-banner v-if="erroreStanza" class="vp-banner-errore" rounded dense>
            {{ erroreStanza }}
          </q-banner>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn v-close-popup flat label="Annulla" />
          <q-btn
            color="primary"
            label="Salva"
            :loading="savingStanza"
            data-testid="salva-stanza"
            @click="salvaStanza"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Dialog contratto -->
    <q-dialog v-model="dialogContratto">
      <q-card style="min-width: 460px">
        <q-card-section>
          <div class="vp-section-title">
            {{ contrattoInModifica ? 'Modifica contratto' : 'Nuovo contratto' }}
          </div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input
            v-model="formContratto.nome"
            label="Nome (es. 'Contratto 2025')"
            outlined
            dense
            autofocus
            data-testid="contratto-nome"
          />
          <div class="row q-col-gutter-sm">
            <div class="col-6">
              <q-input
                v-model="formContratto.data_stipula"
                label="Data stipula"
                type="date"
                outlined
                dense
                data-testid="contratto-stipula"
              />
            </div>
            <div class="col-6">
              <q-input
                v-model="formContratto.data_decorrenza"
                label="Data decorrenza"
                type="date"
                outlined
                dense
                data-testid="contratto-decorrenza"
              />
            </div>
          </div>
          <div class="row q-col-gutter-sm">
            <div class="col-6">
              <q-input
                v-model="formContratto.durata_anni"
                label="Durata (anni)"
                type="number"
                min="1"
                outlined
                dense
                data-testid="contratto-durata"
              />
            </div>
            <div class="col-6">
              <q-input
                v-model="formContratto.termine"
                label="Termine anticipato"
                type="date"
                outlined
                dense
                clearable
                hint="Solo se chiuso prima della scadenza"
              />
            </div>
          </div>
          <q-select
            v-model="formContratto.regime_fiscale"
            :options="opzioniRegimeFiscale"
            label="Regime fiscale"
            outlined
            dense
            emit-value
            map-options
            data-testid="contratto-regime"
          />
          <q-select
            v-model="formContratto.default_pagatore_bollette"
            :options="opzioniPagatore"
            label="Pagatore bollette (convenzione)"
            outlined
            dense
            emit-value
            map-options
            clearable
            data-testid="contratto-pagatore"
          />
          <q-toggle
            v-model="formContratto.asseverato"
            label="Asseverato"
            dense
          />
          <q-input
            v-model="formContratto.note"
            label="Note"
            type="textarea"
            autogrow
            outlined
            dense
          />
          <q-banner v-if="erroreContratto" class="vp-banner-errore" rounded dense>
            {{ erroreContratto }}
          </q-banner>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn v-close-popup flat label="Annulla" />
          <q-btn
            color="primary"
            label="Salva"
            :loading="savingContratto"
            data-testid="salva-contratto"
            @click="salvaContratto"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Dialog categoria spesa -->
    <q-dialog v-model="dialogCategoria">
      <q-card style="min-width: 380px">
        <q-card-section>
          <div class="vp-section-title">
            {{ categoriaInModifica ? 'Modifica categoria' : 'Nuova categoria' }}
          </div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input
            v-model="formCategoria.nome"
            label="Nome"
            outlined
            dense
            autofocus
            data-testid="categoria-nome"
          />
          <q-input
            v-model="formCategoria.codice"
            label="Codice (slug, es. 'manutenzione')"
            outlined
            dense
            data-testid="categoria-codice"
          />
          <q-toggle
            v-model="formCategoria.ripartibile_inquilini"
            label="Ripartibile tra inquilini"
            dense
          />
          <q-banner v-if="erroreCategoria" class="vp-banner-errore" rounded dense>
            {{ erroreCategoria }}
          </q-banner>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn v-close-popup flat label="Annulla" />
          <q-btn
            color="primary"
            label="Salva"
            :loading="savingCategoria"
            data-testid="salva-categoria"
            @click="salvaCategoria"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Dialog fornitore -->
    <q-dialog v-model="dialogFornitore">
      <q-card style="min-width: 380px">
        <q-card-section>
          <div class="vp-section-title">
            {{ fornitoreInModifica ? 'Modifica fornitore' : 'Nuovo fornitore' }}
          </div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input
            v-model="formFornitore.nome"
            label="Nome"
            outlined
            dense
            autofocus
            data-testid="fornitore-nome"
          />
          <q-select
            v-model="formFornitore.tipo"
            :options="opzioniTipoFornitore"
            label="Tipo"
            outlined
            dense
            emit-value
            map-options
            data-testid="fornitore-tipo"
          />
          <q-input
            v-model="formFornitore.partita_iva"
            label="Partita IVA"
            outlined
            dense
          />
          <q-input
            v-model="formFornitore.contatto"
            label="Contatto"
            type="textarea"
            autogrow
            outlined
            dense
          />
          <q-banner v-if="erroreFornitore" class="vp-banner-errore" rounded dense>
            {{ erroreFornitore }}
          </q-banner>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn v-close-popup flat label="Annulla" />
          <q-btn
            color="primary"
            label="Salva"
            :loading="savingFornitore"
            data-testid="salva-fornitore"
            @click="salvaFornitore"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Dialog costo annuale -->
    <q-dialog v-model="dialogCosto">
      <q-card style="min-width: 420px">
        <q-card-section>
          <div class="vp-section-title">
            {{ costoInModifica ? 'Modifica costo annuale' : 'Nuovo costo annuale' }}
          </div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <q-select
            v-model="formCosto.voce"
            :options="opzioniVoce"
            label="Voce"
            outlined
            dense
            emit-value
            map-options
            data-testid="costo-voce"
          />
          <div class="row q-col-gutter-sm">
            <div class="col-6">
              <q-input
                v-model="formCosto.anno"
                label="Anno"
                type="number"
                outlined
                dense
                data-testid="costo-anno"
              />
            </div>
            <div class="col-6">
              <q-input
                v-model="formCosto.importo_annuale"
                label="Importo annuale"
                type="number"
                min="0"
                step="0.01"
                suffix="€"
                outlined
                dense
                data-testid="costo-importo"
              />
            </div>
          </div>
          <div class="row q-col-gutter-sm">
            <div class="col-6">
              <q-input
                v-model="formCosto.valid_from"
                label="Valido dal"
                type="date"
                outlined
                dense
                data-testid="costo-valid-from"
              />
            </div>
            <div class="col-6">
              <q-input
                v-model="formCosto.valid_to"
                label="Valido fino al"
                type="date"
                outlined
                dense
                clearable
                hint="Vuoto = tuttora in vigore"
              />
            </div>
          </div>
          <q-input
            v-model="formCosto.note"
            label="Note"
            type="textarea"
            autogrow
            outlined
            dense
          />
          <q-banner v-if="erroreCosto" class="vp-banner-errore" rounded dense>
            {{ erroreCosto }}
          </q-banner>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn v-close-popup flat label="Annulla" />
          <q-btn
            color="primary"
            label="Salva"
            :loading="savingCosto"
            data-testid="salva-costo"
            @click="salvaCosto"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { isAxiosError } from 'axios';
import { useQuasar, type QTableProps } from 'quasar';
import { api } from 'boot/axios';
import { usePropertiesStore } from 'stores/properties';

// ---------------------------------------------------------------------------
// Tipi (allineati ai serializer backend: properties/billing)
// ---------------------------------------------------------------------------

interface Stanza {
  id: number;
  nome: string;
  superficie_mq: string | null;
  ordinamento: number;
}

type RegimeFiscale = 'cedolare_10' | 'cedolare_21' | 'irpef';

interface Contratto {
  id: number;
  nome: string;
  data_stipula: string;
  data_decorrenza: string;
  termine: string | null;
  durata_anni: number;
  asseverato: boolean;
  regime_fiscale: RegimeFiscale;
  regime_fiscale_display?: string;
  default_pagatore_bollette: number | null;
  note: string;
}

interface Owner {
  id: number;
  nominativo: string;
}

interface Categoria {
  id: number;
  nome: string;
  codice: string;
  ripartibile_inquilini: boolean;
}

type TipoFornitore = 'energia' | 'gas' | 'acqua' | 'condominio' | 'altro';

interface Fornitore {
  id: number;
  nome: string;
  tipo: TipoFornitore;
  tipo_display?: string;
  partita_iva: string;
  contatto: string;
}

type VoceAnnuale = 'tari' | 'altro';

interface CostoAnnuale {
  id: number;
  voce: VoceAnnuale;
  voce_display?: string;
  anno: number;
  importo_annuale: string;
  valid_from: string;
  valid_to: string | null;
  note: string;
}

const $q = useQuasar();
const propStore = usePropertiesStore();

const tabAttivo = ref<'stanze' | 'contratti' | 'spese' | 'tari'>('stanze');

const puoModificare = computed(
  () => propStore.mioRuolo === 'proprietario' || propStore.mioRuolo === 'gestore',
);

function asArray<T>(data: T[] | { results: T[] } | undefined | null): T[] {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  return data.results ?? [];
}

function messaggioErrore(e: unknown, fallback: string): string {
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

function formattaImporto(v: string | number): string {
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v);
  return n.toLocaleString('it-IT', {
    style: 'currency',
    currency: 'EUR',
  });
}

// ---------------------------------------------------------------------------
// Stanze
// ---------------------------------------------------------------------------

const stanze = ref<Stanza[]>([]);
const loadingStanze = ref(false);

const colonneStanze: QTableProps['columns'] = [
  { name: 'nome', label: 'Nome', field: 'nome', align: 'left', sortable: true },
  {
    name: 'superficie_mq',
    label: 'Superficie (mq)',
    field: 'superficie_mq',
    align: 'right',
    sortable: true,
    format: (v: string | null) => (v ? Number(v).toLocaleString('it-IT') : '—'),
  },
  {
    name: 'ordinamento',
    label: 'Ordinamento',
    field: 'ordinamento',
    align: 'right',
    sortable: true,
  },
  { name: 'azioni', label: '', field: 'id', align: 'right' },
];

async function caricaStanze() {
  loadingStanze.value = true;
  try {
    const { data } = await api.get<Stanza[] | { results: Stanza[] }>('/api/v1/rooms/');
    stanze.value = asArray(data);
  } catch (e: unknown) {
    $q.notify({
      type: 'negative',
      message: messaggioErrore(e, 'Caricamento stanze non riuscito.'),
    });
  } finally {
    loadingStanze.value = false;
  }
}

const dialogStanza = ref(false);
const stanzaInModifica = ref<Stanza | null>(null);
const formStanza = ref({ nome: '', superficie_mq: '', ordinamento: '0' });
const savingStanza = ref(false);
const erroreStanza = ref('');

function apriDialogStanza(s: Stanza | null) {
  stanzaInModifica.value = s;
  erroreStanza.value = '';
  formStanza.value = {
    nome: s?.nome ?? '',
    superficie_mq: s?.superficie_mq ?? '',
    ordinamento: String(s?.ordinamento ?? stanze.value.length),
  };
  dialogStanza.value = true;
}

async function salvaStanza() {
  erroreStanza.value = '';
  if (!formStanza.value.nome.trim()) {
    erroreStanza.value = 'Il nome è obbligatorio.';
    return;
  }
  savingStanza.value = true;
  const payload = {
    nome: formStanza.value.nome.trim(),
    superficie_mq: formStanza.value.superficie_mq !== '' ? formStanza.value.superficie_mq : null,
    ordinamento: Number(formStanza.value.ordinamento) || 0,
  };
  try {
    if (stanzaInModifica.value) {
      await api.patch(`/api/v1/rooms/${stanzaInModifica.value.id}/`, payload);
      $q.notify({ type: 'positive', message: 'Stanza aggiornata.' });
    } else {
      await api.post('/api/v1/rooms/', payload);
      $q.notify({ type: 'positive', message: 'Stanza creata.' });
    }
    dialogStanza.value = false;
    await caricaStanze();
  } catch (e: unknown) {
    erroreStanza.value = messaggioErrore(e, 'Salvataggio non riuscito.');
  } finally {
    savingStanza.value = false;
  }
}

function eliminaStanza(s: Stanza) {
  $q.dialog({
    title: 'Eliminare la stanza?',
    message: `"${s.nome}" verrà rimossa dall'immobile.`,
    cancel: { flat: true, label: 'Annulla' },
    ok: { color: 'negative', label: 'Elimina' },
  }).onOk(() => {
    void (async () => {
      try {
        await api.delete(`/api/v1/rooms/${s.id}/`);
        stanze.value = stanze.value.filter((x) => x.id !== s.id);
        $q.notify({ type: 'positive', message: 'Stanza eliminata.' });
      } catch (e: unknown) {
        $q.notify({
          type: 'negative',
          message: messaggioErrore(
            e,
            'Eliminazione non riuscita: la stanza ha assegnazioni collegate.',
          ),
        });
      }
    })();
  });
}

// ---------------------------------------------------------------------------
// Contratti
// ---------------------------------------------------------------------------

const contratti = ref<Contratto[]>([]);
const loadingContratti = ref(false);
const owners = ref<Owner[]>([]);

const opzioniRegimeFiscale = [
  { label: 'Cedolare secca 10%', value: 'cedolare_10' },
  { label: 'Cedolare secca 21%', value: 'cedolare_21' },
  { label: 'IRPEF ordinario', value: 'irpef' },
];

const opzioniPagatore = computed(() =>
  owners.value.map((o) => ({ label: o.nominativo, value: o.id })),
);

function nominativoOwner(id: number): string {
  return owners.value.find((o) => o.id === id)?.nominativo ?? `#${id}`;
}

function nomeContratto(c: Contratto): string {
  return c.nome || `Contratto dal ${c.data_decorrenza}`;
}

async function caricaContratti() {
  loadingContratti.value = true;
  try {
    const [{ data: dataContratti }, { data: dataOwners }] = await Promise.all([
      api.get<Contratto[] | { results: Contratto[] }>('/api/v1/contracts/'),
      api.get<Owner[] | { results: Owner[] }>('/api/v1/owners/'),
    ]);
    contratti.value = asArray(dataContratti);
    owners.value = asArray(dataOwners);
  } catch (e: unknown) {
    $q.notify({
      type: 'negative',
      message: messaggioErrore(e, 'Caricamento contratti non riuscito.'),
    });
  } finally {
    loadingContratti.value = false;
  }
}

const dialogContratto = ref(false);
const contrattoInModifica = ref<Contratto | null>(null);
interface FormContratto {
  nome: string;
  data_stipula: string;
  data_decorrenza: string;
  termine: string | null;
  durata_anni: string;
  asseverato: boolean;
  regime_fiscale: RegimeFiscale;
  default_pagatore_bollette: number | null;
  note: string;
}

const formContratto = ref<FormContratto>({
  nome: '',
  data_stipula: '',
  data_decorrenza: '',
  termine: null,
  durata_anni: '4',
  asseverato: false,
  regime_fiscale: 'cedolare_10',
  default_pagatore_bollette: null,
  note: '',
});
const savingContratto = ref(false);
const erroreContratto = ref('');

function apriDialogContratto(c: Contratto | null) {
  contrattoInModifica.value = c;
  erroreContratto.value = '';
  formContratto.value = {
    nome: c?.nome ?? '',
    data_stipula: c?.data_stipula ?? '',
    data_decorrenza: c?.data_decorrenza ?? '',
    termine: c?.termine ?? null,
    durata_anni: String(c?.durata_anni ?? 4),
    asseverato: c?.asseverato ?? false,
    regime_fiscale: c?.regime_fiscale ?? 'cedolare_10',
    default_pagatore_bollette: c?.default_pagatore_bollette ?? null,
    note: c?.note ?? '',
  };
  dialogContratto.value = true;
}

async function salvaContratto() {
  erroreContratto.value = '';
  const f = formContratto.value;
  if (!f.data_stipula || !f.data_decorrenza) {
    erroreContratto.value = 'Data stipula e data decorrenza sono obbligatorie.';
    return;
  }
  if (!Number(f.durata_anni)) {
    erroreContratto.value = 'La durata in anni è obbligatoria.';
    return;
  }
  savingContratto.value = true;
  const payload = {
    nome: f.nome.trim(),
    data_stipula: f.data_stipula,
    data_decorrenza: f.data_decorrenza,
    termine: f.termine || null,
    durata_anni: Number(f.durata_anni),
    asseverato: f.asseverato,
    regime_fiscale: f.regime_fiscale,
    default_pagatore_bollette: f.default_pagatore_bollette,
    note: f.note,
  };
  try {
    if (contrattoInModifica.value) {
      await api.patch(`/api/v1/contracts/${contrattoInModifica.value.id}/`, payload);
      $q.notify({ type: 'positive', message: 'Contratto aggiornato.' });
    } else {
      await api.post('/api/v1/contracts/', payload);
      $q.notify({ type: 'positive', message: 'Contratto creato.' });
    }
    dialogContratto.value = false;
    await caricaContratti();
  } catch (e: unknown) {
    erroreContratto.value = messaggioErrore(e, 'Salvataggio non riuscito.');
  } finally {
    savingContratto.value = false;
  }
}

function eliminaContratto(c: Contratto) {
  $q.dialog({
    title: 'Eliminare il contratto?',
    message: `"${nomeContratto(c)}" verrà rimosso.`,
    cancel: { flat: true, label: 'Annulla' },
    ok: { color: 'negative', label: 'Elimina' },
  }).onOk(() => {
    void (async () => {
      try {
        await api.delete(`/api/v1/contracts/${c.id}/`);
        contratti.value = contratti.value.filter((x) => x.id !== c.id);
        $q.notify({ type: 'positive', message: 'Contratto eliminato.' });
      } catch (e: unknown) {
        $q.notify({
          type: 'negative',
          message: messaggioErrore(e, 'Eliminazione non riuscita: dati collegati.'),
        });
      }
    })();
  });
}

// ---------------------------------------------------------------------------
// Spese: categorie
// ---------------------------------------------------------------------------

const categorie = ref<Categoria[]>([]);
const loadingCategorie = ref(false);

async function caricaCategorie() {
  loadingCategorie.value = true;
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
    loadingCategorie.value = false;
  }
}

const dialogCategoria = ref(false);
const categoriaInModifica = ref<Categoria | null>(null);
const formCategoria = ref({ nome: '', codice: '', ripartibile_inquilini: false });
const savingCategoria = ref(false);
const erroreCategoria = ref('');

function apriDialogCategoria(c: Categoria | null) {
  categoriaInModifica.value = c;
  erroreCategoria.value = '';
  formCategoria.value = {
    nome: c?.nome ?? '',
    codice: c?.codice ?? '',
    ripartibile_inquilini: c?.ripartibile_inquilini ?? false,
  };
  dialogCategoria.value = true;
}

async function salvaCategoria() {
  erroreCategoria.value = '';
  const f = formCategoria.value;
  if (!f.nome.trim() || !f.codice.trim()) {
    erroreCategoria.value = 'Nome e codice sono obbligatori.';
    return;
  }
  savingCategoria.value = true;
  const payload = {
    nome: f.nome.trim(),
    codice: f.codice.trim(),
    ripartibile_inquilini: f.ripartibile_inquilini,
  };
  try {
    if (categoriaInModifica.value) {
      await api.patch(`/api/v1/expense-categories/${categoriaInModifica.value.id}/`, payload);
      $q.notify({ type: 'positive', message: 'Categoria aggiornata.' });
    } else {
      await api.post('/api/v1/expense-categories/', payload);
      $q.notify({ type: 'positive', message: 'Categoria creata.' });
    }
    dialogCategoria.value = false;
    await caricaCategorie();
  } catch (e: unknown) {
    erroreCategoria.value = messaggioErrore(e, 'Salvataggio non riuscito.');
  } finally {
    savingCategoria.value = false;
  }
}

function eliminaCategoria(c: Categoria) {
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

// ---------------------------------------------------------------------------
// Spese: fornitori
// ---------------------------------------------------------------------------

const fornitori = ref<Fornitore[]>([]);
const loadingFornitori = ref(false);

const opzioniTipoFornitore = [
  { label: 'Energia elettrica', value: 'energia' },
  { label: 'Gas', value: 'gas' },
  { label: 'Acqua', value: 'acqua' },
  { label: 'Condominio', value: 'condominio' },
  { label: 'Altro', value: 'altro' },
];

function etichettaTipoFornitore(tipo: TipoFornitore): string {
  return opzioniTipoFornitore.find((o) => o.value === tipo)?.label ?? tipo;
}

async function caricaFornitori() {
  loadingFornitori.value = true;
  try {
    const { data } = await api.get<Fornitore[] | { results: Fornitore[] }>(
      '/api/v1/suppliers/',
    );
    fornitori.value = asArray(data);
  } catch (e: unknown) {
    $q.notify({
      type: 'negative',
      message: messaggioErrore(e, 'Caricamento fornitori non riuscito.'),
    });
  } finally {
    loadingFornitori.value = false;
  }
}

const dialogFornitore = ref(false);
const fornitoreInModifica = ref<Fornitore | null>(null);
interface FormFornitore {
  nome: string;
  tipo: TipoFornitore;
  partita_iva: string;
  contatto: string;
}

const formFornitore = ref<FormFornitore>({
  nome: '',
  tipo: 'altro',
  partita_iva: '',
  contatto: '',
});
const savingFornitore = ref(false);
const erroreFornitore = ref('');

function apriDialogFornitore(f: Fornitore | null) {
  fornitoreInModifica.value = f;
  erroreFornitore.value = '';
  formFornitore.value = {
    nome: f?.nome ?? '',
    tipo: f?.tipo ?? 'altro',
    partita_iva: f?.partita_iva ?? '',
    contatto: f?.contatto ?? '',
  };
  dialogFornitore.value = true;
}

async function salvaFornitore() {
  erroreFornitore.value = '';
  const f = formFornitore.value;
  if (!f.nome.trim()) {
    erroreFornitore.value = 'Il nome è obbligatorio.';
    return;
  }
  savingFornitore.value = true;
  const payload = {
    nome: f.nome.trim(),
    tipo: f.tipo,
    partita_iva: f.partita_iva.trim(),
    contatto: f.contatto.trim(),
  };
  try {
    if (fornitoreInModifica.value) {
      await api.patch(`/api/v1/suppliers/${fornitoreInModifica.value.id}/`, payload);
      $q.notify({ type: 'positive', message: 'Fornitore aggiornato.' });
    } else {
      await api.post('/api/v1/suppliers/', payload);
      $q.notify({ type: 'positive', message: 'Fornitore creato.' });
    }
    dialogFornitore.value = false;
    await caricaFornitori();
  } catch (e: unknown) {
    erroreFornitore.value = messaggioErrore(e, 'Salvataggio non riuscito.');
  } finally {
    savingFornitore.value = false;
  }
}

function eliminaFornitore(f: Fornitore) {
  $q.dialog({
    title: 'Eliminare il fornitore?',
    message: `"${f.nome}" verrà rimosso.`,
    cancel: { flat: true, label: 'Annulla' },
    ok: { color: 'negative', label: 'Elimina' },
  }).onOk(() => {
    void (async () => {
      try {
        await api.delete(`/api/v1/suppliers/${f.id}/`);
        fornitori.value = fornitori.value.filter((x) => x.id !== f.id);
        $q.notify({ type: 'positive', message: 'Fornitore eliminato.' });
      } catch (e: unknown) {
        $q.notify({
          type: 'negative',
          message: messaggioErrore(e, 'Eliminazione non riuscita: dati collegati.'),
        });
      }
    })();
  });
}

// ---------------------------------------------------------------------------
// TARI / costi annuali
// ---------------------------------------------------------------------------

const costiAnnuali = ref<CostoAnnuale[]>([]);
const loadingCosti = ref(false);

const opzioniVoce = [
  { label: 'TARI (tassa rifiuti)', value: 'tari' },
  { label: 'Altro', value: 'altro' },
];

function etichettaVoce(voce: VoceAnnuale): string {
  return opzioniVoce.find((o) => o.value === voce)?.label ?? voce;
}

async function caricaCosti() {
  loadingCosti.value = true;
  try {
    const { data } = await api.get<CostoAnnuale[] | { results: CostoAnnuale[] }>(
      '/api/v1/annual-utility-costs/',
    );
    costiAnnuali.value = asArray(data).sort((a, b) => b.anno - a.anno);
  } catch (e: unknown) {
    $q.notify({
      type: 'negative',
      message: messaggioErrore(e, 'Caricamento costi annuali non riuscito.'),
    });
  } finally {
    loadingCosti.value = false;
  }
}

const dialogCosto = ref(false);
const costoInModifica = ref<CostoAnnuale | null>(null);
interface FormCosto {
  voce: VoceAnnuale;
  anno: string;
  importo_annuale: string;
  valid_from: string;
  valid_to: string | null;
  note: string;
}

const formCosto = ref<FormCosto>({
  voce: 'tari',
  anno: String(new Date().getFullYear()),
  importo_annuale: '',
  valid_from: '',
  valid_to: null,
  note: '',
});
const savingCosto = ref(false);
const erroreCosto = ref('');

function apriDialogCosto(c: CostoAnnuale | null) {
  costoInModifica.value = c;
  erroreCosto.value = '';
  const annoCorrente = new Date().getFullYear();
  formCosto.value = {
    voce: c?.voce ?? 'tari',
    anno: String(c?.anno ?? annoCorrente),
    importo_annuale: c?.importo_annuale ?? '',
    valid_from: c?.valid_from ?? `${annoCorrente}-01-01`,
    valid_to: c?.valid_to ?? null,
    note: c?.note ?? '',
  };
  dialogCosto.value = true;
}

async function salvaCosto() {
  erroreCosto.value = '';
  const f = formCosto.value;
  if (!Number(f.anno) || f.importo_annuale === '' || !f.valid_from) {
    erroreCosto.value = 'Anno, importo e data di inizio validità sono obbligatori.';
    return;
  }
  savingCosto.value = true;
  const payload = {
    voce: f.voce,
    anno: Number(f.anno),
    importo_annuale: f.importo_annuale,
    valid_from: f.valid_from,
    valid_to: f.valid_to || null,
    note: f.note,
  };
  try {
    if (costoInModifica.value) {
      await api.patch(`/api/v1/annual-utility-costs/${costoInModifica.value.id}/`, payload);
      $q.notify({ type: 'positive', message: 'Costo annuale aggiornato.' });
    } else {
      await api.post('/api/v1/annual-utility-costs/', payload);
      $q.notify({ type: 'positive', message: 'Costo annuale creato.' });
    }
    dialogCosto.value = false;
    await caricaCosti();
  } catch (e: unknown) {
    erroreCosto.value = messaggioErrore(e, 'Salvataggio non riuscito.');
  } finally {
    savingCosto.value = false;
  }
}

function eliminaCosto(c: CostoAnnuale) {
  $q.dialog({
    title: 'Eliminare il costo annuale?',
    message: `${c.voce_display || etichettaVoce(c.voce)} ${c.anno} verrà rimosso.`,
    cancel: { flat: true, label: 'Annulla' },
    ok: { color: 'negative', label: 'Elimina' },
  }).onOk(() => {
    void (async () => {
      try {
        await api.delete(`/api/v1/annual-utility-costs/${c.id}/`);
        costiAnnuali.value = costiAnnuali.value.filter((x) => x.id !== c.id);
        $q.notify({ type: 'positive', message: 'Costo annuale eliminato.' });
      } catch (e: unknown) {
        $q.notify({
          type: 'negative',
          message: messaggioErrore(e, 'Eliminazione non riuscita.'),
        });
      }
    })();
  });
}

// ---------------------------------------------------------------------------

onMounted(() => {
  void caricaStanze();
  void caricaContratti();
  void caricaCategorie();
  void caricaFornitori();
  void caricaCosti();
});
</script>

<style scoped>
.vp-page-head {
  margin-bottom: var(--vp-gap-4);
}
.vp-h1 {
  font-size: 26px;
  line-height: 1.2;
  margin: 0;
}
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
.vp-casa__tabs {
  border-bottom: 1px solid var(--vp-paper-3);
  margin-bottom: var(--vp-gap-3);
}
.vp-casa__panels {
  background: transparent;
}
.vp-casa__panel {
  padding: 0;
}
</style>
