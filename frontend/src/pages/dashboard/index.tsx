import React, { useEffect, useState } from 'react'
import { Alert, Card, Col, Progress, Row, Spin, Statistic, Table, Tag, Typography } from 'antd'
import { api, unwrap } from '../../services/api'

const { Title, Text } = Typography

interface DashboardData {
  summary: { devices: number; changes_today: number; compliance_score: number; automation_rate: number; alerts: number; agents_run_today: number }
  device_health: { healthy: number; warning: number; critical: number }
  change_pipeline: { draft: number; approved: number; deployed: number; rolled_back: number }
  rca_hit_rate: number
  top_alerts: { severity: string; device: string; message: string }[]
  version: string
}

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
      } catch (e) {
        setError((e as Error).message)
      } finally {
        setLoading(false)
      }
    }
    load()
    const timer = setInterval(load, 30000)
    return () => clearInterval(timer)
  }, [])

  if (loading) return <Spin tip="加载大屏..." />
  if (error) return <Alert type="error" message={error} />
  if (!data) return null

  return (
    <div>
      <Title level={4}>运营大屏 · {data.version}</Title>
      <Row gutter={16}>
        <Col span={4}>
          <Card><Statistic title="设备总数" value={data.summary.devices} /></Card>
        </Col>
        <Col span={4}>
          <Card><Statistic title="今日变更" value={data.summary.changes_today} /></Card>
        </Col>
        <Col span={4}>
          <Card><Statistic title="合规得分" value={data.summary.compliance_score} suffix="/100" /></Card>
        </Col>
        <Col span={4}>
          <Card><Statistic title="自动化率" value={Math.round(data.summary.automation_rate * 100)} suffix="%" /></Card>
        </Col>
        <Col span={4}>
          <Card><Statistic title="今日告警" value={data.summary.alerts} valueStyle={{ color: data.summary.alerts > 0 ? '#faad14' : '#52c41a' }} /></Card>
        </Col>
        <Col span={4}>
          <Card><Statistic title="Agent 运行" value={data.summary.agents_run_today} /></Card>
        </Col>
      </Row>
      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={8}>
          <Card title="设备健康">
            <Progress percent={(data.device_health.healthy / data.summary.devices) * 100} status="success" format={() => `健康 ${data.device_health.healthy}`} />
            <div style={{ marginTop: 8 }}>
              <Tag color="green">健康 {data.device_health.healthy}</Tag>
              <Tag color="orange">告警 {data.device_health.warning}</Tag>
              <Tag color="red">严重 {data.device_health.critical}</Tag>
            </div>
          </Card>
        </Col>
        <Col span={8}>
          <Card title="变更流水线">
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <Tag color="default">草稿 {data.change_pipeline.draft}</Tag>
              <Tag color="blue">已批 {data.change_pipeline.approved}</Tag>
              <Tag color="green">已部署 {data.change_pipeline.deployed}</Tag>
              <Tag color="red">已回滚 {data.change_pipeline.rolled_back}</Tag>
            </div>
            <Progress percent={data.summary.automation_rate * 100} format={(p) => `自动化 ${p}%`} style={{ marginTop: 12 }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card title="RCA 命中率">
            <Progress type="circle" percent={Math.round(data.rca_hit_rate * 100)} format={(p) => `${p}%`} />
            <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>Top-1 根因命中率</Text>
          </Card>
        </Col>
      </Row>
      <Card title="实时告警" style={{ marginTop: 16 }}>
        {data.top_alerts.length === 0 ? (
          <Text type="secondary">暂无告警</Text>
        ) : (
          <Table
            size="small"
            pagination={false}
            dataSource={data.top_alerts}
            rowKey="device"
            columns={[
              { title: '严重度', dataIndex: 'severity', width: 100, render: (s) => <Tag color={s === 'critical' ? 'red' : 'orange'}>{s}</Tag> },
              { title: '设备', dataIndex: 'device', width: 120 },
              { title: '消息', dataIndex: 'message' },
            ]}
          />
        )}
      </Card>
    </div>
  )
}

export default DashboardPage
