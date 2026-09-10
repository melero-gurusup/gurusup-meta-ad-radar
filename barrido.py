#!/usr/bin/env python3
"""Barre la Biblioteca de Anuncios de Meta sobre el set de competidores del config.

Guarda un snapshot fechado en data/ y deja el consolidado en data/ultimo.json,
que es lo que consume informe.py. Comparar dos snapshots es lo que permite decir
"esto ha cambiado desde el barrido anterior", que es la mitad del valor del radar.

Uso:  python barrido.py [--limit 250] [--marca "Nombre"]
"""
import argparse
import glob
import json
import os
from datetime import datetime, timezone

import adlib

RAIZ = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(RAIZ, "config.json")


def cargar_config():
    if not os.path.exists(CONFIG):
        raise SystemExit(
            "No hay config.json.\n"
            "Copia config.example.json a config.json y pon tus competidores,\n"
            "o pídeselo a Claude: la skill radar-competencia lo monta preguntando."
        )
    with open(CONFIG, encoding="utf-8") as fh:
        cfg = json.load(fh)
    if not cfg.get("competidores"):
        raise SystemExit("config.json no tiene ningún competidor en 'competidores'.")
    return cfg


def snapshot_anterior():
    """El snapshot más reciente que no sea el que estamos escribiendo hoy."""
    hoy = datetime.now().strftime("%Y-%m-%d")
    previos = sorted(
        f for f in glob.glob(os.path.join(RAIZ, "data", "snapshot-*.json"))
        if hoy not in os.path.basename(f)
    )
    if not previos:
        return None
    with open(previos[-1], encoding="utf-8") as fh:
        return json.load(fh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=250, help="anuncios máximos por marca")
    ap.add_argument("--marca", action="append", help="barrer solo estas marcas (repetible)")
    args = ap.parse_args()

    cfg = cargar_config()
    objetivo = cfg["competidores"]
    if args.marca:
        pedidas = [m.lower() for m in args.marca]
        objetivo = [c for c in objetivo if any(p in c["nombre"].lower() for p in pedidas)]
        if not objetivo:
            raise SystemExit(f"Ninguna marca del config coincide con {args.marca}")

    marcas, creditos = [], None

    for c in objetivo:
        print(f"  {c['nombre'][:24]:24}", end="", flush=True)
        try:
            ads, total, creditos = adlib.anuncios_de(c["page_id"], args.limit)
        except adlib.SinCreditos as e:
            raise SystemExit(f"\n{e}")
        except Exception as e:  # noqa: BLE001 — una marca caída no debe tumbar el barrido
            print(f"  ERROR: {e}")
            marcas.append({**c, "anuncios": [], "total_api": None, "error": str(e)})
            continue

        truncado = total is not None and len(ads) < total
        print(f"  {len(ads):>3} anuncios"
              + (f"  (de {total} que declara la API)" if truncado else ""))
        marcas.append({**c, "anuncios": ads, "total_api": total, "truncado": truncado,
                       "page_name_real": ads[0].get("page_name") if ads else None})

    snap = {
        "fecha": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "limite_consulta": args.limit,
        "credits_remaining": creditos,
        "marcas": marcas,
        "sin_pagina_identificada": cfg.get("sin_pagina_identificada", []),
    }

    os.makedirs(os.path.join(RAIZ, "data"), exist_ok=True)
    fecha = datetime.now().strftime("%Y-%m-%d")
    for destino in (f"data/snapshot-{fecha}.json", "data/ultimo.json"):
        with open(os.path.join(RAIZ, destino), "w", encoding="utf-8") as fh:
            json.dump(snap, fh, ensure_ascii=False)

    anterior = os.path.join(RAIZ, "data", "anterior.json")
    prev = snapshot_anterior()
    if prev:
        with open(anterior, "w", encoding="utf-8") as fh:
            json.dump(prev, fh, ensure_ascii=False)
        print(f"\nComparando contra el barrido del {prev['fecha'][:10]}")
    else:
        if os.path.exists(anterior):
            os.remove(anterior)
        print("\nPrimer barrido: no hay anterior con el que comparar")

    total = sum(len(m["anuncios"]) for m in marcas)
    activas = sum(1 for m in marcas if m["anuncios"])
    print(f"{total} anuncios de {activas} marcas con paid activo (de {len(marcas)} rastreadas)")
    if creditos is not None:
        print(f"Créditos restantes en ScrapeCreators: {creditos}")


if __name__ == "__main__":
    main()
