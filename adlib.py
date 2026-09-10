#!/usr/bin/env python3
"""Cliente de la Biblioteca de Anuncios de Meta a través de ScrapeCreators.

Es la única pieza que habla con una API. Se mantiene aparte del barrido para que
se pueda leer entera de una sentada y para que cambiar de proveedor de datos sea
tocar un archivo, no tres.

La Biblioteca **no publica inversión ni impresiones** de anuncios comerciales:
`spend`, `reach_estimate` e `impressions` vienen a nulo salvo en publicidad
política. Por eso lo único que se extrae aquí como señal de rendimiento son
`days_active` (días que el anuncio lleva corriendo) y `collation_count`
(variantes agrupadas bajo un mismo anuncio).

El parseo replica el del servidor MCP `facebook-ads-library-mcp` (MIT, Gala Labs),
reescrito aquí para que este repo no dependa de tenerlo instalado.
"""
import os
import time
from datetime import datetime

import requests

ADS_API = "https://api.scrapecreators.com/v1/facebook/adLibrary/company/ads"
SEARCH_API = "https://api.scrapecreators.com/v1/facebook/adLibrary/search/companies"

FORMATOS = {"IMAGE", "VIDEO", "DCO"}


class SinCreditos(RuntimeError):
    """ScrapeCreators devolvió 402: se acabaron los créditos de la cuenta."""


def api_key():
    """La key de ScrapeCreators, del entorno o del .env del repo."""
    if os.environ.get("SCRAPECREATORS_API_KEY"):
        return os.environ["SCRAPECREATORS_API_KEY"]

    env = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env):
        for linea in open(env, encoding="utf-8"):
            if linea.strip().startswith("SCRAPECREATORS_API_KEY="):
                clave = linea.split("=", 1)[1].strip().strip("'\"")
                if clave:
                    os.environ["SCRAPECREATORS_API_KEY"] = clave
                    return clave

    raise SystemExit(
        "Falta SCRAPECREATORS_API_KEY.\n"
        "Copia .env.example a .env y pon tu key de scrapecreators.com/dashboard"
    )


def _get(url, params):
    """GET con reintento corto: la API devuelve 500 esporádicos que se absorben solos."""
    cabeceras = {"x-api-key": api_key()}
    for intento in range(3):
        r = requests.get(url, headers=cabeceras, params=params, timeout=60)
        if r.status_code == 402:
            raise SinCreditos(
                "Créditos de ScrapeCreators agotados. Recarga en scrapecreators.com/dashboard"
            )
        if r.status_code < 500:
            break
        time.sleep(1.5 * (intento + 1))
    r.raise_for_status()
    return r.json()


def _dias_activo(inicio_ts, fin_ts):
    """Días que un anuncio lleva corriendo, desde sus timestamps crudos.

    Si sigue activo se usa hoy como final, para que un anuncio veterano lea como
    veterano y no como uno que termina hoy.
    """
    if not inicio_ts:
        return None
    try:
        inicio = datetime.fromtimestamp(inicio_ts)
        fin = min(datetime.fromtimestamp(fin_ts), datetime.now()) if fin_ts else datetime.now()
        return max((fin - inicio).days, 0)
    except (TypeError, ValueError, OSError):
        return None


