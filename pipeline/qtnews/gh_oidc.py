"""Проверка OIDC-токена GitHub Actions: рилсы собирает workflow этого репозитория, и ему не нужны
секреты в GitHub — он подтверждает себя подписанным токеном, который выдаёт сам GitHub."""
from __future__ import annotations

import os

import jwt  # PyJWT

ISSUER = "https://token.actions.githubusercontent.com"
AUDIENCE = "techtalq-reels"
_jwks: jwt.PyJWKClient | None = None


def verify(token: str) -> dict:
    """Возвращает claims или бросает jwt.PyJWTError / PermissionError."""
    global _jwks
    if _jwks is None:
        _jwks = jwt.PyJWKClient(f"{ISSUER}/.well-known/jwks", cache_keys=True)
    key = _jwks.get_signing_key_from_jwt(token).key
    claims = jwt.decode(token, key, algorithms=["RS256"], audience=AUDIENCE, issuer=ISSUER)
    repo = os.environ.get("REELS_REPOSITORY", "smash-web/qazaqtech-new")
    if claims.get("repository") != repo or claims.get("ref") != "refs/heads/main":
        raise PermissionError("чужой репозиторий или ветка")
    if not str(claims.get("workflow_ref", "")).startswith(f"{repo}/.github/workflows/reels.yml@"):
        raise PermissionError("чужой workflow")
    return claims
