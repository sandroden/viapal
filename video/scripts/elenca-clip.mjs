#!/usr/bin/env node
// Elenca le clip presenti in public/clips (e la musica opzionale) e scrive
// src/clips-disponibili.json, letto dal montaggio a build time.
// Una clip compare solo se ffprobe ne legge la durata (un file ancora in
// scrittura viene ignorato). Il file viene riscritto solo se cambia, così lo
// Studio non si ricarica a vuoto.
import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const RADICE = join(dirname(fileURLToPath(import.meta.url)), "..");
const DIR_CLIP = join(RADICE, "public", "clips");
const FILE_MUSICA = join(RADICE, "public", "musica.mp3");
const USCITA = join(RADICE, "src", "clips-disponibili.json");

function aiuto() {
  console.log(`Uso: node scripts/elenca-clip.mjs [-h] [-q]

Scrive src/clips-disponibili.json con le clip .mp4 leggibili in public/clips
(nome -> durata in secondi) e la presenza di public/musica.mp3.

  -h   mostra questo aiuto
  -q   silenzioso (nessun riepilogo)`);
}

function ffprobeDisponibile() {
  const r = spawnSync("ffprobe", ["-version"], { stdio: "ignore" });
  return r.status === 0;
}

function durataClip(percorso) {
  const r = spawnSync(
    "ffprobe",
    ["-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", percorso],
    { encoding: "utf8" },
  );
  const durata = Number.parseFloat((r.stdout ?? "").trim());
  return r.status === 0 && Number.isFinite(durata) && durata > 0 ? durata : undefined;
}

function elencaClip(conFfprobe) {
  if (!existsSync(DIR_CLIP)) return {};
  const clips = {};
  for (const nome of readdirSync(DIR_CLIP).sort()) {
    if (!nome.toLowerCase().endsWith(".mp4")) continue;
    const percorso = join(DIR_CLIP, nome);
    if (statSync(percorso).size === 0) continue;
    if (!conFfprobe) {
      clips[nome] = { durata: null };
      continue;
    }
    const durata = durataClip(percorso);
    if (durata !== undefined) clips[nome] = { durata: Math.round(durata * 1000) / 1000 };
  }
  return clips;
}

function scriviSeCambiato(contenuto) {
  const attuale = existsSync(USCITA) ? readFileSync(USCITA, "utf8") : "";
  if (attuale === contenuto) return false;
  writeFileSync(USCITA, contenuto);
  return true;
}

function main(argv) {
  if (argv.includes("-h") || argv.includes("--help")) return aiuto();
  const silenzioso = argv.includes("-q");
  const conFfprobe = ffprobeDisponibile();
  const dati = { clips: elencaClip(conFfprobe), musica: existsSync(FILE_MUSICA) };
  const cambiato = scriviSeCambiato(JSON.stringify(dati, null, 2) + "\n");
  if (silenzioso) return;
  if (!conFfprobe) console.warn("ffprobe non trovato: durate ignote, uso durataPrevista del manifest.");
  const nomi = Object.keys(dati.clips);
  console.log(
    `clip disponibili: ${nomi.length ? nomi.join(", ") : "nessuna"}` +
      ` | musica: ${dati.musica ? "sì" : "no"}` +
      (cambiato ? " (aggiornato)" : ""),
  );
}

main(process.argv.slice(2));
