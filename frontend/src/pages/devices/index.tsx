import React, { useEffect, useState } from 'react'
import { Alert, Button, Card, Col, Row, Statistic, Table, Tag, Typography } from 'antd'
import type { TableColumnsType } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { api, errorMessage, unwrap } from '../../services/api'

const { Title } = Typography

// GET /reports/devices 信封 data（SUZIEQ/NetBox 维度聚合，多数字段可能为 null）
interface DeviceReport {
  total: number | null
  by_vendor: { vendor: string; count: number }[] | null
  by_role: { role: string; count: number }[] | null
  by_site: { site: string; count: number }[] | null
  health: { no_data?: string } | null
  source: string | null
}

const vendorCols: TableColumnsType<{ vendor: string; count: number }> = [
  { title: '厂商', dataIndex: 'vendor' },
  { title: '数量', dataIndex: 'count', width: 72, align: 'right' },
]

const roleCols: TableColumnsType<{ role: string; count: number }> = [
  { title: '角色', dataIndex: 'role' },
  { title: '数量', dataIndex: 'count', width: 72, align: 'right' },
]

const siteCols: TableColumnsType<{ site: string; count: number }> = [
  { title: '站点', dataIndex: 'site' },
  { title: '数量', dataIndex: 'count', width: 72, align: 'right' },
]

const DevicesPage: React.FC = () => {
  const [data, setData] = useState<DeviceReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const resp = await api.get('/reports/devices')
      const d = await unwrap<DeviceReport>(resp)
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

  return (
    <>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>设备管理</Title>
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>刷新</Button>
      </Row>
      {error && <Alert type="error" message={error} showIcon closable onClose={() => setError(null)} style={{ marginBottom: 16 }} />}
      <Card title="设备总览">
        <Row gutter={16}>
          <Col span={6}>
            <Statistic title="设备总数" value={data?.total ?? '-'} />
          </Col>
          <Col span={6} style={{ display: 'flex', alignItems: 'center' }}>
            <Statistic
              title="数据来源"
              valueRender={() => (data?.source ? <Tag color={data.source === 'demo' ? 'orange' : 'geekblue'}>{data.source}</Tag> : <span>—</span>)}
            />
          </Col>
        </Row>
        {data?.health?.no_data && (
          <Alert
            type="info"
            showIcon
            style={{ marginTop: 16 }}
            message="设备健康数据需 SUZIEQ 接入"
            description={data.health.no_data}
          />
        )}
      </Card>
      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={8}>
          <Card title="按厂商" size="small">
            <Table
              rowKey="vendor"
              size="small"
              pagination={false}
              columns={vendorCols}
              dataSource={data?.by_vendor ?? []}
              locale={{ emptyText: '暂无数据' }}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card title="按角色" size="small">
            <Table
              rowKey="role"
              size="small"
              pagination={false}
              columns={roleCols}
              dataSource={data?.by_role ?? []}
              locale={{ emptyText: '暂无数据' }}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card title="按站点" size="small">
            <Table
              rowKey="site"
              size="small"
              pagination={false}
              columns={siteCols}
              dataSource={data?.by_site ?? []}
              locale={{ emptyText: '暂无数据' }}
            />
          </Card>
        </Col>
      </Row>
    </>
  )
}

export default DevicesPage
