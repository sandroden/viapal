"""Wrapper minimo su agent-browser (CLI). Solo lettura: apre, scrolla, legge.

Non esiste nessuna funzione che clicchi, scriva o invii — è una scelta, non
una dimenticanza: vedi i non-obiettivi in spec.md.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


class ErroreBrowser(RuntimeError):
    pass


@dataclass
class Browser:
    """Pilota agent-browser su un profilo Chrome persistente.

    Il profilo (non `--session-name`) conserva anche IndexedDB e service worker,
    dove Facebook tiene pezzi dell'identità di dispositivo: cambiarli a sessione
    già stabilita è uno dei segnali che fanno scattare i checkpoint.

    Attenzione: Chrome tiene un lock sulla directory del profilo. La finestra
    headed usata per il login va chiusa prima di far girare il loop.
    """

    profilo: str
    headed: bool = False
    user_agent: str | None = None
    timeout: int = 120

    def _cmd(self, *args: str) -> list[str]:
        cmd = ["agent-browser", "--profile", self.profilo, "--json"]
        if self.headed:
            cmd.append("--headed")
        if self.user_agent:
            cmd += ["--user-agent", self.user_agent]
        return cmd + list(args)

    def _esegui(self, *args: str):
        proc = subprocess.run(
            self._cmd(*args), capture_output=True, text=True, timeout=self.timeout
        )
        if proc.returncode != 0:
            raise ErroreBrowser(f"agent-browser {args[0]}: {proc.stderr.strip()[:400]}")
        try:
            risposta = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise ErroreBrowser(f"output non JSON da {args[0]}: {proc.stdout[:200]}") from exc
        if not risposta.get("success"):
            raise ErroreBrowser(f"{args[0]} fallito: {risposta.get('error')}")
        return risposta.get("data", {}).get("result")

    def apri(self, url: str) -> None:
        self._esegui("open", url)

    def valuta(self, js: str):
        return self._esegui("eval", js)

    def scorri(self, pixel: int = 1200) -> None:
        """Scroll nativo (rotella). Quello via JS non muove il feed di Facebook.

        Pixel negativi risalgono: serve al ripasso che recupera i permalink.
        """
        verso = "up" if pixel < 0 else "down"
        self._esegui("scroll", verso, str(abs(pixel)))

    def chiudi(self) -> None:
        subprocess.run(["agent-browser", "close"], capture_output=True, timeout=30)
