"""Registro de la app en un archivo rotativo.

Hasta el 08-nov-2026 los `logger.error` de la app (generación agotada, proveedor
del modelo caído, audio) solo salían por la consola de uvicorn: al cerrarla se
perdían, y un fallo de generación no deja ninguna fila en la base. Así pasó con
la cápsula que falló en la prueba de usuario de ese día: no se pudo saber qué
tema se pidió ni por qué falló.

Se registra solo la jerarquía `studify.*`, no la de uvicorn ni la de las
bibliotecas: el archivo es para diagnosticar la app, no un log de accesos.
Los mensajes identifican al estudiante solo por su id (sin nombre, correo ni
respuestas), igual que el resto de los logs del proyecto.

**Ninguna dirección IP se escribe.** Los mensajes de la app no la incluyen, y
`ocultar_direcciones_en_accesos` la quita del registro de accesos de uvicorn,
que sale por consola: así tampoco queda guardada si alguien redirige esa salida
a un archivo, como ocurrió durante el piloto (RV-04, 26-nov-2026).
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# <raíz del repo>/logs, ignorado por Git.
DIRECTORIO_LOGS = Path(__file__).resolve().parents[2] / "logs"
NOMBRE_ARCHIVO = "studify.log"

# 1 MB por archivo y 5 respaldos: semanas de uso del piloto en menos de 6 MB.
MAX_BYTES = 1_000_000
RESPALDOS = 5

FORMATO = "%(asctime)s %(levelname)s %(name)s: %(message)s"
FORMATO_FECHA = "%Y-%m-%d %H:%M:%S%z"


class SinDireccionIP(logging.Filter):
    """Reemplaza por «-» la dirección del cliente en una línea de acceso de uvicorn.

    Uvicorn manda esas líneas con los argumentos
    `(cliente, método, ruta, versión_http, estado)`.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and len(record.args) == 5:
            record.args = ("-", *record.args[1:])
        return True


def ocultar_direcciones_en_accesos() -> None:
    """Instala `SinDireccionIP` en `uvicorn.access`. Es idempotente."""
    accesos = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, SinDireccionIP) for f in accesos.filters):
        accesos.addFilter(SinDireccionIP())


def configurar_registro(
    directorio: Path = DIRECTORIO_LOGS, *, nivel: int = logging.INFO
) -> Path:
    """Agrega al logger `studify` un `RotatingFileHandler` y devuelve la ruta.

    Es idempotente: con `uvicorn --reload` el módulo principal se vuelve a
    importar y, sin esta guarda, cada recarga duplicaría las líneas del archivo.
    `propagate` queda como estaba, así que los mensajes siguen saliendo también
    por la consola.
    """
    directorio.mkdir(parents=True, exist_ok=True)
    ruta = (directorio / NOMBRE_ARCHIVO).resolve()

    logger = logging.getLogger("studify")
    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler) and Path(handler.baseFilename) == ruta:
            return ruta

    handler = RotatingFileHandler(
        ruta, maxBytes=MAX_BYTES, backupCount=RESPALDOS, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(FORMATO, datefmt=FORMATO_FECHA))
    logger.addHandler(handler)
    # Sin nivel propio el logger hereda WARNING del root y descartaría los INFO.
    if logger.level == logging.NOTSET or logger.level > nivel:
        logger.setLevel(nivel)
    return ruta
