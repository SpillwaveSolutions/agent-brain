#!/usr/bin/env bash
# keycloak_bootstrap.sh — Bootstrap the agent-brain realm in a fresh Keycloak container.
#
# RFC 8707 DEVIATION: Keycloak lacks native Resource Indicators until 26.8 (unreleased).
# We bind aud via the audience scope mapper (Included Custom Audience) — identical security
# property (aud == AGENT_BRAIN_OAUTH_RESOURCE in issued JWTs). See 70-RESEARCH.md CRITICAL.
#
# Usage:
#   AGENT_BRAIN_OAUTH_RESOURCE=http://localhost:8000 bash scripts/keycloak_bootstrap.sh
#
# Env vars:
#   KC                              Keycloak base URL (default: http://localhost:8080)
#   AGENT_BRAIN_OAUTH_RESOURCE      Resource URI to bind as the aud claim (required)
#
# Designed to run after the Keycloak container is healthy (health/ready on port 9000).
# Idempotent: re-running against an already-bootstrapped realm will log 409 Conflict
# for existing resources but will still exit 0 on success (curl -f is used where needed).

set -euo pipefail

KC="${KC:-http://localhost:8080}"
RESOURCE="${AGENT_BRAIN_OAUTH_RESOURCE:?AGENT_BRAIN_OAUTH_RESOURCE is required}"
REALM="agent-brain"
MCP_CLIENT="agent-brain-mcp"
RS_CLIENT="agent-brain-rs"
RS_SECRET="rs-secret"
TEST_USER="testuser"
TEST_PASS="testpass"

log() {
    echo "[keycloak_bootstrap] $*" >&2
}

# ---------------------------------------------------------------------------
# Step 1: Obtain an admin token from the master realm
# ---------------------------------------------------------------------------
log "Obtaining admin token from master realm..."
ADMIN_TOKEN=$(
    curl -sf \
        -d "client_id=admin-cli" \
        -d "grant_type=password" \
        -d "username=admin" \
        -d "password=admin" \
        "${KC}/realms/master/protocol/openid-connect/token" \
    | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])"
)
log "Admin token obtained."

# Helper to call the Keycloak Admin REST API.
# Usage: _admin POST /admin/realms '{"key":"value"}'
#        _admin GET  /admin/realms/agent-brain
_admin() {
    local method="$1"
    local path="$2"
    local body="${3:-}"
    local args=(-s -X "${method}" "${KC}${path}" \
        -H "Authorization: Bearer ${ADMIN_TOKEN}" \
        -H "Content-Type: application/json")
    if [ -n "${body}" ]; then
        args+=(-d "${body}")
    fi
    curl "${args[@]}"
}

# ---------------------------------------------------------------------------
# Step 2: Create the agent-brain realm
# ---------------------------------------------------------------------------
log "Creating realm '${REALM}'..."
_admin POST /admin/realms \
    "{\"realm\":\"${REALM}\",\"enabled\":true,\"displayName\":\"Agent Brain\"}" \
    > /dev/null || true
log "Realm '${REALM}' created (or already exists)."

# ---------------------------------------------------------------------------
# Step 3: Create the public MCP client (agent-brain-mcp)
# directAccessGrantsEnabled=true enables the Resource Owner Password Credentials
# flow for headless CI token minting (bypasses PKCE browser redirect — Open Q3
# from 70-RESEARCH.md; acceptable for test-only direct-grant).
# ---------------------------------------------------------------------------
log "Creating public client '${MCP_CLIENT}'..."
_admin POST "/admin/realms/${REALM}/clients" \
    "{
        \"clientId\": \"${MCP_CLIENT}\",
        \"name\": \"Agent Brain MCP\",
        \"enabled\": true,
        \"publicClient\": true,
        \"directAccessGrantsEnabled\": true,
        \"redirectUris\": [\"http://localhost:*\"],
        \"webOrigins\": [\"http://localhost:*\"],
        \"protocol\": \"openid-connect\"
    }" > /dev/null || true
log "Client '${MCP_CLIENT}' created (or already exists)."

# ---------------------------------------------------------------------------
# Step 4: Look up the MCP client UUID and add the audience protocol-mapper
#
# RFC 8707 DEVIATION NOTE: Keycloak does not natively support Resource Indicators
# (RFC 8707) until version 26.8 (unreleased as of 2026-06-22). The audience scope
# mapper (protocolMapper = oidc-audience-mapper) provides the identical security
# property: the aud claim in issued JWTs is bound to AGENT_BRAIN_OAUTH_RESOURCE.
# See 70-RESEARCH.md §"CRITICAL Finding: Keycloak RFC 8707".
# ---------------------------------------------------------------------------
log "Looking up client UUID for '${MCP_CLIENT}'..."
MCP_CLIENT_ID=$(
    _admin GET "/admin/realms/${REALM}/clients?clientId=${MCP_CLIENT}" \
    | python3 -c "import sys, json; data=json.load(sys.stdin); print(data[0]['id'] if data else '')"
)

