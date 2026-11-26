"""Una prueba por cada corrección de la revisión previa a la profesora (26-nov-2026).

Los identificadores `RV-xx` son los de esa revisión (AVANCE.md §5.39).
"""

import importlib.util
import io
import json
import logging
import threading
import zipfile
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.requests import Request

from studify import registro
from studify.config import get_settings
from studify.db.models import Estudiante, ObjetivoAprendizaje
from studify.knowledge.extract import ArchivoIlegible, extraer
from studify.main import app
from studify.web import sesion, textos
from studify.web.routers import auth
from tests import test_api_capsulas as pruebas_capsulas
from tests import test_interaccion_quiz as pruebas_quiz
from tests.conftest import CLAVE_DOCENTE, USUARIO_DOCENTE, cookie_de, necesita_bd
from tests.identidad_web import enviar_vark

RAIZ = Path(__file__).resolve().parents[1]
NAVEGADOR = {"accept": "text/html,application/xhtml+xml"}

escenario_capsulas = pruebas_capsulas.escenario
cliente_falso = pruebas_capsulas.cliente_falso
escenario_quiz = pruebas_quiz.escenario


def _como(id_estudiante: int) -> TestClient:
    cliente = TestClient(app)
    cliente.cookies.set("id_estudiante", cookie_de(id_estudiante))
    return cliente


@pytest.fixture
def google(monkeypatch):
    ajustes = get_settings()
    monkeypatch.setattr(ajustes, "google_client_id", "cliente-de-prueba")
    monkeypatch.setattr(ajustes, "google_client_secret", "secreto-de-prueba")


@pytest.fixture
def estudiantes(db):
    """Ids creados por una prueba; se borran al terminar."""
    ids: list[int] = []
    yield ids
    db.rollback()
    for id_estudiante in ids:
        if (fila := db.get(Estudiante, id_estudiante)) is not None:
            db.delete(fila)
    db.commit()


def _alta(db, estudiantes, rol="estudiante") -> TestClient:
    estudiante = Estudiante(rol=rol, google_sub=f"revision-{datetime.now(UTC).timestamp()}")
    db.add(estudiante)
    db.commit()
    estudiantes.append(estudiante.id_estudiante)
    cliente = TestClient(app)
    cliente.cookies.set(
        "id_estudiante", cookie_de(estudiante.id_estudiante), domain="testserver.local"
    )
    cliente.id_estudiante = estudiante.id_estudiante
    return cliente


# --- RV-04: ninguna IP en archivos ni en la consola -----------------------------


def test_un_acceso_docente_fallido_no_anota_la_direccion(tmp_path, clave_docente):
    registrador = logging.getLogger("studify")
    nivel = registrador.level
    ruta = registro.configurar_registro(tmp_path)
    auth.reiniciar_intentos()
    try:
        atacante = TestClient(app, client=("203.0.113.77", 5000))
        for _ in range(auth.INTENTOS_MAXIMOS + 1):
            atacante.post("/teacher/login", data={"usuario": "x", "clave": "mala"})
            atacante.get("/api/objetivos", auth=("x", "mala"))
    finally:
        auth.reiniciar_intentos()
        for manejador in list(registrador.handlers):
            if getattr(manejador, "baseFilename", "") == str(ruta):
                registrador.removeHandler(manejador)
                manejador.close()
        registrador.setLevel(nivel)

    contenido = ruta.read_text(encoding="utf-8")
    assert "credenciales de docente incorrectas" in contenido
    assert "bloqueado por intentos fallidos" in contenido
    assert "203.0.113.77" not in contenido


def test_el_registro_de_accesos_de_uvicorn_sale_sin_la_direccion(caplog):
    accesos = logging.getLogger("uvicorn.access")
    assert any(isinstance(f, registro.SinDireccionIP) for f in accesos.filters)
    linea = logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
        ("203.0.113.77:5000", "GET", "/student/login", "1.1", 200), None,
    )

    assert all(f.filter(linea) for f in accesos.filters)

    assert linea.getMessage() == '- - "GET /student/login HTTP/1.1" 200'


# --- RV-05: las páginas personales no quedan en el navegador --------------------


@pytest.mark.parametrize(
    "ruta",
    ["/student/vark", "/student/profile", "/mis-datos", "/mis-datos/exportar",
     "/teacher", "/teacher/login", "/teacher/analytics"],
)
def test_las_paginas_personales_no_se_guardan(ruta):
    respuesta = TestClient(app).get(ruta, follow_redirects=False)

    assert respuesta.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("ruta", ["/", "/privacidad", "/static/css/app.css"])
