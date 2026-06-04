"""User store stub démo (Cycle 15.1, D-032).

UN SEUL utilisateur hardcodé `demo / demo` (password bcrypt cost=12 pinned).
Justifié par `context.md` out-of-scope : "Pas d'authentification utilisateurs
réelle (JWT stub pour démo)". DB users + signup + reset = post-soutenance.

Le hash est pinned (généré une fois) pour que les tests pytest restent rapides
(sinon ~250 ms par run de cost=12) et reproductibles.
"""

from __future__ import annotations

import bcrypt

# bcrypt direct (pas passlib : incompatible bcrypt>=5.0, cf. pyproject [api]).
# Hash de "demo" généré avec `bcrypt.hashpw(b"demo", bcrypt.gensalt(rounds=12))`.
# Le salt est aléatoire mais une fois généré il vérifie déterministiquement.
_DEMO_PASSWORD_HASH = b"$2b$12$TmLYMih1OCvRhg3O580OVO8ojY3k9737MO7y5Wzu5/hIvQr8VVNmC"

# {username: bcrypt_hash}. Un seul user stub. Étendre vers une DB en post-soutenance.
_USERS: dict[str, bytes] = {
    "demo": _DEMO_PASSWORD_HASH,
}


def authenticate(username: str, password: str) -> bool:
    """Vérifie (username, password). True si valide, False sinon.

    Note : on évite de distinguer "user inconnu" vs "password faux" dans le
    code appelant pour ne pas révéler l'existence d'un compte (timing attack
    aussi : bcrypt.checkpw fait un compare constant-time).
    """
    stored_hash = _USERS.get(username)
    if stored_hash is None:
        # Compute un hash bidon pour éviter d'exposer le timing "user non trouvé"
        # vs "password faux". Cost identique → temps comparable.
        bcrypt.checkpw(password.encode(), _DEMO_PASSWORD_HASH)
        return False
    return bcrypt.checkpw(password.encode(), stored_hash)


__all__ = ["authenticate"]
