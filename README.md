# campus-unr-mcp

Servidor MCP + CLI para el Campus Virtual FCEIA UNR (Moodle).

Confirmado: el campus virtual https://campusv.fceia.unr.edu.ar/ está basado en **Moodle** (cookie `MoodleSession`, login via `login/token.php`, Web Services REST con 435 funciones disponibles).

Agente Plugins spec 1.0.0 compliant (`plugin.json` + `mcp.json` en la raíz).

## Estructura

```
src/campus_unr_mcp/
├── __init__.py
├── client.py      # CampusClient: login token + Moodle Web Services (read + write)
├── cli.py         # CLI con click + rich (21 subcomandos)
└── mcp_server.py  # Servidor MCP stdio (21 tools)
bin/campus-server  # Launcher portable para Agent Plugins
plugin.json        # Manifest Agent Plugins 1.0.0
mcp.json           # Config MCP stdio
```

## Instalación

```bash
cd campus-unr-mcp
uv sync
```

## Configuración

Crear `.env` (ya existe):

```env
CAMPUS_USER=tu_usuario
CAMPUS_PASS=tu_password
CAMPUS_BASE_URL=https://campusv.fceia.unr.edu.ar/
```

## Uso CLI — Lectura

```bash
# Info del sitio y usuario
uv run campus site-info

# Listar cursadas
uv run campus courses
uv run campus courses --json

# Categorías (períodos lectivos / carreras / áreas)
uv run campus categories

# Contenido de un curso (secciones y actividades)
uv run campus contents 442

# Usuarios enrolados (estudiantes)
uv run campus users 442 --role student

# Grupos (comisiones)
uv run campus groups 442

# Miembros de grupos con lista de estudiantes
uv run campus group-members 442

# Actividades agrupadas por tipo
uv run campus activities 442

# Entregas (assignments) con conteo de envíos y calificaciones
uv run campus assignments 442

# Foros de un curso
uv run campus forums 503

# Discusiones (temas) de un foro
uv run campus discussions 7119

# Calificaciones del curso (quizzes + assignments)
uv run campus course-grades 442

# Intentos de quiz (parcial/examen)
uv run campus quiz-attempts 9417

# Iniciar servidor MCP
uv run campus serve
```

## Uso CLI — Escritura

Todas las operaciones de escritura tienen `--dry-run` por defecto. Pasar `--no-dry-run` para ejecutar.

```bash
# Renombrar un foro y definir su visibilidad (dry-run por defecto)
uv run campus update-forum 121831 "Avisos 2026 C1" --hidden
uv run campus update-forum 121831 "Avisos 2026 C1" --hidden --no-dry-run

# Crear tema en foro (dry-run por defecto, valida permisos)
uv run campus post-discussion 7119 "Aviso importante" "<p>Mensaje HTML</p>"
uv run campus post-discussion 7119 "Aviso" "Mensaje" --no-dry-run   # ejecutar

# Responder a un post
uv run campus reply-post 113371 "Re: Aviso" "Respuesta" --no-dry-run

# Cargar nota de TP (0-10, con feedback opcional)
uv run campus save-grade 16255 13341 8.5 --feedback "Buen trabajo"
uv run campus save-grade 16255 13341 8.5 --feedback "Buen trabajo" --no-dry-run

# Enviar mensaje a un usuario
uv run campus send-message 13341 "Recordatorio entrega TP"

# Crear evento de calendario (fecha de examen, entrega, etc.)
uv run campus create-event "Parcial" 503 "2026-12-15T10:00:00" --description "Aula 3"
```

## Uso como servidor MCP en Hermes

Las credenciales viven en el `.env` del repo (no en `config.yaml`). Con
`uv --directory <ruta-del-repo>`, el cwd del proceso es el repo y se lee ese `.env`.

En `~/.hermes/config.yaml` (ajustá la ruta al clone local):

```yaml
mcp_servers:
  campus_unr:
    command: uv
    args:
      - --directory
      - /path/to/campus-unr-mcp
      - run
      - campus
      - serve
    connect_timeout: 90.0
    enabled: true
    timeout: 120
```

O por CLI (sin pasar flags de Hermes como `--connect-timeout` en `--args`;
si no, caen como argumentos de `campus serve` y el server falla):

```bash
uv sync
printf 'Y\n' | hermes mcp add campus_unr --command uv \
  --args --directory /path/to/campus-unr-mcp run campus serve
hermes config set mcp_servers.campus_unr.timeout 120
hermes config set mcp_servers.campus_unr.connect_timeout 90
hermes config set mcp_servers.campus_unr.enabled true
# Si args quedó como string JSON, dejalo como lista YAML real (como arriba).
hermes mcp test campus_unr
```

Reiniciá la sesión CLI / el gateway de Hermes para descubrir las tools
(en Telegram hace falta reiniciar el gateway).

## Tools MCP disponibles (21 total)

### Lectura (15)

| Tool | Descripción |
|------|-------------|
| `get_site_info` | Info del sitio y usuario actual |
| `list_courses` | Cursos donde el usuario está enrolado |
| `list_categories` | Categorías (jerarquía académica) |
| `get_course_contents` | Secciones y actividades de un curso |
| `list_enrolled_users` | Usuarios enrolados con filtro por rol |
| `list_groups` | Grupos (comisiones) de un curso |
| `list_group_members` | Grupos con lista de miembros y roles |
| `list_activities` | Actividades agrupadas por tipo |
| `list_assignments` | Entregas con stats de envíos/calificaciones |
| `get_grades_report` | Reporte de calificaciones |
| `get_assignment_submissions` | Detalle de entregas de un TP |
| `list_forums` | Foros de un curso con conteo de discusiones |
| `list_forum_discussions` | Temas de un foro con contenido |
| `get_course_grades` | Todos los items de calificación del curso |
| `list_quiz_attempts` | Intentos de un quiz (parcial/examen) |

### Escritura (6) — dry_run=True por defecto

| Tool | Descripción |
|------|-------------|
| `update_forum` | Renombrar un foro y mostrarlo/ocultarlo |
| `create_forum_discussion` | Crear tema en foro (valida permisos en dry-run) |
| `reply_forum_post` | Responder a un post existente |
| `save_assignment_grade` | Cargar nota de TP (0-10) con feedback opcional |
| `send_message_to_user` | Enviar mensaje instantáneo a un usuario |
| `create_calendar_event` | Crear evento (examen, entrega, etc.) |

Cada tool de escritura acepta `dry_run: bool = True`. En modo dry-run
valida permisos y parámetros sin ejecutar la operación. Pasar
`dry_run=False` para ejecutar realmente.

## Notas

- El cliente usa Web Services de Moodle (REST + token), no scraping HTML. Es más rápido y estable.
- Autenticación: `login/token.php` con servicio `moodle_mobile_app` obtiene un token de WS automáticamente.
- SSL auto-firmado: `verify_ssl=False` por defecto (común en deployments universitarios).
- El cliente httpx se cachea y persiste toda la sesión MCP, reutilizando conexiones.
- Todos los datos de estudiantes son PII: no commitear exports ni dumps.
