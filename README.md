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

Agregar a `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  campus-unr:
    command: "uv"
    args:
      - "--directory"
      - "/Users/jpmanson/Development/campus-unr-mcp"
      - "run"
      - "campus"
      - "serve"
    timeout: 120
    connect_timeout: 60
```

Reiniciar Hermes para que descubra las tools.

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
