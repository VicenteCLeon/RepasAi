"""Muestras de voz del selector: el script que las genera y cómo se ofrecen.

Sin modelos ni red: los motores se sustituyen por un doble en `audio.MOTORES`
(como en `test_audio.py`) y las muestras se escriben en un directorio temporal.
Las dos pantallas completas (visor y perfil) se prueban en
`test_preferencia_voz.py`, que ya tiene su escenario con base de datos.
"""

import importlib.util
import shutil
import subprocess
import wave
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studify.config import get_settings
from studify.main import EstaticosConCache, app
from studify.media import audio, muestras
from studify.media.guion import normalizar_guion
from studify.web.deps import templates
from studify.web.textos import OPCIONES_VOZ

RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "generar_muestras_voz", RAIZ / "scripts" / "generar_muestras_voz.py"
)
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)

NOMBRES = ("calidad_femenina", "calidad_masculina", "rapida_femenina", "rapida_masculina")
ETIQUETAS = [
    "Escuchar voz Calidad, mujer",
    "Escuchar voz Calidad, hombre",
    "Escuchar voz Rápida, mujer",
    "Escuchar voz Rápida, hombre",
]


@pytest.fixture(autouse=True)
def carpeta(monkeypatch, tmp_path) -> Path:
    """Las muestras van a un directorio temporal: el del repo no se toca."""
    directorio = tmp_path / "muestras_voz"
    directorio.mkdir()
    monkeypatch.setattr(muestras, "DIRECTORIO_MUESTRAS", directorio)
    monkeypatch.setattr(get_settings(), "tts_motor", "kokoro")
    return directorio


@pytest.fixture
def modelos(monkeypatch, tmp_path) -> Path:
    """Los cuatro archivos de modelo, vacíos: al script le basta con que estén."""
    voces = tmp_path / "voces"
    voces.mkdir()
    ajustes = get_settings()
    monkeypatch.setattr(ajustes, "tts_modelos_dir", str(voces))
    for nombre in (
        audio.KOKORO_MODELO,
        audio.KOKORO_VOCES,
        f"{ajustes.tts_voz_rapida_modelo}.onnx",
        f"{ajustes.tts_voz_rapida_modelo}.onnx.json",
    ):
        (voces / nombre).write_bytes(b"")
    return voces


@pytest.fixture
def sintesis(monkeypatch) -> list[tuple[str, audio.VozElegida, str]]:
    """Motores falsos que anotan (archivo, voz, guion) y dejan un WAV corto."""
    llamadas: list[tuple[str, audio.VozElegida, str]] = []

    def _falso(guion, destino, eleccion, language, ajustes):
        # El nombre del temporal de `generar_audio` es `.<base>.<hex>.partial.wav`.
        llamadas.append((destino.name.split(".")[1], eleccion, guion))
        with wave.open(str(destino), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(b"\x00\x00" * 2400)

    for motor in ("kokoro", "piper", "xtts"):
        monkeypatch.setitem(audio.MOTORES, motor, _falso)
    return llamadas


@pytest.fixture
def sin_ffmpeg(monkeypatch):
    monkeypatch.setattr(script.shutil, "which", lambda _: None)


def _archivos(directorio: Path) -> list[str]:
    return sorted(p.name for p in directorio.iterdir())


def _crear_muestras(directorio: Path, nombres=NOMBRES, formato="mp3") -> None:
    for nombre in nombres:
        (directorio / f"{nombre}.{formato}").write_bytes(b"audio falso")


# --- El script ------------------------------------------------------------------


def test_genera_las_cuatro_con_el_mismo_texto_y_la_voz_de_cada_una(
    carpeta, modelos, sintesis, sin_ffmpeg
):
    assert script.main([]) == 0

    assert _archivos(carpeta) == [f"{nombre}.wav" for nombre in NOMBRES]
    sharvard = "es_ES-sharvard-medium"
    assert {nombre: voz for nombre, voz, _ in sintesis} == {
        "calidad_femenina": audio.VozElegida("kokoro", "ef_dora"),
        "calidad_masculina": audio.VozElegida("kokoro", "em_alex"),
        "rapida_femenina": audio.VozElegida("piper", sharvard, 1),
        "rapida_masculina": audio.VozElegida("piper", sharvard, 0),
    }
    assert len(sintesis) == 4
    # El mismo texto para las cuatro, ya normalizado como un guion real.
    assert {guion for *_, guion in sintesis} == {normalizar_guion(muestras.TEXTO_MUESTRA)}


def test_el_texto_pasa_por_la_normalizacion_del_guion(
    carpeta, modelos, sintesis, sin_ffmpeg, monkeypatch
):
    monkeypatch.setattr(muestras, "TEXTO_MUESTRA", "Se lee X -> Y.")

    script.main([])

    assert {guion for *_, guion in sintesis} == {normalizar_guion("Se lee X -> Y.")}
    assert "->" not in sintesis[0][2]


def test_una_segunda_corrida_no_regenera_y_forzar_si(carpeta, modelos, sintesis, sin_ffmpeg):
    script.main([])
    assert script.main([]) == 0
    assert len(sintesis) == 4

    assert script.main(["--forzar"]) == 0
    assert len(sintesis) == 8
    assert _archivos(carpeta) == [f"{nombre}.wav" for nombre in NOMBRES]


def test_solo_genera_la_que_falta(carpeta, modelos, sintesis, sin_ffmpeg):
    _crear_muestras(carpeta, NOMBRES[:3])

    script.main([])

    assert [nombre for nombre, *_ in sintesis] == ["rapida_masculina"]


def test_con_ffmpeg_deja_mp3_y_borra_el_wav_anterior(carpeta, modelos, sintesis, monkeypatch):
    _crear_muestras(carpeta, formato="wav")
    monkeypatch.setattr(script.shutil, "which", lambda _: "ffmpeg")

    def _convertir(wav, mp3, ffmpeg):
        mp3.write_bytes(b"mp3 falso")
        return True

    monkeypatch.setattr(script, "convertir_a_mp3", _convertir)

    script.main(["--forzar"])

    assert _archivos(carpeta) == [f"{nombre}.mp3" for nombre in NOMBRES]


def test_si_ffmpeg_falla_queda_el_wav(carpeta, modelos, sintesis, monkeypatch, capsys):
    monkeypatch.setattr(script.shutil, "which", lambda _: "ffmpeg")
    monkeypatch.setattr(
        script.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "Unknown encoder"),
    )

    assert script.main([]) == 0

    assert _archivos(carpeta) == [f"{nombre}.wav" for nombre in NOMBRES]
    assert "Unknown encoder" in capsys.readouterr().out


