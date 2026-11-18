# Lavadero App

App móvil **privada** (Flutter + Supabase) para administrar un lavadero de vehículos en Colombia.
La usan **solo sus dos propietarios**, en dos celulares distintos, con los mismos datos sincronizados.
Sirve para registrar los carros que entran, controlar el estado del trabajo, los pagos y el historial,
y ver cuántos servicios se hicieron por día, semana, mes y año.

> **Para el agente/desarrollador que continúa este proyecto:** lea este archivo completo antes de
> escribir código. Contiene las decisiones ya tomadas, el modelo de datos real, las reglas de negocio,
> el estado actual y lo que falta. La sección 12 explica cómo debe trabajar.

---

## 1. Estado actual

| Etapa | Contenido | Estado |
|---|---|---|
| 1 | Estructura, `pubspec.yaml`, configuración, utilidades de placa, formatos, tema | Escrita (sin compilar por quien la escribió) |
| 2 | Base de datos Supabase: esquema, seguridad (RLS), catálogo, funciones admin, pruebas SQL | Escrita (sin ejecutar por quien la escribió) |
| 3 | Base local (Drift/SQLite), repositorios y sincronización | **Pendiente** |
| 4 | Autenticación de los dos propietarios y sesión segura | Pendiente |
| 5 | Pantalla principal y barra de 5 botones | Pendiente |
| 6 | Módulo Registrar | Pendiente |
| 7 | Módulos Jornada e Historial | Pendiente |
| 8 | Módulo Pagos | Pendiente |
| 9 | Módulo Estadísticas y exportación CSV | Pendiente |
| 10 | Pruebas finales, APK firmado, guía de instalación | Pendiente |

**Importante:** el código y el SQL de las etapas 1 y 2 se escribieron sin poder ejecutarlos.
Lo primero que debe hacerse es **verificarlos** (sección 3). No dé nada por funcionando hasta verlo correr.

El proyecto se desarrolla en **Windows 11** con VS Code, Flutter, Dart y Git. Se prioriza **Android**
(APK firmado). iOS requiere un Mac y una cuenta Apple Developer (≈ USD 99/año); queda para después.

---

## 2. Tecnologías

| Necesidad | Elección |
|---|---|
| Framework | Flutter 3.x / Dart (Android primero, iOS después) |
| Nube | Supabase, **plan gratuito** (PostgreSQL + Auth + RLS) |
| Base local | Drift sobre SQLite (offline-first) |
| Estado | Riverpod (`flutter_riverpod`) |
| Navegación | `go_router` |
| Gráficos | `fl_chart` |
| Fechas/moneda | `intl` — fecha `DD/MM/AAAA`, moneda COP (`$`), locale `es_CO` |
| Sesión segura | `flutter_secure_storage` |
| Exportación | `csv` + `share_plus` |
| Identificadores | `uuid` (UUID v4 generados **en el celular**) |
| Conectividad | `connectivity_plus` |

Las versiones de `pubspec.yaml` son un punto de partida **no verificado**. Si `flutter pub get` da
conflictos: `flutter pub upgrade --major-versions` o `flutter pub outdated`, y ajustar.

**Zona horaria:** Colombia es UTC-5 todo el año (sin horario de verano). En la base de datos todo se
guarda en **UTC** (`timestamptz`); `lib/core/config/zona_horaria.dart` convierte a hora de Bogotá
solo para mostrar o para calcular "el día". `fecha_ingreso` es la **fecha de Bogotá**.

---

## 3. Puesta en marcha

### 3.1 Base de datos (Supabase)
1. Proyecto Supabase **nuevo y vacío**.
2. SQL Editor → pegar **todo** `supabase/setup_completo.sql` → Run (una sola vez). Es atómico: si algo
   falla se revierte todo. Si el proyecto ya fue instalado, el script se detiene con un aviso.
3. Ejecutar `supabase/tests/verificacion.sql`. Debe terminar con el mensaje de error controlado
   `TODAS LAS PRUEBAS PASARON (los datos de prueba se revirtieron)`. Cualquier otro mensaje = falló
   una comprobación; **no continuar** hasta resolverlo.
