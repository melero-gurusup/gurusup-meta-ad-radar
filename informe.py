#!/usr/bin/env python3
"""Genera out/radar.html a partir del último barrido, comparado con el anterior.

Uso:  python informe.py [--top 14]
"""
import argparse
import base64
import hashlib
import html
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime

RAIZ = os.path.dirname(os.path.abspath(__file__))
MEDIA = os.path.join(RAIZ, "media")
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

REPO = "github.com/melero-gurusup/gurusup-meta-ad-radar"

# Un color por marca, en el orden en que están en config.json. Cada par es
# (claro, oscuro): el segundo se usa en tema oscuro para que el contraste
# aguante contra el fondo. Con más de doce marcas los colores se repiten; no
# es grave, porque el color acompaña al nombre y nunca lo sustituye.
PALETA = [
    ("#4A46C8", "#9C99F0"),
    ("#E2701C", "#F2A46B"),
    ("#0E7490", "#61C5D2"),
    ("#B5327A", "#E88AC0"),
    ("#2563A8", "#7FB3EF"),
    ("#A33A2C", "#F09A8C"),
    ("#7A6A1F", "#D6C264"),
    ("#3F7A3A", "#8FD08A"),
    ("#8A4FBF", "#C4A0E8"),
    ("#C43F5C", "#F095A8"),
    ("#146B63", "#5CC4B8"),
    ("#8A5A1A", "#D2A06A"),
]


