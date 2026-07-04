from fnmatch import fnmatch
from typing import Any

from fastapi import HTTPException, status

from app.core.security import AuthContext
from app.db.models import Model, Provider


def _merged_access(auth: AuthContext) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for source in (auth.client.access_config or {}, auth.api_key.access_config or {}):
        for key, value in source.items():
            if isinstance(value, list):
                merged[key] = [*merged.get(key, []), *value]
            elif isinstance(value, dict):
                merged[key] = {**merged.get(key, {}), **value}
            else:
                merged[key] = value
    return merged


def _allowed(value: str | int, allowed_values: list[Any] | None) -> bool:
    if not allowed_values:
        return True
    return "*" in allowed_values or value in allowed_values or str(value) in {str(item) for item in allowed_values}


class AccessPolicyService:
    def ensure_chat_allowed(self, auth: AuthContext, model_alias: str, provider: Provider, model: Model) -> None:
        access = _merged_access(auth)
        if not _allowed(model_alias, access.get("model_aliases")):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Model alias is not allowed")
        if not _allowed(provider.id, access.get("provider_ids")):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Provider is not allowed")
        if not _allowed(provider.name, access.get("provider_names")):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Provider is not allowed")
        if not _allowed(model.id, access.get("model_ids")):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Model is not allowed")

    def ensure_native_allowed(self, auth: AuthContext, provider: Provider, native_path: str) -> None:
        access = _merged_access(auth)
        if not _allowed(provider.id, access.get("provider_ids")):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Provider is not allowed")
        if not _allowed(provider.name, access.get("provider_names")):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Provider is not allowed")
        patterns = access.get("native_paths") or access.get("native_path_patterns")
        if patterns and not any(fnmatch(native_path, pattern) for pattern in patterns):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Native path is not allowed")