def test_lo_publico_se_puede_guardar(ruta):
    assert TestClient(app).get(ruta).headers.get("cache-control") != "no-store"


# --- RV-06: el enlace de la cabecera conserva el borrador -----------------------


@necesita_bd
def test_la_cabecera_conserva_la_continuacion_del_cuestionario(google):
    html = TestClient(app).get("/student/login?continuar=vark").text
    cabecera = html.split("</header>")[0]

    assert 'href="/student/login?continuar=vark"' in cabecera
    assert 'href="/student/login"' not in cabecera


@necesita_bd
def test_sin_cuestionario_pendiente_el_enlace_queda_igual(google):
    cabecera = TestClient(app).get("/student/login").text.split("</header>")[0]

    assert 'href="/student/login"' in cabecera


# --- RV-07: archivos que no se pueden abrir -------------------------------------


def _archivo_ilegible(carpeta: Path, caso: str) -> Path:
    pymupdf = pytest.importorskip("pymupdf")
    if caso == "protegido.pdf":
        documento = pymupdf.open()
        documento.new_page().insert_text((50, 50), "texto " * 30)
        documento.save(
            carpeta / caso, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="a", user_pw="b"
        )
    elif caso == "vacio.pdf":
        (carpeta / caso).write_bytes(b"")
    elif caso == "otro-zip.pptx":
        paquete = io.BytesIO()
        with zipfile.ZipFile(paquete, "w") as z:
            z.writestr("hola.txt", "no es una presentación")
        (carpeta / caso).write_bytes(paquete.getvalue())
    else:
        (carpeta / caso).write_bytes(b"esto no es un documento " * 20)
    return carpeta / caso


ILEGIBLES = [
    ("protegido.pdf", "protegido con contraseña"),
    ("vacio.pdf", "está vacío"),
    ("danado.pdf", "no se pudo abrir"),
    ("danado.pptx", "no se pudo abrir"),
    ("otro-zip.pptx", "no se pudo abrir"),
]


@pytest.mark.parametrize(("caso", "mensaje"), ILEGIBLES)
def test_un_archivo_ilegible_se_explica_y_no_queda_tomado(tmp_path, caso, mensaje):
    if caso.endswith(".pptx"):
        pytest.importorskip("pptx")
    ruta = _archivo_ilegible(tmp_path, caso)

    with pytest.raises(ArchivoIlegible, match=mensaje):
        extraer(ruta)

    ruta.unlink()  # en Windows falla si el lector dejó el archivo abierto


@necesita_bd
@pytest.mark.parametrize(("caso", "mensaje"), ILEGIBLES)
def test_subir_un_archivo_ilegible_responde_422_y_el_panel_lo_muestra(
    tmp_path, http_docente, caso, mensaje
):
    if caso.endswith(".pptx"):
        pytest.importorskip("pptx")
    ruta = _archivo_ilegible(tmp_path, caso)
    with ruta.open("rb") as fh:
        api = http_docente.post("/api/documentos", files={"archivo": (caso, fh)},
                                auth=(USUARIO_DOCENTE, CLAVE_DOCENTE))
    with ruta.open("rb") as fh:
        panel = http_docente.post("/teacher/curation/upload", files={"file": (caso, fh)})

    assert api.status_code == 422 and mensaje in api.json()["detail"]
    assert panel.status_code == 200
    assert "alerta-error" in panel.text and mensaje in panel.text
    assert "escaneados" not in panel.text


# --- RV-10: un doble clic no es un reintento -------------------------------------


@necesita_bd
def test_un_doble_clic_registra_un_solo_intento(db, escenario_quiz):
    capsula = escenario_quiz["capsula"]
    cliente = _como(escenario_quiz["duenio"].id_estudiante)
    ruta = f"/student/viewer/{capsula.id_capsula}/submit"

    primera = cliente.post(ruta, data={"answer": "1"})
    segunda = cliente.post(ruta, data={"answer": "1"})

    assert "No es esa" in primera.text and "No es esa" in segunda.text
    assert len(pruebas_quiz._intentos(db, capsula)) == 1
    # Cambiar la respuesta sí es un reintento, aunque sea inmediato.
    cliente.post(ruta, data={"answer": "0"})
    assert [i.numero_intento for i in pruebas_quiz._intentos(db, capsula)] == [1, 2]


