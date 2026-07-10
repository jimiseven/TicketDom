# TicketDom - Resumen Del Proyecto

Fecha del resumen: 2026-07-10

## Objetivo Del Sistema

TicketDom es una aplicacion de escritorio para Windows orientada a la gestion local de tickets de soporte. La aplicacion funciona sin servidor web, usa SQLite como base de datos local y esta preparada para empaquetarse como programa Windows con PyInstaller.

## Stack Tecnologico

- Lenguaje: Python 3.x
- Interfaz grafica: CustomTkinter
- Selector de fecha: tkcalendar
- Base de datos: SQLite
- Empaquetado: PyInstaller

## Archivos Principales

- `app.py`: interfaz grafica, ventanas modales, tabla de tickets, reportes y acciones de usuario.
- `services.py`: logica de negocio, CRUD de tickets, reportes, rollover, carga masiva y conteos.
- `database.py`: conexion SQLite, ubicacion de base de datos, creacion de tablas y migraciones.
- `seed_demo_data.py`: generacion de datos ficticios para pruebas.
- `requirements.txt`: dependencias del proyecto.
- `TicketDom.spec`: archivo generado por PyInstaller.

## Base De Datos

Archivo SQLite:

```text
tickets_data.db
```

Cuando se ejecuta desde codigo fuente, la base se crea en la carpeta del proyecto. Cuando se ejecuta desde el `.exe`, la base se crea junto a `TicketDom.exe`.

### Tablas

#### `tickets`

Guarda los tickets principales.

Campos relevantes:

- `id`
- `fecha_creacion`
- `pais`
- `numero_ticket`
- `mail`
- `phone`
- `estado`
- `problem_name`
- `description`
- `estado_actual`

Estados disponibles:

- `respondido`
- `pendiente`
- `cerrado`
- `no tomado`
- `critico`

#### `comentarios`

Guarda historial de progreso por ticket.

Campos:

- `id`
- `ticket_id`
- `fecha_hora`
- `comentario`

Los comentarios se eliminan en cascada cuando se elimina un ticket.

#### `opciones_dinamicas`

Guarda opciones dinamicas para:

- `pais`
- `estado_actual`

Valores iniciales:

- Pais: `United States`
- Estado actual:
  - `Awaiting hq team response`
  - `Awaiting customer response`

#### `daily_reports`

Guarda los contadores diarios para el reporte de Neil/Jimi.

Campos:

- `fecha`
- `inbound_calls`
- `outbound_calls`
- `calls_failed`
- `moor_chat`
- `first_call_resolved`
- `emails`
- `tickets_hq_help`
- `updated_at`

Cada fecha tiene un unico registro.

#### `ticket_daily_updates`

Guarda si un ticket fue actualizado/manipulado en una fecha especifica.

Campos:

- `ticket_id`
- `fecha`
- `updated_at`

Tiene restriccion unica por `ticket_id` y `fecha`.

## Funcionalidades Implementadas

### Gestion De Tickets

- Crear ticket desde ventana modal.
- Editar ticket desde la tabla.
- Eliminar ticket individual.
- Eliminar varios tickets marcados.
- Ver progreso/comentarios de cada ticket.
- Agregar comentario al historial.
- Marcar ticket como actualizado en el dia.

### Campos Del Ticket

- Fecha
- Pais
- Numero de ticket
- Mail
- Phone
- Estado
- Problema
- Descripcion
- Estado actual

### Creacion Flexible

Un ticket puede crearse incompleto. Los campos minimos son:

- Fecha
- Pais
- Estado
- Estado actual

Los demas datos pueden completarse luego desde `Editar`.

### Rollover Diario

La vista de la fecha actual muestra:

- Tickets creados hoy.
- Tickets antiguos cuyo estado sea:
  - `respondido`
  - `pendiente`
  - `critico`

Los estados `cerrado` y `no tomado` no pasan al dia siguiente.

