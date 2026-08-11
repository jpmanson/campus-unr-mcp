# campus-unr-mcp

Servidor MCP + CLI para el Campus Virtual FCEIA UNR (Moodle).

Confirmado: el campus virtual https://campusv.fceia.unr.edu.ar/ está basado en **Moodle** (cookie `MoodleSession`, login via `login/token.php`, Web Services REST con 435 funciones disponibles).

## Estructura

```
src/campus_unr_mcp/
├── __init__.py
├── client.py      # CampusClient: login token + Moodle Web Services
├── cli.py         # CLI con click + rich
└── mcp_server.py  # Servidor MCP stdio (10 tools)
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

## Uso CLI

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

# Actividades agrupadas por tipo
uv run campus activities 442

# Entregas (assignments) con conteo de envíos y calificaciones
uv run campus assignments 442

# Reporte de calificaciones
uv run campus grades 442

# Iniciar servidor MCP
uv run campus serve
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

## Tools MCP disponibles

| Tool | Descripción |
|------|-------------|
| `get_site_info` | Info del sitio y usuario actual |
| `list_courses` | Cursos donde el usuario está enrolado |
| `list_categories` | Categorías (jerarquía académica) |
| `get_course_contents` | Secciones y actividades de un curso |
| `list_enrolled_users` | Usuarios enrolados con filtro por rol |
| `list_groups` | Grupos (comisiones) de un curso |
| `list_activities` | Actividades agrupadas por tipo |
| `list_assignments` | Entregas con stats de envíos/calificaciones |
| `get_grades_report` | Reporte de calificaciones |
| `get_assignment_submissions` | Detalle de entregas de un TP |

## Notas

- El cliente usa Web Services de Moodle (REST + token), no scraping HTML. Es más rápido y estable.
- Autenticación: `login/token.php` con servicio `moodle_mobile_app` obtiene un token de WS automáticamente.
- SSL auto-firmado: `verify_ssl=False` por defecto (común en deployments universitarios).
- Todos los datos de estudiantes son PII: no commitear exports ni dumps.