4. Crear a los dos propietarios (instrucciones al final de `setup_completo.sql` y en
   `supabase/admin/registrar_propietarios.sql`): crear 2 usuarios en *Authentication → Users*
   (correo + contraseña propia, *Auto Confirm User*), y luego
   `select public.admin_registrar_propietario('UUID', 'Nombre Completo', 'cédula');` para cada uno.
5. En Authentication, **desactivar el registro público** ("Allow new users to sign up").
6. Copiar de *Project Settings → API* la **URL** y la clave **anon**. **Nunca** la `service_role`.

### 3.2 Flutter
```powershell
flutter doctor                 # sin errores de Flutter ni Android toolchain
flutter pub get
flutter analyze                # debe quedar sin errores
flutter test                   # pruebas de placas
flutter run --dart-define=SUPABASE_URL=https://TU-PROYECTO.supabase.co --dart-define=SUPABASE_ANON_KEY=TU-CLAVE-ANON
```
Si el proyecto no tiene `android/` ni `ios/`:
`flutter create --platforms=android,ios --org com.lavadero --project-name lavadero_app .`
y luego borrar `test/widget_test.dart` (apunta a la app de ejemplo). Resultado esperado de la etapa 1:
la app abre y muestra "Lavadero · ETAPA 1 lista"; sin configuración de Supabase muestra un aviso.

Las claves se pasan con `--dart-define` (no se leen de un archivo empaquetado). `.env.example` solo
documenta qué valores hacen falta; `.env` está en `.gitignore`.

---

## 4. Reglas de negocio (obligatorias)

1. Cada vehículo se identifica por su **placa**, normalizada (`ABC123`: mayúsculas, sin espacios ni
   guiones) y validada con formato colombiano (`ABC123` carro, `ABC12D` moto). **No se crea un vehículo
   nuevo cuando regresa:** se agrega una visita al vehículo existente.
2. **Un vehículo solo puede tener UNA visita activa por día** (las canceladas no cuentan; se puede
   volver a registrar tras cancelar). Lo exige un índice único parcial en la base.
3. Avisar cuando una placa nueva sea casi igual a una existente (una letra de diferencia o confusiones
   O/0, I/1, B/8, S/5, Z/2): `Placa.parecidas(...)`. Es un aviso, no un bloqueo.
4. No se aceptan placas vacías ni campos obligatorios vacíos.
5. Cada visita es un registro independiente con uno o varios servicios y uno o varios pagos.
6. Los registros históricos **no se borran** (solo `eliminado_en`). Cancelados se conservan.
7. **Estado del servicio y estado del pago son independientes:** una visita puede estar *terminada*
   con pago *pendiente*.
8. El estado de pago se **calcula** (suma de pagos vs total); nunca se guarda.
9. Los **ingresos** de las estadísticas salen de los pagos realmente registrados **menos las
   devoluciones**, no de los servicios programados.
10. Los servicios cancelados **no** cuentan como terminados.
11. **Cancelar con abono → devolución:** la app inserta un pago de tipo `devolucion` (valor negativo).
    El pago original no se borra. La vista `v_cancelados_sin_devolucion` alerta si falta devolver.
12. Los **precios** son configurables desde la app. La base **no trae precios**: la app debe obligar a
    configurarlos antes de poder registrar. Cada visita **congela** el precio aplicado
    (`servicios_visita.precio_aplicado`), así cambiar tarifas no altera el historial.
13. Cambios importantes (precios, cancelaciones, ediciones, devoluciones) quedan en `auditoria`.
14. Exportación de todo a **CSV** (compatible con Excel). Es el respaldo: Supabase gratuito **no hace
    copias de seguridad automáticas**.
15. Acciones importantes (cancelar, devolver dinero, cambiar precios) piden confirmación.
16. Los dos propietarios ven siempre la misma información actualizada.

---

## 5. Modelo de datos (nombres reales, en español)

Fuente de verdad: `supabase/setup_completo.sql`. **No renombrar tablas ni columnas** sin actualizar
SQL, base local, repositorios y esta sección.

