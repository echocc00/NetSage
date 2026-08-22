"""拓扑 API（Phase 2 P2-3）。

GET /topology?scope=<site> → NetBox 真实拓扑（React Flow 格式），不可达降级 mock。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.access.netbox_adapter import NetBoxAdapter
from app.core.config import get_settings
from app.core.deps import CurrentUser, get_current_user
from app.schemas.common import Envelope

router = APIRouter(tags=["topology"])


class TopologyNodeOut(BaseModel):
    id: str
    name: str
    vendor: str
    role: str
    mgmt_ip: str
    site: str


class TopologyLinkOut(BaseModel):
    id: str
    source: str
    target: str
    source_interface: str = ""
    target_interface: str = ""


class TopologyOut(BaseModel):
    nodes: list[TopologyNodeOut]
    links: list[TopologyLinkOut]
    scope: str
    source: str = "netbox"  # netbox / mock


# Mock 拓扑（NetBox 不可达时降级）
MOCK_TOPOLOGY = TopologyOut(
    nodes=[
        TopologyNodeOut(id="spine01", name="spine01", vendor="huawei", role="spine", mgmt_ip="10.1.1.1", site="shanghai"),
        TopologyNodeOut(id="spine02", name="spine02", vendor="huawei", role="spine", mgmt_ip="10.1.1.2", site="shanghai"),
        TopologyNodeOut(id="leaf01", name="leaf01", vendor="cisco", role="leaf", mgmt_ip="10.1.2.1", site="shanghai"),
        TopologyNodeOut(id="leaf02", name="leaf02", vendor="h3c", role="leaf", mgmt_ip="10.1.2.2", site="beijing"),
        TopologyNodeOut(id="leaf03", name="leaf03", vendor="arista", role="leaf", mgmt_ip="10.1.2.3", site="beijing"),
    ],
    links=[
        TopologyLinkOut(id="e1", source="spine01", target="leaf01"),
        TopologyLinkOut(id="e2", source="spine01", target="leaf02"),
        TopologyLinkOut(id="e3", source="spine02", target="leaf01"),
        TopologyLinkOut(id="e4", source="spine02", target="leaf03"),
    ],
    scope="mock",
    source="mock",
)


@router.get("/topology", response_model=Envelope[TopologyOut])
async def get_topology(
    user: CurrentUser = Depends(get_current_user),
    scope: str = Query("mock", description="site slug，或 'mock' 用静态数据"),
) -> Envelope[TopologyOut]:
    """获取拓扑（React Flow 格式）。

    - scope=mock：静态演示拓扑（不依赖 NetBox）
    - scope=<site>：从 NetBox 拉真实拓扑
    """
    if scope == "mock":
        return Envelope.ok(MOCK_TOPOLOGY)

    settings = get_settings()
    if not settings.netbox_url or not settings.netbox_token:
        return Envelope.ok(MOCK_TOPOLOGY)

    adapter = NetBoxAdapter(base_url=settings.netbox_url, token=settings.netbox_token)
    try:
        topology = await adapter.get_topology(scope)
        raw_nodes = topology.nodes if hasattr(topology, "nodes") else topology.get("nodes", [])
        raw_edges = topology.edges if hasattr(topology, "edges") else topology.get("edges", [])

        nodes = [
            TopologyNodeOut(
                id=n["id"] if isinstance(n, dict) else n.id,
                name=n["name"] if isinstance(n, dict) else n.name,
                vendor=n.get("vendor", "") if isinstance(n, dict) else getattr(n, "vendor", ""),
                role=n.get("role", "") if isinstance(n, dict) else getattr(n, "role", ""),
                mgmt_ip=n.get("mgmt_ip", "") if isinstance(n, dict) else getattr(n, "mgmt_ip", ""),
                site=scope,
            )
            for n in raw_nodes
        ]
        links = [
            TopologyLinkOut(
                id=e["id"] if isinstance(e, dict) else e.id,
                source=e["source"] if isinstance(e, dict) else e.source,
                target=e["target"] if isinstance(e, dict) else e.target,
                source_interface=e.get("src_iface", "") if isinstance(e, dict) else getattr(e, "src_iface", ""),
                target_interface=e.get("dst_iface", "") if isinstance(e, dict) else getattr(e, "dst_iface", ""),
            )
            for e in raw_edges
        ]
        return Envelope.ok(
            TopologyOut(nodes=nodes, links=links, scope=scope, source="netbox")
        )
    except Exception as e:
        # NetBox 不可达时降级 mock（不阻断前端）
        return Envelope.ok(MOCK_TOPOLOGY)
    finally:
        await adapter.client.aclose()