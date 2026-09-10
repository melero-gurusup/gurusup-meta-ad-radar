---
name: radar-competencia
description: Barre la Biblioteca de Anuncios de Meta sobre un set de competidores y publica un informe de inteligencia competitiva con días en activo, variantes y enlace a la ficha de cada anuncio. Usar cuando pidan "radar de competencia", "actualiza el radar", "qué está anunciando la competencia", "analiza los anuncios de X", "qué creatividades tiene <marca>", "mira la Ad Library de", "añade un competidor al radar", "qué ha cambiado desde el último barrido", o cualquier variación sobre revisar el paid de la competencia en Meta.
---

# Radar Meta de la competencia

Barre la Biblioteca de Anuncios de Meta sobre el set de competidores del
`config.json`, guarda un snapshot fechado y publica el informe como artefacto.

Ejecuta siempre desde la raíz del repo. Si hay un venv en `venv/`, usa
`./venv/bin/python`; si no, `python3`.

---

## Primera vez: la preparación

**Si no existe `config.json`, no barras: prepara primero.** Es una conversación,
no un formulario. No des por hecho que hay ninguna base de conocimiento interna
disponible: lo normal es que no la haya.

### 1. Mira qué contexto tienes antes de preguntar

Por este orden, y sin dar nada por sentado:

- ¿Hay un `CLAUDE.md`, un README de producto o notas en el proyecto? Léelos.
- ¿Esta sesión tiene alguna herramienta de memoria de empresa, CRM, Notion o
  similar conectada? Si la hay, **pide permiso** antes de consultarla y di qué
  vas a buscar. Si no la hay, no la menciones como requisito: no hace falta.
- ¿La persona tiene una web? Ofrécete a leerla para proponer tú los competidores
  en vez de hacérselos escribir.

Lo que saques de ahí lo llevas a la conversación como propuesta, no como hecho:
«por tu web diría que compites con A, B y C, ¿voy bien?».

### 2. Pregunta lo que falte

Tres preguntas bastan. Hazlas juntas, no de una en una:

1. **¿Qué vendes y a quién?** Una frase. De aquí sale el campo `categoria`, que
   es la frase que aparece en el informe («el panorama de soporte con IA»,
   «el CRM para pymes»).
2. **¿Contra quién compites?** Nombres, aunque sean aproximados. Ocho o quince
   está bien; menos de cinco da un informe pobre y más de veinte encarece el
   barrido sin añadir criterio.
3. **¿Hay alguien a quien quieras vigilar aunque no sea competencia directa?**
   Referentes de categoría, adyacentes, el que siempre copia todo el mundo.

### 3. Pide la key de ScrapeCreators

La Biblioteca de Anuncios se consulta a través de ScrapeCreators. Dile que la
saque en `https://scrapecreators.com/dashboard` y que la ponga él mismo en `.env`:

```bash
cp .env.example .env   # y pegar la key dentro
```

**No le pidas que te dicte la key ni la escribas tú en el archivo.** Es una
credencial: la pone la persona.

Comprueba también que hay `ffmpeg` en el PATH (`ffmpeg -version`). Sin él el
informe sale igual, pero sin miniaturas de las creatividades, que es la mitad
de la gracia. En macOS: `brew install ffmpeg`.

### 4. Resuelve cada marca a su page_id, y verifícala

```bash
python3 adlib.py "Nombre de la marca"
```

Devuelve las páginas candidatas con su categoría y su handle de Instagram.
**Los homónimos son la norma, no la excepción**: buscar "Sierra" devuelve el
Sierra Club, buscar "Crisp" devuelve una consultora de coaching para bufetes.

El criterio para marcar `"verificado": true` es uno solo: has traído sus
anuncios y el `page_name` y el `link_url` que salen son de la empresa real. Si
la página no tiene anuncios, no puedes verificarla: déjala en `false` y dilo.

