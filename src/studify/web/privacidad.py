"""Que las páginas con datos de una persona no queden en el navegador (RV-05).

«Salir» borra la cookie, pero el navegador guardaba la página ya dibujada: con
«atrás», la siguiente persona del mismo computador veía «Mis datos» de la
anterior. `Cache-Control: no-store` obliga a pedirla de nuevo, y sin sesión el
servidor ya no la entrega.

Es un middleware ASGI y no una dependencia por router porque también tiene que
cubrir las redirecciones y los errores de esas rutas.
"""

from starlette.datastructures import MutableHeaders

# Las vistas del estudiante, «Mis datos» y sus acciones, y el panel del docente.
RUTAS_PERSONALES = ("/student/", "/mis-datos", "/teacher")


class SinCacheEnPaginasPersonales:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith(RUTAS_PERSONALES):
            await self.app(scope, receive, send)
            return

        async def enviar(mensaje):
            if mensaje["type"] == "http.response.start":
                MutableHeaders(scope=mensaje)["Cache-Control"] = "no-store"
            await send(mensaje)

        await self.app(scope, receive, enviar)
