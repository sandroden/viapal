<template>
  <q-dialog v-model="open" @hide="reset">
    <q-card class="sf-card">
      <q-card-section class="sf-head">
        <div>
          <div class="sf-title">Scarica foto</div>
          <div class="sf-sub">
            Seleziona le foto da usare nei post dell'annuncio.
          </div>
        </div>
        <q-btn flat dense round icon="close" v-close-popup />
      </q-card-section>

      <q-card-section class="sf-toolbar">
        <q-btn flat dense no-caps size="sm" icon="select_all" label="Tutte" @click="selezionaTutte" />
        <q-btn flat dense no-caps size="sm" icon="deselect" label="Nessuna" @click="deselezionaTutte" />
        <q-space />
        <span class="sf-count">{{ selezione.size }} / {{ tutte.length }} selezionate</span>
      </q-card-section>

      <q-card-section class="sf-body">
        <div v-if="!tutte.length" class="sf-empty">Nessuna foto in galleria.</div>

        <div v-for="sez in sezioni" :key="sez.chiave" class="sf-sez">
          <div class="sf-sez-head">
            <span class="sf-sez-nome">{{ sez.nome }}</span>
            <span class="sf-sez-n">{{ sez.foto.length }}</span>
            <q-btn
              flat
              dense
              no-caps
              size="sm"
              :label="tutteSelezionate(sez) ? 'deseleziona' : 'seleziona'"
              @click="toggleSezione(sez)"
            />
          </div>
          <div class="sf-grid">
            <button
              v-for="f in sez.foto"
              :key="f.url"
              type="button"
              class="sf-thumb"
              :class="{ on: selezione.has(f.url) }"
              :title="f.nomeFile"
              @click="toggle(f.url)"
            >
              <img :src="f.url" alt="" loading="lazy" />
              <span class="sf-check">
                <q-icon :name="selezione.has(f.url) ? 'check_circle' : 'radio_button_unchecked'" size="20px" />
              </span>
            </button>
          </div>
        </div>
      </q-card-section>

      <q-card-actions class="sf-actions">
        <div v-if="errore" class="sf-err">{{ errore }}</div>
        <q-space />
        <q-btn flat no-caps label="Chiudi" v-close-popup />
        <q-btn
          unelevated
          no-caps
          color="primary"
          icon="download"
          :disable="!selezione.size || scaricando"
          :loading="scaricando"
          :label="etichettaScarica"
          @click="scarica"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import type { GalleriaPubblica } from 'stores/galleria';
import { scaricaUrl } from 'src/utils/image';

const props = defineProps<{
  modelValue: boolean;
  galleria: GalleriaPubblica | null;
}>();
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>();

const open = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
});

interface FotoScaricabile {
  url: string;
  nomeFile: string;
}
interface Sezione {
  chiave: string;
  nome: string;
  foto: FotoScaricabile[];
}

// La selezione è per URL: identifica la foto anche quando arriva da campi
// singleton (hero/planimetria/mappa) che non hanno un id di GalleryImage.
const selezione = ref(new Set<string>());
const scaricando = ref(false);
const errore = ref<string | null>(null);

