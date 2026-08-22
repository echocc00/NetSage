import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Descriptions, Drawer, List, Segmented, Space, Spin, Tag, Typography } from 'antd'
import { HistoryOutlined } from '@ant-design/icons'
import { ReactFlow, Background, Controls, MiniMap, type Node, type Edge, type NodeMouseHandler } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { api, unwrap } from '../../services/api'

const { Title, Text } = Typography

interface TopologyNode {
  id: string
  name: string
  vendor: string
  role: string
  mgmt_ip: string
  site: string
}
interface TopologyLink {
  id: string
  source: string
  target: string
  source_interface?: string
  target_interface?: string
}
interface TopologyData {
  nodes: TopologyNode[]
  links: TopologyLink[]
  scope: string
  source: string
}
interface DeviceState {
  device: {
    id: number
    name: string
    vendor: string
    os: string
    model: string
    version: string
    mgmt_ip: string
    role: string
    site: string
    status: string
  }
  realtime: { source: string; note: string }
  health: string
}
interface NetworkDesignItem {
  id: number
  name: string
  site: string
  scenario: string
  vendor: string
  config_diff: string
  rollback_config: string
  lint_passed: boolean
  created_by: string
}

const ROLE_COLOR: Record<string, string> = {
  spine: '#1677ff',
  leaf: '#52c41a',
  pe: '#faad14',
  ce: '#13c2c2',
}
const HEALTH_BORDER: Record<string, string> = {
  healthy: '#52c41a',
  warning: '#faad14',
  critical: '#ff4d4f',
  unknown: '#d9d9d9',
}

function layoutNodes(nodes: TopologyNode[], healthMap: Record<string, string>): Node[] {
  const spines = nodes.filter((n) => n.role === 'spine')
  const others = nodes.filter((n) => n.role !== 'spine')
  const layout = (arr: TopologyNode[], y: number, startX: number, gap: number): Node[] =>
    arr.map((n, i) => ({
      id: n.id,
      position: { x: startX + i * gap, y },
      data: { label: `${n.name}\n${n.vendor}` },
      style: {
        background: ROLE_COLOR[n.role] ?? '#8c8c8c',
        color: '#fff',
        fontSize: 11,
        border: `2px solid ${HEALTH_BORDER[healthMap[n.id] ?? 'unknown']}`,
      },
    }))
  return [...layout(spines, 60, 300, 200), ...layout(others, 280, 100, 180)]
}

