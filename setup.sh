#!/usr/bin/env bash
# Deja el radar listo para usar: entorno del proyecto, servidor MCP y token.
#
# El MCP es la ruta recomendada. Sin él el barrido funciona igual, pero el
# análisis se escribe leyendo solo el texto de los anuncios: nadie mira la
# creatividad. Con el MCP conectado, Claude puede ver la imagen y el vídeo,
# y ahí es donde cambia la calidad de las lecturas.
#
# Uso:  ./setup.sh [--mcp-path /ruta/a/un/clon/existente] [--sin-mcp]
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_REPO="https://github.com/proxy-intell/facebook-ads-library-mcp.git"
MCP_DIR="$RAIZ/.mcp-server"
NOMBRE_MCP="facebook-ads-library"
SIN_MCP=0

while [ $# -gt 0 ]; do
  case "$1" in
    --mcp-path) MCP_DIR="$2"; shift 2 ;;
    --sin-mcp)  SIN_MCP=1; shift ;;
    *) echo "Opción desconocida: $1"; exit 1 ;;
  esac
done

ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
avisa(){ printf '  \033[33m!\033[0m %s\n' "$1"; }
para() { printf '\n  \033[31m✗\033[0m %s\n\n' "$1"; exit 1; }

echo
echo "Meta Ad Radar — preparación"
echo

# ---------------------------------------------------------------- 1. requisitos
command -v python3 >/dev/null || para "Falta python3. Instálalo y vuelve a lanzarlo."
ok "python3 $(python3 -c 'import sys;print(".".join(map(str,sys.version_info[:3])))')"

if command -v ffmpeg >/dev/null; then
  ok "ffmpeg"
else
  avisa "Sin ffmpeg: el informe saldrá sin miniaturas de las creatividades."
  avisa "  macOS: brew install ffmpeg · Debian/Ubuntu: apt install ffmpeg"
fi

# ---------------------------------------------------------------- 2. entorno
if [ ! -d "$RAIZ/venv" ]; then
  python3 -m venv "$RAIZ/venv"
fi
"$RAIZ/venv/bin/pip" install -q --upgrade pip
"$RAIZ/venv/bin/pip" install -q -r "$RAIZ/requirements.txt"
ok "entorno del proyecto listo"

# ---------------------------------------------------------------- 3. token
# El token es de ScrapeCreators, que es quien sirve la Biblioteca de Anuncios.
# El mismo vale para el barrido y para el MCP: se pide una vez.
[ -f "$RAIZ/.env" ] || cp "$RAIZ/.env.example" "$RAIZ/.env"
leer_key() {
  grep -E '^SCRAPECREATORS_API_KEY=' "$RAIZ/.env" 2>/dev/null | cut -d= -f2- | tr -d " \"'" || true
}
KEY="$(leer_key)"

if [ -z "$KEY" ]; then
  # Si ya tiene una key de otro sitio, se la ofrecemos antes de crear cuenta.
  # El plugin last30days usa el mismo proveedor y mucha gente lo tiene puesto.
  OTRA=""
  L30="$HOME/.config/last30days/.env"
  if [ -f "$L30" ]; then
    OTRA="$(grep -E '^SCRAPECREATORS_API_KEY=' "$L30" | cut -d= -f2- | tr -d " \"'" || true)"
  fi

  if [ -n "$OTRA" ] && [ -t 0 ]; then
    echo
    echo "  Tienes ya un token de ScrapeCreators del plugin last30days."
    echo "  Puedes reutilizarlo, pero entonces el radar y tus informes de"
    echo "  last30days gastan de la misma bolsa de créditos."
    echo
    printf "  ¿Reutilizarlo? [s/N] "
    read -r RESP
    case "$RESP" in
      s|S|si|SI|sí|Sí|y|Y) sed -i.bak "s|^SCRAPECREATORS_API_KEY=.*|SCRAPECREATORS_API_KEY=$OTRA|" "$RAIZ/.env"
                           rm -f "$RAIZ/.env.bak"; chmod 600 "$RAIZ/.env"
                           KEY="$(leer_key)"; ok "token reutilizado" ;;
    esac
  fi

  if [ -z "$KEY" ]; then
    if [ -t 0 ]; then
      # Alta gratuita por GitHub: 10.000 llamadas, sin tarjeta.
      # La autoriza la persona en su navegador; el script solo espera.
      python3 "$RAIZ/alta.py" || true
      KEY="$(leer_key)"
    fi
  fi

  if [ -z "$KEY" ]; then
    echo
    echo "  Sin token no se puede seguir. Dos formas de conseguirlo:"
    echo "    ./alta.py                 alta gratuita con GitHub, 10.000 llamadas"
    echo "    https://scrapecreators.com   registro normal, y pegas el token en .env"
    echo
    exit 1
  fi