@necesita_bd
def test_pasada_la_ventana_la_misma_respuesta_cuenta(db, escenario_quiz):
    capsula = escenario_quiz["capsula"]
    cliente = _como(escenario_quiz["duenio"].id_estudiante)
    ruta = f"/student/viewer/{capsula.id_capsula}/submit"
    cliente.post(ruta, data={"answer": "1"})
    [primero] = pruebas_quiz._intentos(db, capsula)
    primero.fecha_respuesta = primero.fecha_respuesta - timedelta(seconds=10)
    db.commit()

    cliente.post(ruta, data={"answer": "1"})

    assert len(pruebas_quiz._intentos(db, capsula)) == 2


def test_los_formularios_de_la_actividad_descartan_el_envio_repetido():
    plantilla = (RAIZ / "src/studify/web/templates/student/_capsula.html").read_text("utf-8")

    envios = plantilla.count('hx-post="/student/viewer/')
    assert envios == 4
    assert plantilla.count('hx-sync="this:drop" hx-post="/student/viewer/') == envios


# --- RV-11: objetivos en blanco o repetidos --------------------------------------


@pytest.fixture
def sin_objetivos_de_prueba(db):
    yield
    db.rollback()
    de_la_prueba = ObjetivoAprendizaje.codigo_objetivo.ilike("rv11%")
    for fila in db.scalars(select(ObjetivoAprendizaje).where(de_la_prueba)):
        db.delete(fila)
    db.commit()


@necesita_bd
@pytest.mark.parametrize("valor", ["", "   "])
def test_un_objetivo_en_blanco_se_rechaza_en_el_panel_y_la_api(db, http_docente, valor):
    datos = {"codigo_objetivo": valor, "asignatura": valor, "unidad": valor, "tema": valor}
    antes = db.query(ObjetivoAprendizaje).count()

    panel = http_docente.post("/teacher/curation/objetivos", data=datos)
    api = http_docente.post("/api/objetivos", json=datos)

    assert panel.status_code == 200
    assert "alerta-error" in panel.text and "tema: es obligatorio" in panel.text
    assert api.status_code == 422
    assert db.query(ObjetivoAprendizaje).count() == antes


@necesita_bd
def test_el_codigo_no_se_repite_cambiando_mayusculas(http_docente, sin_objetivos_de_prueba):
    datos = {"codigo_objetivo": "RV11-A", "asignatura": "a", "unidad": "u", "tema": "t"}
    assert http_docente.post("/api/objetivos", json=datos).status_code == 201

    repetido = http_docente.post("/api/objetivos", json=datos | {"codigo_objetivo": " rv11-a "})

    assert repetido.status_code == 409
    assert "RV11-A" in repetido.json()["detail"]


# --- RV-12 y RV-19: errores en español y sin 500 ---------------------------------


@pytest.mark.parametrize(
    ("ruta", "estado", "titulo"),
    [("/no-existe", 404, "No encontramos esa página"),
     ("/student/viewer/abc", 422, "La dirección no es válida")],
)
def test_quien_navega_ve_la_pagina_de_error_en_espanol(ruta, estado, titulo):
    respuesta = TestClient(app).get(ruta, headers=NAVEGADOR)

    assert respuesta.status_code == estado
    assert respuesta.headers["content-type"].startswith("text/html")
    assert titulo in respuesta.text and 'href="/"' in respuesta.text


@pytest.mark.parametrize(
    ("ruta", "cabeceras"),
    [("/no-existe", {}), ("/api/no-existe", NAVEGADOR),
     ("/no-existe", NAVEGADOR | {"HX-Request": "true"})],
)
def test_la_api_y_htmx_conservan_la_respuesta_json(ruta, cabeceras):
    respuesta = TestClient(app).get(ruta, headers=cabeceras)

    assert respuesta.status_code == 404
    assert respuesta.json() == {"detail": "Not Found"}


def test_un_error_inesperado_tambien_se_explica(monkeypatch):
    from studify.web.routers import legal

    def _romper(*args):
        raise RuntimeError("fallo de prueba")

    monkeypatch.setattr(legal, "_documento", _romper)
    cliente = TestClient(app, raise_server_exceptions=False)

    respuesta = cliente.get("/terminos", headers=NAVEGADOR)

    assert respuesta.status_code == 500
    assert "Algo salió mal" in respuesta.text and "fallo de prueba" not in respuesta.text


