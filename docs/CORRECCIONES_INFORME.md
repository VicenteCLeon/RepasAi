# Correcciones al informe

> Qué había que corregir, actualizar o agregar en el informe final respecto del
> **informe de avance** (`seminario_titulo.md`, abril de 2026, y su versión LaTeX
> del 11-sep-2026), y dónde quedó aplicado.
>
> **El informe final se entregó el 20-nov-2026 con los resultados del A/B.** La
> versión final se compiló en Prism, fuera del repo.
>
> Cuando se aplica una corrección al informe, se tacha o se borra acá. El
> **15-nov-2026 se aplicaron** en el LaTeX del informe final (carpeta `Informe`,
> fuera del repo) las de la tabla de abajo; lo que quedaba se resolvió antes de la
> entrega. El registro detallado, con archivo, sección y motivo de cada cambio del
> 15-nov, está en `Informe/CAMBIOS_REALIZADOS.md`; las decisiones del equipo, en
> `AVANCE.md` §5.37. El texto completo de cada ítem queda en el historial de git
> de este archivo.
>
> Última revisión: 26-nov-2026.

## Lo que sigue pendiente

Nada.

## Resuelto antes de la entrega (20-nov-2026)

- ✅ ~~**Resultados del estudio A/B:**~~ completados los `\pendiente`: las 17
  celdas de la Tabla 5.6 (n, pre, post, diferencia, acierto en `quiz_mc`,
  cuestionarios, esfuerzo, usabilidad y satisfacción) y la conclusión del cap. 6
  sobre el efecto de la adaptación (`PENDIENTES.md` E1 y E5).
- ✅ ~~**Forma, menores:**~~ corregidos los 4 overfull del diccionario de datos y
  de la tabla del stack, y el aviso `page.i` de pdfTeX.

## Aplicado el 15-nov-2026

Los capítulos son los del LaTeX final.

| Ítem | Cómo quedó |
|---|---|
| ~~A1~~ Referencias cruzadas desfasadas | Resuelto con la reestructuración en 6 capítulos y `\ref`. |
| ~~A2~~ Resumen y Abstract | Reescritos con el mismo contenido y grado de certeza; el efecto pedagógico va en condicional. |
| ~~A3~~ Cita de Saha et al. | Verificada en el paper: «50 to 75 minutes». |
| ~~A4~~ Tabla 16.2 sin porcentaje | Figuras regeneradas con el mismo formato y tabla de promedios nueva (§3.2.2). |
| ~~A5~~ Redondeo | Nota al pie de redondeo (año de carrera y género). |
| ~~B1~~ Criterio de multimodalidad | Unificado: canales activos a ≤ 10 pp del máximo (tabla de reglas, §3.2). |
| ~~B2~~ Reglas no excluyentes | Declaradas «en capas»; la fila 7 quedó reemplazada, con nota al pie (cierra D4 y R14). |
| ~~B3~~ Componentes prácticos | La actividad completa el tercer componente; el cuerpo lleva dos. |
| ~~B4~~ Perfil persistido | Solo como vector; la jerarquía se deriva al leer. |
| ~~B5~~ `palabras_texto` | Declarado como decisión del equipo (interpolado sobre C_texto en [40, 75]). |
| ~~C1~~ Tablas 16.2/16.3 | Recalculadas desde el CSV con los módulos del repo, con nota metodológica (cierra D1). |
| ~~I1~~ El prompt no nombra el perfil | §3.2.1, con las 13 directivas reales. |
| ~~I2~~ Sin plantilla por estilo | Directivas por canal y de equilibrio. |
| ~~I3~~ El perfil reordena | §2.4.1 y §5.1.2: hasta 8 fragmentos, sin filtrar por perfil. |
| ~~I4~~ Validador | Seis reglas, dos reintentos, caché por huella y versionado (caps. 2 a 4). |
| ~~I5~~ Sin imágenes | Diccionario de `fragmento` corregido; sin generación de imágenes (§4.4.2). |
| ~~I6~~ Siete pasos | §3.3.1, con los nombres reales de los campos. |
| ~~I7~~ Cinco actividades | §3.3. |
| ~~I8~~ 3–7 minutos | Se refieren al cuerpo; la actividad se suma. |
| ~~I9~~ Perfil K→A | El informe describe lo implementado: sin diagnóstico no se genera. K→A queda como caracterización de la cohorte. |
| ~~I10~~ Diccionario de datos | 11 tablas transcritas de `db/models.py` y figura ER nueva. |
| ~~I11~~ Stack | `deepseek-flash`, Kokoro/Piper, SQLAlchemy/Alembic y Google OIDC; DeepSeek como único candidato medible. |
| ~~I12~~ y ~~I13~~ Diseño del A/B | Implementado: Control con cápsula básica y el mismo RAG; sorteo por el equipo y sesiones moderadas. |
| ~~I14~~ Validación docente | Descartada: salió del informe (AVANCE §5.37). |
| ~~I15~~ Métrica por instrumento | «Selección única» y «Cuestionario» por separado. |
| ~~I16~~ Tolerancia de 350 | 150–300 como rango pedido y 350 como tope aceptado, con su justificación. |
| ~~N1~~ Batería VARK | §5.1.6: 29/30 válidas tras reparar (96,7 %), 26/30 a la primera (86,7 %), 0 citas inventadas. |
| ~~N2~~ Narración | §4.4.3: Kokoro y Piper en CPU, preferencia de voz y caché. |
| ~~N3~~ Sin difusión | §4.4.2: el equipo descartó la generación de imágenes; apoyo visual con bloques estructurados. |
| ~~N4~~ Marco legal y ético | §4.7. |
| ~~N5~~ Licencia AGPL | §4.7 y §6.5. |
| ~~N6~~ Limitaciones | §5.3 y §6.3. |
