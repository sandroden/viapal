"""Giro a secco su post veri salvati: classifica e compone senza toccare il browser.

    uv run python tests/prova_su_fixture.py [--componi]
"""
import argparse, json, sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import anthropic
from bot.classifier import analizza
from bot.composer import componi
from bot.config import carica


@dataclass
class Post:
    post_id: str; permalink: str; author_name: str | None
    author_url: str | None; text: str; troncato: bool = False


ap = argparse.ArgumentParser()
ap.add_argument("--componi", action="store_true")
args = ap.parse_args()

cfg = carica("~/.viapal-bot/config.toml")
client = anthropic.Anthropic()
posts = [Post(**p) for p in json.load(open(Path(__file__).parent.parent / "fixtures/posts.json"))]

print(f"{len(posts)} post · stanze libere: {[s.id for s in cfg.stanze_libere]}\n")
for p in posts:
    a = analizza(client, cfg, p)
    segno = "✅" if a.match else "  "
    tronc = " ✂️" if p.troncato else ""
    print(f"{segno} {a.intent:6} {a.tipo_immobile:16} {str(a.zona)[:22]:22} "
          f"budget={str(a.budget_max):5} {a.motivo[:70]}{tronc}")
    if a.match and args.componi:
        m = componi(client, cfg, p, a)
        print(f"     stanze: {a.stanze_compatibili}")
        print(f"     [pub] {m.commento_pubblico}")
        print(f"     [prv] " + m.privato.replace("\n", "\n           "))
        print()