function slugifica(s: string): string {
  return s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

/** Estensione dedotta dall'URL servito (i nomi su disco sono opachi). */
function estensione(url: string): string {
  const m = /\.([a-z0-9]{3,4})(?:\?|$)/i.exec(url);
  return m?.[1]?.toLowerCase() ?? 'jpg';
}

/** `viapal-<sezione>-01.webp`: nome parlante per il post, non quello su disco. */
function nomeFile(sezione: string, i: number, url: string): string {
  const n = String(i + 1).padStart(2, '0');
  return `${slugifica(props.galleria?.slug ?? 'galleria')}-${slugifica(sezione)}-${n}.${estensione(url)}`;
}

// Tutte le foto della pagina: singleton dell'immobile + foto stanze + foto
// ambienti comuni. Nota: il serializer pubblico non espone le foto delle
// stanze non disponibili, che quindi non compaiono qui.
const sezioni = computed<Sezione[]>(() => {
  const g = props.galleria;
  if (!g) return [];
  const out: Sezione[] = [];

  const generali: { nome: string; url: string | null }[] = [
    { nome: 'principale', url: g.foto_hero },
    { nome: 'planimetria', url: g.foto_planimetria },
    { nome: 'mappa', url: g.foto_mappa },
  ];
  const gen = generali.filter((x) => !!x.url);
  if (gen.length) {
    out.push({
      chiave: 'generali',
      nome: 'Immagini generali',
      foto: gen.map((x) => ({
        url: x.url as string,
        nomeFile: nomeFile(x.nome, 0, x.url as string),
      })),
    });
  }

  for (const r of g.rooms) {
    if (!r.foto.length) continue;
    out.push({
      chiave: `room-${r.id}`,
      nome: r.nome,
      foto: r.foto.map((f, i) => ({ url: f.url, nomeFile: nomeFile(r.nome, i, f.url) })),
    });
  }
  for (const a of g.aree) {
    if (!a.foto.length) continue;
    out.push({
      chiave: `area-${a.id}`,
      nome: a.nome,
      foto: a.foto.map((f, i) => ({ url: f.url, nomeFile: nomeFile(a.nome, i, f.url) })),
    });
  }
  return out;
});

const tutte = computed<FotoScaricabile[]>(() => sezioni.value.flatMap((s) => s.foto));

const etichettaScarica = computed(() =>
  selezione.value.size ? `Scarica ${selezione.value.size}` : 'Scarica',
);

function toggle(url: string) {
  if (selezione.value.has(url)) selezione.value.delete(url);
  else selezione.value.add(url);
}
function tutteSelezionate(sez: Sezione): boolean {
  return sez.foto.every((f) => selezione.value.has(f.url));
}
function toggleSezione(sez: Sezione) {
  const spegni = tutteSelezionate(sez);
  sez.foto.forEach((f) => {
    if (spegni) selezione.value.delete(f.url);
    else selezione.value.add(f.url);
  });
}
function selezionaTutte() {
  tutte.value.forEach((f) => selezione.value.add(f.url));
}
function deselezionaTutte() {
  selezione.value.clear();
}

function reset() {
  errore.value = null;
}

/** Download uno alla volta: niente zip (nessuna dipendenza aggiunta), con
 *  una pausa breve fra i file perché i browser limitano i download a raffica. */
async function scarica() {
  const daScaricare = tutte.value.filter((f) => selezione.value.has(f.url));
  if (!daScaricare.length) return;
  scaricando.value = true;
  errore.value = null;
  let falliti = 0;
  for (const f of daScaricare) {
    try {
      await scaricaUrl(f.url, f.nomeFile);
    } catch {
      falliti += 1;
    }
    await new Promise((r) => setTimeout(r, 150));
  }
  scaricando.value = false;
  if (falliti) errore.value = `${falliti} foto non scaricate.`;
}
</script>

<style scoped>
.sf-card {
  width: 760px;
  max-width: 94vw;
  display: flex;
  flex-direction: column;
  max-height: 88vh;
}
.sf-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 8px;
}
.sf-title {
  font-family: var(--vp-font-display);
  font-size: 20px;
}
.sf-sub {
  font-size: 13px;
  color: var(--vp-ink-3);
  margin-top: 2px;
}
.sf-toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-top: 0;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--vp-paper-3);
}
.sf-count {
  font-size: 12.5px;
  color: var(--vp-ink-3);
  font-family: var(--vp-font-mono);
}
.sf-body {
  overflow-y: auto;
  flex: 1;
}
.sf-empty {
  padding: 24px 0;
  text-align: center;
  color: var(--vp-ink-3);
  font-size: 13.5px;
}
.sf-sez + .sf-sez {
  margin-top: 20px;
}
.sf-sez-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.sf-sez-nome {
  font-weight: 600;
  font-size: 14.5px;
}
.sf-sez-n {
  font-size: 11.5px;
  font-family: var(--vp-font-mono);
  color: var(--vp-ink-3);
  background: var(--vp-paper-2);
  border-radius: 999px;
  padding: 1px 8px;
}
.sf-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 8px;
}
.sf-thumb {
  position: relative;
  padding: 0;
  border: 2px solid transparent;
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  background: var(--vp-paper-2);
  aspect-ratio: 1 / 1;
}
.sf-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  opacity: 0.85;
  transition: opacity 0.15s;
}
.sf-thumb:hover img {
  opacity: 1;
}
.sf-thumb.on {
  border-color: var(--vp-terra);
}
.sf-thumb.on img {
  opacity: 1;
}
.sf-check {
  position: absolute;
  right: 5px;
  top: 5px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: rgba(20, 15, 10, 0.45);
}
.sf-thumb.on .sf-check {
  background: var(--vp-terra);
}
.sf-actions {
  border-top: 1px solid var(--vp-paper-3);
  gap: 8px;
}
.sf-err {
  font-size: 12.5px;
  color: var(--vp-clay);
  padding-left: 8px;
}
</style>
