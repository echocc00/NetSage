"""NAPALM MCP Server（v2.0 开发计划九章 9.2）。

工具：get_facts / get_config / load_merge_candidate / compare_config / commit / discard
多厂商统一抽象（厂商翻译器，v2.0 三章）。
"""
from __future__ import annotations

import os
from typing import Any

from fastmcp import FastMCP
from napalm import get_network_driver
from netsage_mcp_shared import MCPError, log

mcp = FastMCP("napalm-mcp")

# Phase 1 支持的厂商 driver 映射
# （v0.5.1 实测修正：napalm 的 Cisco IOS/IOS-XE driver 名是 "ios"——
#   原映射 "iosxe" 不是有效 driver，get_facts 即报 Cannot import）
# （v0.6 新增：Nokia SR Linux（napalm-srl，gNMI 传输）——containerlab
#   kind: nokia_srlinux 网元，真实网元下发闭环的验证对象）
DRIVER_MAP: dict[str, str] = {
    "cisco_iosxe": "ios",
    "cisco_ios": "ios",
    "cisco_nxos": "nxos_ssh",
    "huawei_vrp": "huawei",
    "h3c_comware": "h3c",
    "juniper_junos": "junos",
    "arista_eos": "eos",
    "nokia_srl": "srl",
    "nokia_srlinux": "srl",
    "srl": "srl",
}

# napalm 标准端口参数名是 "port"，SR Linux（gNMI）是 "gnmi_port"
_GNMI_DRIVERS = {"srl"}
# SR Linux JSON-RPC 端口（napalm-srl open() 需要；sidecar 端口发布后经此对齐）
_JSONRPC_PORT = int(os.getenv("NAPALM_JSONRPC_PORT", "80"))


def _patch_srl_tmpfile_rw() -> None:
    """napalm-srl 上游 bug 补丁（v0.6 实测）：TemporaryFile(mode='w') 上
    json.load（compare_config/commit_config 读回候选）→ "not readable"。
    换 SpooledTemporaryFile('w+')（可读写）恢复全流程。"""
    try:
        import napalm_srl.srl as _srl_mod
    except ImportError:
        return
    if getattr(_srl_mod, "_nsm_tmpfile_patched", False):
        return
    orig_tempfile = _srl_mod.tempfile

    class _T:
        # 命名对齐 napalm-srl 内部的 tempfile.TemporaryFile 调用点（noqa: N801/N802）
        @staticmethod
        def TemporaryFile(*args: Any, **kwargs: Any) -> Any:  # noqa: N802
            kwargs["mode"] = "w+"
            kwargs.setdefault("encoding", "utf-8")
            return orig_tempfile.SpooledTemporaryFile(*args, **kwargs)

    _srl_mod.tempfile = _T()
    _srl_mod._nsm_tmpfile_patched = True
    log.info("napalm_srl_tmpfile_rw_patched")


_patch_srl_tmpfile_rw()


def _patch_srl_cli_over_ssh(device: Any) -> None:
    """SR Linux：把 napalm-srl 的 JSON-RPC CLI 调用桥接到 SSH（v0.6 实测）。

    napalm-srl 的 checkpoint/rollback/discard/元数据走 _jsonrpcRunCli，
    但 standalone SR Linux 的 JSON-RPC server 不监听（gNMI 正常）。
    SR Linux 的 SSH（mgmt netns :22）能执行同一批 CLI——经 netmiko 桥接。
    环境变量 NAPALM_SRL_SSH_PORT 非零时启用（sidecar 按端口发布对齐）。
    """
    ssh_port = int(os.getenv("NAPALM_SRL_SSH_PORT", "0"))
    if not ssh_port:
        return
    try:
        from netmiko import ConnectHandler
    except ImportError:
        log.warning("srl_ssh_bridge_no_netmiko")
        return

    api = device.device  # napalm-srl NokiaSRLDriver → SRLAPI

    def _run_cli_over_ssh(cmds: list) -> dict:
        # 逐条发送：SR Linux CLI 把多行字符串当单条命令（v0.6 实测，
        # rollback 的 enter/load/commit 序列必须逐条）
        conn = ConnectHandler(
            device_type="linux", host=api.hostname, port=ssh_port,
            username=api.username, password=api.password, timeout=20,
        )
        outputs: list[str] = []
        try:
            for c in cmds:
                outputs.append(conn.send_command_timing(str(c), read_timeout=40))
        finally:
            conn.disconnect()
        return {"result": "\n".join(outputs)}

    api._jsonrpcRunCli = _run_cli_over_ssh
    log.info("srl_cli_over_ssh_bridge_enabled", ssh_port=ssh_port)


