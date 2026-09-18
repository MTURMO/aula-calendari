# Calendari AULA Handbol 26/27 – actualización automática

El calendario se regenera solo **miércoles y jueves** (08:00 y 18:00 UTC) leyendo la web de la
federación. Tú te suscribes una vez a una URL y tu móvil/Google Calendar lo mantiene al día.

Reglas: en casa → día de la web + 19:00 fijo · fuera → día y hora de la web ·
sin fecha publicada → evento provisional (fin de semana / fecha prevista).
Si la web falla o cambia de formato, el script **no toca** el calendario y GitHub te avisa por email.

## Puesta en marcha (una sola vez, ~10 minutos)

1. **Cuenta y repositorio.** En github.com crea una cuenta gratuita → *New repository* →
   nombre `aula-calendari` → **Public** → *Create repository*.
2. **Subir los ficheros.** En el repo: *Add file → Upload files* y arrastra `update_calendar.py`,
   `fixtures.json`, `requirements.txt` y la carpeta `docs` → *Commit changes*.
3. **Crear el workflow.** *Add file → Create new file*. En el nombre escribe exactamente
   `.github/workflows/update-calendar.yml` (al escribir las `/` se crean las carpetas),
   pega el contenido del fichero `update-calendar.yml` de este paquete → *Commit changes*.
4. **Activar la publicación.** *Settings → Pages* → *Source: Deploy from a branch* →
   Branch `main`, carpeta `/docs` → *Save*. La URL quedará como
   `https://TU_USUARIO.github.io/aula-calendari/aula.ics`
5. **Probarlo ya.** Pestaña *Actions* → *Actualitzar calendari AULA* → *Run workflow*.
   Debe salir en verde y en el log verás qué partidos ha cambiado (p. ej. la J1, que la web ya
   tiene a las 10:45). Abre la URL del paso 4 (puede tardar 1–2 min) y comprueba que refleja el cambio.
6. **Suscribirte.**
   - Google Calendar (web): *Otros calendarios (+) → Desde URL* → pega la URL.
   - iPhone: *Ajustes → Calendario → Cuentas → Añadir cuenta → Otra → Añadir calendario suscrito*.
   - Mac: *Archivo → Nueva suscripción de calendario*.
   Borra antes el `.ics` importado para no tener partidos duplicados.

## Notas
- Google Calendar refresca los calendarios suscritos cuando quiere (varias horas, a veces ~1 día).
- Cambiar días/horas de ejecución: línea `cron:` del workflow (la hora es UTC; `3,4` = miércoles y jueves).
- Cambiar la hora de casa: `HOME_TIME` al principio de `update_calendar.py`.
- Pabellones, rivales y fechas provisionales están en `fixtures.json`.
- GitHub pausa los workflows programados tras 60 días sin actividad en el repo; durante la
  temporada hay commits con cada cambio de horario, así que no debería pasar. Si llega ese aviso,
  basta con pulsar *Enable workflow* en la pestaña Actions.
