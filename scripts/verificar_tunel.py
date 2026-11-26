"""Comprueba que `GOOGLE_REDIRECT_URI` apunte al túnel de Cloudflare que está abierto.

Uso, con el túnel ya levantado (`cloudflared tunnel --url http://127.0.0.1:8000`):

    python scripts/verificar_tunel.py
    python scripts/verificar_tunel.py --url https://nombre.trycloudflare.com

Un túnel rápido cambia de nombre cada vez que se levanta, y si el `.env` conserva
el anterior el acceso con Google termina en un error de DNS (RV-01). El script
solo lee: no modifica el `.env` ni Google Cloud.

Sin `--url`, pregunta el nombre a `cloudflared`, que lo publica en su servidor
local de métricas (`/quicktunnel`, puertos 20241 a 20245).

Sale con 0 si coinciden, 1 si no, y 2 si no encontró ningún túnel.
"""

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

# Como los demás scripts: así funciona aunque `studify` no esté instalado.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from studify.config import get_settings  # noqa: E402

PUERTOS_METRICAS = range(20241, 20246)
RUTA_RETORNO = "/student/google/callback"


def host_del_tunel() -> str | None:
    """El nombre público del túnel rápido que `cloudflared` tenga abierto."""
    for puerto in PUERTOS_METRICAS:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{puerto}/quicktunnel", timeout=2
            ) as respuesta:
                host = json.load(respuesta).get("hostname")
        except (OSError, ValueError, AttributeError):
            continue
        if host:
            return host
    return None


def comparar(redirect_uri: str, host: str) -> tuple[bool, str]:
    """Si el retorno configurado corresponde al túnel, y la dirección que debería ser."""
    esperada = f"https://{host}{RUTA_RETORNO}"
    return redirect_uri == esperada, esperada


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", help="dirección del túnel, si no se quiere detectar")
    args = parser.parse_args(argv)

    if args.url:
        url = args.url if "//" in args.url else f"https://{args.url}"
        host = urlsplit(url).netloc
    else:
        host = host_del_tunel()
    if not host:
        print(
            "No encontré un túnel abierto. Levántalo con "
            "`cloudflared tunnel --url http://127.0.0.1:8000` o pasa su dirección con --url."
        )
        return 2

    configurada = get_settings().google_redirect_uri
    coincide, esperada = comparar(configurada, host)
    print(f"Túnel activo:        https://{host}")
    print(f"GOOGLE_REDIRECT_URI: {configurada}")
    if coincide:
        print(
            "\nCoinciden. Comprueba además que esa dirección esté autorizada en Google Cloud\n"
            "y que el servidor se haya reiniciado después del último cambio del .env."
        )
        return 0
    print(
        "\nNO COINCIDEN: el acceso con Google fallará. Pon esta dirección en el .env\n"
        "(GOOGLE_REDIRECT_URI) y en Google Cloud, y reinicia el servidor:\n\n"
        f"    {esperada}"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