Importante: `cerrado` y `no tomado` no se borran del dia original. Siguen apareciendo si se selecciona la fecha en que fueron creados.

### Actualizacion Diaria De Tickets

Se agrego control para saber si un ticket fue actualizado en la fecha seleccionada.

El boton del ticket cambia de color:

- Verde: ticket actualizado en la fecha seleccionada.
- Rojo: ticket abierto/arrastrado que requiere actualizacion y aun no fue actualizado.
- Color normal: tickets que no requieren seguimiento diario, como `cerrado` o `no tomado`.

Acciones que marcan un ticket como actualizado:

- Agregar comentario/progreso.
- Boton `Marcar Actualizado` en la ventana de progreso.
- Cambiar `Estado` desde la tabla.
- Cambiar `Estado Actual` desde la tabla.
- Guardar cambios desde `Editar`.

### Tabla Principal

La tabla muestra tickets visibles segun la fecha seleccionada.

Columnas actuales:

- Sel
- #
- Dias
- Fecha
- Pais
- Ticket
- Mail
- Phone
- Estado
- Problema
- Estado Actual
- Opciones

Funcionalidades de la tabla:

- Seleccion multiple con checkbox.
- Eliminacion masiva con `Eliminar Marcados`.
- Cambio directo de `Estado`.
- Cambio directo de `Estado Actual`.
- Boton de ticket abre progreso.
- Botones `Editar` y `Eliminar` por fila.
- Columnas redimensionables.
- Columnas reordenables arrastrando encabezados.
- Boton `Defecto` restaura orden y tamanos iniciales.
- Celdas largas se muestran truncadas y al hacer click muestran el texto completo.

### Navegacion Por Fechas

La barra superior incluye:

- Selector de fecha.
- Boton `<` para dia anterior.
- Boton `>` para dia siguiente.
- Boton `Cargar Fecha`.

### Carga Masiva Desde Excel Copiado

Boton:

```text
Lista
```

Abre una ventana para pegar columnas copiadas desde Excel, no para importar archivo Excel.

Columnas soportadas:

- Ticket
- Problema

Flujo:

- Copiar columna de tickets desde Excel.
- Presionar `Pegar Tickets`.
- Copiar columna de problemas desde Excel.
- Presionar `Pegar Problemas`.
- Revisar vista previa.
- Presionar `Guardar`.

Reglas:

- Si no hay ticket, la fila se ignora.
- Si hay ticket sin problema, se crea igual.
- Duplicados se detectan por `numero_ticket`.
- Tickets duplicados no se crean.
- Muestra resumen con creados, duplicados e ignorados.

### Reporte SMS

Boton:

```text
Generar Reporte SMS
```

Solo funciona para la fecha actual.

Incluye tickets visibles cuyo estado no sea:

- `cerrado`
- `no tomado`

Formato:

```text
Hi, daily open ticket report: 10 jul 2026

[numero_ticket] : [problem_name] : [estado_actual]
```

El texto se copia al portapapeles.

### Reporte Diario Neil/Jimi

Boton:

```text
Reporte Diario
```

Abre un modal con contadores diarios.

Campos:

- Inbound calls
- Outbound calls
- Calls Failed to connect
- 7 moor platform online chat
- Issues resolved over the first call
- Emails
- Tickets needing HQ help or attention

Cada campo tiene botones:

- `-`
- `+1`

Cada incremento/decremento se guarda automaticamente en la base de datos para la fecha seleccionada.

Botones finales:

- `Guardar`
- `Generar Mensaje y Copiar`

Al guardar o generar:

- Se guarda la informacion.
- Se cierra el modal.
- Aparece una notificacion pequena que desaparece sola.

Formato generado:

```text
Hi Neil, here is my report of today Report - 10 jul 2026

Tickets: 12

Jimi:
-Inbound calls: 0
-Outbound calls: 3
-calls Failed to connect: 0
-7 moor platform online chat: 0
-Issues resolved over the first call: 0
-Emails: 0
-Tickets needing HQ help or attention: 0
```

