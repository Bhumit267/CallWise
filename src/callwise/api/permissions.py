"""Role-Based Access Control (RBAC) permission definitions and FastAPI dependencies."""

from enum import Enum
from typing import Callable, List, Optional, Tuple
from fastapi import Depends, HTTPException, status

from callwise.api.deps import get_auth_context
from callwise.db.models import Business, Session as UserSession, User


class Role(str, Enum):
    """User tenant membership roles in order of decreasing privilege."""
    OWNER = "owner"
    MANAGER = "manager"
    STAFF = "staff"


ROLE_HIERARCHY = {
    Role.OWNER: [Role.OWNER, Role.MANAGER, Role.STAFF],
    Role.MANAGER: [Role.MANAGER, Role.STAFF],
    Role.STAFF: [Role.STAFF],
}


def require_role(min_role: Role) -> Callable:
    """
    Factory creating a dependency that enforces minimum required role.
    - OWNER: only owners
    - MANAGER: owners and managers
    - STAFF: owners, managers, and staff
    """
    async def _role_checker(
        auth_ctx: Tuple[User, Optional[Business], Optional[str], UserSession] = Depends(get_auth_context)
    ) -> Tuple[User, Business, str, UserSession]:
        user, business, role_str, session_obj = auth_ctx

        if not business:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active business tenant selected. Please select a business.",
            )

        if not role_str:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have a membership in this business.",
            )

        try:
            user_role = Role(role_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Unrecognized role '{role_str}'.",
            )

        allowed_roles = ROLE_HIERARCHY.get(min_role, [])
        # Check if user_role possesses the privilege level of min_role
        has_permission = False
        for allowed in ROLE_HIERARCHY:
            if min_role in ROLE_HIERARCHY[allowed] and user_role == allowed:
                has_permission = True
                break

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action requires at least '{min_role.value}' role. Your role is '{user_role.value}'.",
            )

        return user, business, user_role.value, session_obj

    return _role_checker


# Convenient dependencies
require_owner = require_role(Role.OWNER)
require_manager = require_role(Role.MANAGER)
require_staff = require_role(Role.STAFF)
