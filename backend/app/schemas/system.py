from pydantic import BaseModel


class AuthCapabilities(BaseModel):
    password: bool
    microsoft_sso: bool


class NotificationCapabilities(BaseModel):
    email: bool
    teams: bool


class ExportCapabilities(BaseModel):
    csv: bool
    xlsx: bool


class SystemCapabilities(BaseModel):
    demo_mode: bool
    auth: AuthCapabilities
    notifications: NotificationCapabilities
    exports: ExportCapabilities
