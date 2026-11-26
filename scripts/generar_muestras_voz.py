"""Genera las muestras de voz del selector (visor y perfil).

Uso:
    python scripts/generar_muestras_voz.py            # genera las que falten
    python scripts/generar_muestras_voz.py --forzar   # regenera las cuatro

Se corre una vez por instalación, después de `scripts/descargar_voces.py`, y de
nuevo con `--forzar` si cambia el texto (`media/muestras.py::TEXTO_MUESTRA`),
una voz o las reglas de `media/guion.py`.

Cada muestra se sintetiza con `audio.generar_audio`, la misma ruta que usa el
visor, así que suena igual que una narración real. Si hay `ffmpeg` en el PATH
se guarda como MP3 (unas seis veces más liviano y compatible con cualquier
navegador); si no, queda el WAV.

Los archivos no se versionan: ver AVANCE.md §5.38.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Como los demás scripts: así funciona aunque `studify` no esté instalado en el
# entorno (con `pip install -e .` ya resuelve a `src/` por sí solo).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from studify.config import Settings, get_settings  # noqa: E402
from studify.media import audio, muestras  # noqa: E402

# Voz mono: 64 kb/s sobra y deja cada muestra en unas decenas de KB.
BITRATE_MP3 = "64k"


def modelos_faltantes(
    preferencias: list[audio.PreferenciaVoz], ajustes: Settings
) -> list[Path]:
    """Los archivos de modelo que necesitan estas voces y no están en disco."""
    directorio = Path(ajustes.tts_modelos_dir)
    necesarios: dict[Path, None] = {}  # sin repetir y en orden
    for preferencia in preferencias:
        eleccion = audio.resolver_voz(preferencia, ajustes=ajustes)
        if eleccion.motor == "kokoro":
            nombres = (audio.KOKORO_MODELO, audio.KOKORO_VOCES)
        else:
            nombres = (f"{eleccion.voz}.onnx", f"{eleccion.voz}.onnx.json")
        necesarios.update(dict.fromkeys(directorio / nombre for nombre in nombres))
    return [ruta for ruta in necesarios if not ruta.is_file()]


def convertir_a_mp3(wav: Path, mp3: Path, ffmpeg: str) -> bool:
    """`True` si ffmpeg dejó el MP3; si falla, lo dice y se conserva el WAV."""
    orden = [
        ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(wav),
        "-codec:a", "libmp3lame", "-b:a", BITRATE_MP3, "-map_metadata", "-1",
        str(mp3),
    ]
    resultado = subprocess.run(orden, capture_output=True, text=True, errors="replace")
    if resultado.returncode == 0 and mp3.is_file():
        return True
    print(f"aviso   ffmpeg no pudo convertir {wav.name}: {resultado.stderr.strip()}")
    return False


def generar(preferencia: audio.PreferenciaVoz, ffmpeg: str | None) -> Path:
    """Sintetiza una muestra y la deja en su nombre definitivo.

    Se trabaja en una carpeta temporal y se mueve al final: el servidor nunca
    ve un archivo a medias. La muestra en el otro formato, si quedaba de una
    corrida anterior, se borra para que no tape a la nueva.
    """
    base = muestras.nombre_base(preferencia)
    directorio = muestras.DIRECTORIO_MUESTRAS
    with tempfile.TemporaryDirectory(prefix=".tmp-", dir=directorio) as temporal:
        wav = Path(temporal) / f"{base}.wav"
        # `generar_audio` normaliza el texto con `media/guion.py`, como un guion real.
        audio.generar_audio(muestras.TEXTO_MUESTRA, wav, preferencia=preferencia)
        mp3 = wav.with_suffix(".mp3")
        listo = mp3 if ffmpeg and convertir_a_mp3(wav, mp3, ffmpeg) else wav
        destino = directorio / listo.name
        os.replace(listo, destino)
    for formato in muestras.FORMATOS:
        otro = directorio / f"{base}.{formato}"
        if otro != destino:
            otro.unlink(missing_ok=True)
    return destino


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--forzar", action="store_true", help="regenera las cuatro muestras")
    args = parser.parse_args(argv)

    ajustes = get_settings()
    if ajustes.tts_motor == "xtts":
        print(
            "error   TTS_MOTOR=xtts narra a todos con la misma voz: no hay muestras que "
            "generar. Quita esa variable (o usa TTS_MOTOR=kokoro) y vuelve a correr.",
            file=sys.stderr,
        )
        return 1

    pendientes = []
    for preferencia in muestras.PREFERENCIAS:
        existente = muestras.archivo(preferencia)
        if existente and not args.forzar:
            print(f"ok      {existente.name} (ya estaba)")
        else:
            pendientes.append(preferencia)

    # Se revisa todo antes de sintetizar, para no dejar la mitad de las muestras.
    faltan = modelos_faltantes(pendientes, ajustes)
    if faltan:
        print(
            "error   faltan modelos de voz:\n"
            + "".join(f"          {ruta}\n" for ruta in faltan)
            + "        Ejecuta `python scripts/descargar_voces.py` desde la raíz del "
            "repositorio y vuelve a correr este script.",
            file=sys.stderr,
        )
        return 1

    ffmpeg = shutil.which("ffmpeg")
    if pendientes and not ffmpeg:
        print("aviso   no se encontró ffmpeg: las muestras quedan en WAV")

    muestras.DIRECTORIO_MUESTRAS.mkdir(parents=True, exist_ok=True)
    for preferencia in pendientes:
        try:
            destino = generar(preferencia, ffmpeg)
        except audio.ErrorAudio as error:
            print(f"error   {muestras.nombre_base(preferencia)}: {error}", file=sys.stderr)
            return 1
        print(f"ok      {destino.name} ({destino.stat().st_size / 1024:.0f} KB)")

    print(f"muestras en {muestras.DIRECTORIO_MUESTRAS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