def parsear(cuerpo):
    """Aplana la respuesta de la API a una lista de anuncios con los campos que usa el informe.

    Un anuncio DCO (varias tarjetas) sale como un anuncio por tarjeta, porque cada
    tarjeta es una creatividad distinta con su propio copy.
    """
    anuncios = []

    for ad in cuerpo.get("results", []):
        try:
            ad_id = ad.get("ad_archive_id")
            if not ad_id:
                continue

            snapshot = ad.get("snapshot", {}) or {}
            formato = snapshot.get("display_format")
            if formato not in FORMATOS:
                continue

            cuerpos = [(snapshot.get("body") or {}).get("text")]
            medios = []
            if formato == "IMAGE":
                imgs = snapshot.get("images") or []
                medios = [imgs[0].get("resized_image_url")] if imgs else []
            elif formato == "VIDEO":
                vids = snapshot.get("videos") or []
                medios = [vids[0].get("video_sd_url")] if vids else []
            elif formato == "DCO":
                cards = snapshot.get("cards") or []
                medios = [c.get("resized_image_url") for c in cards]
                cuerpos = [c.get("body") for c in cards]

            if not medios or not cuerpos:
                continue

            inicio = ad.get("start_date")
            fin = ad.get("end_date")

            for media_url, texto in zip(medios, cuerpos):
                if not media_url or not texto:
                    continue
                anuncios.append({
                    "ad_id": ad_id,
                    "start_date": datetime.fromtimestamp(inicio).isoformat() if inicio else None,
                    "end_date": datetime.fromtimestamp(fin).isoformat() if fin else None,
                    "media_url": media_url,
                    "media_type": formato,
                    "body": texto,
                    # Los dos únicos proxis de rendimiento que publica la Biblioteca.
                    "days_active": _dias_activo(inicio, fin),
                    "collation_count": ad.get("collation_count"),
                    "is_active": ad.get("is_active"),
                    "ad_library_url": ad.get("url") or f"https://www.facebook.com/ads/library?id={ad_id}",
                    "title": snapshot.get("title"),
                    "cta_text": snapshot.get("cta_text"),
                    "link_url": snapshot.get("link_url"),
                    "publisher_platform": ad.get("publisher_platform"),
                    "page_id": ad.get("page_id"),
                    "page_name": ad.get("page_name"),
                })
        except Exception:  # noqa: BLE001 — un anuncio raro no debe tumbar el barrido
            continue

    return anuncios


def anuncios_de(page_id, limite=250):
    """Pagina la API con su cursor y devuelve (anuncios, total_declarado, créditos).

    `total_declarado` viene de `searchResultsCount`: es el recuento real de la
    página sin truncar por el límite que pidamos, así que sirve para saber si
    nos hemos dejado cola sin traer.
    """
    anuncios, cursor, total, creditos = [], None, None, None

    while len(anuncios) < limite:
        params = {"pageId": page_id, "trim": "false"}
        if cursor:
            params["cursor"] = cursor

        cuerpo = _get(ADS_API, params)
        total = cuerpo.get("searchResultsCount", total)
        creditos = cuerpo.get("credits_remaining", creditos)
        anuncios.extend(a for a in parsear(cuerpo) if a.get("body"))

        cursor = cuerpo.get("cursor")
        if not cursor or not cuerpo.get("results"):
            break
        time.sleep(0.2)

    return anuncios[:limite], total, creditos


def buscar_paginas(nombre):
    """Resuelve un nombre de marca a páginas candidatas de Meta.

    Devuelve *candidatas*, no la respuesta. Los homónimos son la norma: "Sierra"
    devuelve el Sierra Club y "Crisp" una consultora de coaching. Hay que
    verificar cada una trayendo sus anuncios antes de meterla en el config.
    """
    cuerpo = _get(SEARCH_API, {"query": nombre})
    salida = []
    for p in cuerpo.get("searchResults", []) or []:
        salida.append({
            "page_id": p.get("page_id"),
            "nombre": p.get("name"),
            "categoria": p.get("category"),
            # El handle de Instagram es el mejor desempate: la página real de una
            # empresa suele traerlo, y el homónimo casi nunca.
            "instagram": p.get("ig_username"),
            "verificada": p.get("verification"),
            "likes": p.get("likes"),
            "tipo": p.get("entity_type"),
        })
    return salida


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("Uso: python adlib.py \"Nombre de la marca\"")

    for p in buscar_paginas(" ".join(sys.argv[1:])):
        print(f"{p['page_id']:>18}  {p['nombre'][:28]:28}  "
              f"{(p.get('categoria') or '—')[:26]:26}  "
              f"ig:{p.get('instagram') or '—'}")
