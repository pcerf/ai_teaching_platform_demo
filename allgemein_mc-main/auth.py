from __future__ import annotations
from fastapi import HTTPException, Request

def get_forward_auth(request: Request) -> dict[str, str]:
    email_hash = request.headers.get("x-auth-email-hash")
    session_id = request.headers.get("x-auth-session-id")
    user_id = request.headers.get("x-auth-user-id", "")

    if not email_hash or not session_id:
        raise HTTPException(status_code=500, detail="auth_headers_missing")

    return {"email_hash": email_hash, "session_id": session_id, "user_id": user_id}
