# Authentication Flow

The fictional auth flow lives in `src/auth.py` and delegates verification
to `QueryService.verify_token`. Clients call `authenticate(token)` which:

1. Validates the token format.
2. Calls `QueryService.verify_token(token)` to look up the session.
3. Returns the resolved user or raises `AuthError`.

## Error handling

- Malformed token → `MalformedTokenError`.
- Expired token → `ExpiredTokenError`.
- Unknown token → `UnknownTokenError`.

All inherit from `AuthError`.