| Tabla | Columnas principales |
|---|---|
| `perfiles` | `id` (= `auth.users.id`), `nombre`, `cedula_hash` (bcrypt), `activo`, `creado_en`. Máximo 2 filas. |
| `propietarios` | `id`, `nombre`, `celular` (10 dígitos, empieza por 3), `creado_en`, `actualizado_en`, `eliminado_en` |
| `vehiculos` | `id`, `placa` (única, normalizada), `tipo` (`automovil`\|`camioneta`), `marca`, `modelo`, `color`, `propietario_id`, `creado_en`, `actualizado_en`, `eliminado_en` |
| `servicios` | `id`, `codigo` (único), `tipo_vehiculo`, `nombre`, `orden`, `activo`, `actualizado_en`. **12 filas fijas.** |
| `tarifas` | `id`, `servicio_id`, `precio`, `vigente_desde`, `creado_por`, `creado_en`. **Solo inserción**; el precio vigente es el último. |
| `visitas` | `id`, `vehiculo_id`, `propietario_id` (dueño al momento de la visita), `fecha_ingreso`, `hora_ingreso`, `hora_entrega`, `estado` (`pendiente`\|`en_proceso`\|`terminado`\|`cancelado`), `observaciones`, `total`, `creado_por`, `creado_en`, `actualizado_en`, `eliminado_en` |
| `servicios_visita` | `id`, `visita_id`, `servicio_id`, `precio_aplicado`, `creado_en`, `actualizado_en`, `eliminado_en`. Único por (`visita_id`,`servicio_id`) activo. |
| `pagos` | `id`, `visita_id`, `tipo` (`pago`\|`devolucion`), `valor` (`pago` > 0, `devolucion` < 0), `metodo` (`efectivo`\|`transferencia`), `pagado_en`, `registrado_por`, `nota`, `creado_en`. **Solo inserción.** |
| `auditoria` | `id`, `tabla`, `registro_id`, `accion`, `datos_antes`, `datos_despues`, `usuario`, `fecha`. Solo lectura desde la app. |

**Catálogo (`servicios.codigo`):** `auto_basico`, `auto_super`, `auto_motor`, `auto_polichado`,
`auto_cojin_tela`, `auto_cojin_cuero`, `cam_basico`, `cam_super`, `cam_motor`, `cam_polichado`,
`cam_cojin_tela`, `cam_cojin_cuero`. Nombres: Básico, Súper, Lavado de motor, Polichado,
Cojinería en tela, Cojinería en cuero (los mismos 6 para cada tipo de vehículo; se cuentan por separado).

**Vistas:** `v_tarifa_vigente` (precio actual por servicio) · `v_pago_visita` (`visita_id`,
`estado_servicio`, `total`, `pagado_neto`, `saldo`, `estado_pago` ∈ `pendiente_pago`|`abono_parcial`|
`pagado`|`anulado`) · `v_ingresos_dia` (ingresos netos por fecha de Bogotá) ·
`v_cancelados_sin_devolucion`.

### Lo que la base de datos ya hace sola (no duplicar en la app sin motivo)
- Normaliza la placa y valida el formato.
- Mantiene `visitas.total` = suma de `servicios_visita.precio_aplicado` activos (trigger). El `total`
  que envíe el cliente se **sobrescribe** al cambiar los servicios.
- Valida que cada servicio corresponda al tipo del vehículo.
- Rechaza (excepción) un pago mayor al saldo, una devolución mayor a lo pagado, un pago en una visita
  cancelada, y cualquier UPDATE/DELETE de pagos.
- Actualiza `actualizado_en` en cada UPDATE y escribe en `auditoria`.
- RLS: solo los propietarios **activos** de `perfiles` leen/escriben (`public.es_propietario()`).
  Sin borrado físico para nadie; `anon` no tiene acceso a nada.

---

## 6. Arquitectura

**Offline-first en tres capas:**
- **Presentación** (`features/`): pantallas y widgets, **sin lógica de negocio**.
- **Dominio** (`domain/`): modelos y reglas (totales, estado de pago, validaciones, duplicados).
- **Datos** (`data/`): repositorios que **siempre leen y escriben en SQLite local**; un servicio de
  sincronización envía y recibe cambios con Supabase.

La app nunca depende de internet para trabajar. Cada cambio se guarda primero en el celular y entra
en una **cola de salida**; se sube cuando hay conexión.