def _connect(vendor: str, host: str, username: str, password: str, port: int = 22) -> Any:
    """建立 NAPALM 连接。凭证由调用方注入（生产态走 Vault）。"""
    driver_name = DRIVER_MAP.get(vendor)
    if not driver_name:
        raise MCPError("unsupported_vendor", f"不支持的厂商: {vendor}", list(DRIVER_MAP))
    # gNMI 驱动（SR Linux）：端口参数名不同 + lab 自签证书需 insecure
    # （napalm-srl：insecure=True 用服务端证书做根 CA；skip_verify 仅作用于
    #   JSON-RPC 路径。注意：gRPC 会继承 http_proxy 环境变量，sidecar 部署
    #   需设 NO_PROXY 覆盖网段，否则连到代理上——v0.6 实测）
    if driver_name in _GNMI_DRIVERS:
        optional_args: dict[str, Any] = {
            "gnmi_port": port, "jsonrpc_port": _JSONRPC_PORT,
            "skip_verify": True, "insecure": True,
        }
    else:
        optional_args = {"port": port}
    try:
        driver = get_network_driver(driver_name)
        device = driver(hostname=host, username=username, password=password, optional_args=optional_args)
        device.open()
        if driver_name in _GNMI_DRIVERS:
            _patch_srl_cli_over_ssh(device)
        return device
    except Exception as e:
        raise MCPError("connect_failed", f"连接设备 {host} 失败: {e}") from e


@mcp.tool()
async def get_facts(vendor: str, host: str, username: str, password: str, port: int = 22) -> dict:
    """获取设备 facts（厂商/型号/版本/接口）。"""
    device = _connect(vendor, host, username, password, port)
    try:
        facts = device.get_facts()
        log.info("napalm_get_facts", host=host, vendor=facts.get("vendor"))
        return {
            "host": host,
            "vendor": facts.get("vendor"),
            "model": facts.get("model"),
            "os_version": facts.get("os_version"),
            "hostname": facts.get("hostname"),
            "serial_number": facts.get("serial_number"),
            "interface_list": facts.get("interface_list", []),
        }
    finally:
        device.close()


@mcp.tool()
async def get_config(vendor: str, host: str, username: str, password: str, source: str = "running", port: int = 22) -> dict:
    """获取设备配置（running/startup/candidate）。"""
    device = _connect(vendor, host, username, password, port)
    try:
        config = device.get_config(retrieve=source)
        log.info("napalm_get_config", host=host, source=source)
        return {"host": host, "source": source, "config": config.get(source, "")}
    finally:
        device.close()


@mcp.tool()
async def load_merge_candidate(
    vendor: str, host: str, username: str, password: str, config: str, port: int = 22
) -> dict:
    """加载合并候选配置（不提交，供 compare_config 用）。"""
    device = _connect(vendor, host, username, password, port)
    try:
        device.load_merge_candidate(config=config)
        log.info("napalm_load_candidate", host=host)
        return {"host": host, "status": "candidate_loaded"}
    finally:
        device.close()


@mcp.tool()
async def compare_config(vendor: str, host: str, username: str, password: str, port: int = 22) -> dict:
    """对比 candidate 与 running，返回 diff。"""
    device = _connect(vendor, host, username, password, port)
    try:
        diff = device.compare_config()
        log.info("napalm_compare", host=host, diff_len=len(diff))
        return {"host": host, "diff": diff}
    finally:
        device.close()


@mcp.tool()
async def commit(vendor: str, host: str, username: str, password: str, port: int = 22) -> dict:
    """提交候选配置（写操作，必须经三道闸 + 审批，v2.0 十章）。"""
    device = _connect(vendor, host, username, password, port)
    try:
        device.commit_config()
        log.info("napalm_commit", host=host)
        return {"host": host, "status": "committed"}
    except Exception as e:
        raise MCPError("commit_failed", f"commit 失败: {e}") from e
    finally:
        device.close()


