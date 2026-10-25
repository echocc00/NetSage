import React, { useEffect, useState } from 'react'
import { Alert, Badge, Button, Card, Descriptions, Popconfirm, Space, Table, Tag, Typography, message } from 'antd'
import type { TableColumnsType } from 'antd'
import { api, errorMessage, unwrap } from '../../services/api'

const { Title, Text } = Typography

// GET /changes 信封 data（v2.0 变更工单列表）
interface ChangeListData {
  count: number
  storage: string
  items: ChangeItem[]
}

interface ChangeItem {
  id: number
  title: string
  status: string
  impact_confirmed: boolean | null
}

// POST /changes/{id}/approve 信封 data
interface ApproveResult {
  change_id: number
  status: string
  approver: string
}

const STATUS_COLOR: Record<string, 'default' | 'success' | 'processing' | 'error' | 'warning'> = {
  draft: 'default',
  approval: 'processing',
  approved: 'success',
  rejected: 'error',
  deployed: 'success',
  rolled_back: 'warning',
}

const STATUS_TEXT: Record<string, string> = {
  draft: '草稿',
  approval: '审批中',
  approved: '已批准',
  rejected: '已驳回',
  deployed: '已部署',
  rolled_back: '已回滚',
}

const ChangesPage: React.FC = () => {
  const [data, setData] = useState<ChangeListData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [approvingId, setApprovingId] = useState<number | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const resp = await api.get('/changes')
      const d = await unwrap<ChangeListData>(resp)
      setData(d)
      setError(null)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  // POST /changes/{id}/approve?decision=...（仅 approval 状态可审批，需 admin 角色，否则 409/403）
  const approve = async (id: number, decision: 'approved' | 'rejected') => {
    setApprovingId(id)
    try {
      const resp = await api.post(`/changes/${id}/approve`, null, { params: { decision } })
      const d = await unwrap<ApproveResult>(resp)
      message.success(`变更 #${d.change_id} 已${decision === 'approved' ? '批准' : '驳回'}（状态：${STATUS_TEXT[d.status] ?? d.status}）`)
      await load()
    } catch (e) {
      message.error(errorMessage(e))
    } finally {
      setApprovingId(null)
    }
  }

  const columns: TableColumnsType<ChangeItem> = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    { title: '标题', dataIndex: 'title' },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (v: string) => <Badge status={STATUS_COLOR[v] ?? 'default'} text={STATUS_TEXT[v] ?? v} />,
    },
    {
      title: '影响已确认',
      dataIndex: 'impact_confirmed',
      width: 110,
      render: (v: boolean | null) =>
        v === true ? <Tag color="green">已确认</Tag> : v === false ? <Tag>未确认</Tag> : '—',
    },
    {
      title: '操作',
      key: 'action',
      width: 170,
      render: (_, r) =>
        r.status === 'approval' ? (
          <Space>
            <Popconfirm title="确认批准该变更？" onConfirm={() => approve(r.id, 'approved')}>
              <Button size="small" type="primary" loading={approvingId === r.id}>
                批准
              </Button>
            </Popconfirm>
            <Popconfirm title="确认驳回该变更？" onConfirm={() => approve(r.id, 'rejected')}>
              <Button size="small" danger disabled={approvingId === r.id}>
                驳回
              </Button>
            </Popconfirm>
          </Space>
        ) : null,
    },
  ]

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Title level={4}>变更审批（三道闸工作台）</Title>
      {error && <Alert type="error" message={error} showIcon closable onClose={() => setError(null)} />}
      <Card
        title={`变更单${data ? `（共 ${data.count} 条）` : ''}`}
        extra={
          <Space>
            {data && (
              <Space size={6}>
                <Tag color={data.storage === 'db' ? 'geekblue' : 'orange'}>存储：{data.storage}</Tag>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {data.storage === 'db' ? '数据库持久化' : '进程内存态（后端重启后丢失）'}
                </Text>
              </Space>
            )}
            <Button onClick={load} loading={loading}>刷新</Button>
          </Space>
        }
      >
        <Table<ChangeItem>
          rowKey="id"
          columns={columns}
          dataSource={data?.items ?? []}
          loading={loading}
          pagination={false}
        />
        <Descriptions size="small" style={{ marginTop: 12 }}>
          <Descriptions.Item label="审批流">
            仿真（①）→ Batfish 校验（②）→ 人工审批（③）→ 快照回滚（v2.0 十章）；审批需 admin 角色登录
          </Descriptions.Item>
        </Descriptions>
      </Card>
    </Space>
  )
}

export default ChangesPage
