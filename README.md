# Meta Ad Radar

**Qué está anunciando tu competencia en Meta, cuánto lleva corriendo cada anuncio y qué ha cambiado desde la última vez que miraste.** Una skill de Claude Code y dos scripts de Python que barren la Biblioteca de Anuncios de Meta sobre tu set de competidores y publican un informe navegable.

*English: a Claude Code skill that sweeps Meta's Ad Library for your competitor set and publishes a competitive-intelligence report — days each ad has been running, number of variants, deep links to every ad. Setup is a conversation: Claude interviews you, resolves each brand to its Meta page and verifies it isn't a namesake. Spanish output. MIT.*

Hecho por [GuruSup](https://gurusup.com).

---

## Por qué días en activo y no CTR

La Biblioteca de Anuncios de Meta **no publica inversión ni impresiones** de los anuncios comerciales: `spend`, `reach_estimate` e `impressions` vienen vacíos y solo se rellenan en publicidad política. Cualquier herramienta que te dé el gasto de un competidor en Meta se lo está inventando.

Lo que sí es público, y es suficiente, son dos cosas:

- **Días que un anuncio lleva corriendo.** Nadie deja dos meses en el aire algo que no convierte. La longevidad es la confesión más honesta que hace un anunciante.
- **Variantes agrupadas** bajo un mismo anuncio (`collation_count`). Cuántas versiones ha montado detrás de un mismo mensaje, que es cuánto está apostando por él.

Con esos dos números el informe responde a las preguntas que de verdad se hacen: quién acaba de entrar, qué mensaje aguanta, qué argumento repite todo el mundo (y por tanto ya no te diferencia), y quién no está pujando aquí.

## Qué produce

Un HTML de una sola página, en español, con:

- **El radar.** Tabla de todas las marcas: anuncios activos, cambio respecto al barrido anterior, días del más veterano y estado.
- **Los que llevan más tiempo corriendo.** Las creatividades más longevas de todo el set, mezclando marcas, con miniatura y enlace a su ficha pública en la Ad Library.
- **Cómo hablan.** Por marca, sus mensajes ordenados por longevidad, agrupados por copy en vez de por anuncio.
- **Lo que esto significa para tu paid.** Tus lecturas, escritas a mano en `lecturas.md`. El barrido trae los datos; esta parte es criterio y la pones tú.

Tema claro y oscuro, responsive, sin dependencias en runtime: las miniaturas van embebidas, así que el archivo se abre en cualquier sitio.

## Instalación

```bash
git clone https://github.com/melero-gurusup/gurusup-meta-ad-radar
cd gurusup-meta-ad-radar
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
```

Necesitas además:

- **Una key de [ScrapeCreators](https://scrapecreators.com/dashboard)**, que es quien sirve la Biblioteca de Anuncios. Un barrido de quince marcas cuesta unos 25 créditos.
- **ffmpeg** en el PATH, para las miniaturas (`brew install ffmpeg`). Sin él el informe sale igual, pero sin imágenes.

## Puesta en marcha con Claude Code

Abre Claude Code en la carpeta del repo y pídele el radar. La skill vive en `.claude/skills/radar-competencia/`, así que está disponible sin instalar nada más.

**No hace falta que le des ninguna base de conocimiento ni que tengas nada conectado.** Si no existe `config.json`, la skill entra en modo preparación y monta el set contigo:

1. Mira si hay contexto disponible (un `CLAUDE.md`, tu web, alguna herramienta que tengas conectada) y te pide permiso antes de usarlo. Si no hay nada, sigue igual.
2. Te hace tres preguntas: qué vendes y a quién, contra quién compites, y a quién quieres vigilar aunque no sea competencia directa.
3. Te pide que pongas tú la key en `.env` — no te la pide dictada ni la escribe por ti.
4. Resuelve cada marca a su página de Meta y **la verifica**, que es el paso que todo el mundo se salta: buscar "Sierra" devuelve el Sierra Club y buscar "Crisp" devuelve una consultora para bufetes.
5. Escribe `config.json`, hace el primer barrido y publica el informe.

A partir de ahí, «actualiza el radar» hace el barrido, reescribe las lecturas comparando con el anterior y republica al mismo enlace.

## Uso a mano

```bash
cp config.example.json config.json      # tus competidores y los textos del informe
cp .env.example .env                    # tu key de ScrapeCreators
cp lecturas.example.md lecturas.md      # tus lecturas

./venv/bin/python adlib.py "Nombre"     # resolver una marca a su page_id
./venv/bin/python barrido.py --limit 250
./venv/bin/python informe.py --top 14   # escribe out/radar.html
```

## Las piezas

| Archivo | Papel |
|---|---|
| `config.json` | El set rastreado y los textos del informe |
| `adlib.py` | Único punto de contacto con la API: pagina, parsea y resuelve nombres a `page_id` |
| `barrido.py` | Guarda un snapshot fechado y copia el previo, que es lo que permite decir «esto ha cambiado» |
| `informe.py` | Agrupa por copy, calcula longevidad y variantes, saca miniaturas y escribe el HTML |
| `lecturas.md` | Tu análisis. Reescríbelo en cada barrido |

Los directorios `data/`, `media/` y `out/` se generan solos y están en el `.gitignore`.

## Personalizarlo

- **Los textos del informe** (título, etiqueta de cabecera, la frase que describe tu categoría) están en el bloque `informe` del `config.json`.
- **El logo de la cabecera** es `assets/logo.svg`. Es el de GuruSup por defecto; sustitúyelo por el tuyo si prefieres. Se pinta en `currentColor`, así que sirve el mismo archivo en tema claro y oscuro.
- **Los colores por marca** se asignan por orden en el `config.json`, así que una marca conserva su color entre barridos aunque suba o baje en la tabla. La paleta está en `informe.py`.
- **El informe sale en español.** Las cadenas están en las plantillas de `informe.py`, todas juntas al final del archivo.

## Límites, dichos en voz alta

- Sin inversión ni impresiones. Ver arriba: no es una limitación del script, es que Meta no lo publica.
- Un anuncio sin texto o con un formato que no sea imagen, vídeo o DCO se descarta en el parseo.
- `--marca` sobrescribe `data/ultimo.json` con solo esa marca. Para el informe completo hay que barrer entero.
- Las creatividades son de sus titulares. El informe las reproduce en miniatura y enlazando a su ficha pública, para análisis competitivo.

## Créditos

El parseo de la respuesta de la Biblioteca sigue el del servidor MCP [facebook-ads-library-mcp](https://github.com/proxy-intell/facebook-ads-library-mcp) (MIT, Gala Labs), reescrito aquí para que este repo no dependa de tenerlo instalado.

MIT. Si te sirve, cuéntalo — y si lo mejoras, manda el PR.
