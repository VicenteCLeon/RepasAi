// Muestras de voz del selector: reproducir no guarda y solo suena una a la vez.
// Ejecuta el módulo real de app.js con botones y audios falsos; no requiere
// navegador ni dependencias npm.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname,
  "../src/studify/web/static/js/app.js"), "utf8");
new vm.Script(source); // Comprueba la sintaxis de todo app.js.
const inicio = source.indexOf("  let detenerMuestra = null;");
const fin = source.indexOf("  // Registro de módulos", inicio);
assert.ok(inicio >= 0 && fin > inicio, "No se encontró initMuestraVoz");
assert.ok(source.includes('["[data-muestra-voz]", initMuestraVoz]'), "módulo sin registrar");

// Cualquier intento de pedir o enviar algo hace fallar la prueba.
const peticiones = [];
const prohibido = (nombre) => () => { peticiones.push(nombre); };
const contexto = {
  fetch: prohibido("fetch"),
  XMLHttpRequest: prohibido("XMLHttpRequest"),
  htmx: { ajax: prohibido("htmx.ajax"), trigger: prohibido("htmx.trigger") },
  navigator: { sendBeacon: prohibido("sendBeacon") },
};
const modulo = vm.runInNewContext(
  "(function () {" + source.slice(inicio, fin) + "; return initMuestraVoz; })()", contexto);

function emisor(base) {
  const oyentes = {};
  return Object.assign(base, {
    addEventListener: (tipo, fn) => (oyentes[tipo] = oyentes[tipo] || []).push(fn),
    emitir: (tipo) => (oyentes[tipo] || []).forEach((fn) => fn({ type: tipo })),
  });
}

function opcion(nombre, falla) {
  const audio = emisor({
    paused: true, currentTime: 0, reproducciones: 0,
    play() {
      this.reproducciones++;
      if (falla) return Promise.reject(Object.assign(new Error(), { name: falla }));
      this.paused = false;
      return Promise.resolve();
    },
    pause() { this.paused = true; },
  });
  const clases = new Set();
  const atributos = { "aria-label": `Escuchar ${nombre}` };
  const boton = emisor({
    hidden: true, disabled: false, title: "", dataset: { muestraVoz: nombre },
    nextElementSibling: audio,
    form: { requestSubmit: prohibido("requestSubmit"), submit: prohibido("submit") },
    classList: {
      contains: (c) => clases.has(c),
      toggle: (c, si) => (si ? clases.add(c) : clases.delete(c)),
    },
    setAttribute: (n, v) => { atributos[n] = v; },
    click: prohibido("click programático"),
  });
  modulo(boton);
  return { boton, audio, sonando: () => clases.has("is-playing"), etiqueta: () => atributos["aria-label"] };
}

(async () => {
  const a = opcion("voz Calidad, mujer");
  const b = opcion("voz Rápida, hombre");
  // Con JS el botón aparece; hasta el clic no se reproduce (ni descarga) nada.
  assert.equal(a.boton.hidden, false);
  assert.equal(a.audio.reproducciones, 0);

  a.boton.emitir("click");
  assert.equal(a.audio.reproducciones, 1);
  assert.equal(a.sonando(), true);
  assert.equal(a.etiqueta(), "Detener voz Calidad, mujer");

  // Otra muestra detiene la anterior y la rebobina.
  a.audio.currentTime = 2;
  b.boton.emitir("click");
  assert.equal(a.audio.paused, true);
  assert.equal(a.audio.currentTime, 0);
  assert.equal(a.sonando(), false);
  assert.equal(a.etiqueta(), "Escuchar voz Calidad, mujer");
  assert.equal(b.sonando(), true);

  // El mismo botón detiene.
  b.boton.emitir("click");
  assert.equal(b.audio.paused, true);
  assert.equal(b.sonando(), false);
  assert.equal(b.audio.reproducciones, 1);

  // Al terminar, vuelve a «Escuchar» desde el principio.
  b.boton.emitir("click");
  b.audio.paused = true;
  b.audio.currentTime = 5;
  b.audio.emitir("ended");
  assert.equal(b.sonando(), false);
  assert.equal(b.audio.currentTime, 0);
  assert.equal(b.etiqueta(), "Escuchar voz Rápida, hombre");

  // Una pausa externa se refleja; un evento «pause» atrasado no apaga la nueva.
  a.boton.emitir("click");
  a.audio.emitir("pause");
  assert.equal(a.sonando(), true);
  a.audio.paused = true;
  a.audio.emitir("pause");
  assert.equal(a.sonando(), false);

  // Archivo que no carga: el botón queda desactivado.
  const rota = opcion("voz Calidad, hombre", "NotSupportedError");
  rota.boton.emitir("click");
  await new Promise((r) => setImmediate(r));
  assert.equal(rota.boton.disabled, true);
  assert.equal(rota.sonando(), false);
  assert.equal(rota.etiqueta(), "Muestra no disponible: voz Calidad, hombre");

  // El «pause» que el navegador manda después del error no borra el aviso.
  const conError = opcion("voz Rápida, mujer");
  conError.boton.emitir("click");
  conError.audio.emitir("error");
  conError.audio.paused = true;
  conError.audio.emitir("pause");
  assert.equal(conError.boton.disabled, true);
  assert.equal(conError.etiqueta(), "Muestra no disponible: voz Rápida, mujer");

  // Detener antes de que alcance a sonar (AbortError) no la da por rota.
  const abortada = opcion("voz Rápida, mujer", "AbortError");
  abortada.boton.emitir("click");
  await new Promise((r) => setImmediate(r));
  assert.equal(abortada.boton.disabled, false);

  assert.deepEqual(peticiones, []);
  console.log("Muestras de voz: correcto (sin envíos, una a la vez, estados y fallos).");
})().catch((error) => { console.error(error); process.exit(1); });
