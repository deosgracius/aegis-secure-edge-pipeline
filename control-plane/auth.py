"""
auth.py -- bearer-token authentication + role-based access control (RBAC).

Every request carries `Authorization: Bearer <token>`. The token maps to a user
with a role; endpoints declare the minimum role they require via require_role().

Roles form a ladder: viewer < operator < admin.
  - viewer   : read dashboards
  - operator : + ingest telemetry, quarantine, approve/reject investigations
  - admin    : + read the audit log, manage users

This is intentionally simple (a demo control plane). The upgrade path is the
same shape: swap static tokens for OAuth/OIDC + MFA, keep the role checks.
"""

from fastapi import Depends, Header, HTTPException

import store

ROLE_LEVEL = {"viewer": 1, "operator": 2, "admin": 3}


def get_current_user(authorization: str = Header(default="")):
    """Resolve the bearer token to a user, or 401."""
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    user = store.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid token")
    return user


def require_role(min_role: str):
    """Dependency factory: require at least `min_role`."""
    need = ROLE_LEVEL[min_role]

    def _dep(user=Depends(get_current_user)):
        if ROLE_LEVEL.get(user["role"], 0) < need:
            raise HTTPException(
                status_code=403,
                detail="role '%s' cannot perform this action (needs %s)"
                       % (user["role"], min_role))
        return user

    return _dep