@pytest.mark.parametrize("ausente", [audio.KOKORO_MODELO, "es_ES-sharvard-medium.onnx"])
def test_sin_un_modelo_falla_antes_de_sintetizar(carpeta, modelos, sintesis, capsys, ausente):
    (modelos / ausente).unlink()

    assert script.main([]) == 1

    error = capsys.readouterr().err
    assert ausente in error and "scripts/descargar_voces.py" in error
    assert sintesis == [] and _archivos(carpeta) == []


def test_con_las_muestras_ya_hechas_no_exige_los_modelos(carpeta, monkeypatch, tmp_path):
    _crear_muestras(carpeta)
    monkeypatch.setattr(get_settings(), "tts_modelos_dir", str(tmp_path / "no-existe"))

    assert script.main([]) == 0


def test_un_fallo_del_motor_se_informa_y_no_deja_restos(
    carpeta, modelos, monkeypatch, sin_ffmpeg, capsys
):
    def _roto(*args):
        raise audio.ErrorAudio("falta el paquete de Kokoro")

    monkeypatch.setitem(audio.MOTORES, "kokoro", _roto)

    assert script.main([]) == 1

    assert "falta el paquete de Kokoro" in capsys.readouterr().err
    assert _archivos(carpeta) == []


def test_con_xtts_no_hay_muestras_que_generar(carpeta, sintesis, monkeypatch, capsys):
    monkeypatch.setattr(get_settings(), "tts_motor", "xtts")

    assert script.main([]) == 1
    assert "xtts" in capsys.readouterr().err
    assert sintesis == []


# --- La URL y el servidor -------------------------------------------------------


def test_sin_archivo_no_hay_url(carpeta):
    assert muestras.url("femenina-calidad") is None


def test_la_url_lleva_la_version_y_prefiere_el_mp3(carpeta):
    _crear_muestras(carpeta, ["calidad_femenina"], "wav")
    assert muestras.url("femenina-calidad").startswith(
        "/public/muestras_voz/calidad_femenina.wav?v="
    )

    _crear_muestras(carpeta, ["calidad_femenina"], "mp3")
    assert muestras.url("femenina-calidad").startswith(
        "/public/muestras_voz/calidad_femenina.mp3?v="
    )


def test_con_xtts_no_se_ofrecen_muestras(carpeta, monkeypatch):
    _crear_muestras(carpeta)
    monkeypatch.setattr(get_settings(), "tts_motor", "xtts")

    assert muestras.url("femenina-calidad") is None


