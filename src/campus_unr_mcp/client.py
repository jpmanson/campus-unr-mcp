"""HTTP client for Campus Virtual FCEIA UNR (Moodle Web Services).

This is a thin, reusable client that authenticates via Moodle's token-based
authentication (login/token.php) and calls the REST/XML-RPC web service
endpoint (webservice/rest/server.php). All business logic lives here so the
CLI and MCP layers are pure adapters.
"""

from __future__ import annotations

import os
import ssl
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import dotenv_values

DEFAULT_BASE_URL = "https://campusv.fceia.unr.edu.ar/"
DEFAULT_SERVICE = "moodle_mobile_app"


class CampusError(Exception):
    """Base error for campus API failures."""


class AuthenticationError(CampusError):
    """Login failed."""


@dataclass
class CampusConfig:
    base_url: str = DEFAULT_BASE_URL
    username: str = ""
    password: str = ""
    service: str = DEFAULT_SERVICE
    # Pre-obtained token (skip login flow). If empty, client will authenticate.
    token: str = ""
    # Allow self-signed certs (common in university deployments)
    verify_ssl: bool = False
    timeout: float = 30.0

    @classmethod
    def from_env(cls, env_path: str | Path | None = None) -> "CampusConfig":
        """Load config from a .env file or process environment."""
        vals: dict[str, str | None] = {}
        if env_path:
            vals = dotenv_values(env_path)
        vals = {k: v for k, v in vals.items() if v is not None}  # type: ignore

        base_url = (
            vals.get("CAMPUS_BASE_URL")
            or os.environ.get("CAMPUS_BASE_URL")
            or DEFAULT_BASE_URL
        )
        if not base_url.endswith("/"):
            base_url += "/"
        username = vals.get("CAMPUS_USER") or os.environ.get("CAMPUS_USER", "")
        password = vals.get("CAMPUS_PASS") or os.environ.get("CAMPUS_PASS", "")
        token = vals.get("CAMPUS_TOKEN") or os.environ.get("CAMPUS_TOKEN", "")

        return cls(
            base_url=base_url,
            username=username,
            password=password,
            token=token,
        )


def _ts_to_iso(ts: int | None | str) -> str | None:
    """Convert a unix timestamp (int/str) to ISO-8601 or None."""
    if not ts:
        return None
    try:
        ts_int = int(ts)
    except (ValueError, TypeError):
        return None
    if ts_int == 0:
        return None
    return datetime.fromtimestamp(ts_int, tz=timezone.utc).isoformat()


