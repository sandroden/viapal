#!/usr/bin/env node
// Registratore CDP: cattura i frame della pagina attiva di un Chrome avviato
// con --remote-debugging-port e li monta in un mp4 a frame rate costante.
//
// Perché non `agent-browser record`: esce a 10 fps fissi. Lo screencast CDP
// manda un frame a ogni ridisegno (fino a 60/s) con il suo timestamp: qui li
// salviamo come JPEG e ffmpeg li ricompone rispettando i tempi reali.
//
// Uso: node registra.mjs <porta-cdp> <uscita.mp4> [fps]
// Si ferma con SIGINT/SIGTERM (o creando il file <uscita.mp4>.stop).

import { mkdtempSync, writeFileSync, existsSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

const [porta, uscita, fpsArg] = process.argv.slice(2);
if (!porta || !uscita || porta === '-h') {
  console.error('Uso: node registra.mjs <porta-cdp> <uscita.mp4> [fps=30]');
  process.exit(porta === '-h' ? 0 : 1);
}
const fps = Number(fpsArg ?? 30);

const targets = await (await fetch(`http://127.0.0.1:${porta}/json`)).json();
const pagina = targets.find((t) => t.type === 'page' && !t.url.startsWith('devtools://'));
if (!pagina) throw new Error('Nessuna pagina da registrare');

const dir = mkdtempSync(join(tmpdir(), 'registra-'));
const frames = []; // { file, ts }
const ws = new WebSocket(pagina.webSocketDebuggerUrl);
let id = 0;
const invia = (method, params = {}) => ws.send(JSON.stringify({ id: ++id, method, params }));

ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.method !== 'Page.screencastFrame') return;
  const { data, metadata, sessionId } = msg.params;
  const file = join(dir, `f${String(frames.length).padStart(6, '0')}.jpg`);
  writeFileSync(file, Buffer.from(data, 'base64'));
  frames.push({ file, ts: metadata.timestamp });
  invia('Page.screencastFrameAck', { sessionId });
};

await new Promise((ok) => (ws.onopen = ok));
invia('Page.startScreencast', { format: 'jpeg', quality: 95, everyNthFrame: 1 });
const inizio = Date.now() / 1000;
console.error(`registrazione avviata: ${pagina.url}`);

const fine = async () => {
  invia('Page.stopScreencast');
  await new Promise((ok) => setTimeout(ok, 200));
  ws.close();
  const stop = Date.now() / 1000;
  if (!frames.length) throw new Error('Nessun frame ricevuto');
  // Il primo frame copre anche l'attesa iniziale: la ripresa parte dall'avvio.
  const righe = ['ffconcat version 1.0'];
  frames.forEach((f, i) => {
    const t0 = i === 0 ? inizio : f.ts;
    const t1 = i + 1 < frames.length ? frames[i + 1].ts : stop;
    righe.push(`file '${f.file}'`, `duration ${Math.max(t1 - t0, 0.001).toFixed(4)}`);
  });
  righe.push(`file '${frames.at(-1).file}'`);
  const lista = join(dir, 'lista.txt');
  writeFileSync(lista, righe.join('\n'));
  const r = spawnSync('ffmpeg', [
    '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lista,
    '-vf', `fps=${fps},scale=trunc(iw/2)*2:trunc(ih/2)*2`,
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', uscita,
  ], { stdio: 'inherit' });
  rmSync(dir, { recursive: true, force: true });
  console.error(`salvato ${uscita}: ${frames.length} frame in ${(stop - inizio).toFixed(1)} s`);
  process.exit(r.status ?? 1);
};

process.on('SIGINT', fine);
process.on('SIGTERM', fine);
const stopFile = `${uscita}.stop`;
setInterval(() => {
  if (existsSync(stopFile)) { rmSync(stopFile); fine(); }
}, 200);