def test_teacher_lleva_al_panel(http_docente):
    respuesta = http_docente.get("/teacher", follow_redirects=False)

    assert (respuesta.status_code, respuesta.headers["location"]) == (303, "/teacher/curation")
    anonimo = TestClient(app).get("/teacher", follow_redirects=False)
    assert anonimo.headers["location"].startswith("/teacher/login")


GIGANTE = 99_999_999_999


@necesita_bd
def test_un_numero_enorme_no_provoca_un_500(db, estudiantes, http_docente):
    cliente = _alta(db, estudiantes)
    from studify.web import consentimiento

    consentimiento.registrar(db, cliente.id_estudiante)
    for metodo, ruta, quien, datos in [
        ("get", f"/student/viewer/{GIGANTE}", cliente, None),
        ("post", f"/student/viewer/{GIGANTE}/submit", cliente, {"answer": "0"}),
        ("post", f"/student/viewer/{GIGANTE}/generate-audio", cliente, None),
        ("get", f"/api/capsulas/{GIGANTE}", cliente, None),
        ("get", f"/teacher/curation?id_documento={GIGANTE}", http_docente, None),
        ("post", f"/teacher/curation/{GIGANTE}/reject", http_docente, None),
    ]:
        respuesta = quien.request(metodo.upper(), ruta, data=datos)
        assert respuesta.status_code == 422, (ruta, respuesta.status_code)


@pytest.mark.parametrize(
    "cookie",
    [b"id_estudiante=\xb2.1.1.a", b"id_estudiante=1.1.1.\xf1",
     b"docente=9999999999.\xf1", b"docente=\xb2.a"],
)
def test_una_cookie_con_caracteres_raros_se_ignora(cookie, clave_docente):
    """Se arma la petición a mano: `TestClient` recodificaría los bytes a UTF-8."""
    peticion = Request({"type": "http", "headers": [(b"cookie", cookie)]})

    assert sesion._leer(peticion) is None
    assert sesion.es_docente(peticion) is False


# --- RV-13: la navegación del docente --------------------------------------------


@necesita_bd
def test_el_docente_sin_sesion_de_estudiante_no_ve_destinos_ajenos(google, http_docente):
    html = http_docente.get("/teacher/analytics").text

    assert 'href="/student/catalog"' not in html.split("</header>")[0]
    assert 'class="tabbar"' not in html
    assert 'href="/student/login"' not in html.split("</header>")[0]


@necesita_bd
def test_con_las_dos_sesiones_la_navegacion_sigue_completa(db, estudiantes, http_docente):
    cliente = _alta(db, estudiantes)
    http_docente.cookies.set("id_estudiante", cliente.cookies["id_estudiante"])

    html = http_docente.get("/teacher/analytics").text

    assert 'class="tabbar"' in html


# --- RV-14: empates en el perfil --------------------------------------------------


def _perfil_con(db, estudiantes, respuestas: dict) -> str:
    cliente = TestClient(app)
    envio = enviar_vark(cliente, data=respuestas | {"acepto": "si"})
    assert envio.status_code == 204, envio.text
    estudiantes.append(int(cliente.cookies["id_estudiante"].split(".")[0]))
    return " ".join(cliente.get("/student/profile").text.split())


def _marcas(**por_canal) -> dict:
    from studify.vark import instrumento

    respuestas, item = {}, 1
    for canal, cantidad in por_canal.items():
        for _ in range(cantidad):
            letra = next(
                x for x in "abcd" if instrumento.canal_por_posicion(item, x) == canal
            )
            respuestas[f"q{item}"] = letra
            item += 1
    return respuestas


@necesita_bd
@pytest.mark.parametrize(
    ("reparto", "titulo"),
    [({"A": 8, "K": 8}, "Tienes un empate entre Auditivo y Kinestésico"),
     ({"V": 4, "A": 4, "R": 4, "K": 4}, "Tus cuatro canales están empatados"),
     ({"V": 1, "A": 1, "R": 1}, "Tienes un empate entre Visual, Auditivo y Lectura / Escritura")],
)
def test_con_empate_no_se_afirma_un_canal_principal(db, estudiantes, reparto, titulo):
    html = _perfil_con(db, estudiantes, _marcas(**reparto))

    assert titulo in html
    assert "Tu canal principal es" not in html
    assert ">Principal<" not in html and ">Empate<" in html
    assert "Jerarquía" not in html


