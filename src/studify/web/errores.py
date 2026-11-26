"""Páginas de error en español para quien navega (RV-12, RV-19).

Solo cambia lo que ve una **persona**: una petición de navegador (`Accept:
text/html`) fuera de `/api`. La API, HTMX y los scripts siguen recibiendo lo
mismo de siempre, así que sus contratos no se tocan.

Aparte, un número que no cabe en la columna de la base (p. ej.
`/student/viewer/99999999999`) responde 422 y no 500. Se resuelve acá, en un
solo lugar, en vez de acotar cada parámetro de cada ruta.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from psycopg.errors import NumericValueOutOfRange
from sqlalchemy.exc import DataError
from starlette.exceptions import HTTPException as StarletteHTTPException

from studify.web.deps import templates

logger = logging.getLogger(__name__)

# Rutas que consumen programas: conservan su respuesta JSON.
PREFIJOS_DE_PROGRAMAS = ("/api/", "/docs", "/redoc", "/openapi.json", "/health")

MENSAJES = {
    400: ("No pudimos procesar la solicitud", "Revisa la dirección y vuelve a intentarlo."),
    403: ("No tienes acceso a esta página", "Tu sesión no permite abrirla."),
    404: ("No encontramos esa página", "La dirección no existe o ya no está disponible."),
    405: ("Esa dirección no se abre así", "Vuelve al inicio y entra desde ahí."),
    422: ("La dirección no es válida", "Alguno de sus datos no corresponde. Vuelve al inicio."),
    500: (
        "Algo salió mal",
        "Vuelve a intentarlo en un momento. Si se repite, avísale al equipo.",
    ),
}


def _es_navegacion(request: Request) -> bool:
    return (
        not request.url.path.startswith(PREFIJOS_DE_PROGRAMAS)
        and "text/html" in request.headers.get("accept", "")
        and request.headers.get("hx-request") != "true"
    )


def _pagina(request: Request, estado: int, mensaje: str | None = None):
    titulo, detalle = MENSAJES[estado]
    try:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={"titulo": titulo, "mensaje": mensaje or detalle},
            status_code=estado,
        )
    except Exception:  # la página de error nunca puede provocar otro error
        logger.exception("no se pudo dibujar la página de error %s", estado)
        return PlainTextResponse(titulo, status_code=estado)


async def _http(request: Request, exc: StarletteHTTPException):
    if exc.status_code in MENSAJES and _es_navegacion(request):
        # Los 400 de la app traen una explicación propia en español (p. ej. la
        # fecha mal escrita del CSV); en el resto, el detalle es técnico.
        return _pagina(request, exc.status_code, exc.detail if exc.status_code == 400 else None)
    return await http_exception_handler(request, exc)


async def _validacion(request: Request, exc: RequestValidationError):
    if _es_navegacion(request):
        return _pagina(request, 422)
    return await request_validation_exception_handler(request, exc)


async def _dato_fuera_de_rango(request: Request, exc: DataError):
    if not isinstance(exc.orig, NumericValueOutOfRange):
        raise exc
    if _es_navegacion(request):
        return _pagina(request, 422)
    return JSONResponse({"detail": "número fuera del rango permitido"}, status_code=422)


async def _inesperado(request: Request, exc: Exception):
    # Starlette vuelve a levantar la excepción después de responder, así que la
    # traza sigue saliendo en la consola del servidor.
    if _es_navegacion(request):
        return _pagina(request, 500)
    return PlainTextResponse("Internal Server Error", status_code=500)


def registrar(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http)
    app.add_exception_handler(RequestValidationError, _validacion)
    app.add_exception_handler(DataError, _dato_fuera_de_rango)
    app.add_exception_handler(Exception, _inesperado)
