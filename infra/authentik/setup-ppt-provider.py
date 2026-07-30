#!/usr/bin/env python3
"""创建 Authentik OIDC Provider + Application + 超管组 给 ppt-library。

幂等:已存在则跳过。成功后输出 client_id / client_secret,填入 ppt-library 的 .env。

用法:
  AUTHENTIK_URL=http://localhost:9000 AUTHENTIK_TOKEN=<api_token> python3 setup-ppt-provider.py

获取 admin API token(在 Authentik server 容器内):
  docker exec authentik-server-1 ak shell -c "
  from authentik.core.models import User, Token
  u = User.objects.filter(username='akadmin').first()
  t, _ = Token.objects.get_or_create(user=u, identifier='api-ppt',
                                     defaults={'expiring': False, 'intent': 'api'})
  print(t.key)
  "

redirect_uri 默认 http://localhost:13000/api/auth/callback。
"""
import os
import sys
import urllib.request
import urllib.error
import json

URL = os.environ.get("AUTHENTIK_URL", "http://localhost:9000").rstrip("/")
TOKEN = os.environ.get("AUTHENTIK_TOKEN", "")
REDIRECT_URI = os.environ.get("OIDC_REDIRECT_URI", "http://localhost:13000/api/auth/callback")
APP_SLUG = "ppt-library"
APP_NAME = "PPT 素材库"
SUPERUSER_GROUP = os.environ.get("OIDC_SUPERUSER_GROUP", "ppt-admins")

if not TOKEN:
    print("ERROR: set AUTHENTIK_TOKEN (admin API token).", file=sys.stderr)
    sys.exit(1)


def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{URL}/api/v3{path}",
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as r:
            txt = r.read().decode()
            return r.status, (json.loads(txt) if txt else {})
    except urllib.error.HTTPError as e:
        txt = e.read().decode()
        try:
            return e.code, json.loads(txt) if txt else {}
        except Exception:
            return e.code, {"raw": txt[:500]}


def get_flow_uuid(slug: str) -> str:
    code, body = api("get", f"/flows/instances/?slug={slug}")
    res = body.get("results", [])
    return res[0]["pk"] if res else ""


def main():
    # 1. 超管组
    code, body = api("get", f"/core/groups/?name={SUPERUSER_GROUP}")
    if not body.get("results"):
        code, body = api("post", "/core/groups/", {"name": SUPERUSER_GROUP})
        print(f"created group: {SUPERUSER_GROUP}")
    else:
        print(f"group exists: {SUPERUSER_GROUP}")

    # 2. flow UUIDs(Authentik API 需要 UUID,非 slug)
    auth_flow = get_flow_uuid("default-provider-authorization-implicit-consent")
    inv_flow = get_flow_uuid("default-invalidation-flow")
    if not auth_flow or not inv_flow:
        print(f"ERROR: flow UUID missing (auth={auth_flow} inv={inv_flow})", file=sys.stderr)
        sys.exit(1)

    # 3. OIDC Provider(幂等)
    # 取默认 OIDC scope mapping 的 pk(openid/profile/email),否则 userinfo 返 403。
    def scope_pk(managed):
        code, body = api("get", f"/propertymappings/provider/scope/?managed={managed}")
        res = body.get("results", [])
        return res[0]["pk"] if res else None

    scope_openid = scope_pk("goauthentik.io/providers/oauth2/scope-openid")
    scope_profile = scope_pk("goauthentik.io/providers/oauth2/scope-profile")
    scope_email = scope_pk("goauthentik.io/providers/oauth2/scope-email")
    mappings = [m for m in (scope_openid, scope_profile, scope_email) if m]

    code, body = api("get", f"/providers/oauth2/?name={APP_SLUG}")
    existing = body.get("results", [])
    if existing:
        prov = existing[0]
        print(f"provider exists: client_id={prov['client_id']}")
        client_id = prov["client_id"]
        client_secret = prov.get("client_secret") or ""
        # 补 scope mappings(若缺)
        if mappings and not prov.get("property_mappings"):
            api("patch", f"/providers/oauth2/{prov['pk']}/", {"property_mappings": mappings})
            print("  added scope mappings to existing provider")
    else:
        prov_body = {
            "name": APP_SLUG,
            "authorization_flow": auth_flow,
            "invalidation_flow": inv_flow,
            "client_type": "confidential",
            "client_id": APP_SLUG,
            "redirect_uris": [{"matching_mode": "strict", "url": REDIRECT_URI}],
            "property_mappings": mappings,
            "sub_mode": "hashed_user_id",
            "issuer_mode": "per_provider",
        }
        code, body = api("post", "/providers/oauth2/", prov_body)
        if code >= 300:
            print(f"ERROR creating provider ({code}): {json.dumps(body, ensure_ascii=False)}", file=sys.stderr)
            sys.exit(1)
        client_id = body["client_id"]
        client_secret = body.get("client_secret", "")
        print(f"created provider: {APP_SLUG}")

    # 4. Application(关联 provider)
    code, body = api("get", f"/core/applications/?slug={APP_SLUG}")
    if not body.get("results"):
        code, body = api("post", "/core/applications/", {
            "name": APP_NAME,
            "slug": APP_SLUG,
            "provider": client_id,
        })
        if code >= 300:
            print(f"WARNING: app link failed ({code}): {json.dumps(body, ensure_ascii=False)}", file=sys.stderr)
        else:
            print(f"created application: {APP_NAME}")
    else:
        print(f"application exists: {APP_NAME}")

    print("\n========================================")
    print("✅ Authentik provider ready. Add to ppt-library .env:")
    print(f"OIDC_ENABLED=true")
    print(f"OIDC_CLIENT_ID={client_id}")
    print(f"OIDC_CLIENT_SECRET={client_secret}")
    print(f"OIDC_SUPERUSER_GROUP={SUPERUSER_GROUP}")
    print(f"OIDC_REDIRECT_URI={REDIRECT_URI}")
    print("========================================")
    print(f"\n注:把超管用户加入组「{SUPERUSER_GROUP}」(Authentik admin > Groups)后即为超管。")


if __name__ == "__main__":
    main()
