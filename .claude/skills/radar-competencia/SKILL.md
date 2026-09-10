---
name: radar-competencia
description: Barre la Biblioteca de Anuncios de Meta sobre un set de competidores y publica un informe de inteligencia competitiva con días en activo, variantes, análisis de las creatividades y enlace a la ficha de cada anuncio. Usar cuando pidan "radar de competencia", "actualiza el radar", "qué está anunciando la competencia", "analiza los anuncios de X", "qué creatividades tiene <marca>", "mira la Ad Library de", "añade un competidor al radar", "qué ha cambiado desde el último barrido", o cualquier variación sobre revisar el paid de la competencia en Meta.
---

# Radar Meta de la competencia

Barre la Biblioteca de Anuncios de Meta sobre el set de competidores del
`config.json`, guarda un snapshot fechado y publica el informe como artefacto.

Ejecuta siempre desde la raíz del repo, con `./venv/bin/python`.

## El reparto de trabajo

Dos piezas, y cada una hace lo que la otra no puede:

- **El servidor MCP `facebook-ads-library`** es para resolver marcas, verificar
  páginas y, sobre todo, **ver las creatividades**. Sus herramientas de análisis
  de imagen y vídeo son la diferencia entre unas lecturas escritas leyendo solo
  el texto del anuncio y unas escritas habiendo visto la pieza.
- **Los scripts** son para el barrido. Necesitan paginar entero y escribir un
  snapshot exacto en disco, porque la mitad del valor del informe es el delta
  contra el barrido anterior, y eso no se sostiene sobre respuestas de chat.

Usa las dos. La skill da por hecho que el MCP está conectado.

---

## Primera vez: la preparación

**Si no existe `config.json`, no barras: prepara primero.** Es una conversación,
no un formulario. No des por hecho que hay ninguna base de conocimiento interna
disponible: lo normal es que no la haya.

### 1. Deja el MCP conectado antes que nada

```bash
./setup.sh
```

Monta el entorno, clona e instala el servidor MCP y lo registra en Claude Code
con el token. Comprueba después con `/mcp` que `facebook-ads-library` aparece
conectado; si no, la sesión tiene que reiniciarse para que cargue.

**No le pidas ningún token.** Si no hay ninguno, `setup.sh` lanza el alta
gratuita de ScrapeCreators por GitHub: 10.000 llamadas, sin tarjeta. Imprime un
código, abre el navegador y espera a que la persona autorice; al volver, guarda
el token en `.env` con permisos 600. La autorización la da ella con su cuenta de
GitHub, en su navegador.

Tres reglas al respecto, y no se saltan:

- **Nunca pidas un token por el chat.** Todo lo que se escribe aquí queda en la
  conversación. Si alguien insiste en poner el suyo a mano, que lo pegue en
  `.env` directamente.
- **Nunca enseñes un token**, ni entero ni un trozo, ni lo escribas en un
  archivo que vaya a git. `.env` está en el `.gitignore` por eso.
- **Nunca reutilices el token de otro sitio sin preguntar.** `setup.sh` detecta
  el del plugin `last30days` y ofrece reutilizarlo, avisando de que entonces
  las dos herramientas comparten bolsa de créditos. La decisión es de la
  persona, no tuya.

Si después de dos intentos honestos el MCP no levanta, sigue con
`./setup.sh --sin-mcp` y **dilo en voz alta**: el radar funciona, pero las
lecturas se van a escribir sin haber visto una sola creatividad, que es
justo la parte que las hace buenas. No lo dejes pasar en silencio.

### 2. Mira qué contexto tienes antes de preguntar

Por este orden, y sin dar nada por sentado:

- ¿Hay un `CLAUDE.md`, un README de producto o notas en el proyecto? Léelos.
- ¿Esta sesión tiene alguna herramienta de memoria de empresa, CRM, Notion o
  similar conectada? Si la hay, **pide permiso** antes de consultarla y di qué
  vas a buscar. Si no la hay, no la menciones como requisito: no hace falta.
- ¿La persona tiene una web? Ofrécete a leerla para proponer tú los competidores
  en vez de hacérselos escribir.

Lo que saques de ahí lo llevas a la conversación como propuesta, no como hecho:
«por tu web diría que compites con A, B y C, ¿voy bien?».

### 3. Pregunta lo que falte

Tres preguntas bastan. Hazlas juntas, no de una en una:

1. **¿Qué vendes y a quién?** Una frase. De aquí sale el campo `categoria`, que
   es la frase que aparece en el informe («el panorama de soporte con IA»,
   «el CRM para pymes»).
2. **¿Contra quién compites?** Nombres, aunque sean aproximados. Ocho o quince
   está bien; menos de cinco da un informe pobre y más de veinte encarece el
   barrido sin añadir criterio.
3. **¿Hay alguien a quien quieras vigilar aunque no sea competencia directa?**
   Referentes de categoría, adyacentes, el que siempre copia todo el mundo.

### 4. Resuelve cada marca a su page_id, y verifícala

Con el MCP conectado, en una sola llamada para todas:

