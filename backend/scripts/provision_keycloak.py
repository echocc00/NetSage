"""Keycloak E2E 基础数据幂等 provision（v0.5.0 阶段1 去 🟡 OIDC）。

用 Admin REST 在本地 Keycloak（docker-compose.keycloak.yml）创建：
realm=netsage / groups(netsage-{admin,engineer,operator,auditor,viewer}) /
users(alice/bob/carol/dave) / 机密 client netsage-web(PKCE S256 + 标准流 + 直连授权) /
groups→id_token 的 `groups` claim mapper。

幂等：已存在的实体直接跳过，可反复执行。
用法：python backend/scripts/provision_keycloak.py [--base http://localhost:9090] [--admin-user admin] [--admin-pass admin]
结束后会打印一组 OIDC 环境变量（写入 .env 或注入测试）。

依赖：httpx（backend 依赖已含）。
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import httpx

REALM = "netsage"
CLIENT_ID = "netsage-web"
CLIENT_SECRET = "netsage-web-secret"  # 期望值；Keycloak 22 会忽略并生成随机值，实际值以服务端返回为准
REDIRECT_CALLBACK = "http://localhost:8000/api/v1/auth/oidc/callback"
REDIRECT_CALLBACK_DEV = "http://localhost:5173/api/v1/auth/oidc/callback"

# 本地持久化实际 client secret（Keycloak 无法回读已哈希 secret，只能存本地）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OIDC_ENV_PATH = PROJECT_ROOT / ".env.keycloak"

GROUPS = {
    "netsage-admin": "admin",
    "netsage-engineer": "engineer",
    "netsage-operator": "operator",
    "netsage-auditor": "auditor",
    "netsage-viewer": "viewer",
}
USERS = {
    "alice": ("netsage-engineer", "alice@example.local"),
    "bob": ("netsage-admin", "bob@example.local"),
    "carol": ("netsage-auditor", "carol@example.local"),
    "dave": ("netsage-viewer", "dave@example.local"),
}


class Rest:
    """Keycloak Admin REST 客户端。"""

    def __init__(self, base: str, admin_user: str, admin_pass: str) -> None:
        self.base = base.rstrip("/")
        self.admin_user = admin_user
        self.admin_pass = admin_pass
        self.token = ""

    def wait_ready(self, timeout: int = 60) -> None:
        """轮询 master realm discovery 直到 Keycloak 就绪。"""
        url = f"{self.base}/realms/master/.well-known/openid-configuration"
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                r = httpx.get(url, timeout=3)
                if r.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(2)
        print("✗ Keycloak 未在期限内就绪")
        sys.exit(1)

    def login(self) -> None:
        r = httpx.post(
            f"{self.base}/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": self.admin_user,
                "password": self.admin_pass,
            },
            timeout=15,
        )
        r.raise_for_status()
        self.token = r.json()["access_token"]

    def _h(self, **extra: Any) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.token}"}
        headers.update(extra)
        return headers

    def get(self, path: str) -> httpx.Response:
        return httpx.get(f"{self.base}/admin/realms/{path}", headers=self._h(), timeout=15)

    def post(self, path: str, body: dict) -> httpx.Response:
        return httpx.post(
            f"{self.base}/admin/realms/{path}", headers=self._h(), json=body, timeout=15
        )

    def put(self, path: str, body: dict) -> httpx.Response:
        return httpx.put(
            f"{self.base}/admin/realms/{path}", headers=self._h(), json=body, timeout=15
        )

    def idempotent_create(self, path: str, name: str, body: dict) -> None:
        """存在即跳过，否则创建并等待 201（新 realm 需稍等索引）。"""
        r = self.get(path)
        if r.status_code == 200:
            print(f"  ✓ {name} 已存在")
            return
        if r.status_code != 404:
            r.raise_for_status()
        created = self.post(path, body)
        if created.status_code not in (201, 204):
            print(f"  ✗ 创建 {name} 失败: {created.status_code} {created.text[:200]}")
            sys.exit(1)
        print(f"  ✓ 已创建 {name}")
        time.sleep(0.2)


def ensure_realm(rest: Rest) -> None:
    # realm 可 GET /admin/realms/<realm>；创建须 POST /admin/realms
    r = rest.get(REALM)
    if r.status_code == 200:
        print(f"  ✓ realm {REALM} 已存在")
        return
    created = httpx.post(
        f"{rest.base}/admin/realms",
        headers=rest._h(),
        json={
            "realm": REALM,
            "enabled": True,
            "loginWithEmailAllowed": True,
            "accessTokenLifespan": 300,
            "ssoSessionIdleTimeout": 600,
            "ssoSessionMaxLifespan": 3600,
        },
        timeout=15,
    )
    if created.status_code not in (201, 204):
        print(f"  ✗ 创建 realm 失败: {created.status_code} {created.text[:200]}")
        sys.exit(1)
    print(f"  ✓ 已创建 realm {REALM}")
    # realm 刚建需等角色/索引就绪
    time.sleep(1)


def ensure_groups(rest: Rest) -> dict[str, str]:
    """创建角色组，返回 {group_name: group_id}。"""
    ids: dict[str, str] = {}
    for gname in GROUPS:
        r = rest.get(f"{REALM}/groups?search=" + gname)
        existing = [g for g in r.json() if g.get("name") == gname]
        if existing:
            ids[gname] = existing[0]["id"]
            print(f"  ✓ 组 {gname} 已存在")
            continue
        created = rest.post(f"{REALM}/groups", {"name": gname})
        if created.status_code not in (201, 204):
            print(f"  ✗ 创建组失败 {gname}: {created.text[:150]}")
            sys.exit(1)
        # 回查 id
        found = rest.get(f"{REALM}/groups?search=" + gname).json()
        ids[gname] = next(g["id"] for g in found if g.get("name") == gname)
        print(f"  ✓ 已创建组 {gname}")
    return ids


def ensure_users(rest: Rest, group_ids: dict[str, str]) -> None:
    for username, (group, email) in USERS.items():
        r = rest.get(f"{REALM}/users?username={username}&exact=true")
        if r.json():
            print(f"  ✓ 用户 {username} 已存在")
            continue
        payload = {
            "username": username,
            "email": email,
            "enabled": True,
            "emailVerified": True,
            "credentials": [{"type": "password", "value": username, "temporary": False}],
        }
        created = rest.post(f"{REALM}/users", payload)
        if created.status_code not in (201, 204):
            print(f"  ✗ 创建用户失败 {username}: {created.text[:150]}")
            sys.exit(1)
        uid = rest.get(f"{REALM}/users?username={username}&exact=true").json()[0]["id"]
        joined = rest.put(f"{REALM}/users/{uid}/groups/{group_ids[group]}", {})
        if joined.status_code not in (204, 201):
            print(f"  ✗ 加组失败 {username}→{group}: {joined.text[:150]}")
            sys.exit(1)
        print(f"  ✓ 已创建用户 {username}（组 {group}）")


def _set_client_secret(rest: Rest, client_uuid: str) -> str:
    """旋转 client secret 并持久化，返回 Keycloak 实际存储值（服务端生成）。"""
    rep = rest.post(
        f"{REALM}/clients/{client_uuid}/client-secret",
        {"type": "secret", "value": CLIENT_SECRET},
    )
    if rep.status_code != 200:
        print(f"  ✗ 设置 client secret 失败: {rep.text[:150]}")
        sys.exit(1)
    secret = rep.json().get("value", CLIENT_SECRET)
    _write_env(secret)
    return secret


def _secret_from_env() -> str | None:
    """从本地 .env.keycloak 读取已持久化的实际 secret（避免每次旋转）。"""
    if not OIDC_ENV_PATH.exists():
        return None
    for line in OIDC_ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("OIDC_CLIENT_SECRET="):
            return line.split("=", 1)[1].strip()
    return None


def _write_env(secret: str) -> None:
    discovery = f"http://localhost:9090/realms/{REALM}"
    OIDC_ENV_PATH.write_text(
        "\n".join([
            "# 由 provision_keycloak.py 自动生成（Keycloak 22 secret 为服务端随机值，回读不到）",
            f"OIDC_DISCOVERY_URL={discovery}",
            f"OIDC_CLIENT_ID={CLIENT_ID}",
            f"OIDC_CLIENT_SECRET={secret}",
            "OIDC_REDIRECT_BASE=http://localhost:8000",
        ]) + "\n",
        encoding="utf-8",
    )


def ensure_client(rest: Rest) -> tuple[str, str]:
    """创建机密 client（标准流+直连授权+PKCE），返回 (client_uuid, secret)。"""
    found = rest.get(f"{REALM}/clients?clientId={CLIENT_ID}").json()
    if found:
        cid = found[0]["id"]
        print(f"  ✓ client {CLIENT_ID} 已存在")
        existing = _secret_from_env()
        if existing:
            return cid, existing  # 不旋转，用本地持久化 secret
        secret = _set_client_secret(rest, cid)
        return cid, secret

    payload = {
        "clientId": CLIENT_ID,
        "protocol": "openid-connect",
        "enabled": True,
        "publicClient": False,
        "standardFlowEnabled": True,
        "directAccessGrantsEnabled": True,
        "redirectUris": [REDIRECT_CALLBACK, REDIRECT_CALLBACK_DEV],
        "webOrigins": ["+"],
        "attributes": {
            "pkce.code.challenge.method": "S256",
        },
    }
    created = rest.post(f"{REALM}/clients", payload)
    if created.status_code not in (201, 204):
        print(f"  ✗ 创建 client 失败: {created.text[:150]}")
        sys.exit(1)
    cid = rest.get(f"{REALM}/clients?clientId={CLIENT_ID}").json()[0]["id"]
    secret = _set_client_secret(rest, cid)
    print(f"  ✓ 已创建 client {CLIENT_ID}")
    return cid, secret


def ensure_group_mapper(rest: Rest, client_uuid: str) -> None:
    """groups→claims['groups'] mapper（登录后 id_token 顶层带 groups，_map_user 使用）。"""
    mappers = rest.get(f"{REALM}/clients/{client_uuid}/protocol-mappers/models").json()
    if any(m.get("name") == "netsage-groups" for m in mappers):
        print("  ✓ groups mapper 已存在")
        return
    payload = {
        "name": "netsage-groups",
        "protocol": "openid-connect",
        "protocolMapper": "oidc-group-membership-mapper",
        "config": {
            "claim.name": "groups",
            "access.token.claim": "true",
            "id.token.claim": "true",
            "userinfo.token.claim": "true",
            "multivalued": "true",
        },
    }
    created = rest.post(f"{REALM}/clients/{client_uuid}/protocol-mappers/models", payload)
    if created.status_code not in (201, 204):
        print(f"  ✗ 创建 mapper 失败: {created.text[:150]}")
        sys.exit(1)
    print("  ✓ 已创建 groups mapper（claims['groups']）")


def main() -> None:
    parser = argparse.ArgumentParser(description="Keycloak E2E 幂等 provision")
    parser.add_argument("--base", default="http://localhost:9090", help="Keycloak 根地址")
    parser.add_argument("--admin-user", default="admin")
    parser.add_argument("--admin-pass", default="admin")
    args = parser.parse_args()

    rest = Rest(args.base, args.admin_user, args.admin_pass)
    print(f"等待 Keycloak 就绪: {args.base}")
    rest.wait_ready()
    rest.login()
    print("已登录 Admin API")
    print("· realm")
    ensure_realm(rest)
    print("· groups")
    group_ids = ensure_groups(rest)
    print("· users")
    ensure_users(rest, group_ids)
    print("· client")
    client_uuid, secret = ensure_client(rest)
    print("· mapper")
    ensure_group_mapper(rest, client_uuid)

    print(f"\n=== 已写入 {OIDC_ENV_PATH.relative_to(PROJECT_ROOT)}（本地，不入仓库） ===")
    discovery = f"{args.base}/realms/{REALM}"
    print(f"OIDC_DISCOVERY_URL={discovery}")
    print(f"OIDC_CLIENT_ID={CLIENT_ID}")
    print(f"OIDC_CLIENT_SECRET={secret}")
    print("OIDC_REDIRECT_BASE=http://localhost:8000")


if __name__ == "__main__":
    main()