### Sincronización (diseño para la ETAPA 3)
- Los IDs son **UUID generados en el celular** para que dos teléfonos no choquen offline.
- La base local replica las tablas de la nube con los **mismos nombres** de tablas y columnas.
- **Bajada:** pedir filas con `actualizado_en` > última marca (tablas editables) o `creado_en` >
  última marca (`tarifas`, `pagos`, `auditoria`, solo-inserción). Guardar la marca por tabla.
- **Subida, en este orden** (por las llaves foráneas): `propietarios` → `vehiculos` → `visitas` →
  `servicios_visita` → `pagos` (y `tarifas`).
- **Conflictos en ediciones simultáneas:** gana el cambio más reciente (`actualizado_en` del servidor).
- **Rechazos del servidor:** la base puede rechazar con excepción (pago > saldo, pago en visita
  cancelada, visita duplicada del día, placa duplicada). La sincronización **no debe ignorarlos ni
  reintentar para siempre**: debe dejar el cambio marcado con error y **mostrarlo al usuario** para
  que lo resuelva.
- Borrados: solo lógicos (`eliminado_en`), y se sincronizan como cualquier otra edición.
- Los pagos y tarifas **nunca se editan**; una corrección es un movimiento nuevo.

---

## 7. Navegación y pantallas

Barra inferior fija con 5 botones, de izquierda a derecha:
**Jornada · Historial · Registrar (central, destacado) · Pagos · Estadísticas.**
Cada uno con icono, nombre y pantalla propia. (Si los dueños prefieren otro orden, es un cambio menor.)

### Registrar (el más importante)
1. Dos botones grandes: **AUTOMÓVIL** y **CAMIONETA**.
2. Formulario: *Vehículo* (placa, nombre/marca-modelo, color opcional) · *Dueño* (nombre, celular) ·
   *Servicio* (fecha, hora de ingreso automática, hora a la que el cliente quiere el vehículo,
   observaciones opcionales) · *Servicios* (uno o varios del tipo elegido; total automático).
3. Botón grande **GUARDAR**; confirmación; la visita aparece sola en Jornada, Pagos e Historial.
4. **Vehículo recurrente:** al escribir la placa se consulta la base local; si existe, sugerir con
   placa, marca/modelo, dueño, celular y nº de visitas; al elegirlo se autocompleta y solo hay que
   marcar servicios nuevos y hora de entrega. Permitir actualizar el dueño/celular si cambió.
5. Bloquear si ya hay visita activa de esa placa hoy; avisar placas parecidas.
6. No permitir registrar mientras no estén configurados los precios.

### Jornada
Vehículos del día elegido en tarjetas (placa, nombre del vehículo, dueño, servicio, hora de ingreso,
hora de entrega, estado). Estados: Pendiente, En proceso, Terminado, Cancelado; tocar la tarjeta
permite cambiarlo. Cancelar pide confirmación (y gestiona la devolución si hubo abonos). Ordenar por
hora de entrega y marcar en rojo los retrasados. Terminados y cancelados no desaparecen de la jornada.

### Historial
Calendario del año completo; tocar un día lista sus vehículos (placa, servicios, dueño, celular,
horas, valor, si se pagó). Lupa arriba a la derecha: buscar por placa, nombre del vehículo o nombre del
dueño, con sugerencias mientras se escribe. Al elegir un vehículo: historial completo de visitas,
servicios, fechas, pagos y teléfono. Se guardan **todos** los servicios, incluidos los cancelados.

### Pagos
Pestañas **Pagados** y **Pendientes por cobrar**. Al tocar un vehículo: datos, servicio, total,
abonado y saldo. Registrar pago en **Efectivo** o **Transferencia**, completo o parcial, y completar
el saldo después. Cada pago guarda fecha, hora, valor, método y quién lo registró.

### Estadísticas
Calendario por días y meses; elegir día, semana, mes o año. Para el periodo: vehículos registrados,
servicios terminados / pendientes / cancelados, vehículos atendidos, ingresos reales (pagos −
devoluciones) y dinero pendiente por cobrar. Conteo de cada uno de los **12 servicios** con ranking de
más y menos solicitados, tablas y gráficos sencillos. Calculado en el celular desde SQLite.

