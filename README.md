# Meta Ad Radar

**Qué está anunciando tu competencia en Meta, cuánto lleva corriendo cada anuncio y qué ha cambiado desde la última vez que miraste.** Una skill de Claude Code, un servidor MCP y dos scripts de Python que barren la Biblioteca de Anuncios de Meta sobre tu set de competidores y publican un informe navegable.

*English: a Claude Code skill that sweeps Meta's Ad Library for your competitor set and publishes a competitive-intelligence report — days each ad has been running, number of variants, deep links to every ad. One `./setup.sh` wires up the Ad Library MCP server so Claude can actually look at the creatives, not just read the ad copy. Setup is a conversation: Claude interviews you, resolves each brand to its Meta page and verifies it isn't a namesake. Spanish output. MIT.*

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
- **Lo que esto significa para tu paid.** Tus lecturas, en `lecturas.md`. El barrido trae los datos; esta parte es criterio, y se escribe después de mirar las creatividades más longevas con el MCP.

Tema claro y oscuro, responsive, sin dependencias en runtime: las miniaturas van embebidas, así que el archivo se abre en cualquier sitio.

## Instalación

```bash
git clone https://github.com/melero-gurusup/gurusup-meta-ad-radar
cd gurusup-meta-ad-radar
./setup.sh
```

`setup.sh` monta el entorno, clona e instala el **servidor MCP de la Ad Library** y lo registra en Claude Code con tu token. Si falta el token, se para y te dice dónde ponerlo: lo sacas en [ScrapeCreators](https://scrapecreators.com/dashboard) y lo pegas en `.env`. Un barrido de quince marcas cuesta unos 25 créditos.

Instala también **ffmpeg** si no lo tienes (`brew install ffmpeg`), para las miniaturas de las creatividades.

### Por qué el MCP no es opcional del todo

Dos piezas, y cada una hace lo que la otra no puede.

El **servidor MCP** resuelve marcas, verifica páginas y, sobre todo, **ve las creatividades**: `analyze_ad_image` y `analyze_ad_videos_batch` son la diferencia entre unas lecturas escritas leyendo el texto del anuncio y unas escritas habiendo visto la pieza. Es donde está el salto de calidad.

Los **scripts** hacen el barrido, porque necesitan paginar entero y escribir un snapshot exacto en disco: la mitad del valor del informe es el delta contra el barrido anterior, y eso no se sostiene sobre respuestas de chat.

Comparten el mismo token, que se pide una vez.

Si el MCP no te levanta, `./setup.sh --sin-mcp` deja el radar funcionando. Pierdes el análisis de creatividades, y se nota en las lecturas.

<details>
<summary>Detalles de instalación del MCP, por si algo falla</summary>

- **No uses `npx @proxy-intell/facebook-ads-library-mcp`.** Su `postinstall` hace `pip install` sobre el Python del sistema, y en macOS PEP 668 lo bloquea sin devolver error: el servidor arranca y muere con `ModuleNotFoundError: No module named 'mcp'`. Por eso `setup.sh` clona y monta un venv propio.
- **El venv del MCP necesita Python 3.13 o 3.12.** Su `requirements.txt` pinnea `pydantic` a versiones sin wheel para 3.14, así que en un intérprete más nuevo intenta compilar `pydantic-core` con Rust y falla. `setup.sh` elige el intérprete adecuado solo.
- Si ya tienes el servidor registrado con ese nombre, `setup.sh` lo detecta y no lo toca.
- Para reutilizar un clon que ya tengas: `./setup.sh --mcp-path /ruta/al/clon`.
- El servidor es [proxy-intell/facebook-ads-library-mcp](https://github.com/proxy-intell/facebook-ads-library-mcp) (MIT). Tiene también una versión alojada sin claves en [useproxy.dev](https://useproxy.dev/), que es de un tercero: si la usas, la registras tú y `setup.sh` no la toca.

</details>

## Puesta en marcha con Claude Code

Abre Claude Code en la carpeta del repo y pídele el radar. La skill vive en `.claude/skills/radar-competencia/`, así que está disponible sin instalar nada más.

**No necesitas ninguna base de conocimiento interna, ni tener nada más conectado que lo que monta `setup.sh`.** Si no existe `config.json`, la skill entra en modo preparación:

1. Comprueba que el MCP está conectado. Si no lo está, te manda a `./setup.sh` antes de seguir, y el token lo pones tú en `.env`: no te lo pide dictado ni lo escribe por ti.
2. Mira si hay contexto aprovechable — un `CLAUDE.md`, tu web, un CRM o un Notion que ya tengas conectado — y **te pide permiso** antes de tocarlo. Si no hay nada, sigue igual.
3. Te hace tres preguntas: qué vendes y a quién, contra quién compites, y a quién quieres vigilar aunque no sea competencia directa.
4. Resuelve cada marca a su página de Meta y **la verifica**, que es el paso que todo el mundo se salta: un nombre corto devuelve una docena de páginas homónimas y la primera casi nunca es la buena.
5. Escribe `config.json`, hace el primer barrido y publica el informe.

A partir de ahí, «actualiza el radar» barre, compara contra el anterior, mira las creatividades que llevan más tiempo corriendo, reescribe las lecturas y republica al mismo enlace.

## Uso a mano

```bash
cp config.example.json config.json      # tus competidores y los textos del informe
cp lecturas.example.md lecturas.md      # tus lecturas

./venv/bin/python adlib.py "Nombre"     # resolver una marca a su page_id, sin MCP
./venv/bin/python barrido.py --limit 250
./venv/bin/python informe.py --top 14   # escribe out/radar.html
```

## Las piezas

| Archivo | Papel |
|---|---|
| `setup.sh` | Entorno, servidor MCP y token. Se lanza una vez |
| `config.json` | El set rastreado y los textos del informe |
| `adlib.py` | Cliente de la API para el barrido, y resolutor de marcas si no hay MCP |
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

El servidor MCP es [proxy-intell/facebook-ads-library-mcp](https://github.com/proxy-intell/facebook-ads-library-mcp) (MIT, Gala Labs). `setup.sh` lo clona y lo registra tal cual, sin modificarlo. El parseo de `adlib.py` sigue el suyo, reescrito aquí para que el barrido no dependa de que el servidor esté levantado.

MIT. Si te sirve, cuéntalo — y si lo mejoras, manda el PR.
