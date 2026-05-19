from fastapi import APIRouter

from app.config import settings
from app.schemas.system import AuthCapabilities, ExportCapabilities, NotificationCapabilities, SystemCapabilities

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/capabilities", response_model=SystemCapabilities)
async def get_capabilities() -> SystemCapabilities:
    return SystemCapabilities(
        demo_mode=settings.demo_mode,
        auth=AuthCapabilities(
            password=settings.password_auth_enabled,
            microsoft_sso=settings.microsoft_sso_enabled,
        ),
        notifications=NotificationCapabilities(
            email=settings.email_enabled,
            teams=settings.teams_enabled,
        ),
        exports=ExportCapabilities(csv=True, xlsx=True),
    )