```
mcp__facebook-ads-library__get_meta_platform_id(brand_names=["Marca A", "Marca B", …])
```

**Los homónimos son la norma, no la excepción.** Un nombre corto devuelve una
docena de páginas y la primera casi nunca es la buena: asociaciones, negocios
locales, perfiles personales con el mismo nombre.

El criterio para marcar `"verificado": true` es uno solo: has traído sus
anuncios con `get_meta_ads` y el `page_name` y el `link_url` que salen son de
la empresa real. Si la página no tiene anuncios, no puedes verificarla: déjala
en `false` y dilo.

Si una marca no aparece por ningún lado, va a `sin_pagina_identificada` con el
motivo escrito. Aparece en el informe como «sin página», que es información, no
un fallo.

Sin MCP, el mismo paso a mano: `./venv/bin/python adlib.py "Nombre"`.

### 5. Escribe el config y haz el primer barrido

Copia `config.example.json` a `config.json`, rellénalo, y lanza el barrido
completo. Al terminar, avisa de cuántos créditos quedan.

---

## Barrido normal

```bash
./venv/bin/python barrido.py --limit 250
./venv/bin/python informe.py --top 14
```

Después **mira las creatividades y reescribe `lecturas.md`** (siguiente
sección), y vuelve a correr `informe.py` para que entren en el HTML. Luego
publica `out/radar.html` como artefacto.

Para conservar el mismo enlace entre barridos, guarda la URL del artefacto en
este archivo la primera vez que lo publiques y pásala como `url` en los
siguientes. Antes de republicar, lee el artefacto con `action: "read"` si esta
conversación no lo ha publicado todavía.

> URL del artefacto: _(pega aquí la tuya la primera vez)_

---

## Las lecturas: mira antes de escribir

`lecturas.md` es la única parte del informe con criterio, y la única que no
puede salir de un script. **Reescríbela entera en cada barrido.** Si los datos
cambiaron y las lecturas no, el informe miente.

El orden que da lecturas que valen algo:

1. **Compara** `data/ultimo.json` con `data/anterior.json`: qué anuncios son
   nuevos, qué mensajes han muerto, qué marcas entran o salen.
2. **Mira las creatividades más longevas** con
   `mcp__facebook-ads-library__analyze_ad_image` sobre las `media_url` del top
   del ranking. Un anuncio que lleva dos meses corriendo merece que alguien
   mire qué hay en la imagen, no solo qué dice el copy. Para vídeo,
   `analyze_ad_videos_batch` en una sola llamada, que ahorra bastante contexto
   y necesita `GEMINI_API_KEY` en el `.env`.
3. **Escribe** cada lectura como una afirmación con su prueba al lado.

Sin el MCP este paso se salta, y las lecturas salen del texto y ya. Se nota.

Cinco preguntas que suelen dar buenas lecturas están en `lecturas.example.md`.

---

## Qué hace cada pieza

| Archivo | Papel |
|---|---|
| `setup.sh` | Entorno, servidor MCP y token. Se lanza una vez |
| `alta.py` | Alta gratuita en ScrapeCreators por GitHub. Lo llama `setup.sh` si hace falta |
| `config.json` | El set rastreado y los textos del informe |
| `adlib.py` | Cliente de la API para el barrido, y resolutor de marcas si no hay MCP |
| `barrido.py` | Guarda `data/snapshot-<fecha>.json`, `data/ultimo.json` y copia el previo a `data/anterior.json` |
| `informe.py` | Agrupa por copy, calcula longevidad y variantes, saca miniaturas y escribe `out/radar.html` |
| `lecturas.md` | El análisis, escrito a mano tras mirar las creatividades |
| `media/` | Caché de miniaturas por URL, para no re-descargar entre barridos |

---

## Reglas

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

**Un solo token para todo.** El de ScrapeCreators, en `.env`. `setup.sh` se lo
pasa al MCP al registrarlo. Si alguien lo rota, hay que volver a lanzar
`./setup.sh` para que el MCP se quede con el nuevo.

**Los créditos son suyos y se gastan.** Cada página de 30 anuncios es un
crédito y cada búsqueda de marca otro; el alta gratuita trae 10.000. Antes de
un barrido grande o de añadir diez marcas de golpe, di lo que va a costar.

---

## Añadir un competidor

1. `get_meta_platform_id` con el nombre.
2. `get_meta_ads` con el candidato, y comprobar que la página es la buena.
3. Añadir la entrada a `config.json`.
4. `./venv/bin/python barrido.py --marca "Nombre" --limit 250` para comprobar.

Ojo: `--marca` sobrescribe `data/ultimo.json` con **solo** esa marca. Para el
informe completo hay que volver a barrer entero.

## Consultas sueltas

Para una pregunta puntual que no necesita informe («¿qué está anunciando X ahora
mismo?», «¿cómo es la creatividad de este anuncio?»), tira directamente de las
herramientas `mcp__facebook-ads-library__*`. Los scripts son para el informe;
el MCP es para explorar en conversación.