class CampusClient:
    """Authenticated client for Moodle Web Services.

    Usage::

        client = CampusClient(CampusConfig.from_env(".env"))
        info = client.get_site_info()
        courses = client.get_courses(info["userid"])
    """

    def __init__(self, config: CampusConfig):
        self.config = config
        self._token: str | None = config.token or None
        self._userid: int | None = None
        self._site_info: dict | None = None
        self._http = httpx.Client(
            timeout=config.timeout,
            verify=config.verify_ssl,
            follow_redirects=True,
            headers={"User-Agent": "campus-unr-mcp/0.1"},
        )

    # -- Lifecycle --

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "CampusClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- Auth --

    def login(self) -> str:
        """Obtain a web service token via login/token.php."""
        if self._token:
            return self._token
        if not self.config.username or not self.config.password:
            raise AuthenticationError(
                "No credentials: set CAMPUS_USER/CAMPUS_PASS or provide a token."
            )
        url = urllib.parse.urljoin(self.config.base_url, "login/token.php")
        resp = self._http.post(
            url,
            data={
                "username": self.config.username,
                "password": self.config.password,
                "service": self.config.service,
            },
        )
        data = resp.json()
        if "token" not in data:
            raise AuthenticationError(
                f"Login failed: {data.get('error', data)}"
            )
        self._token = data["token"]
        return self._token

    @property
    def token(self) -> str:
        if not self._token:
            self.login()
        assert self._token is not None
        return self._token

    # -- Low-level WS call --

    def ws(self, function: str, **params) -> object:
        """Call a Moodle Web Service function and return parsed JSON."""
        # Build form data as a flat dict (Moodle accepts bracketed keys)
        data: dict[str, str] = {
            "wstoken": self.token,
            "wsfunction": function,
            "moodlewsrestformat": "json",
        }
        for k, v in params.items():
            if isinstance(v, list):
                for i, item in enumerate(v):
                    data[f"{k}[{i}]"] = str(item)
            elif isinstance(v, dict):
                for dk, dv in v.items():
                    data[f"{k}[{dk}]"] = str(dv)
            elif v is not None:
                data[k] = str(v)

        url = urllib.parse.urljoin(
            self.config.base_url, "webservice/rest/server.php"
        )
        resp = self._http.post(url, data=data)
        data = resp.json()

        if isinstance(data, dict) and "exception" in data:
            raise CampusError(
                f"WS error calling {function}: "
                f"{data.get('errorcode', '?')} - {data.get('message', '?')}"
            )
        return data

    # -- High-level convenience methods --

    def get_site_info(self) -> dict:
        """Get site info including current user details."""
        info = self.ws("core_webservice_get_site_info")  # type: ignore[assignment]
        self._site_info = info  # type: ignore[assignment]
        if isinstance(info, dict):
            self._userid = info.get("userid")
        return info  # type: ignore[return-value]

    @property
    def userid(self) -> int:
        if self._userid is None:
            self.get_site_info()
        assert self._userid is not None
        return self._userid

    def get_courses(
        self, userid: int | None = None, include_details: bool = True
    ) -> list[dict]:
        """Get courses for a user (default: current user)."""
        uid = userid or self.userid
        courses = self.ws("core_enrol_get_users_courses", userid=uid)
        if not isinstance(courses, list):
            return []
        if include_details:
            for c in courses:
                _enrich_course(c)
        return courses

    def get_categories(
        self, parent: int | None = None, add_subcategories: bool = True
    ) -> list[dict]:
        """Get course categories (periods/departments hierarchy)."""
        params: dict = {}
        criteria: list[dict] = []
        if parent is not None:
            criteria.append({"key": "parent", "value": str(parent)})
        criteria.append({"key": "visible", "value": "0"})
        params["addsubcategories"] = int(add_subcategories)
        if criteria:
            for i, c in enumerate(criteria):
                params[f"criteria[{i}][key]"] = c["key"]
                params[f"criteria[{i}][value]"] = c["value"]

        # The visible=0 trick with criteria doesn't work well; do a plain call
        params = {"addsubcategories": 1 if add_subcategories else 0}
        cats = self.ws("core_course_get_categories", **params)
        if not isinstance(cats, list):
            return []
        return cats

    def get_course_contents(self, courseid: int) -> list[dict]:
        """Get sections and modules (activities/resources) of a course."""
        result = self.ws("core_course_get_contents", courseid=courseid)
        return result if isinstance(result, list) else []

    def get_enrolled_users(self, courseid: int) -> list[dict]:
        """Get all enrolled users in a course with their roles."""
        users = self.ws("core_enrol_get_enrolled_users", courseid=courseid)
        return users if isinstance(users, list) else []

    def get_groups(self, courseid: int) -> list[dict]:
        """Get groups in a course."""
        groups = self.ws("core_group_get_course_groups", courseid=courseid)
        return groups if isinstance(groups, list) else []

    def get_groups_with_members(self, courseid: int) -> list[dict]:
        """Get groups with their member lists.

        Builds membership from enrolled users (each user carries a 'groups'
        array in Moodle WS), then attaches it to each group.
        """
        groups = self.get_groups(courseid)
        if not groups:
            return []
        member_map = self.get_group_members(courseid)
        for g in groups:
            members = member_map.get(g.get("name", ""), [])
            g["members"] = members
            g["member_count"] = len(members)
        return groups

    # -- Activities --

    def get_course_activities(self, courseid: int) -> dict:
        """Get all activities in a course, grouped by type.

        Returns dict with keys: quizzes, assignments, forums, resources, etc.
        Each is a list of activity dicts with id, name, instance, section.
        """
        contents = self.get_course_contents(courseid)
        by_type: dict[str, list[dict]] = {}
        for section in contents:
            for mod in section.get("modules", []):
                modtype = mod.get("modname", "unknown")
                entry = {
                    "id": mod.get("id"),
                    "instance": mod.get("instance"),
                    "name": mod.get("name"),
                    "modname": modtype,
                    "section": section.get("name"),
                    "section_id": section.get("id"),
                    "visible": section.get("visible", 1) == 1
                    and mod.get("visible", 1) == 1,
                    "url": mod.get("url"),
                }
                by_type.setdefault(modtype, []).append(entry)
        return by_type

    def get_assignments(self, courseid: int) -> list[dict]:
        """Get assignments (TP/entregas) in a course with submission/grade info."""
        # Get assignment instances from course contents
        activities = self.get_course_activities(courseid)
        assigns = activities.get("assign", [])
        if not assigns:
            return []
        # Enrich with details
        for a in assigns:
            inst = a.get("instance")
            if not inst:
                continue
            # Get submissions count
            try:
                sub_data = self.ws(
                    "mod_assign_get_submissions", **{"assignmentids[0]": inst}
                )
                if isinstance(sub_data, dict):
                    for sa in sub_data.get("assignments", []):
                        subs = sa.get("submissions", [])
                        a["submission_count"] = len(subs)
            except CampusError:
                a["submission_count"] = None
            # Get grades count
            try:
                grade_data = self.ws(
                    "mod_assign_get_grades", **{"assignmentids[0]": inst}
                )
                if isinstance(grade_data, dict):
                    for ga in grade_data.get("assignments", []):
                        grades = ga.get("grades", [])
                        a["graded_count"] = len(
                            [g for g in grades if float(g.get("grade", -1)) >= 0]
                        )
            except CampusError:
                a["graded_count"] = None
        return assigns

    def get_assignment_submissions(self, assignmentid: int) -> list[dict]:
        """Get submissions for a specific assignment."""
        data = self.ws(
            "mod_assign_get_submissions", **{"assignmentids[0]": assignmentid}
        )
        if not isinstance(data, dict):
            return []
        subs: list[dict] = []
        for a in data.get("assignments", []):
            for s in a.get("submissions", []):
                subs.append(s)
        return subs

    # -- Grades --

    def get_grades_report(
        self, courseid: int, userid: int | None = None
    ) -> list[dict]:
        """Get grade items for a course (all students or one).

        Returns a list of user grade entries.
        """
        params: dict = {"courseid": courseid}
        if userid is not None:
            params["userid"] = userid
        data = self.ws("gradereport_user_get_grade_items", **params)
        if not isinstance(data, dict):
            return []
        return data.get("usergrades", [])

    # -- Forums --

    def get_forums(self, courseid: int) -> list[dict]:
        """List forums in a course with discussion counts."""
        data = self.ws(
            "mod_forum_get_forums_by_courses", **{"courseids[0]": courseid}
        )
        return data if isinstance(data, list) else []

    def get_forum_discussions(self, forumid: int) -> list[dict]:
        """List discussions (temas) in a forum, including message content."""
        data = self.ws(
            "mod_forum_get_forum_discussions",
            forumid=forumid,
        )
        if not isinstance(data, dict):
            return []
        return data.get("discussions", [])

    def get_forum_discussion_posts(self, discussionid: int) -> list[dict]:
        """Get posts (respuestas) in a discussion thread."""
        data = self.ws(
            "mod_forum_get_forum_discussion_posts", discussionid=discussionid
        )
        if not isinstance(data, dict):
            return []
        return data.get("posts", [])

    # -- Quiz --

    def get_quiz_attempts(self, quizid: int, userid: int = 0) -> list[dict]:
        """Get attempts for a quiz (userid=0 = current user only)."""
        data = self.ws(
            "mod_quiz_get_user_attempts", quizid=quizid, userid=userid
        )
        if not isinstance(data, dict):
            return []
        return data.get("attempts", [])

    def get_course_grades(self, courseid: int) -> list[dict]:
        """Get all grade items for a course via the grade report.

        Each entry has userid, fullname, and gradeitems with per-item grades.
        Use this to get quiz/assignment grades for all students at once.
        """
        data = self.ws("gradereport_user_get_grade_items", courseid=courseid)
        if not isinstance(data, dict):
            return []
        return data.get("usergrades", [])

    # -- Groups --

    def get_group_members(self, courseid: int) -> dict[str, list[dict]]:
        """Build a group-name -> members map from enrolled users.

        Moodle's core_enrol_get_enrolled_users includes a 'groups' array per
        user, which we invert into a membership map.
        """
        users = self.get_enrolled_users(courseid)
        from collections import defaultdict

        group_map: dict[str, list[dict]] = defaultdict(list)
        for u in users:
            roles = [
                r.get("shortname")
                for r in u.get("roles", [])
                if isinstance(r, dict)
            ]
            for g in u.get("groups", []):
                group_map[g.get("name", "?")].append(
                    {
                        "userid": u.get("id"),
                        "fullname": u.get("fullname"),
                        "email": u.get("email", ""),
                        "roles": roles,
                    }
                )
        return dict(group_map)

    def get_calendar_events(
        self,
        courseids: list[int] | None = None,
        timestart: int | None = None,
        timeend: int | None = None,
    ) -> list[dict]:
        """Get calendar events (exámenes, parciales, deadlines).

        Args:
            courseids: Optional list of course IDs to filter.
            timestart: Optional unix timestamp lower bound.
            timeend: Optional unix timestamp upper bound.
        """
        params: dict = {}
        if courseids:
            for i, cid in enumerate(courseids):
                params[f"courseids[{i}]"] = cid
        events_filter: dict = {}
        if timestart is not None:
            events_filter["eventtype"] = "all"
        data = self.ws("core_calendar_get_calendar_events", **params)
        if not isinstance(data, dict):
            return []
        return data.get("events", [])

    # ========================================
    # WRITE OPERATIONS — all support dry_run
    # ========================================

    def can_add_discussion(self, forumid: int) -> bool:
        """Check if current user can post to a forum (no side effects)."""
        data = self.ws("mod_forum_can_add_discussion", forumid=forumid)
        if isinstance(data, dict):
            return bool(data.get("status", False))
        return False

    def create_forum_discussion(
        self,
        forumid: int,
        subject: str,
        message: str,
        dry_run: bool = True,
    ) -> dict:
        """Create a new discussion (tema) in a forum.

        Args:
            forumid: Forum instance ID.
            subject: Discussion title.
            message: Body text (HTML allowed).
            dry_run: If True, only validate permissions without posting.

        Returns:
            dict with 'validated' (bool), and 'discussionid' (int|None).
        """
        # Validate permissions first
        can = self.can_add_discussion(forumid)
        if not can:
            return {"validated": False, "error": "No permission to post in this forum"}

        if dry_run:
            return {"validated": True, "discussionid": None, "dry_run": True}

        result = self.ws(
            "mod_forum_add_discussion",
            forumid=forumid,
            subject=subject,
            message=message,
        )
        if isinstance(result, dict) and "discussionid" in result:
            return {"validated": True, "discussionid": result["discussionid"]}
        return {"validated": False, "error": str(result)}

    def delete_forum_post(self, postid: int) -> bool:
        """Delete a forum post or discussion."""
        result = self.ws("mod_forum_delete_post", postid=postid)
        if isinstance(result, dict):
            return bool(result.get("status", False))
        return False

    def reply_forum_post(
        self,
        postid: int,
        subject: str,
        message: str,
        dry_run: bool = True,
    ) -> dict:
        """Reply to an existing forum post.

        Args:
            postid: The ID of the post being replied to (parent).
            subject: Reply subject.
            message: Reply body.
            dry_run: If True, only validate without posting.

        Returns:
            dict with 'validated' (bool) and 'postid' (int|None).
        """
        # In dry_run mode, just check the params are valid
        if dry_run:
            return {"validated": True, "postid": None, "dry_run": True}

        result = self.ws(
            "mod_forum_add_discussion_post",
            postid=postid,
            subject=subject,
            message=message,
        )
        if isinstance(result, dict) and "postid" in result:
            return {"validated": True, "postid": result["postid"]}
        return {"validated": False, "error": str(result)}

    def save_assignment_grade(
        self,
        assignmentid: int,
        userid: int,
        grade: float,
        feedback: str = "",
        attemptnumber: int = -1,
        dry_run: bool = True,
    ) -> dict:
        """Save a grade for a student's assignment.

        Args:
            assignmentid: Assignment instance ID.
            userid: Student user ID.
            grade: Numeric grade.
            feedback: Feedback comment text.
            attemptnumber: Attempt number (-1 = latest).
            dry_run: If True, only validate parameters.

        Returns:
            dict with 'validated' (bool) and confirmation.
        """
        if not 0 <= grade <= 10:
            return {"validated": False, "error": "Grade must be between 0 and 10"}

        if dry_run:
            return {
                "validated": True,
                "dry_run": True,
                "assignmentid": assignmentid,
                "userid": userid,
                "grade": grade,
            }

        params = {
            "assignmentid": assignmentid,
            "userid": userid,
            "grade": str(grade),
            "attemptnumber": attemptnumber,
            "addattempt": 0,
            "workflowstate": "graded",
            "applytoall": 0,
            "plugindata[assignfeedbackcomments_editor][text]": feedback,
            "plugindata[assignfeedbackcomments_editor][format]": 1,
            "plugindata[files_filemanager]": 0,
        }
        result = self.ws("mod_assign_save_grade", **params)
        if isinstance(result, dict) and result.get("status") is None:
            # mod_assign_save_grade returns null/empty on success
            return {
                "validated": True,
                "saved": True,
                "assignmentid": assignmentid,
                "userid": userid,
                "grade": grade,
            }
        if isinstance(result, list) and not result:
            return {
                "validated": True,
                "saved": True,
                "assignmentid": assignmentid,
                "userid": userid,
                "grade": grade,
            }
        return {"validated": False, "error": str(result)}

    def send_message_to_user(
        self,
        userid: int,
        message: str,
        dry_run: bool = True,
    ) -> dict:
        """Send an instant message to a user.

        Args:
            userid: Recipient user ID.
            message: Message text.
            dry_run: If True, only validate parameters.

        Returns:
            dict with 'validated' (bool) and 'msgid' (int|None).
        """
        if dry_run:
            return {"validated": True, "dry_run": True, "userid": userid}

        # core_message_send_instant_messages expects messages[0][touserid] and [text]
        result = self.ws(
            "core_message_send_instant_messages",
            **{"messages[0][touserid]": userid, "messages[0][text]": message},
        )
        if isinstance(result, list) and result:
            entry = result[0]
            if entry.get("msgid"):
                return {"validated": True, "msgid": entry["msgid"]}
            if entry.get("errormessage"):
                return {"validated": False, "error": entry["errormessage"]}
        return {"validated": False, "error": str(result)}

    def create_calendar_event(
        self,
        name: str,
        courseid: int,
        timestart: int,
        description: str = "",
        eventtype: str = "course",
        duration: int = 0,
        dry_run: bool = True,
    ) -> dict:
        """Create a calendar event (fecha de examen, entrega, etc.).

        Args:
            name: Event title.
            courseid: Course ID.
            timestart: Unix timestamp for event start.
            description: Event description.
            eventtype: Event type (course, user, group).
            duration: Duration in seconds (0 = no duration).
            dry_run: If True, only validate parameters.

        Returns:
            dict with 'validated' (bool) and 'eventid' (int|None).
        """
        if not name or not courseid or not timestart:
            return {"validated": False, "error": "name, courseid, timestart required"}

        if dry_run:
            return {
                "validated": True,
                "dry_run": True,
                "name": name,
                "courseid": courseid,
                "timestart_iso": _ts_to_iso(timestart),
            }

        result = self.ws(
            "core_calendar_create_calendar_events",
            **{
                "events[0][name]": name,
                "events[0][description]": description,
                "events[0][courseid]": courseid,
                "events[0][eventtype]": eventtype,
                "events[0][timestart]": timestart,
                "events[0][timeduration]": duration,
            },
        )
        if isinstance(result, dict):
            events = result.get("events", [])
            if events:
                return {"validated": True, "eventid": events[0].get("id")}
        return {"validated": False, "error": str(result)}


# -- Helpers --

def _enrich_course(c: dict) -> None:
    """Add ISO date fields and role short-names to a course dict (in-place)."""
    c["startdate_iso"] = _ts_to_iso(c.get("startdate"))
    c["enddate_iso"] = _ts_to_iso(c.get("enddate"))
    roles = c.get("roles", [])
    if isinstance(roles, list):
        c["role_shortnames"] = [
            r.get("shortname") for r in roles if isinstance(r, dict)
        ]
    else:
        c["role_shortnames"] = []


def ts_to_iso(ts: int | None | str) -> str | None:
    """Public helper to format timestamps."""
    return _ts_to_iso(ts)
