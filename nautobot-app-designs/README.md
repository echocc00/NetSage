# nautobot-app-designs — 自研 Nautobot App v0.1（Phase 3）

> NetSage 差异化护城河：AI 网络设计方案持久化为 Nautobot 自定义 model，
> 形成"网络 AI 平台 + 自带 SSoT"一体化方案（v2.0 三章 + 卖点 #6）。

## 当前状态（Phase 3 决策 2026-08-23）

**不部署 Nautobot 服务**——App 代码就绪，本地 Postgres `network_designs` 表先行落地。
未来部署 Nautobot 时，此 plugin 可直接安装，model 字段与本地 `app/models/design.py` 对齐。

## 功能

`NetworkDesign` model 持久化 ConfigEngineer 生成的设计方案：
- HLD/LLD（JSON）
- 配置 diff + 回滚配置
- lint 校验结果
- 创建者（AI Agent / 用户）

## 安装（未来 Nautobot 部署时）

```python
# nautobot_config.py
PLUGINS = ["designs"]
PLUGINS_CONFIG = {
    "designs": {
        "default_vendor": "huawei",
    }
}
```

```bash
nautobot-server migrate designs
```

## 目录结构

```
nautobot-app-designs/
  designs/
    __init__.py
    models.py          # NetworkDesign Django model
    api.py             # DRF serializer + viewset
    urls.py            # /api/plugins/designs/
    migrations/
      0001_initial.py
  pyproject.toml
  README.md
```
