"""Muestras de voz del selector: un mismo texto narrado con cada voz.

El estudiante las escucha antes de elegir. Se generan **una sola vez** con
`scripts/generar_muestras_voz.py`, por la misma ruta que la narración del visor
(`audio.generar_audio`), y se sirven como archivos estáticos: no hay síntesis
en ninguna petición.

Van en su propia carpeta, aparte del caché por huella de `public/audio`: son
las mismas para todos, no contienen datos personales y la supresión de datos no
las toca. No se versionan (ver `.gitignore` y AVANCE.md §5.38).
"""

from pathlib import Path

from studify.config import get_settings
from studify.media.audio import PreferenciaVoz

# El único texto de las cuatro muestras. Si cambia, hay que regenerarlas con
# `--forzar`: el script no compara el contenido de los archivos que ya existen.
TEXTO_MUESTRA = (
    "Hola, así sonará la narración de tus cápsulas. Puedes cambiar la voz cuando quieras."
)

# Junto al paquete, como `narracion.DIRECTORIO_AUDIO`: dentro de lo que
# `main.py` publica en `/public`, sin depender del directorio de trabajo.
DIRECTORIO_MUESTRAS = Path(__file__).resolve().parents[1] / "public" / "muestras_voz"
URL_MUESTRAS = "/public/muestras_voz"

# En orden de preferencia: el MP3 (si había ffmpeg) y, si no, el WAV.
FORMATOS = ("mp3", "wav")

PREFERENCIAS: tuple[PreferenciaVoz, ...] = tuple(
    PreferenciaVoz(genero=genero, modo=modo)
    for modo in ("calidad", "rapida")
    for genero in ("femenina", "masculina")
)


def nombre_base(preferencia: PreferenciaVoz) -> str:
    """El nombre del archivo sin extensión, p. ej. `calidad_femenina`."""
    return f"{preferencia.modo}_{preferencia.genero}"


def archivo(preferencia: PreferenciaVoz) -> Path | None:
    """La muestra de esa voz en disco, o `None` si no se ha generado."""
    for formato in FORMATOS:
        ruta = DIRECTORIO_MUESTRAS / f"{nombre_base(preferencia)}.{formato}"
        if ruta.is_file():
            return ruta
    return None


def url(opcion: str) -> str | None:
    """La URL de la muestra de una opción del selector («<genero>-<modo>»).

    `None` cuando no hay nada que ofrecer, y entonces el selector no dibuja el
    botón: falta el archivo, o `TTS_MOTOR=xtts`, caso en que el visor narra a
    todos con la voz clonada y una muestra de Kokoro o Piper engañaría.

    La versión (`?v=`) es la fecha del archivo: permite que el navegador lo
    guarde sin volver a preguntar y que aun así reciba una muestra regenerada.
    """
    if get_settings().tts_motor == "xtts":
        return None
    genero, modo = opcion.split("-")
    ruta = archivo(PreferenciaVoz(genero=genero, modo=modo))
    if ruta is None:
        return None
    return f"{URL_MUESTRAS}/{ruta.name}?v={ruta.stat().st_mtime_ns}"
