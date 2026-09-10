#!/usr/bin/env python3
"""Da de alta una cuenta gratuita de ScrapeCreators y guarda el token en .env.

ScrapeCreators permite registrarse con GitHub por flujo de dispositivo, sin
tarjeta y con 10.000 llamadas gratis. El alta la autorizas tú en tu navegador,
con tu cuenta de GitHub: este script solo pide el código, abre la página y
espera. No pide ni ve tu contraseña.

El token se escribe en .env con permisos 600 y no se imprime nunca en pantalla,
ni entero ni a trozos.

Uso:  python3 alta.py [--forzar]
"""
import argparse
import json
import os
import re
import stat
import sys
import time
import webbrowser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

RAIZ = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(RAIZ, ".env")
BASE = "https://api.scrapecreators.com/v1/github/device"

# El código de dispositivo de GitHub es siempre XXXX-XXXX. Se valida antes de
# enseñarlo para no imprimir por error algo con forma de token si el servidor
# responde otra cosa a una cuenta que ya existía.
RE_CODIGO = re.compile(r"^[0-9A-Z]{4}-[0-9A-Z]{4}$")


def _post(ruta, datos=None):
    cuerpo = json.dumps(datos or {}).encode()
    req = Request(f"{BASE}/{ruta}", data=cuerpo, method="POST")
    req.add_header("Content-Type", "application/json")
    with urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def key_actual():
    if not os.path.exists(ENV):
        return None
    for linea in open(ENV, encoding="utf-8"):
        if linea.strip().startswith("SCRAPECREATORS_API_KEY="):
            return linea.split("=", 1)[1].strip().strip("\"'") or None
    return None


def guardar(token):
    """Escribe el token en .env sin tocar el resto del archivo."""
    if os.path.exists(ENV):
        lineas = open(ENV, encoding="utf-8").read().splitlines()
    else:
        plantilla = os.path.join(RAIZ, ".env.example")
        lineas = open(plantilla, encoding="utf-8").read().splitlines() if os.path.exists(plantilla) else []

    salida, puesto = [], False
    for linea in lineas:
        if linea.strip().startswith("SCRAPECREATORS_API_KEY="):
            salida.append(f"SCRAPECREATORS_API_KEY={token}")
            puesto = True
        else:
            salida.append(linea)
    if not puesto:
        salida.append(f"SCRAPECREATORS_API_KEY={token}")

    with open(ENV, "w", encoding="utf-8") as fh:
        fh.write("\n".join(salida) + "\n")
    os.chmod(ENV, stat.S_IRUSR | stat.S_IWUSR)  # 600: solo tú


def creditos(token):
    req = Request("https://api.scrapecreators.com/v1/account/credit-balance")
    req.add_header("x-api-key", token)
    try:
        with urlopen(req, timeout=20) as r:
            return json.loads(r.read()).get("creditCount")
    except (HTTPError, URLError, OSError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--forzar", action="store_true",
                    help="dar de alta otra cuenta aunque ya haya un token en .env")
    args = ap.parse_args()

    if key_actual() and not args.forzar:
        saldo = creditos(key_actual())
        print("Ya hay un token de ScrapeCreators en .env.")
        if saldo is not None:
            print(f"Le quedan {saldo} créditos.")
        print("Para dar de alta otra cuenta distinta: python3 alta.py --forzar")
        return 0

    print()
    print("  Alta gratuita en ScrapeCreators")
    print("  10.000 llamadas gratis, sin tarjeta. Autorizas tú con tu GitHub.")
    print()

    try:
        d = _post("code")
    except (HTTPError, URLError, OSError) as e:
        print(f"  No se ha podido arrancar el alta: {e}")
        print("  Alternativa a mano: regístrate en https://scrapecreators.com")
        print("  y pega el token en la línea SCRAPECREATORS_API_KEY= de .env")
        return 1

    codigo = d.get("device_code")
    visible = d.get("user_code") or ""
    url = d.get("verification_uri") or "https://github.com/login/device"
    intervalo = int(d.get("interval") or 5)

    if not codigo or not RE_CODIGO.match(visible):
        print("  El servidor ha respondido algo inesperado. Regístrate a mano en")
        print("  https://scrapecreators.com y pega el token en .env")
        return 1

    print(f"  1. Abre  {url}")
    print(f"  2. Pega este código:  {visible}")
    print( "  3. Autoriza, y vuelve aquí. Esto se queda esperando.")
    print()
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001 — sin navegador, la URL ya está impresa
        pass

    limite = time.time() + 300
    ultimo_aviso = time.time()
    while time.time() < limite:
        time.sleep(intervalo)
        try:
            r = _post("token", {"device_code": codigo})
        except HTTPError as e:
            if e.code in (400, 403, 428):   # todavía sin autorizar
                continue
            print(f"  Error consultando el alta: {e}")
            return 1
        except (URLError, OSError):
            continue

        if r.get("access_token"):
            guardar(r["access_token"])
            saldo = creditos(r["access_token"])
            print("  ✓ Cuenta creada y token guardado en .env (permisos 600)")
            if saldo is not None:
                print(f"  ✓ {saldo} créditos disponibles")
            print()
            print("  Sigue con:  ./setup.sh")
            print()
            return 0

        if r.get("error") == "slow_down":
            intervalo += 5

        if time.time() - ultimo_aviso >= 30:
            print(f"  Esperando autorización… código: {visible}")
            ultimo_aviso = time.time()

    print("  Se ha agotado el tiempo de espera. Vuelve a lanzarlo cuando quieras.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