@mcp.tool()
async def discard(vendor: str, host: str, username: str, password: str, port: int = 22) -> dict:
    """丢弃候选配置。"""
    device = _connect(vendor, host, username, password, port)
    try:
        device.discard_config()
        log.info("napalm_discard", host=host)
        return {"host": host, "status": "discarded"}
    finally:
        device.close()


@mcp.tool()
async def apply_candidate(
    vendor: str, host: str, username: str, password: str, config: str, port: int = 22
) -> dict:
    """原子下发：单连接内 load_merge_candidate + commit_config（写操作）。

    审查 H2 修复：本 server 每次工具调用新建连接，客户端分两次调
    load_merge_candidate / commit 时 candidate 会话必丢（commit 空提交）。
    下发/回滚必须走此复合工具。必须经三道闸 + 审批（v2.0 十章）。

    gNMI 驱动（SR Linux）：下发前经 SSH 桥创建确定性 pre-change checkpoint
    「NSV-PRE」（驱动自建 checkpoint 计数是连接级状态，跨连接回滚找不到——
    v0.6 实测），rollback 工具按此名回退。
    """
    device = _connect(vendor, host, username, password, port)
    try:
        checkpoint_name = ""
        if getattr(device, "device", None) is not None and hasattr(device.device, "_jsonrpcRunCli"):
            try:
                device.device._jsonrpcRunCli(
                    ["/ tools system configuration generate-checkpoint name NSV-PRE"]
                )
                checkpoint_name = "NSV-PRE"
            except Exception as e:
                log.warning("srl_prechange_checkpoint_failed", error=str(e)[:100])

        device.load_merge_candidate(config=config)
        try:
            diff = device.compare_config()
        except Exception as e:
            # napalm-srl 上游 bug：compare_config 对候选临时文件 json.load
            # （not readable）——diff 是锦上添花，失败不阻断下发
            log.warning("compare_config_skipped", vendor=vendor, error=str(e)[:100])
            diff = ""
        # commit_config 内部再次 json.load 候选文件——比较器读后指针在 EOF，
        # 重置到头部（napalm-srl 未处理；tmp_cfgfile 在 driver 实例上）
        for _holder in (device, getattr(device, "device", None)):
            try:
                _holder.tmp_cfgfile.seek(0)  # type: ignore[union-attr]
                break
            except Exception:
                continue
        device.commit_config()
        log.info("napalm_apply_candidate", host=host, diff_len=len(str(diff)))
        return {
            "host": host, "status": "committed",
            "diff": str(diff), "checkpoint": checkpoint_name,
        }
    except Exception as e:
        raise MCPError("apply_failed", f"apply_candidate 失败: {e}") from e
    finally:
        device.close()


@mcp.tool()
async def rollback(
    vendor: str, host: str, username: str, password: str,
    port: int = 22, checkpoint: str = "",
) -> dict:
    """回滚到 commit 前配置（写操作，必须经三道闸审批）。

    优先级：checkpoint 参数（确定性命名，如 apply_candidate 返回的 NSV-PRE）
    → 经 SSH 桥 enter candidate private / load checkpoint / commit now；
    无参数时用 driver 内建 rollback（checkpoint 机制，同连接内有效）。
    """
    device = _connect(vendor, host, username, password, port)
    try:
        if checkpoint and getattr(device, "device", None) is not None and hasattr(device.device, "_jsonrpcRunCli"):
            out = device.device._jsonrpcRunCli([
                "enter candidate private",
                f"load checkpoint name {checkpoint}",
                "commit now",
            ])
            log.info("napalm_rollback_named", host=host, checkpoint=checkpoint)
            return {"host": host, "status": "rolled_back", "checkpoint": checkpoint,
                    "detail": str(out)[:200]}
        device.rollback()
        log.info("napalm_rollback", host=host)
        return {"host": host, "status": "rolled_back"}
    except Exception as e:
        raise MCPError("rollback_failed", f"rollback 失败: {e}") from e
    finally:
        device.close()


if __name__ == "__main__":
    mcp.run(transport="stdio")
