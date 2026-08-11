"""MCP server exposing Campus Virtual FCEIA UNR docente tools via stdio.

Run with::

    campus serve
    # or
    uv run campus serve
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from mcp.server.mcpserver.server import MCPServer

from .client import CampusClient, CampusConfig

# Cache the client across tool calls within a session
_client: CampusClient | None = None


def _get_client() -> CampusClient:
    global _client
    if _client is None:
        # Try .env in cwd first, then environment variables
        env_path = Path.cwd() / ".env"
        config = CampusConfig.from_env(env_path if env_path.exists() else None)
        _client = CampusClient(config)
    return _client


mcp = MCPServer(
    name="campus-unr-mcp",
    title="Campus Virtual FCEIA UNR",
    description="Docente tools for Campus Virtual FCEIA UNR (Moodle).",
    version="0.1.0",
)


@mcp.tool()
def get_site_info() -> str:
    """Get site information and current user details from the campus.

    Returns: JSON with site name, URL, user id, username, full name, and
    available web service functions count.
    """
    with _get_client() as c:
        info = c.get_site_info()
    return json.dumps(
        {
            "sitename": info.get("sitename"),
            "siteurl": info.get("siteurl"),
            "userid": info.get("userid"),
            "username": info.get("username"),
            "fullname": info.get("fullname"),
            "lang": info.get("lang"),
            "ws_functions_count": len(info.get("functions", [])),
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
def list_courses() -> str:
    """List all courses where the current user is enrolled (cursadas).

    Returns: JSON array of courses with id, shortname, fullname, category,
    start/end dates, and the user's roles in each.
    """
    with _get_client() as c:
        courses = c.get_courses()
    result = [
        {
            "id": crs.get("id"),
            "shortname": crs.get("shortname"),
            "fullname": crs.get("fullname"),
            "category": crs.get("category"),
            "startdate": crs.get("startdate_iso"),
            "enddate": crs.get("enddate_iso"),
            "format": crs.get("format"),
            "roles": crs.get("role_shortnames", []),
            "url": f"{c.config.base_url}course/view.php?id={crs.get('id')}",
        }
        for crs in courses
    ]
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def list_categories() -> str:
    """List course categories (períodos lectivos, carreras, áreas).

    In Moodle, categories organize courses hierarchically by faculty,
    degree program, year, or academic period.

    Returns: JSON array of categories with id, name, parent, depth,
    and course count.
    """
    with _get_client() as c:
        cats = c.get_categories()
    result = [
        {
            "id": cat.get("id"),
            "name": cat.get("name"),
            "parent": cat.get("parent"),
            "depth": cat.get("depth"),
            "coursecount": cat.get("coursecount"),
            "visible": cat.get("visible"),
        }
        for cat in cats
    ]
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def get_course_contents(course_id: int) -> str:
    """Get all sections and activities/resources in a course.

    Args:
        course_id: The Moodle course ID.

    Returns: JSON array of sections, each with a list of modules
    (activities and resources) including type, name, and URL.
    """
    with _get_client() as c:
        contents = c.get_course_contents(course_id)
    result = [
        {
            "section": section.get("name"),
            "section_id": section.get("id"),
            "visible": section.get("visible", 1) == 1,
            "modules": [
                {
                    "id": mod.get("id"),
                    "name": mod.get("name"),
                    "type": mod.get("modname"),
                    "instance": mod.get("instance"),
                    "visible": mod.get("visible", 1) == 1,
                    "url": mod.get("url"),
                }
                for mod in section.get("modules", [])
            ],
        }
        for section in contents
    ]
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def list_enrolled_users(course_id: int, role: str = "") -> str:
    """List users enrolled in a course with their roles.

    Args:
        course_id: The Moodle course ID.
        role: Optional role filter (e.g. 'student', 'editingteacher',
              'teacher', 'manager'). Empty = all.

    Returns: JSON array of users with id, fullname, email, and roles.
    """
    with _get_client() as c:
        users = c.get_enrolled_users(course_id)
    if role:
        users = [
            u
            for u in users
            if any(r.get("shortname") == role for r in u.get("roles", []))
        ]
    result = [
        {
            "id": u.get("id"),
            "fullname": u.get("fullname"),
            "username": u.get("username"),
            "email": u.get("email"),
            "roles": [r.get("shortname") for r in u.get("roles", [])],
            "groups": [g.get("name") for g in u.get("groups", [])],
        }
        for u in users
    ]
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def list_groups(course_id: int) -> str:
    """List groups (comisiones) in a course.

    Args:
        course_id: The Moodle course ID.

    Returns: JSON array of groups with id, name, and description.
    """
    with _get_client() as c:
        groups = c.get_groups(course_id)
    result = [
        {
            "id": g.get("id"),
            "name": g.get("name"),
            "description": g.get("description"),
        }
        for g in groups
    ]
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def list_activities(course_id: int) -> str:
    """List all activities in a course, grouped by type (quiz, assign, forum, etc.).

    Args:
        course_id: The Moodle course ID.

    Returns: JSON object mapping activity type -> list of activities.
    """
    with _get_client() as c:
        activities = c.get_course_activities(course_id)
    return json.dumps(activities, ensure_ascii=False, indent=2)


@mcp.tool()
def list_assignments(course_id: int) -> str:
    """List assignments (trabajos prácticos/entregas) with submission stats.

    Args:
        course_id: The Moodle course ID.

    Returns: JSON array of assignments with submission and grade counts.
    """
    with _get_client() as c:
        assigns = c.get_assignments(course_id)
    return json.dumps(assigns, ensure_ascii=False, indent=2)


@mcp.tool()
def get_grades_report(course_id: int, user_id: int = 0) -> str:
    """Get grade report for a course (all users or a specific user).

    Args:
        course_id: The Moodle course ID.
        user_id: Optional user ID to get grades for one student only.
                 0 or omitted = all enrolled users.

    Returns: JSON with grade items and grades per user.
    """
    with _get_client() as c:
        grades = c.get_grades_report(course_id, user_id if user_id else None)
    return json.dumps(grades, ensure_ascii=False, indent=2, default=str)


@mcp.tool()
def get_assignment_submissions(assignment_id: int) -> str:
    """List submissions for a specific assignment.

    Args:
        assignment_id: The assignment instance ID (not course module ID).

    Returns: JSON array of submissions with status, dates, and content.
    """
    with _get_client() as c:
        subs = c.get_assignment_submissions(assignment_id)
    return json.dumps(subs, ensure_ascii=False, indent=2)


def run_server() -> None:
    """Entry point for the MCP stdio server."""
    mcp.run(transport="stdio")
