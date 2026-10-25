import React, { useEffect, useState } from 'react'
import { Alert, Card, Col, Progress, Row, Space, Spin, Statistic, Table, Tag, Typography } from 'antd'
import { api, errorMessage, unwrap } from '../../services/api'

const { Title, Text } = Typography

// GET /reports/dashboard 信封 data（多数字段可能为 null）
interface DashboardData {
  summary: {
    devices: number | null
    changes_total: number | null
    automation_rate: number | null
    alerts: number | null
    agents_run: number | null
  } | null
  device_health: { no_data?: string } | null
  change_pipeline: {
    draft: number | null
    approval: number | null
    approved: number | null
    deployed: number | null
    rolled_back: number | null
  } | null
  rca_hit_rate: number | null
  top_alerts: { severity?: string; device?: string; message?: string }[] | null
  meta: { generated_at?: string; change_storage?: string; device_source?: string; demo?: boolean } | null
  version: string | null
}

// null 数值统一显示 '-'
const num = (v: number | null | undefined) => v ?? '-'

const PIPELINE_STAGES: { key: keyof NonNullable<DashboardData['change_pipeline']>; label: string; color: string }[] = [
  { key: 'draft', label: '草稿', color: 'default' },
  { key: 'approval', label: '审批中', color: 'processing' },
  { key: 'approved', label: '已批准', color: 'blue' },
  { key: 'deployed', label: '已部署', color: 'green' },
  { key: 'rolled_back', label: '已回滚', color: 'red' },
]

const DashboardPage: React.FC = () => {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const resp = await api.get('/reports/dashboard')
        const d = await unwrap<DashboardData>(resp)
        setData(d)
        setError(null)
      } catch (e) {
        setError(errorMessage(e))
      } finally {
        setLoading(false)
      }
    }
    load()
    // 30s 轮询刷新
    const timer = setInterval(load, 30000)
    return () => clearInterval(timer)
  }, [])

  if (loading) return <Spin tip="加载大屏..." />
  if (error) return <Alert type="error" message={error} showIcon />
  if (!data) return null

  const s = data.summary
  const alerts = s?.alerts ?? null
  const rate = s?.automation_rate ?? null

  return (
    <div>
      <Row justify="space-between" align="middle">
        <Title level={4} style={{ margin: 0 }}>运营大屏{data.version ? ` · ${data.version}` : ''}</Title>
        <Space size={6} wrap>
          {data.meta?.generated_at && <Tag>生成于 {data.meta.generated_at}</Tag>}
          {data.meta?.change_storage && (
            <Tag color={data.meta.change_storage === 'db' ? 'geekblue' : 'orange'}>
              变更存储 {data.meta.change_storage}
            </Tag>
          )}
          {data.meta?.device_source && <Tag>设备源 {data.meta.device_source}</Tag>}
          {data.meta?.demo && <Tag color="gold">演示数据</Tag>}
        </Space>
      </Row>
      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col flex={1}>
          <Card><Statistic title="设备总数" value={num(s?.devices)} /></Card>
        </Col>
        <Col flex={1}>
          <Card><Statistic title="变更总数" value={num(s?.changes_total)} /></Card>
        </Col>
        <Col flex={1}>
          <Card>
            {rate == null ? (
              // 无闭环历史数据时如实提示，不再展示假数
              <Statistic title="自动化率" value="待闭环历史" valueStyle={{ fontSize: 22 }} />
            ) : (
              <Statistic title="自动化率" value={Math.round(rate * 100)} suffix="%" />
            )}
          </Card>
        </Col>
        <Col flex={1}>
          <Card>
            <Statistic
              title="告警"
              value={num(alerts)}
              valueStyle={alerts != null && alerts > 0 ? { color: '#faad14' } : undefined}
            />
          </Card>
        </Col>
        <Col flex={1}>
          <Card><Statistic title="Agent 运行" value={num(s?.agents_run)} /></Card>
        </Col>
      </Row>
      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={8}>
          <Card title="设备健康">
            {data.device_health?.no_data ? (
              <Alert type="info" showIcon message="需 SUZIEQ 接入" description={data.device_health.no_data} />
            ) : (
              <Text type="secondary">暂无数据</Text>
            )}
          </Card>
        </Col>
        <Col span={8}>
          <Card title="变更流水线">
            {data.change_pipeline ? (
              <Row gutter={8}>
                {PIPELINE_STAGES.map((st) => (
                  <Col flex={1} key={st.key}>
                    <Statistic
                      title={<Tag color={st.color} style={{ margin: 0 }}>{st.label}</Tag>}
                      value={num(data.change_pipeline?.[st.key])}
                      valueStyle={{ fontSize: 20 }}
                    />
                  </Col>
                ))}
              </Row>
            ) : (
              <Text type="secondary">暂无数据</Text>
            )}
          </Card>
        </Col>
        <Col span={8}>
          <Card title="RCA 命中率">
            {data.rca_hit_rate == null ? (
              <Text type="secondary">暂无数据</Text>
            ) : (
              <>
                <Progress type="circle" percent={Math.round(data.rca_hit_rate * 100)} format={(p) => `${p}%`} />
                <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>Top-1 根因命中率</Text>
              </>
            )}
          </Card>
        </Col>
      </Row>
      <Card title="实时告警" style={{ marginTop: 16 }}>
        {(data.top_alerts?.length ?? 0) === 0 ? (
          <Text type="secondary">暂无告警</Text>
        ) : (
          <Table
            size="small"
            pagination={false}
            dataSource={data.top_alerts ?? []}
            rowKey="device"
            columns={[
              { title: '严重度', dataIndex: 'severity', width: 100, render: (v) => <Tag color={v === 'critical' ? 'red' : 'orange'}>{v ?? '-'}</Tag> },
              { title: '设备', dataIndex: 'device', width: 120, render: (v) => v ?? '-' },
              { title: '消息', dataIndex: 'message', render: (v) => v ?? '-' },
            ]}
          />
        )}
      </Card>
    </div>
  )
}

export default DashboardPage