# ---------------------------------------------------------------- miniaturas
def miniatura(ad):
    """Devuelve un data URI de 320px de ancho, o None si no se puede obtener.

    Las imágenes se redimensionan; de los vídeos se extrae el primer fotograma.
    Todo queda cacheado en media/ para que un barrido posterior no re-descargue.
    Necesita ffmpeg en el PATH; sin él, el informe sale con las tarjetas sin
    miniatura, que sigue siendo legible.
    """
    url = ad.get("media_url")
    if not url:
        return None
    os.makedirs(MEDIA, exist_ok=True)
    clave = hashlib.sha1(url.encode()).hexdigest()[:16]
    destino = os.path.join(MEDIA, f"{clave}.jpg")

    if not os.path.exists(destino):
        cmd = ["ffmpeg", "-loglevel", "error", "-y"]
        if ad.get("media_type") == "VIDEO":
            cmd += ["-ss", "1"]
        cmd += ["-i", url, "-frames:v", "1", "-vf", "scale=320:-2", "-q:v", "6", destino]
        try:
            subprocess.run(cmd, check=True, timeout=90,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return None
    if not os.path.exists(destino) or os.path.getsize(destino) == 0:
        return None
    with open(destino, "rb") as fh:
        return "data:image/jpeg;base64," + base64.b64encode(fh.read()).decode()


def logo_svg():
    """El lockup de marca, inline y en currentColor.

    Heredando el color del texto, el mismo archivo sirve en tema claro y oscuro.
    Sustituye assets/logo.svg por el tuyo si prefieres tu marca en la cabecera.
    """
    ruta = os.path.join(RAIZ, "assets", "logo.svg")
    if not os.path.exists(ruta):
        return ""
    svg = open(ruta, encoding="utf-8").read()
    svg = re.sub(r'fill="(black|#000000|#000)"', 'fill="currentColor"', svg)
    svg = re.sub(r"<svg\b[^>]*?(?=\sviewBox)", '<svg class="logo" role="img" aria-label="Logo"',
                 svg, count=1)
    return svg


# ---------------------------------------------------------------- agregación
def normaliza(texto):
    return re.sub(r"\s+", " ", (texto or "")).strip()


def agrupa_mensajes(anuncios):
    """Un grupo por copy: reúne sus anuncios, días en activo y variantes.

    Agrupar por texto y no por ad_id es lo que convierte "185 anuncios" en
    "12 mensajes", que es la unidad con la que de verdad se piensa.
    """
    grupos = defaultdict(lambda: {"anuncios": [], "ad_ids": {}})
    for a in anuncios:
        cuerpo = normaliza(a.get("body"))
        if not cuerpo:
            continue
        g = grupos[cuerpo]
        g["anuncios"].append(a)
        g["ad_ids"][a.get("ad_id")] = a.get("collation_count") or 1

    salida = []
    for cuerpo, g in grupos.items():
        dias = [a["days_active"] for a in g["anuncios"] if a.get("days_active") is not None]
        arranques = sorted(a["start_date"][:10] for a in g["anuncios"] if a.get("start_date"))
        con_img = next((a for a in g["anuncios"] if a.get("media_type") != "VIDEO"), None)
        salida.append({
            "copy": cuerpo,
            "n_anuncios": len(g["anuncios"]),
            "n_ads_unicos": len(g["ad_ids"]),
            "variantes": sum(g["ad_ids"].values()),
            "dias_max": max(dias) if dias else 0,
            "arranque": arranques[0] if arranques else None,
            "formatos": Counter(a.get("media_type") for a in g["anuncios"]),
            "titulo": next((a.get("title") for a in g["anuncios"] if a.get("title")), None),
            "cta": next((a.get("cta_text") for a in g["anuncios"] if a.get("cta_text")), None),
            "landing": next((a.get("link_url") for a in g["anuncios"] if a.get("link_url")), None),
            "plataformas": sorted({p for a in g["anuncios"]
                                   for p in (a.get("publisher_platform") or [])}),
            "url": next((a.get("ad_library_url") for a in g["anuncios"] if a.get("ad_library_url")), None),
            "muestra": con_img or g["anuncios"][0],
        })
    return sorted(salida, key=lambda g: (-g["dias_max"], -g["variantes"]))


def resumen_marca(m):
    ads = m["anuncios"]
    dias = [a["days_active"] for a in ads if a.get("days_active") is not None]
    return {
        "nombre": m["nombre"], "page_id": m["page_id"], "web": m.get("web"),
        "verificado": m.get("verificado"), "page_name_real": m.get("page_name_real"),
        "error": m.get("error"), "truncado": m.get("truncado"),
        "total_api": m.get("total_api"),
        "n": len(ads),
        "formatos": Counter(a.get("media_type") for a in ads),
        "copys": len({normaliza(a.get("body")) for a in ads if normaliza(a.get("body"))}),
        "dias_max": max(dias) if dias else 0,
        "dias_medio": round(sum(dias) / len(dias)) if dias else 0,
        "grupos": agrupa_mensajes(ads),
    }


# ---------------------------------------------------------------- plantilla
def fecha_larga(iso):
    d = datetime.fromisoformat(iso)
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def delta_html(ahora, antes):
    if antes is None:
        return '<span class="d none">nuevo en el radar</span>'
    diff = ahora - antes
    if diff == 0:
        return '<span class="d flat">sin cambio</span>'
    signo = "+" if diff > 0 else "−"
    cls = "up" if diff > 0 else "down"
    return f'<span class="d {cls}">{signo}{abs(diff)}</span>'


def css_paleta(n_marcas):
    """Variables y reglas de color, una por marca del config."""
    usadas = range(min(max(n_marcas, 1), len(PALETA)))
    claro = " ".join(f"--m{i}:{PALETA[i][0]};" for i in usadas)
    oscuro = " ".join(f"--m{i}:{PALETA[i][1]};" for i in usadas)
    reglas = "\n".join(f".m{i} .dot{{background:var(--m{i})}} "
                       f".ad.m{i} .brand{{color:var(--m{i})}}" for i in usadas)
    return (f":root{{{claro}}}\n"
            f'@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{{oscuro}}}}}\n'
            f':root[data-theme="dark"]{{{oscuro}}}\n{reglas}\n')


CSS = '''
:root{
  --sans:'Geist',ui-sans-serif,system-ui,sans-serif;
  --mono:'Geist Mono',ui-monospace,SFMono-Regular,Menlo,monospace;
  --bg:#FCFCF8; --card:#FFFFFF; --well:#F1F1EA;
  --ink:#1D1E1A; --dim:#6E6C60; --line:#E5E5E5;
  --green:#2ECF8F; --green-ink:#1B8A5E;
  --zero:#BEBBB2; --up:#15803D; --down:#C4432E;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#1D1E1A; --card:#24261F; --well:#2E3027;
  --ink:#F8F9F2; --dim:#BEBBB2; --line:#34362C;
  --green-ink:#2ECF8F;
  --zero:#4A4C42; --up:#34D399; --down:#FF9F8F;
}}
:root[data-theme="dark"]{
  --bg:#1D1E1A; --card:#24261F; --well:#2E3027;
  --ink:#F8F9F2; --dim:#BEBBB2; --line:#34362C;
  --green-ink:#2ECF8F;
  --zero:#4A4C42; --up:#34D399; --down:#FF9F8F;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
  font-size:16px;line-height:24px;-webkit-font-smoothing:antialiased}
.shell{max-width:1200px;margin:0 auto;border-left:1px solid var(--line);
  border-right:1px solid var(--line);background:var(--bg)}
section{padding:32px 40px;border-bottom:1px solid var(--line)}
h1,h2{margin:0;text-wrap:balance}
h1{font-size:48px;line-height:52px;font-weight:600;letter-spacing:-.02em;max-width:24ch}
h2{font-size:24px;line-height:32px;font-weight:600;margin-bottom:8px}
h3{font-family:var(--mono);font-size:14px;line-height:20px;font-weight:500;
  text-transform:uppercase;letter-spacing:.08em;color:var(--dim);margin:0 0 12px}
p{margin:0}
.lede{font-size:16px;line-height:24px;color:var(--dim);max-width:70ch;margin-top:16px}
.sub{font-size:14px;line-height:20px;color:var(--dim);max-width:74ch;margin-bottom:24px}
a{color:var(--green-ink)}
a:focus-visible,.shot:focus-visible{outline:2px solid var(--green-ink);outline-offset:2px}

.brandbar{display:flex;align-items:center;gap:16px;padding:16px 40px;
  border-bottom:1px solid var(--line)}
.brandbar .logo{height:24px;width:auto;display:block;color:var(--ink);flex:none}
.brandbar .rule{width:1px;height:20px;background:var(--line);flex:none}
.brandbar .name{font-family:var(--mono);font-size:14px;font-weight:500;
  text-transform:uppercase;letter-spacing:.1em;color:var(--dim)}
@media (max-width:860px){
  .brandbar{padding:12px 20px;gap:12px}
  .brandbar .logo{height:20px}
  .brandbar .name{font-size:12px;letter-spacing:.08em}
}
.brandbar .aged{margin-left:auto;font-family:var(--mono);font-size:12px;
  color:var(--dim);white-space:nowrap}
.meta{display:flex;flex-wrap:wrap;margin-top:32px;border-top:1px solid var(--line);
  border-left:1px solid var(--line)}
.meta div{flex:1 1 150px;padding:12px 16px;border-right:1px solid var(--line);
  border-bottom:1px solid var(--line)}
.meta dt{font-family:var(--mono);font-size:12px;line-height:16px;text-transform:uppercase;
  letter-spacing:.08em;color:var(--dim);margin:0}
.meta dd{font-family:var(--mono);font-size:24px;line-height:32px;margin:4px 0 0;
  font-variant-numeric:tabular-nums}

table{width:100%;border-collapse:collapse;font-size:14px;line-height:20px}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--line)}
thead th{font-family:var(--mono);font-size:12px;line-height:16px;text-transform:uppercase;
  letter-spacing:.08em;color:var(--dim);font-weight:500}
tbody th{font-weight:400}
td.num{font-family:var(--mono);font-variant-numeric:tabular-nums;width:70px}
td.bar{width:32%;padding-right:24px}
td.bar span{display:block;height:8px;background:var(--zero)}
tr.on td.bar span{background:var(--green)}
tr.on th,tr.on td.num{font-weight:500}
td.dl{width:120px}
.d{font-family:var(--mono);font-size:12px;letter-spacing:.04em}
.d.up{color:var(--up)} .d.down{color:var(--down)} .d.flat,.d.none{color:var(--dim)}
td.state{font-family:var(--mono);font-size:12px;text-transform:uppercase;
  letter-spacing:.06em;color:var(--dim);width:130px}

.ads{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
  border-top:1px solid var(--line);border-left:1px solid var(--line)}
.ad{display:flex;flex-direction:column;border-right:1px solid var(--line);
  border-bottom:1px solid var(--line);background:var(--card)}
.ad .shot{position:relative;display:flex;align-items:center;justify-content:center;
  background:var(--well);min-height:210px;padding:16px;text-decoration:none;
  border-bottom:1px solid var(--line)}
.ad .shot img{display:block;max-width:100%;max-height:280px;height:auto}
.ad .shot .sinimg{font-family:var(--mono);font-size:12px;color:var(--dim);
  text-transform:uppercase;letter-spacing:.06em}
.ad .shot .go{position:absolute;left:0;right:0;bottom:0;padding:6px 12px;
  font-family:var(--mono);font-size:12px;color:#1D1E1A;background:var(--green);
  opacity:0;transition:opacity .12s}
.ad .shot:hover .go,.ad .shot:focus-visible .go{opacity:1}
@media (prefers-reduced-motion:reduce){.ad .shot .go{transition:none}}
.ad .body{padding:16px;display:flex;flex-direction:column;gap:8px;flex:1}
.ad .head{display:flex;align-items:baseline;justify-content:space-between;gap:12px}
.ad .brand{font-family:var(--mono);font-size:12px;font-weight:500;
  text-transform:uppercase;letter-spacing:.06em}
.ad .live{font-family:var(--mono);font-size:12px;color:var(--ink);
  background:var(--well);padding:2px 8px;white-space:nowrap;
  font-variant-numeric:tabular-nums}
.ad .tit{font-weight:600;font-size:16px;line-height:24px}
.ad .copy{font-size:14px;line-height:20px;color:var(--dim)}
.facts{display:grid;grid-template-columns:auto 1fr;gap:2px 12px;margin:8px 0 0;
  padding-top:12px;border-top:1px solid var(--line)}
.facts .k{font-family:var(--mono);font-size:12px;line-height:18px;color:var(--dim);
  text-transform:uppercase;letter-spacing:.05em}
.facts .v{font-family:var(--mono);font-size:12px;line-height:18px;
  font-variant-numeric:tabular-nums;overflow-wrap:anywhere}

.msg{border-top:1px solid var(--line)}
.msg li{list-style:none;display:grid;grid-template-columns:56px 64px 1fr;gap:16px;
  padding:14px 0;border-bottom:1px solid var(--line);align-items:start}
.msg ul{margin:0;padding:0}
.msg .n,.msg .dias{font-family:var(--mono);font-size:14px;color:var(--dim);
  font-variant-numeric:tabular-nums;padding-top:1px}
.msg .t{font-size:14px;line-height:20px}
.two{display:grid;grid-template-columns:1fr 1fr;border-top:1px solid var(--line);
  border-left:1px solid var(--line)}
.two>div{padding:20px 24px;border-right:1px solid var(--line);
  border-bottom:1px solid var(--line)}
.who{display:flex;align-items:baseline;gap:12px;margin-bottom:4px}
.who b{font-size:24px;line-height:32px;font-weight:600}
.who .dot{width:8px;height:8px;flex:none;background:var(--dim)}
.who em{font-family:var(--mono);font-size:12px;font-style:normal;color:var(--dim);
  text-transform:uppercase;letter-spacing:.06em}
ol.reads{list-style:none;margin:0;padding:0;counter-reset:r;border-top:1px solid var(--line)}
ol.reads li{counter-increment:r;display:grid;grid-template-columns:44px 1fr;gap:16px;
  padding:20px 0;border-bottom:1px solid var(--line)}
ol.reads li::before{content:counter(r,decimal-leading-zero);font-family:var(--mono);
  font-size:14px;color:var(--dim)}
ol.reads b{display:block;font-weight:600;margin-bottom:4px}
ol.reads p{font-size:14px;line-height:20px;color:var(--dim);max-width:72ch}
code{font-family:var(--mono);font-size:13px;background:var(--well);padding:1px 5px}
footer{padding:24px 40px;font-family:var(--mono);font-size:12px;line-height:20px;color:var(--dim)}
.scroll{overflow-x:auto}
@media (max-width:860px){
  section{padding:24px 20px} h1{font-size:30px;line-height:36px}
  .two{grid-template-columns:1fr} td.bar{display:none}
  .msg li{grid-template-columns:48px 56px 1fr;gap:12px}
  footer{padding:20px}
}
'''


def bloque_grupo(g, marca, clase):
    img = miniatura(g["muestra"])
    dias = g["dias_max"]
    etiqueta_dias = "1 día" if dias == 1 else f"{dias} días"
    fmt = " · ".join(f"{k.lower()}" for k, _ in g["formatos"].most_common())
    visual = (f'<img src="{img}" alt="Creatividad de {html.escape(marca)}" loading="lazy">'
              if img else '<span class="sinimg">sin miniatura</span>')
    titulo = f'<p class="tit">{html.escape(g["titulo"])}</p>' if g.get("titulo") else ""
    landing = ""
    if g.get("landing"):
        corto = re.sub(r"^https?://(www\.)?", "", g["landing"]).split("?")[0][:44]
        landing = f'<span class="k">Landing</span><span class="v">{html.escape(corto)}</span>'
    cta = f'<span class="k">CTA</span><span class="v">{html.escape(g["cta"])}</span>' if g.get("cta") else ""
    plat = ""
    if g.get("plataformas"):
        plat = ('<span class="k">Ubicación</span><span class="v">'
                + ", ".join(p.capitalize() for p in g["plataformas"]) + "</span>")
    enlace = g.get("url") or "https://www.facebook.com/ads/library/"
    return f'''<article class="ad {clase}">
  <a class="shot" href="{html.escape(enlace)}" target="_blank" rel="noopener"
     title="Abrir en la Biblioteca de Anuncios de Meta">{visual}
     <span class="go">Ver en la Ad Library ↗</span></a>
  <div class="body">
    <div class="head">
      <span class="brand">{html.escape(marca)}</span>
      <span class="live">{etiqueta_dias} en activo</span>
    </div>
    {titulo}
    <p class="copy">{html.escape(g["copy"][:230])}{"…" if len(g["copy"]) > 230 else ""}</p>
    <dl class="facts">
      <span class="k">Variantes</span><span class="v">{g["variantes"]}</span>
      <span class="k">Anuncios</span><span class="v">{g["n_ads_unicos"]}</span>
      <span class="k">Formato</span><span class="v">{fmt}</span>
      {cta}{plat}{landing}
      <span class="k">Arrancó</span><span class="v">{g["arranque"] or "—"}</span>
    </dl>
  </div>
</article>'''


def lecturas_html():
    """Renderiza lecturas.md: el análisis lo escribe una persona, no el barrido."""
    ruta = os.path.join(RAIZ, "lecturas.md")
    if not os.path.exists(ruta):
        return ""
    bloques, titulo, cuerpo = [], None, []
    for linea in open(ruta, encoding="utf-8"):
        if linea.startswith("## "):
            if titulo:
                bloques.append((titulo, " ".join(cuerpo).strip()))
            titulo, cuerpo = linea[3:].strip(), []
        elif linea.strip() and not linea.startswith("<!--"):
            cuerpo.append(linea.strip())
    if titulo:
        bloques.append((titulo, " ".join(cuerpo).strip()))
    if not bloques:
        return ""
    items = "".join(f'<li><div><b>{html.escape(t)}</b><p>{html.escape(c)}</p></div></li>'
                    for t, c in bloques)
    return f"""<section>
  <h2>Lo que esto significa para nuestro paid</h2>
  <p class="sub">Escrito a mano en <code>lecturas.md</code>. El barrido trae los datos;
  esta parte es criterio y hay que reescribirla cuando los datos cambien.</p>
  <ol class="reads">{items}</ol>
</section>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=14,
                    help="cuántas creatividades mostrar en el ranking de longevidad")
    args = ap.parse_args()

    ruta = os.path.join(RAIZ, "data", "ultimo.json")
    if not os.path.exists(ruta):
        raise SystemExit("No hay data/ultimo.json. Corre barrido.py primero.")
    snap = json.load(open(ruta, encoding="utf-8"))

    cfg_ruta = os.path.join(RAIZ, "config.json")
    cfg = json.load(open(cfg_ruta, encoding="utf-8")) if os.path.exists(cfg_ruta) else {}
    ajustes = cfg.get("informe", {})
    titulo_doc = ajustes.get("titulo") or "Radar Meta de la competencia"
    etiqueta = ajustes.get("etiqueta") or "Meta Ad Radar"
    categoria = ajustes.get("categoria") or "tu categoría"

    ruta_prev = os.path.join(RAIZ, "data", "anterior.json")
    prev = json.load(open(ruta_prev, encoding="utf-8")) if os.path.exists(ruta_prev) else None
    prev_n = {m["page_id"]: len(m["anuncios"]) for m in prev["marcas"]} if prev else {}

    marcas = [resumen_marca(m) for m in snap["marcas"]]
    # El color se fija por posición en el config, no por actividad: así una marca
    # conserva su color entre barridos aunque suba o baje en la tabla.
    color = {m["nombre"]: f"m{i % len(PALETA)}" for i, m in enumerate(marcas)}

    activas = [m for m in marcas if m["n"]]
    activas.sort(key=lambda m: -m["n"])
    inactivas = [m for m in marcas if not m["n"]]

    # ---- ranking de longevidad, mezclando marcas
    ranking = []
    for m in activas:
        for g in m["grupos"]:
            ranking.append((g, m["nombre"]))
    ranking.sort(key=lambda x: (-x[0]["dias_max"], -x[0]["variantes"]))
    ranking = ranking[:args.top]

    total = sum(m["n"] for m in marcas)
    copys = sum(m["copys"] for m in marcas)
    veterano = ranking[0][0]["dias_max"] if ranking else 0

    # ---- tabla del radar
    filas = ""
    tope = max((m["n"] for m in marcas), default=1) or 1
    for m in activas + inactivas:
        ancho = m["n"] / tope * 100 if m["n"] else 0
        if m["error"]:
            estado, val = "error de API", "—"
        elif m["n"]:
            estado, val = "activo", str(m["n"])
        else:
            estado, val = "cero", "0"
        aviso = ""
        if m["page_name_real"] and m["page_name_real"].lower() not in m["nombre"].lower():
            aviso = f' <span class="d none">página: {html.escape(m["page_name_real"])}</span>'
        filas += (f'<tr class="{"on" if m["n"] else ""}">'
                  f'<th scope="row">{html.escape(m["nombre"])}{aviso}</th>'
                  f'<td class="num">{val}</td>'
                  f'<td class="dl">{delta_html(m["n"], prev_n.get(m["page_id"]))}</td>'
                  f'<td class="bar"><span style="width:{ancho:.1f}%"></span></td>'
                  f'<td class="num">{m["dias_max"] or "—"}</td>'
                  f'<td class="state">{estado}</td></tr>\n')

    for s in snap.get("sin_pagina_identificada", []):
        filas += (f'<tr><th scope="row">{html.escape(s["nombre"])}</th>'
                  f'<td class="num">—</td><td class="dl"></td><td class="bar"></td>'
                  f'<td class="num">—</td><td class="state">sin página</td></tr>\n')

    # ---- mensajería por marca
    columnas = ""
    for m in activas:
        items = ""
        for g in m["grupos"][:8]:
            items += (f'<li><span class="n">{g["variantes"]} var.</span>'
                      f'<span class="dias">{g["dias_max"]} d</span>'
                      f'<span class="t">{html.escape(g["copy"][:200])}'
                      f'{"…" if len(g["copy"]) > 200 else ""}</span></li>')
        fmt = " · ".join(f"{k.lower()} {v}" for k, v in m["formatos"].most_common())
        columnas += (f'<div class="{color[m["nombre"]]}"><div class="who"><span class="dot"></span>'
                     f'<b>{html.escape(m["nombre"])}</b>'
                     f'<em>{m["n"]} anuncios · {m["copys"]} copys</em></div>'
                     f'<p class="sub">{fmt}. Media de {m["dias_medio"]} días en activo, '
                     f'el más veterano {m["dias_max"]}.</p>'
                     f'<div class="msg"><ul>{items}</ul></div></div>')
    if len(activas) % 2:
        columnas += "<div></div>"

    tarjetas = "".join(bloque_grupo(g, marca, color[marca]) for g, marca in ranking)

    fecha = fecha_larga(snap["fecha"])
    comparativa = (f'Comparado con el barrido del {fecha_larga(prev["fecha"])}.'
                   if prev else "Primer barrido: todavía no hay uno anterior con el que comparar.")
    truncadas = [m["nombre"] for m in activas if m.get("truncado")]
    nota_trunc = (f' {", ".join(truncadas)} llega al tope de {snap["limite_consulta"]} '
                  f"que pidió la consulta, así que su cifra real es mayor." if truncadas else "")

    doc = f'''<title>{html.escape(titulo_doc)}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap">
<style>{CSS}{css_paleta(len(marcas))}</style>
<div class="shell">

<header class="brandbar">
  {logo_svg()}
  <span class="rule"></span>
  <span class="name">{html.escape(etiqueta)}</span>
  <span class="aged">Barrido del {datetime.fromisoformat(snap["fecha"]).strftime("%d/%m/%Y")}</span>
</header>

<section>
  <h1>{len(activas)} de {len(marcas)} competidores están comprando Meta ahora mismo</h1>
  <p class="lede">Barrido de la Biblioteca de Anuncios de Meta sobre {html.escape(categoria)}.
  La biblioteca no publica inversión ni impresiones de anuncios comerciales, así que
  aquí la señal de que algo les funciona son los <strong>días que un anuncio lleva corriendo</strong>
  y el <strong>número de variantes</strong> que le han montado detrás. {comparativa}</p>
  <dl class="meta">
    <div><dt>Barrido</dt><dd>{datetime.fromisoformat(snap["fecha"]).strftime("%d/%m/%y")}</dd></div>
    <div><dt>Marcas rastreadas</dt><dd>{len(marcas)}</dd></div>
    <div><dt>Con paid activo</dt><dd>{len(activas)}</dd></div>
    <div><dt>Anuncios</dt><dd>{total}</dd></div>
    <div><dt>Copys únicos</dt><dd>{copys}</dd></div>
    <div><dt>El más veterano</dt><dd>{veterano} d</dd></div>
  </dl>
</section>

<section>
  <h2>El radar</h2>
  <p class="sub">Anuncios activos por página, cambio respecto al barrido anterior y días del
  anuncio más veterano de cada marca.{nota_trunc}</p>
  <div class="scroll"><table>
    <thead><tr><th>Página</th><th>Anuncios</th><th>Cambio</th><th></th>
    <th>Días máx.</th><th>Estado</th></tr></thead>
    <tbody>
{filas}    </tbody>
  </table></div>
</section>

<section>
  <h2>Los que llevan más tiempo corriendo</h2>
  <p class="sub">Ordenados por días en activo, que es el mejor indicador disponible de que un
  anuncio está rindiendo: nadie deja corriendo semanas algo que no convierte. Cada creatividad
  abre su ficha en la Biblioteca de Anuncios de Meta.</p>
  <div class="ads">{tarjetas}</div>
</section>

<section>
  <h2>Cómo hablan</h2>
  <p class="sub">Por marca, sus mensajes ordenados por longevidad. A la izquierda, variantes
  montadas sobre ese mensaje; después, días que lleva el más antiguo.</p>
  <div class="two">{columnas}</div>
</section>

{lecturas_html()}
<footer>
  Biblioteca de Anuncios de Meta vía ScrapeCreators · barrido del {fecha} ·
  {snap.get("credits_remaining") or "?"} créditos restantes.
  Las creatividades son de sus titulares y se reproducen para análisis competitivo.<br>
  Meta Ad Radar, hecho por <a href="https://gurusup.com">GuruSup</a> ·
  <a href="https://{REPO}">{REPO}</a> · Regenerar: <code>/radar-competencia</code>
</footer>
</div>
'''

    os.makedirs(os.path.join(RAIZ, "out"), exist_ok=True)
    salida = os.path.join(RAIZ, "out", "radar.html")
    with open(salida, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"{salida}  ({len(doc) // 1024} KB)")
    print(f"{len(activas)} marcas activas · {total} anuncios · {len(ranking)} creatividades en el ranking")


if __name__ == "__main__":
    main()