@necesita_bd
def test_sin_empate_el_perfil_no_cambia(db, estudiantes):
    html = _perfil_con(db, estudiantes, _marcas(K=9, R=7))

    assert "Tu canal principal es" in html and "Jerarquía" in html
    assert "empate" not in html.lower()


# --- RV-15: la API no entrega las claves al estudiante ---------------------------


def _sin_claves(actividad: dict) -> bool:
    return not ({"indice_correcta", "retroalimentacion"} & set(actividad)) and not any(
        {"indice_correcta", "explicacion"} & set(p) for p in actividad.get("preguntas") or []
    )


@necesita_bd
def test_el_estudiante_no_recibe_las_claves_por_la_api(
    escenario_capsulas, cliente_falso, clave_docente
):
    estudiante = escenario_capsulas["estudiante"].id_estudiante
    cuerpo = {
        "id_estudiante": estudiante,
        "id_objetivo": escenario_capsulas["objetivo"].id_objetivo,
    }
    propio = _como(estudiante)

    creada = propio.post("/api/capsulas", json=cuerpo)
    leida = propio.get(f"/api/capsulas/{creada.json()['id_capsula']}")
    docente = TestClient(app).get(
        f"/api/capsulas/{creada.json()['id_capsula']}", auth=(USUARIO_DOCENTE, clave_docente)
    )

    assert (creada.status_code, leida.status_code) == (201, 200)
    assert _sin_claves(creada.json()["actividad"]) and _sin_claves(leida.json()["actividad"])
    assert not _sin_claves(docente.json()["actividad"])


# --- RV-18, RV-20, RV-22, RV-25, RV-28, RV-29, RV-31, RV-32 ------------------------


def test_las_fechas_se_muestran_en_hora_de_chile():
    assert textos.fecha_corta_chile(datetime(2026, 11, 27, 1, 30, tzinfo=UTC)) == "26-11-2026 22:30"
    for plantilla in ("teacher/analytics.html", "legal/mis_datos.html"):
        texto = (RAIZ / "src/studify/web/templates" / plantilla).read_text("utf-8")
        assert "strftime" not in texto and " UTC)" not in texto


@necesita_bd
@pytest.mark.parametrize(
    "datos",
    [{"rango_etario": "999 años"}, {"genero": "<b>otro</b>", "consiento_genero": "si"}],
)
def test_el_cuestionario_rechaza_opciones_inventadas(db, estudiantes, datos):
    cliente = TestClient(app)

    respuesta = enviar_vark(cliente, data={"q1": "a", "acepto": "si"} | datos)
    estudiantes.append(int(cliente.cookies["id_estudiante"].split(".")[0]))

    assert "no son opciones del formulario" in respuesta.text
    estudiante = db.get(Estudiante, estudiantes[-1])
    assert (estudiante.rango_etario, estudiante.genero, estudiante.diagnosticos) == (None, None, [])


@necesita_bd
def test_el_registro_del_control_rechaza_opciones_inventadas(db, estudiantes):
    from tests.identidad_web import control_google_sin_registro
    from tests.test_grupo_control import _token_control

    cliente = TestClient(app)
    estudiantes.append(control_google_sin_registro(cliente))

    respuesta = cliente.post("/student/control", data={
        "acepto": "si", "token_sesion": _token_control(cliente), "rango_etario": "999 años",
    })

    assert "no son opciones del formulario" in respuesta.text
    assert db.get(Estudiante, estudiantes[-1]).rango_etario is None


def test_la_comparacion_del_simulador_usa_rotulos_en_espanol():
    plantilla = (RAIZ / "src/studify/web/templates/teacher/_comparacion.html").read_text("utf-8")

    assert "NOMBRE_BLOQUE.get(bloque.tipo" in plantilla
    assert "NOMBRE_ACTIVIDAD.get(col.capsula.actividad.tipo" in plantilla
    assert textos.NOMBRE_BLOQUE["parrafo"] == "Párrafo"


@pytest.mark.parametrize("ruta", ["/", "/terminos", "/privacidad"])
def test_ninguna_pagina_atribuye_la_validacion_a_un_docente(ruta):
    plano = " ".join(TestClient(app).get(ruta).text.split()).lower()

    assert "autorización de la profesora del curso" in plano
    for ausente in ("validados por un docente", "un docente ya revisó", "por el equipo docente"):
        assert ausente not in plano
    assert "sin crear cuenta" not in plano


