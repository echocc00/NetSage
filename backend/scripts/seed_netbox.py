"""NetBox 初始数据导入脚本（Phase 2 P2-2）。

从 Phase 1 仿真设备导入 5-10 台测试设备到 NetBox。
用法：python backend/scripts/seed_netbox.py

前置：NetBox 已启动 + .env 配置 NETBOX_URL/NETBOX_TOKEN
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 添加 backend 到 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from app.core.config import get_settings


# Phase 1 仿真设备 + 典型测试设备
SEED_DEVICES = [
    {
        "name": "spine01",
        "vendor": "huawei",
        "device_type": "CE12800",
        "platform": "vrp",
        "role": "spine",
        "site": "shanghai",
        "mgmt_ip": "10.1.1.1",
        "version": "VRP-8.180",
    },
    {
        "name": "spine02",
        "vendor": "huawei",
        "device_type": "CE12800",
        "platform": "vrp",
        "role": "spine",
        "site": "shanghai",
        "mgmt_ip": "10.1.1.2",
        "version": "VRP-8.180",
    },
    {
        "name": "leaf01",
        "vendor": "cisco",
        "device_type": "Catalyst 9500",
        "platform": "iosxe",
        "role": "leaf",
        "site": "shanghai",
        "mgmt_ip": "10.1.2.1",
        "version": "IOS-XE-17.12",
    },
    {
        "name": "leaf02",
        "vendor": "h3c",
        "device_type": "S6520",
        "platform": "comware",
        "role": "leaf",
        "site": "beijing",
        "mgmt_ip": "10.1.2.2",
        "version": "Comware-7",
    },
    {
        "name": "leaf03",
        "vendor": "arista",
        "device_type": "7050X3",
        "platform": "eos",
        "role": "leaf",
        "site": "beijing",
        "mgmt_ip": "10.1.2.3",
        "version": "EOS-4.28",
    },
]


async def seed():
    settings = get_settings()
    if not settings.netbox_url or not settings.netbox_token:
        print("❌ NETBOX_URL/NETBOX_TOKEN 未配置，请在 backend/.env 填入")
        sys.exit(1)

    async with httpx.AsyncClient(
        base_url=settings.netbox_url.rstrip("/"),
        headers={"Authorization": f"Token {settings.netbox_token}"},
        timeout=30.0,
    ) as client:
        # v2 token 需 Bearer header
        client.headers["Authorization"] = f"Bearer {settings.netbox_token}"

        # 检查 NetBox 可达
        try:
            r = await client.get("/api/dcim/devices/", params={"limit": 1})
            r.raise_for_status()
            print(f"✓ NetBox 可达: {settings.netbox_url}")
        except Exception as e:
            print(f"❌ NetBox 不可达: {e}")
            sys.exit(1)

        # 建 custom field: os_version
        cf_r = await client.get("/api/extras/custom-fields/", params={"name": "os_version"})
        if not cf_r.json().get("results"):
            await client.post("/api/extras/custom-fields/", json={
                "object_type": "dcim.device",
                "type": "text",
                "name": "os_version",
                "label": "OS Version",
                "description": "设备 OS 版本（NetSage 导入）",
            })
            print("  ✓ 创建 custom field: os_version")
        else:
            print("  custom field os_version 已存在")

        # 导入设备
        for dev in SEED_DEVICES:
            # 查/建 manufacturer
            manu_r = await client.get("/api/dcim/manufacturers/", params={"name": dev["vendor"].title()})
            manu_id = manu_r.json()["results"][0]["id"] if manu_r.json()["results"] else None
            if not manu_id:
                m = await client.post("/api/dcim/manufacturers/", json={"name": dev["vendor"].title(), "slug": dev["vendor"]})
                manu_id = m.json()["id"]

            # 查/建 device_type
            dt_r = await client.get("/api/dcim/device-types/", params={"model": dev["device_type"]})
            dt_id = dt_r.json()["results"][0]["id"] if dt_r.json()["results"] else None
            if not dt_id:
                dt = await client.post("/api/dcim/device-types/", json={
                    "manufacturer": manu_id,
                    "model": dev["device_type"],
                    "slug": dev["device_type"].lower().replace(" ", "-"),
                })
                dt_id = dt.json()["id"]

            # 查/建 platform
            pf_r = await client.get("/api/dcim/platforms/", params={"name": dev["platform"]})
            pf_id = pf_r.json()["results"][0]["id"] if pf_r.json()["results"] else None
            if not pf_id:
                pf = await client.post("/api/dcim/platforms/", json={
                    "name": dev["platform"],
                    "slug": dev["platform"],
                    "manufacturer": manu_id,
                })
                pf_id = pf.json()["id"]

            # 查/建 site
            site_r = await client.get("/api/dcim/sites/", params={"name": dev["site"]})
            site_id = site_r.json()["results"][0]["id"] if site_r.json()["results"] else None
            if not site_id:
                s = await client.post("/api/dcim/sites/", json={
                    "name": dev["site"],
                    "slug": dev["site"],
                    "status": "active",
                })
                site_id = s.json()["id"]

            # 查/建 role
            role_r = await client.get("/api/dcim/device-roles/", params={"name": dev["role"]})
            role_id = role_r.json()["results"][0]["id"] if role_r.json()["results"] else None
            if not role_id:
                rl = await client.post("/api/dcim/device-roles/", json={
                    "name": dev["role"],
                    "slug": dev["role"],
                    "color": "1e88e5",
                })
                role_id = rl.json()["id"]

            # 查/建设备
            dev_r = await client.get("/api/dcim/devices/", params={"name": dev["name"]})
            if dev_r.json()["results"]:
                print(f"  设备 {dev['name']} 已存在，跳过")
                continue

            payload = {
                "name": dev["name"],
                "device_type": dt_id,
                "platform": pf_id,
                "site": site_id,
                "role": role_id,
                "status": "active",
                "description": f"{dev['vendor']} {dev['device_type']} {dev['version']}",
            }
            r = await client.post("/api/dcim/devices/", json=payload)
            if r.status_code in (200, 201):
                print(f"  ✓ 导入设备 {dev['name']} ({dev['vendor']} {dev['device_type']})")
            else:
                print(f"  ✗ 设备 {dev['name']} 导入失败: {r.status_code} {r.text[:100]}")

        print(f"\n✓ 导入完成：{len(SEED_DEVICES)} 台设备")


if __name__ == "__main__":
    asyncio.run(seed())