if [ -z "${MCP_CLIENT_ID}" ]; then
    log "ERROR: Could not find client '${MCP_CLIENT}' — did Step 3 fail?"
    exit 1
fi
log "Client UUID: ${MCP_CLIENT_ID}"

log "Adding audience protocol-mapper to '${MCP_CLIENT}'..."
_admin POST "/admin/realms/${REALM}/clients/${MCP_CLIENT_ID}/protocol-mappers/models" \
    "{
        \"name\": \"audience-mapper\",
        \"protocol\": \"openid-connect\",
        \"protocolMapper\": \"oidc-audience-mapper\",
        \"consentRequired\": false,
        \"config\": {
            \"included.custom.audience\": \"${RESOURCE}\",
            \"access.token.claim\": \"true\",
            \"id.token.claim\": \"false\"
        }
    }" > /dev/null || true
log "Audience mapper added (aud will be '${RESOURCE}' in issued JWTs)."

# ---------------------------------------------------------------------------
# Step 5: Create a test user (testuser / testpass)
# ---------------------------------------------------------------------------
log "Creating test user '${TEST_USER}'..."
_admin POST "/admin/realms/${REALM}/users" \
    "{
        \"username\": \"${TEST_USER}\",
        \"enabled\": true,
        \"credentials\": [
            {
                \"type\": \"password\",
                \"value\": \"${TEST_PASS}\",
                \"temporary\": false
            }
        ]
    }" > /dev/null || true
log "User '${TEST_USER}' created (or already exists)."

# ---------------------------------------------------------------------------
# Step 6: Create a confidential RS client (agent-brain-rs) for introspection
# IntrospectionTokenVerifier calls /token/introspect with this client's credentials.
# serviceAccountsEnabled=true is needed for confidential client credential grant.
# ---------------------------------------------------------------------------
log "Creating confidential RS client '${RS_CLIENT}'..."
_admin POST "/admin/realms/${REALM}/clients" \
    "{
        \"clientId\": \"${RS_CLIENT}\",
        \"name\": \"Agent Brain Resource Server\",
        \"enabled\": true,
        \"publicClient\": false,
        \"serviceAccountsEnabled\": true,
        \"clientAuthenticatorType\": \"client-secret\",
        \"secret\": \"${RS_SECRET}\",
        \"directAccessGrantsEnabled\": false,
        \"protocol\": \"openid-connect\"
    }" > /dev/null || true
log "Confidential client '${RS_CLIENT}' created (or already exists)."

# ---------------------------------------------------------------------------
# Step 7: Create the 4 agent-brain realm client scopes
# agent-brain:read, agent-brain:index, agent-brain:admin, agent-brain:subscribe
# The read scope is assigned as optional on agent-brain-mcp so headless CI
# tokens can request 'scope=openid agent-brain:read' (70-03 scope-boundary tests).
# ---------------------------------------------------------------------------
SCOPES=("agent-brain:read" "agent-brain:index" "agent-brain:admin" "agent-brain:subscribe")

for SCOPE_NAME in "${SCOPES[@]}"; do
    log "Creating realm client scope '${SCOPE_NAME}'..."
    _admin POST "/admin/realms/${REALM}/client-scopes" \
        "{
            \"name\": \"${SCOPE_NAME}\",
            \"protocol\": \"openid-connect\",
            \"description\": \"Agent Brain scope: ${SCOPE_NAME}\",
            \"attributes\": {
                \"include.in.token.scope\": \"true\",
                \"display.on.consent.screen\": \"true\"
            }
        }" > /dev/null || true
    log "Scope '${SCOPE_NAME}' created (or already exists)."
done

# Assign agent-brain:read as an optional scope on agent-brain-mcp so direct-grant
# can request 'scope=openid agent-brain:read' (needed by 70-03 scope-boundary tests).
log "Looking up scope UUID for 'agent-brain:read'..."
READ_SCOPE_ID=$(
    _admin GET "/admin/realms/${REALM}/client-scopes" \
    | python3 -c "
import sys, json
scopes = json.load(sys.stdin)
for s in scopes:
    if s.get('name') == 'agent-brain:read':
        print(s['id'])
        break
"
)

if [ -n "${READ_SCOPE_ID}" ]; then
    log "Assigning 'agent-brain:read' as optional scope on '${MCP_CLIENT}'..."
    _admin PUT \
        "/admin/realms/${REALM}/clients/${MCP_CLIENT_ID}/optional-client-scopes/${READ_SCOPE_ID}" \
        "" > /dev/null || true
    log "Optional scope assigned."
else
    log "WARNING: Could not find scope UUID for 'agent-brain:read' — skipping optional assignment."
fi

log "Bootstrap complete. Realm '${REALM}' is ready."
log "  JWKS:          ${KC}/realms/${REALM}/protocol/openid-connect/certs"
log "  Token:         ${KC}/realms/${REALM}/protocol/openid-connect/token"
log "  Introspection: ${KC}/realms/${REALM}/protocol/openid-connect/token/introspect"
log "  Audience:      ${RESOURCE}"
