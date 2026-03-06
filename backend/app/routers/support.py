from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request

from ..auth_utils import build_user_profile
from ..auth_utils import normalize_role
from ..auth_utils import require_current_user
from ..auth_utils import success_response
from ..auth_utils import utcnow_iso
from ..database import get_conn

router = APIRouter(tags=["support"])

VALID_TICKET_STATUS = {"open", "in_progress", "waiting_user", "resolved", "closed"}
VALID_TICKET_PRIORITY = {"low", "normal", "high", "urgent"}
VALID_TICKET_CATEGORY = {"general", "bug", "payment", "account", "suggestion", "cardflip"}


def _is_admin(user_row: Any) -> bool:
    return normalize_role(user_row["role"]) == "admin"


def _ticket_summary(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "ticketNo": row["ticket_no"],
        "title": row["title"],
        "category": row["category"],
        "priority": row["priority"],
        "status": row["status"],
        "description": row["description"],
        "adminAssignee": row["admin_assignee"],
        "lastReplyBy": row["last_reply_by"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "closedAt": row["closed_at"],
        "reporter": {
            "id": int(row["user_id"]),
            "username": row["username"],
            "nickname": row["nickname"],
            "email": row["email"],
        },
    }


def _message_payload(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "ticketId": int(row["ticket_id"]),
        "authorUserId": int(row["author_user_id"]),
        "authorRole": row["author_role"],
        "authorName": row["author_name"],
        "internalOnly": bool(row["is_internal"]),
        "message": row["message"],
        "createdAt": row["created_at"],
    }


def _build_ticket_no() -> str:
    while True:
        code = f"TK{datetime.now():%Y%m%d}{secrets.randbelow(9000) + 1000}"
        with get_conn() as conn:
            existing = conn.execute(
                "SELECT id FROM support_tickets WHERE ticket_no = ? LIMIT 1",
                (code,),
            ).fetchone()
        if existing is None:
            return code


def _load_ticket(conn, ticket_id: int):
    return conn.execute(
        """
        SELECT t.*, u.username, u.nickname, u.email
        FROM support_tickets AS t
        JOIN users AS u ON u.id = t.user_id
        WHERE t.id = ?
        LIMIT 1
        """,
        (ticket_id,),
    ).fetchone()


def _ensure_ticket_access(conn, ticket_id: int, user_row: Any):
    row = _load_ticket(conn, ticket_id)
    if row is None:
        raise HTTPException(status_code=404, detail="工单不存在")
    if _is_admin(user_row):
        return row
    if int(row["user_id"]) != int(user_row["id"]):
        raise HTTPException(status_code=403, detail="无权查看该工单")
    return row


def _ticket_messages(conn, ticket_id: int, *, include_internal: bool) -> list[dict[str, Any]]:
    clauses = ["m.ticket_id = ?"]
    params: list[Any] = [ticket_id]
    if not include_internal:
        clauses.append("m.is_internal = 0")

    rows = conn.execute(
        f"""
        SELECT m.*, COALESCE(u.nickname, u.username) AS author_name
        FROM support_ticket_messages AS m
        JOIN users AS u ON u.id = m.author_user_id
        WHERE {' AND '.join(clauses)}
        ORDER BY m.created_at ASC, m.id ASC
        """,
        tuple(params),
    ).fetchall()
    return [_message_payload(row) for row in rows]


@router.get("/support/tickets")
def list_tickets(
    request: Request,
    status: str = "",
    category: str = "",
    keyword: str = "",
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    with get_conn() as conn:
        user_row = require_current_user(conn, request)
        where_parts = ["1 = 1"]
        params: list[Any] = []

        if not _is_admin(user_row):
            where_parts.append("t.user_id = ?")
            params.append(int(user_row["id"]))
        if status:
            where_parts.append("t.status = ?")
            params.append(status)
        if category:
            where_parts.append("t.category = ?")
            params.append(category)
        if keyword.strip():
            like = f"%{keyword.strip()}%"
            where_parts.append("(t.ticket_no LIKE ? OR t.title LIKE ? OR t.description LIKE ?)")
            params.extend([like, like, like])

        rows = conn.execute(
            f"""
            SELECT t.*, u.username, u.nickname, u.email
            FROM support_tickets AS t
            JOIN users AS u ON u.id = t.user_id
            WHERE {' AND '.join(where_parts)}
            ORDER BY t.updated_at DESC, t.id DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()

        stats_row = conn.execute(
            f"""
            SELECT
                COUNT(*) AS total_count,
                SUM(CASE WHEN t.status IN ('open', 'in_progress', 'waiting_user') THEN 1 ELSE 0 END) AS active_count,
                SUM(CASE WHEN t.status = 'resolved' THEN 1 ELSE 0 END) AS resolved_count,
                SUM(CASE WHEN t.status = 'closed' THEN 1 ELSE 0 END) AS closed_count
            FROM support_tickets AS t
            WHERE {' AND '.join(where_parts)}
            """,
            tuple(params),
        ).fetchone()

        data = {
            "items": [_ticket_summary(row) for row in rows],
            "stats": {
                "total": int(stats_row["total_count"] or 0),
                "active": int(stats_row["active_count"] or 0),
                "resolved": int(stats_row["resolved_count"] or 0),
                "closed": int(stats_row["closed_count"] or 0),
            },
            "viewer": build_user_profile(user_row),
            "canManage": _is_admin(user_row),
        }
    return success_response(data)


@router.post("/support/tickets")
def create_ticket(request: Request, body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = body if isinstance(body, dict) else {}
    title = str(payload.get("title") or "").strip()
    category = str(payload.get("category") or "general").strip().lower()
    priority = str(payload.get("priority") or "normal").strip().lower()
    description = str(payload.get("description") or "").strip()

    if len(title) < 4:
        raise HTTPException(status_code=400, detail="标题至少需要 4 个字")
    if len(description) < 10:
        raise HTTPException(status_code=400, detail="问题描述至少需要 10 个字")
    if category not in VALID_TICKET_CATEGORY:
        category = "general"
    if priority not in VALID_TICKET_PRIORITY:
        priority = "normal"

    ticket_no = _build_ticket_no()
    now = utcnow_iso()

    with get_conn() as conn:
        user_row = require_current_user(conn, request)
        conn.execute(
            """
            INSERT INTO support_tickets (
                ticket_no,
                user_id,
                title,
                category,
                priority,
                status,
                description,
                admin_assignee,
                last_reply_by,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'open', ?, '', ?, ?, ?)
            """,
            (ticket_no, int(user_row["id"]), title, category, priority, description, user_row["username"], now, now),
        )
        ticket_id = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
        conn.execute(
            """
            INSERT INTO support_ticket_messages (
                ticket_id,
                author_user_id,
                author_role,
                is_internal,
                message,
                created_at
            )
            VALUES (?, ?, ?, 0, ?, ?)
            """,
            (ticket_id, int(user_row["id"]), normalize_role(user_row["role"]), description, now),
        )
        row = _load_ticket(conn, ticket_id)
        messages = _ticket_messages(conn, ticket_id, include_internal=False)

    return success_response({"ticket": _ticket_summary(row), "messages": messages}, message="ticket_created")


@router.get("/support/tickets/{ticket_id}")
def get_ticket_detail(ticket_id: int, request: Request) -> dict[str, Any]:
    with get_conn() as conn:
        user_row = require_current_user(conn, request)
        row = _ensure_ticket_access(conn, ticket_id, user_row)
        messages = _ticket_messages(conn, ticket_id, include_internal=_is_admin(user_row))
    return success_response({"ticket": _ticket_summary(row), "messages": messages})


@router.post("/support/tickets/{ticket_id}/reply")
def reply_ticket(ticket_id: int, request: Request, body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = body if isinstance(body, dict) else {}
    message = str(payload.get("message") or "").strip()
    internal_only = bool(payload.get("internalOnly"))
    if len(message) < 2:
        raise HTTPException(status_code=400, detail="回复内容不能为空")

    with get_conn() as conn:
        user_row = require_current_user(conn, request)
        row = _ensure_ticket_access(conn, ticket_id, user_row)
        is_admin = _is_admin(user_row)
        now = utcnow_iso()
        if internal_only and not is_admin:
            internal_only = False

        next_status = row["status"]
        if is_admin and next_status == "open":
            next_status = "in_progress"
        if not is_admin and row["status"] in {"resolved", "closed"}:
            next_status = "waiting_user"

        conn.execute(
            """
            INSERT INTO support_ticket_messages (
                ticket_id,
                author_user_id,
                author_role,
                is_internal,
                message,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                ticket_id,
                int(user_row["id"]),
                normalize_role(user_row["role"]),
                1 if internal_only else 0,
                message,
                now,
            ),
        )
        conn.execute(
            """
            UPDATE support_tickets
            SET status = ?,
                last_reply_by = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (next_status, user_row["username"], now, ticket_id),
        )
        updated = _load_ticket(conn, ticket_id)
        messages = _ticket_messages(conn, ticket_id, include_internal=is_admin)

    return success_response({"ticket": _ticket_summary(updated), "messages": messages}, message="ticket_replied")


@router.patch("/support/tickets/{ticket_id}")
def update_ticket(ticket_id: int, request: Request, body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = body if isinstance(body, dict) else {}
    with get_conn() as conn:
        user_row = require_current_user(conn, request)
        if not _is_admin(user_row):
            raise HTTPException(status_code=403, detail="只有管理员可以处理工单")

        row = _ensure_ticket_access(conn, ticket_id, user_row)
        next_status = str(payload.get("status") or row["status"]).strip().lower()
        next_priority = str(payload.get("priority") or row["priority"]).strip().lower()
        next_assignee = str(payload.get("adminAssignee") or row["admin_assignee"] or "").strip()

        if next_status not in VALID_TICKET_STATUS:
            next_status = row["status"]
        if next_priority not in VALID_TICKET_PRIORITY:
            next_priority = row["priority"]

        now = utcnow_iso()
        closed_at = now if next_status in {"resolved", "closed"} else None
        conn.execute(
            """
            UPDATE support_tickets
            SET status = ?,
                priority = ?,
                admin_assignee = ?,
                updated_at = ?,
                closed_at = ?
            WHERE id = ?
            """,
            (next_status, next_priority, next_assignee, now, closed_at, ticket_id),
        )
        updated = _load_ticket(conn, ticket_id)
        messages = _ticket_messages(conn, ticket_id, include_internal=True)

    return success_response({"ticket": _ticket_summary(updated), "messages": messages}, message="ticket_updated")