def test_la_politica_describe_lo_que_hace_la_app():
    plano = " ".join(TestClient(app).get("/privacidad").text.split())

    for presente in ("Guardamos tu nombre y tu correo verificado", "túnel de Cloudflare",
                     "según sus propios términos y su política de privacidad", "sin direcciones IP",
                     "repasai-carga-visor"):
        assert presente in plano, presente
    for ausente in ("No recolectamos", "Como no te pedimos nombre ni correo",
                    "encargado del tratamiento", "encargados del tratamiento",
                    "Como no tenemos tu correo", "sin acceso público desde internet",
                    "no se guardan en archivo"):
        assert ausente not in plano, ausente


@pytest.mark.parametrize(
    ("cantidad", "esperado"),
    [(0, "0 fragmentos"), (1, "1 fragmento"), (2, "2 fragmentos")],
)
def test_las_cantidades_concuerdan(cantidad, esperado):
    assert textos.cuenta(cantidad, "fragmento") == esperado


@necesita_bd
def test_el_perfil_concuerda_en_singular(db, estudiantes):
    # Un solo componente práctico: K presente bajo el 25 %.
    html = _perfil_con(db, estudiantes, _marcas(A=9, R=4, K=3))

    assert "componente práctico<" in html and "componentes prácticos<" not in html


@necesita_bd
def test_las_tarjetas_responden_con_un_texto_neutro(escenario_quiz):
    respuesta = _como(escenario_quiz["duenio"].id_estudiante).post(
        f"/student/viewer/{escenario_quiz['repaso'].id_capsula}/submit",
        data={"answer": "completado"},
    )

    assert "Repaso con tarjetas completado" in respuesta.text
    for ausente in ("kinest", "Active Recall", "Flashcards"):
        assert ausente not in respuesta.text


@necesita_bd
def test_mis_datos_del_control_no_habla_de_sus_respuestas(db, estudiantes):
    from studify.web import consentimiento

    cliente = _alta(db, estudiantes, rol="control")
    consentimiento.registrar(db, cliente.id_estudiante)

    html = cliente.get("/mis-datos").text

    assert "No aplica en el grupo control" in html and "hora de Chile" in html


def test_el_aviso_sin_modelo_no_nombra_variables_de_entorno():
    from fastapi import HTTPException

    from studify.web.routers.student import _explicar_fallo

    titulo, mensaje = _explicar_fallo(HTTPException(503, "falta LLM_API_KEY en el .env"))

    assert "LLM_API_KEY" not in titulo + mensaje and ".env" not in mensaje


# --- RV-01: comprobar el túnel ----------------------------------------------------

_spec = importlib.util.spec_from_file_location(
    "verificar_tunel", RAIZ / "scripts" / "verificar_tunel.py"
)
tunel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tunel)


class _Metricas(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self.send_response(200 if self.path == "/quicktunnel" else 404)
        self.end_headers()
        self.wfile.write(json.dumps({"hostname": "nuevo.trycloudflare.com"}).encode())

    def log_message(self, *args):
        pass


@pytest.fixture
def cloudflared_falso(monkeypatch):
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), _Metricas)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    monkeypatch.setattr(tunel, "PUERTOS_METRICAS", [servidor.server_port])
    yield
    servidor.shutdown()
    servidor.server_close()


@pytest.mark.parametrize(
    ("configurada", "codigo", "frase"),
    [("https://nuevo.trycloudflare.com/student/google/callback", 0, "Coinciden"),
     ("https://viejo.trycloudflare.com/student/google/callback", 1, "NO COINCIDEN"),
     ("http://127.0.0.1:8000/student/google/callback", 1, "NO COINCIDEN")],
)
def test_avisa_si_el_retorno_no_es_el_del_tunel_activo(
    cloudflared_falso, monkeypatch, capsys, configurada, codigo, frase
):
    monkeypatch.setattr(get_settings(), "google_redirect_uri", configurada)

    assert tunel.main([]) == codigo

    salida = capsys.readouterr().out
    assert frase in salida
    assert "nuevo.trycloudflare.com" in salida


def test_sin_tunel_abierto_lo_dice(monkeypatch, capsys):
    monkeypatch.setattr(tunel, "PUERTOS_METRICAS", [])

    assert tunel.main([]) == 2
    assert "No encontré un túnel abierto" in capsys.readouterr().out