const DesignPage: React.FC = () => {
  const [topo, setTopo] = useState<TopologyData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [scope, setScope] = useState<string>('mock')
  const [drawerDevice, setDrawerDevice] = useState<TopologyNode | null>(null)
  const [deviceState, setDeviceState] = useState<DeviceState | null>(null)
  const [drawerLoading, setDrawerLoading] = useState(false)
  const [healthMap, setHealthMap] = useState<Record<string, string>>({})
  const [designsOpen, setDesignsOpen] = useState(false)
  const [designs, setDesigns] = useState<NetworkDesignItem[]>([])
  const [designsLoading, setDesignsLoading] = useState(false)

  const loadDesigns = async () => {
    setDesignsLoading(true)
    try {
      const resp = await api.get('/designs')
      const data = await unwrap<{ items: NetworkDesignItem[] } | NetworkDesignItem[]>(resp)
      setDesigns(Array.isArray(data) ? data : data.items)
    } catch {
      setDesigns([])
    } finally {
      setDesignsLoading(false)
    }
  }

  const load = async (s: string) => {
    setLoading(true)
    setError(null)
    try {
      const resp = await api.get('/topology', { params: { scope: s } })
      const data = await unwrap<TopologyData>(resp)
      setTopo(data)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load(scope)
  }, [scope])

  const onNodeClick: NodeMouseHandler = useCallback(async (_, node) => {
    if (!topo) return
    const dev = topo.nodes.find((n) => n.id === node.id)
    if (!dev) return
    setDrawerDevice(dev)
    setDrawerLoading(true)
    setDeviceState(null)
    try {
      const resp = await api.get(`/devices/${dev.id}/state`)
      const state = await unwrap<DeviceState>(resp)
      setDeviceState(state)
      // 更新健康状态高亮
      setHealthMap((prev) => ({ ...prev, [dev.id]: state.health }))
    } catch {
      setDeviceState(null)
    } finally {
      setDrawerLoading(false)
    }
  }, [topo])

  const nodes = useMemo(() => (topo ? layoutNodes(topo.nodes, healthMap) : []), [topo, healthMap])
  const edges = useMemo<Edge[]>(
    () => (topo ? topo.links.map((l) => ({ id: l.id, source: l.source, target: l.target })) : []),
    [topo],
  )

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Title level={4}>设计工坊</Title>
      <Card size="small">
        <Space>
          <Text>拓扑来源：</Text>
          <Segmented
            options={[
              { label: 'Mock 演示', value: 'mock' },
              { label: '上海站点', value: 'shanghai' },
              { label: '北京站点', value: 'beijing' },
            ]}
            value={scope}
            onChange={(v) => setScope(v as string)}
          />
          {topo && (
            <Text type="secondary">
              {topo.source === 'netbox' ? '✓ NetBox 真实数据' : '⚠ Mock（NetBox 未配置）'}
            </Text>
          )}
          <Button
            icon={<HistoryOutlined />}
            onClick={() => {
              setDesignsOpen(true)
              loadDesigns()
            }}
          >
            历史方案
          </Button>
        </Space>
      </Card>
      <Card title="拓扑画布（点击节点查看详情）" style={{ height: '70vh' }}>
        {loading ? (
          <Spin tip="加载拓扑..." />
        ) : error ? (
          <Alert type="error" message={error} />
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            fitView
            onNodeClick={onNodeClick}
            nodesDraggable
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
        )}
      </Card>
      <Drawer
        title={drawerDevice ? `设备详情：${drawerDevice.name}` : '设备详情'}
        open={!!drawerDevice}
        onClose={() => setDrawerDevice(null)}
        width={480}
      >
        {drawerLoading ? (
          <Spin tip="加载设备状态..." />
        ) : deviceState ? (
          <>
            <Descriptions title="基本信息" column={1} bordered size="small">
              <Descriptions.Item label="名称">{deviceState.device.name}</Descriptions.Item>
              <Descriptions.Item label="厂商">{deviceState.device.vendor}</Descriptions.Item>
              <Descriptions.Item label="型号">{deviceState.device.model}</Descriptions.Item>
              <Descriptions.Item label="OS">{deviceState.device.os} {deviceState.device.version}</Descriptions.Item>
              <Descriptions.Item label="管理 IP">{deviceState.device.mgmt_ip || '—'}</Descriptions.Item>
              <Descriptions.Item label="角色">{deviceState.device.role}</Descriptions.Item>
              <Descriptions.Item label="站点">{deviceState.device.site}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={deviceState.device.status === 'active' ? 'green' : 'orange'}>
                  {deviceState.device.status}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="健康">
                <Tag color={HEALTH_BORDER[deviceState.health] === '#52c41a' ? 'green' : HEALTH_BORDER[deviceState.health] === '#ff4d4f' ? 'red' : 'default'}>
                  {deviceState.health}
                </Tag>
              </Descriptions.Item>
            </Descriptions>
            <Descriptions title="实时状态" column={1} size="small" style={{ marginTop: 16 }}>
              <Descriptions.Item label="数据源">{deviceState.realtime.source}</Descriptions.Item>
              <Descriptions.Item label="备注">{deviceState.realtime.note}</Descriptions.Item>
            </Descriptions>
          </>
        ) : (
          <Text type="secondary">设备状态不可达（Mock 模式无真实设备 ID）</Text>
        )}
      </Drawer>
      <Drawer
        title="历史设计方案"
        open={designsOpen}
        onClose={() => setDesignsOpen(false)}
        width={560}
      >
        {designsLoading ? (
          <Spin tip="加载方案..." />
        ) : designs.length === 0 ? (
          <Text type="secondary">暂无方案。ConfigEngineer 生成方案后将自动保存。</Text>
        ) : (
          <List
            dataSource={designs}
            renderItem={(d) => (
              <List.Item>
                <Descriptions column={1} size="small" style={{ width: '100%' }}>
                  <Descriptions.Item label="名称">{d.name}</Descriptions.Item>
                  <Descriptions.Item label="场景/厂商">
                    {d.scenario} / {d.vendor}
                  </Descriptions.Item>
                  <Descriptions.Item label="站点">{d.site || '—'}</Descriptions.Item>
                  <Descriptions.Item label="lint">
                    <Tag color={d.lint_passed ? 'green' : 'red'}>
                      {d.lint_passed ? '通过' : '未通过'}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="创建者">{d.created_by}</Descriptions.Item>
                </Descriptions>
              </List.Item>
            )}
          />
        )}
      </Drawer>
    </Space>
  )
}

export default DesignPage