Si una marca no aparece por ningún lado, va a `sin_pagina_identificada` con el
motivo escrito. Aparece en el informe como «sin página», que es información, no
un fallo.

### 5. Escribe el config y haz el primer barrido

Copia `config.example.json` a `config.json`, rellénalo, y lanza el barrido
completo. Al terminar, avisa de cuántos créditos quedan.

---

## Barrido normal

```bash
python3 barrido.py --limit 250
python3 informe.py --top 14
```

Después **reescribe `lecturas.md`** (ver abajo) y vuelve a correr `informe.py`
para que entre en el HTML. Luego publica `out/radar.html` como artefacto.

Para conservar el mismo enlace entre barridos, guarda la URL del artefacto en
este archivo la primera vez que lo publiques y pásala como `url` en los
siguientes. Antes de republicar, lee el artefacto con `action: "read"` si esta
conversación no lo ha publicado todavía.

> URL del artefacto: _(pega aquí la tuya la primera vez)_

---

## Qué hace cada pieza

| Archivo | Papel |
|---|---|
| `config.json` | El set rastreado y los textos del informe. Es lo único que se edita a mano entre barridos, además de las lecturas |
| `adlib.py` | Único punto de contacto con la API: pagina, parsea y resuelve nombres a `page_id`. Ejecutable suelto para buscar marcas |
| `barrido.py` | Guarda `data/snapshot-<fecha>.json`, `data/ultimo.json` y copia el snapshot previo a `data/anterior.json` |
| `informe.py` | Agrupa por copy, calcula longevidad y variantes, saca miniaturas y escribe `out/radar.html` |
| `lecturas.md` | El análisis, escrito a mano. **Reescríbelo en cada barrido**: el script no puede inferirlo |
| `media/` | Caché de miniaturas por URL, para no re-descargar entre barridos |

---

## Reglas

**Reescribe siempre `lecturas.md`.** Es la única parte con criterio. Si los datos
cambiaron y las lecturas no, el informe miente. Compara `data/ultimo.json` con
`data/anterior.json` para ver qué se movió: anuncios nuevos, mensajes que han
muerto, marcas que entran o salen. Copia `lecturas.example.md` la primera vez;
ahí están el formato y las preguntas que suelen dar buenas lecturas.

**Inversión e impresiones no existen.** `spend`, `reach_estimate`,
`impressions` y `total_active_time` vienen a nulo en anuncios comerciales; Meta
solo los publica en publicidad política. Los proxis válidos son **días en
activo** y **`collation_count`** (variantes). No inventes cifras de gasto ni las
estimes, ni siquiera con matices: si alguien las pide, explica por qué no están.

**Verifica el `page_id` de cualquier marca nueva** antes de meterla en el
config, con el criterio de la sección 4.

**Marcas que se truncan.** Si el informe avisa de truncado, sube `--limit`. Cada
página son 30 anuncios y 1 crédito de ScrapeCreators.

**Las creatividades son de sus titulares.** El informe las reproduce en pequeño
y enlazando a su ficha pública, para análisis competitivo. No las republiques
como propias ni las uses de otra manera.

---

## Añadir un competidor

```bash
python3 adlib.py "Nombre"          # 1. resolver candidatas
                                    # 2. verificar que no es un homónimo
                                    # 3. añadir la entrada a config.json
python3 barrido.py --marca "Nombre" --limit 250   # 4. barrer solo esa marca
```

Ojo: `--marca` sobrescribe `data/ultimo.json` con **solo** esa marca. Para el
informe completo hay que volver a barrer entero.

## Consultas sueltas

Para una pregunta puntual que no necesita informe («¿qué está anunciando X ahora
mismo?»), tira de `adlib.py` en un one-liner o del servidor MCP
[facebook-ads-library-mcp](https://github.com/proxy-intell/facebook-ads-library-mcp)
si lo tienes instalado. Los scripts son para el informe; las consultas sueltas
son para explorar en conversación.
