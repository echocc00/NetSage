import React, { useState } from 'react'
import { Badge, Button, Card, Descriptions, Space, Table, Tag, Typography } from 'antd'
import { api } from '../../services/api'

const { Title } = Typography

interface Change {
  id: number
  title: string
  status: string
  impact: { risk_level?: string; affected_devices?: string[]; suggested_window?: string } | null
}

const STATUS_COLOR: Record<string, 'default' | 'success' | 'processing' | 'error' | 'warning'> = {
  draft: 'default',
  approval: 'processing',
  approved: 'success',
  rejected: 'error',
  deployed: 'success',
  rolled_back: 'warning',
}

const ChangesPage: React.FC = () => {
  const [changes, setChanges] = useState<Change[]>([])
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      await api.get('/changes')
      setChanges([])
    } finally {
      setLoading(false)
    }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '标题', dataIndex: 'title' },
    {
      title: '风险等级',
      dataIndex: ['impact', 'risk_level'],
      render: (v: string) => {
        const color = v === 'critical' ? 'red' : v === 'high' ? 'orange' : v === 'medium' ? 'gold' : 'green'
        return v ? <Tag color={color}>{v}</Tag> : '—'
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      render: (v: string) => <Badge status={STATUS_COLOR[v] ?? 'default'} text={v} />,
    },
    {
      title: '变更窗口',
      dataIndex: ['impact', 'suggested_window'],
      render: (v: string) => v ?? '—',
    },
  ]

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Title level={4}>变更审批（三道闸工作台）</Title>
      <Card
        title="变更单"
        extra={<Button type="primary" onClick={load} loading={loading}>刷新</Button>}
      >
        <Table<Change> rowKey="id" columns={columns} dataSource={changes} pagination={false} />
        <Descriptions size="small" style={{ marginTop: 12 }}>
          <Descriptions.Item label="审批流">
            仿真（①）→ Batfish 校验（②）→ 人工审批（③）→ 快照回滚（v2.0 十章）
          </Descriptions.Item>
        </Descriptions>
      </Card>
    </Space>
  )
}

export default ChangesPage