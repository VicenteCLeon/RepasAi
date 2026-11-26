# Checklist antes de una demostración por túnel

Para mostrar RepasAi desde el equipo de un autor, a alguien que entra desde su propio dispositivo y no instala
nada. Un túnel rápido de Cloudflare **cambia de dirección cada vez que se levanta**: los pasos 3 a 7 se
repiten cada vez.

Los comandos son de PowerShell y se corren desde la raíz del repositorio.

## 1. Preparar (puede hacerse el día anterior)

- [ ] Docker Desktop abierto y la base sana:

  ```powershell
  docker compose up -d
  docker ps --filter name=studify-db      # debe decir (healthy)
  .\.venv\Scripts\alembic upgrade head
  ```

- [ ] Respaldo de la base. Lo que se pruebe en la demostración **queda en la base real**, junto a los datos del
  piloto:

  ```powershell
  docker exec studify-db pg_dump -U studify -Fc -f /tmp/antes_demo.dump studify
  docker cp studify-db:/tmp/antes_demo.dump ..\antes_demo.dump
  ```

  El archivo tiene datos personales: guardarlo fuera del repositorio.

- [ ] Muestras de voz generadas (una vez): `.\.venv\Scripts\python scripts\generar_muestras_voz.py`.
- [ ] `LLM_API_KEY` con saldo. Conviene abrir antes los temas que se van a mostrar, para que sus cápsulas ya
  estén guardadas.
- [ ] Clave del panel (`TEACHER_PASSWORD`) que se pueda entregar a quien revisa.
- [ ] Opcional y recomendado al exponer la app: `APP_ENV=prod` en `.env`. Marca las cookies como seguras y deja
  de mostrar las consultas SQL en la consola. Exige `SESSION_SECRET` de 32 o más caracteres y una
  `TEACHER_PASSWORD` de 12 o más.

## 2. Levantar la app

- [ ] En una terminal, sin `--reload`:

  ```powershell
  .\.venv\Scripts\python -m uvicorn studify.main:app --app-dir src --host 127.0.0.1 --port 8000
  ```

## 3. Levantar el túnel

- [ ] En **otra** terminal, y dejarla abierta:

  ```powershell
  cloudflared tunnel --url http://127.0.0.1:8000
  ```

- [ ] Copiar la dirección `https://….trycloudflare.com` que muestra.

## 4. Actualizar el `.env`

- [ ] `GOOGLE_REDIRECT_URI=https://<dirección-del-túnel>/student/google/callback`

## 5. Actualizar Google Cloud Console

- [ ] **APIs y servicios → Credenciales →** el cliente OAuth de la app **→ URI de redirección autorizados:**
  agregar exactamente la misma dirección del paso 4 y guardar. Puede tardar unos minutos en aplicarse.

## 6. Usuarios de prueba

- [ ] **Pantalla de consentimiento (Público).** Si el estado es «Prueba» (*Testing*), agregar el correo de la
  profesora en **Usuarios de prueba**. Sin eso, Google le niega el acceso.

## 7. Reiniciar y verificar

- [ ] Detener el servidor (`Ctrl+C`) y volver a levantarlo: el `.env` se lee solo al arrancar.
- [ ] Comprobar que el túnel y el `.env` coinciden:

  ```powershell
  .\.venv\Scripts\python scripts\verificar_tunel.py
  ```

## 8. Comprobación rápida

En una ventana privada, entrando por la **dirección del túnel** (no por `127.0.0.1`):

- [ ] La portada carga.
- [ ] **Grupo Experimental:** entrar con Google, responder el cuestionario, ver el perfil, abrir un tema y
  responder la actividad.
- [ ] **Muestra de voz:** en el perfil (aparece con 25 % o más en Auditivo), pulsar el botón de una voz y
  escucharla.
- [ ] «Salir».
- [ ] **Grupo Control:** entrar con **otra** cuenta de Google (cada cuenta conserva su grupo), abrir un tema y
  comprobar que no hay audio.
- [ ] **Docente:** `<dirección-del-túnel>/teacher`, entrar con la clave y abrir Curación, Analíticas y
  Simulador.

Las cuentas usadas en esta comprobación suman datos a las analíticas y al CSV. Se pueden borrar desde «Mis
datos». Para exportar solo el piloto: `/teacher/exportar/intentos.csv?hasta=2026-11-19`.

## 9. Al terminar

- [ ] Cerrar el túnel y el servidor.
- [ ] Cambiar `TEACHER_PASSWORD` si se compartió.
- [ ] Quitar de Google Cloud las direcciones de túneles que ya no existen.
