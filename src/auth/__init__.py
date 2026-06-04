"""Auth stub démo (Cycle 15.1, D-032) — JWT HS256 + bcrypt.

Exports
-------
- `create_access_token(subject, expires_delta=None)` : crée un JWT signé.
- `decode_token(token)` : décode + valide signature + expiration → dict claims.
- `get_current_user(token)` : FastAPI dependency, lève 401 si invalide.
- `authenticate(username, password)` : vérifie le user stub demo.

Cf. D-032 : 1 seul user `demo` hardcodé, password `demo` (bcrypt). HS256
secret partagé via env `JWT_SECRET`. Stub de démonstration soutenance —
DB users + signup + RS256 = post-soutenance.
"""

from src.auth.jwt_utils import create_access_token, decode_token
from src.auth.security import get_current_user
from src.auth.users import authenticate

__all__ = ["create_access_token", "decode_token", "get_current_user", "authenticate"]
