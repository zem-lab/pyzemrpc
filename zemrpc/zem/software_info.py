"""Software identity reported by the remote host, not the local SDK version."""

from pydantic import BaseModel, ConfigDict, Field


class SoftwareInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str = Field(strict=True)
    commit_id: str = Field(strict=True)