def test_las_muestras_se_sirven_sin_sesion_y_con_cache_del_navegador(tmp_path):
    (tmp_path / "calidad_femenina.mp3").write_bytes(b"audio falso")
    servidor = FastAPI()
    servidor.mount("/m", EstaticosConCache(directory=tmp_path))
    cliente = TestClient(servidor)

    primera = cliente.get("/m/calidad_femenina.mp3")
    revalidada = cliente.get(
        "/m/calidad_femenina.mp3", headers={"If-None-Match": primera.headers["etag"]}
    )

    assert primera.status_code == 200
    assert primera.headers["content-type"] == "audio/mpeg"
    assert "max-age=31536000" in primera.headers["cache-control"]
    assert revalidada.status_code == 304
    assert "max-age=31536000" in revalidada.headers["cache-control"]
    assert cliente.get("/m/otra.mp3").status_code == 404


def test_la_app_monta_las_muestras_antes_que_public():
    rutas = [getattr(ruta, "path", "") for ruta in app.routes]

    assert rutas.index("/public/muestras_voz") < rutas.index("/public")
    montaje = app.routes[rutas.index("/public/muestras_voz")]
    assert isinstance(montaje.app, EstaticosConCache)
    # El `.gitkeep` asegura que la carpeta exista aunque no se hayan generado.
    assert TestClient(app).get("/public/muestras_voz/no-existe.mp3").status_code == 404


# --- El selector ------------------------------------------------------------------


class _Selector(HTMLParser):
    """Los botones de muestra, sus audios y si alguno quedó dentro de un <label>."""

    def __init__(self, html: str) -> None:
        super().__init__()
        self.botones: list[dict] = []
        self.audios: list[dict] = []
        self.radios = 0
        self.botones_en_label = 0
        self._en_label = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        atributos = dict(attrs)
        if tag == "label":
            self._en_label = True
        elif tag == "button" and "data-muestra-voz" in atributos:
            self.botones.append(atributos)
            self.botones_en_label += self._en_label
        elif tag == "audio":
            self.audios.append(atributos)
        elif tag == "input" and atributos.get("type") == "radio":
            self.radios += 1

    def handle_endtag(self, tag):
        if tag == "label":
            self._en_label = False


def _selector(contexto: str) -> _Selector:
    html = templates.env.get_template("student/_selector_voz.html").render(
        contexto=contexto, voz_actual="femenina-calidad", audio_id=1, uid=1
    )
    return _Selector(html)


@pytest.mark.parametrize("contexto", ["visor", "perfil"])
def test_el_selector_ofrece_una_muestra_por_voz(carpeta, contexto):
    _crear_muestras(carpeta)

    selector = _selector(contexto)

    assert [b["aria-label"] for b in selector.botones] == ETIQUETAS
    assert [a["src"].split("?")[0] for a in selector.audios] == [
        f"/public/muestras_voz/{nombre}.mp3"
        for nombre in (
            "calidad_femenina",
            "calidad_masculina",
            "rapida_femenina",
            "rapida_masculina",
        )
    ]
    assert all(a["preload"] == "none" and "autoplay" not in a for a in selector.audios)
    assert selector.radios == len(OPCIONES_VOZ) == 4


@pytest.mark.parametrize("contexto", ["visor", "perfil"])
def test_el_boton_de_muestra_no_envia_ni_marca_nada(carpeta, contexto):
    """`type="button"`, sin atributos de HTMX y fuera del `<label>` del radio."""
    _crear_muestras(carpeta)

    selector = _selector(contexto)

    assert len(selector.botones) == 4
    for boton in selector.botones:
        assert boton["type"] == "button"
        assert not [a for a in boton if a.startswith(("hx-", "data-hx-", "form", "name"))]
    assert selector.botones_en_label == 0


def test_si_falta_una_muestra_solo_desaparece_su_boton(carpeta):
    _crear_muestras(carpeta, [n for n in NOMBRES if n != "calidad_masculina"])

    selector = _selector("perfil")

    assert [b["aria-label"] for b in selector.botones] == [ETIQUETAS[0], *ETIQUETAS[2:]]
    assert len(selector.audios) == 3
    assert selector.radios == 4


def test_sin_ninguna_muestra_el_selector_queda_como_antes(carpeta):
    selector = _selector("visor")

    assert selector.botones == [] and selector.audios == []
    assert selector.radios == 4


@pytest.mark.skipif(shutil.which("node") is None, reason="requiere node")
def test_reproducir_no_guarda_la_voz_y_solo_suena_una():
    """El comportamiento de `app.js`, ejecutado en node (`test_muestras_voz.cjs`)."""
    resultado = subprocess.run(
        ["node", str(RAIZ / "tests" / "test_muestras_voz.cjs")],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert resultado.returncode == 0, resultado.stderr