fi
chmod 600 "$RAIZ/.env" 2>/dev/null || true
ok "token de ScrapeCreators listo"

if [ "$SIN_MCP" = "1" ]; then
  echo
  avisa "Saltando el MCP porque lo has pedido con --sin-mcp."
  avisa "El barrido y el informe funcionan. Lo que pierdes es el análisis"
  avisa "de las creatividades: las lecturas se escribirán solo con el texto."
  echo
  echo "  Siguiente paso:  ./venv/bin/python barrido.py --limit 250"
  echo
  exit 0
fi

# ---------------------------------------------------------------- 4. MCP
if ! command -v claude >/dev/null; then
  echo
  avisa "No encuentro el CLI de Claude Code, así que no puedo registrar el MCP."
  avisa "Instálalo y relanza esto, o sigue sin él con: ./setup.sh --sin-mcp"
  echo
  exit 1
fi

if claude mcp list 2>/dev/null | grep -q "^$NOMBRE_MCP:"; then
  ok "ya tienes '$NOMBRE_MCP' registrado; no lo toco"
else
  if [ ! -f "$MCP_DIR/mcp_server.py" ]; then
    command -v git >/dev/null || para "Falta git para clonar el servidor MCP."
    echo "  clonando el servidor MCP en ${MCP_DIR/#$RAIZ\//}…"
    git clone -q --depth 1 "$MCP_REPO" "$MCP_DIR"
  fi

  # Venv propio del servidor, y con un intérprete que le sirva. Dos cosas que
  # se aprenden a golpes: su postinstall de npm instala sobre el Python del
  # sistema y en macOS lo bloquea PEP 668 sin decir nada (por eso no hay npx
  # aquí), y su requirements.txt pinnea pydantic a versiones sin wheel para
  # 3.14, así que en un Python demasiado nuevo intenta compilar con Rust y
  # revienta. Se elige el más alto de los que sabemos que funcionan.
  PY_MCP=""
  for v in python3.13 python3.12; do
    command -v "$v" >/dev/null && { PY_MCP="$v"; break; }
  done
  if [ -z "$PY_MCP" ]; then
    PY_MCP="python3"
    avisa "No encuentro python3.13 ni 3.12; pruebo con $(python3 -V 2>&1)."
    avisa "  Si falla compilando pydantic, instala python3.13 y relanza esto."
  fi
  [ -d "$MCP_DIR/venv" ] || "$PY_MCP" -m venv "$MCP_DIR/venv"
  "$MCP_DIR/venv/bin/pip" install -q --upgrade pip
  "$MCP_DIR/venv/bin/pip" install -q -r "$MCP_DIR/requirements.txt"
  ok "servidor MCP instalado"

  # Rutas absolutas y token explícito: así no depende de desde dónde se lance.
  claude mcp add "$NOMBRE_MCP" \
    -e "SCRAPECREATORS_API_KEY=$KEY" \
    -- "$MCP_DIR/venv/bin/python" "$MCP_DIR/mcp_server.py" >/dev/null
  ok "MCP registrado en Claude Code"
fi

ESTADO="$(claude mcp list 2>/dev/null | grep "^$NOMBRE_MCP:" || true)"
case "$ESTADO" in
  *Connected*) ok "MCP conectado" ;;
  *)           avisa "Registrado pero sin confirmar conexión. Abre 'claude' y comprueba con /mcp." ;;
esac

echo
echo "  Listo. Abre Claude Code aquí y pídele el radar:"
echo "    \"monta el radar de competencia\""
echo
echo "  Si no existe config.json, te hará las preguntas para montarlo."
echo