### Administración
Pantalla para configurar los precios de los 12 servicios (inserta en `tarifas`) y exportar todo a CSV.

---

## 8. Seguridad

- **Solo 2 usuarios**, creados por un administrador. No hay registro público.
- Cada dueño entra con **su propia contraseña**. La **cédula identifica pero nunca es contraseña** y se
  guarda solo como hash bcrypt en `perfiles.cedula_hash`. (Una cédula tiene pocos dígitos: un hash
  filtrado podría adivinarse por fuerza bruta; por eso no sirve para autenticar.)
- **Decisión pendiente (ETAPA 4):** Supabase Auth usa correo + contraseña. Si los dueños quieren
  escribir un "nombre de usuario", mapearlo a un correo (por ejemplo `usuario@dominio`) o usar sus
  correos reales (esto último permite recuperación de contraseña).
- La clave `service_role` **nunca** va en la app ni en el repositorio. Solo la `anon`, por
  `--dart-define`. La seguridad real son las políticas RLS.
- Sesión guardada de forma **cifrada** (`flutter_secure_storage`) para abrir la app sin internet.
  En `main.dart` hay un comentario donde se cambia el almacenamiento (ETAPA 4).
- Recuperación de acceso: procedimiento administrativo (restablecer contraseña en el panel de
  Supabase; validar identidad con `admin_verificar_cedula`; bloquear con `admin_desactivar_propietario`).
- La app no pide permisos innecesarios, no tiene publicidad y no recopila datos que no necesite.
- Sin librerías desconocidas o sin mantenimiento.

### Limitaciones de Supabase gratuito
- El proyecto **se pausa tras 7 días sin actividad**; hay que reactivarlo desde el panel.
- **No hay copias de seguridad automáticas:** la exportación CSV (semanal) es el respaldo.

---

## 9. Estructura del proyecto

```
mi app lavadero/
├── pubspec.yaml · analysis_options.yaml · .gitignore · .env.example · README.md
├── supabase/
│   ├── setup_completo.sql              ← instalación completa (esquema + RLS + catálogo + admin)
│   ├── migrations/001_schema.sql · 002_rls.sql · 003_seed_servicios.sql   (mismas piezas por separado)
│   ├── admin/registrar_propietarios.sql
│   └── tests/verificacion.sql
├── lib/
│   ├── main.dart                       # arranque; valida configuración de Supabase
│   ├── app.dart                        # MaterialApp, tema, locale es_CO (home provisional)
│   ├── core/
│   │   ├── config/  env.dart · zona_horaria.dart · formatos.dart
│   │   ├── theme/   app_theme.dart
│   │   ├── utils/   placa.dart         # normalizar, validar, distancia, parecidas
│   │   └── widgets/                    # (vacío) tarjeta de vehículo, botón grande, chip de estado
│   ├── data/   local/ · remote/ · sync/ · repositories/     # (vacío) ETAPA 3
│   ├── domain/                                              # (vacío)
│   └── features/ auth · jornada · historial · registrar · pagos · estadisticas · admin   # (vacío)
└── test/  placa_test.dart
```
`supabase/setup_completo.sql` es la versión consolidada; si se cambia el esquema, actualizar **ambos**
(consolidado y migraciones) o dejar solo el consolidado y borrar las migraciones separadas.

---

## 10. Convenciones de código

- Los nombres del **dominio** van en español, igual que la base: clases `Visita`, `Vehiculo`,
  `Propietario`, `Pago`, `Servicio`, `Tarifa`; campos como en la base pero en `camelCase`
  (`vehiculoId`, `fechaIngreso`, `precioAplicado`). Comentarios y textos de la interfaz en español.
- Archivos en `snake_case`. Un archivo por clase/widget importante; nada de archivos gigantes.
- Sin lógica de negocio en los widgets: va en `domain/` y se prueba con tests unitarios.
- Dinero como **enteros en pesos** (la base usa `numeric(12,0)`), nunca `double`.
- Fechas y horas: guardar en UTC; mostrar con `ZonaBogota` y `Formatos`.
- Cumplir `flutter analyze` sin errores ni advertencias nuevas.
- Textos de error comprensibles para alguien sin conocimientos técnicos.