#### Conteo De `Tickets:` En Reporte Diario

El numero de tickets del reporte diario cuenta tickets manipulados en la fecha seleccionada.

Incluye:

- Tickets creados en esa fecha.
- Tickets de dias anteriores que fueron actualizados/marcados en esa fecha.
- Tickets cerrados en esa fecha aunque hayan sido creados antes.

Evita duplicados usando `COUNT(DISTINCT tickets.id)`.

## Exportacion E Importacion De Base De Datos

Botones:

- `Exportar DB`
- `Importar DB`

Exportar copia el archivo SQLite actual a una ruta elegida por el usuario.

Importar reemplaza la base actual con un archivo `.db` seleccionado y ejecuta inicializacion/migraciones.

## Datos Ficticios

Script:

```powershell
python seed_demo_data.py
```

Crea datos de prueba de una semana.

Incluye:

- Tickets abiertos por varios dias.
- Tickets cerrados.
- Tickets criticos.
- Tickets no tomados.
- Tickets incompletos para probar edicion.

El script solo reemplaza tickets con prefijo `DEMO-`.

## Empaquetado Como EXE

Comando usado:

```powershell
python -m PyInstaller --noconfirm --clean --windowed --name TicketDom --collect-all babel --collect-all tkcalendar app.py
```

Se agregaron `--collect-all babel` y `--collect-all tkcalendar` porque versiones anteriores del EXE fallaban con error de `babel/locale-data`.

Ruta final del EXE:

```text
dist/TicketDom/TicketDom.exe
```

Para mover a otra computadora, copiar la carpeta completa:

```text
dist/
  TicketDom/
    TicketDom.exe
    _internal/
```

No copiar solo `TicketDom.exe`.

## Estado Actual Del Proyecto

Ultimo cambio realizado:

- Se actualizo el conteo del `Reporte Diario` para contar tickets manipulados en el dia.
- Ahora cuenta tickets creados en la fecha seleccionada y tickets de dias anteriores actualizados o cerrados ese dia.
- Se valido que cerrar un ticket antiguo se contabilice en el reporte diario.
- Se genero un nuevo EXE actualizado en `dist/TicketDom/TicketDom.exe`.

## Como Ejecutar En Desarrollo

```powershell
python app.py
```

Si se usa entorno virtual:

```powershell
.\.venv\Scripts\activate
python app.py
```

## Como Instalar Dependencias

```powershell
pip install -r requirements.txt
```

Dependencias principales:

- `customtkinter`
- `tkcalendar`

Para empaquetar:

```powershell
pip install pyinstaller
```

## Consideraciones Para Retomar El Proyecto

- Antes de generar un EXE nuevo, cerrar cualquier instancia abierta de `TicketDom.exe` para evitar bloqueos de archivos.
- Si PyInstaller falla por carpeta bloqueada, eliminar o cerrar procesos `TicketDom.exe` desde el Administrador de tareas.
- La carpeta final usable siempre debe ser `dist/TicketDom`.
- Las migraciones de base se ejecutan en `initialize_database()`.
- No se debe borrar `tickets_data.db` salvo que se quiera resetear la informacion.
- Si se copia la app a otra computadora con datos existentes, copiar tambien `tickets_data.db` junto al `.exe`.

## Mejoras Futuras Sugeridas

- Persistir preferencias de columnas, orden y anchos.
- Agregar filtros por estado, pais o texto.
- Agregar busqueda rapida por numero de ticket.
- Agregar exportacion CSV/Excel de la tabla visible.
- Agregar backup automatico diario de `tickets_data.db`.
- Agregar confirmacion visual mas clara cuando un ticket se marca como actualizado.
- Agregar reporte de tickets actualizados/no actualizados del dia.
- Agregar auditoria de cambios de estado.
- Agregar instalador Windows en lugar de distribuir carpeta `dist/TicketDom`.