---

## 11. Hoja de ruta (lo que falta)

Cada etapa se entrega **completa** (código de todos los archivos tocados), se verifica con
`flutter analyze` y `flutter test`, y **no rompe las etapas anteriores**.

**ETAPA 3 — Base local, repositorios y sincronización.**
Tablas Drift espejo de la nube (mismos nombres), DAOs, cola de salida, sincronizador
(bajada/subida en orden, ver sección 6), detección de conectividad, repositorios que exponen
`Stream`s. *Aceptación:* crear datos sin internet, reabrir la app y verlos; con internet suben sin
duplicarse; dos dispositivos convergen; un rechazo del servidor queda visible. Pruebas con base en
memoria. Los archivos generados por `build_runner` (`dart run build_runner build`) no se suben.

**ETAPA 4 — Autenticación y seguridad.** Pantalla de inicio de sesión, cierre de sesión, sesión
cifrada, apertura sin internet con sesión existente, ruteo protegido, manejo de usuario desactivado.

**ETAPA 5 — Pantalla principal.** `go_router` con la barra de 5 botones y pantallas vacías pero
navegables.

**ETAPA 6 — Registrar.** Todo lo de la sección 7 (incluida configuración de precios obligatoria,
vehículo recurrente, placas parecidas y bloqueo de visita duplicada del día).

**ETAPA 7 — Jornada e Historial.** Tarjetas, cambio de estado con confirmación, atrasados, calendario
anual, búsqueda con sugerencias, ficha del vehículo, cancelación con devolución.

**ETAPA 8 — Pagos.** Pestañas, ventana de cobro, pagos parciales, estado calculado, devoluciones.

**ETAPA 9 — Estadísticas y CSV.** Selector día/semana/mes/año, totales, conteo de los 12 servicios,
gráficos, exportación CSV completa.

**ETAPA 10 — Cierre.** Pruebas de punta a punta con dos dispositivos, APK **firmado** con keystore
propia (nunca en el repositorio), guía de instalación/actualización sin perder datos, y qué avisos de
Android verá el usuario ("origen desconocido"). iOS solo si hay Mac y cuenta Apple Developer.

---

## 12. Cómo debe trabajar el agente

1. **Lea este README y el SQL antes de escribir código.** Si algo contradice lo que ve en el repo,
   avise en vez de adivinar.
2. **Trabaje por etapas** (sección 11), una a la vez. No adelante etapas.
3. Entregue **archivos completos**, con la ruta exacta. No reemplace funciones existentes por
   versiones incompletas. Nada de datos de ejemplo para aparentar que algo está terminado.
4. **No afirme que algo funciona si no lo ha probado.** Diga qué corrió (`flutter analyze`,
   `flutter test`, ejecución en emulador/celular) y qué no pudo probar.
5. **Si falta información, pregunte antes de inventar** (precios, nombres, decisiones pendientes).
6. No cambie el esquema de la base sin avisar y sin actualizar SQL, base local y este README.
7. **Seguridad:** jamás ponga `service_role`, contraseñas, keystores ni cédulas en el código o en el
   repositorio. No use la cédula como contraseña. No agregue permisos de celular innecesarios.
8. Mantenga el código ordenado, comentado y escalable; diseño sobrio y botones grandes (se usa
   rápido mientras se atiende a un cliente).

### Decisiones ya tomadas por el dueño del proyecto
- Una visita por placa por día (el servicio ya se hizo).
- Cancelación con abono → **se devuelve el dinero** (registro de devolución).
- Supabase **plan gratuito** (respaldo manual con CSV).
- Entrega primero en **Android** (APK instalable desde una carpeta); iOS más adelante.
- Interfaz y datos en español, Colombia (`America/Bogota`, `DD/MM/AAAA`, COP).

### Pendientes por decidir
- Cómo escriben su usuario los dueños en el inicio de sesión (sección 8).
- Precios de los 12 servicios (se cargan desde la app).
- Nombre definitivo de la app, colores/logo.
- Si habrá Mac y cuenta Apple Developer para iOS.
