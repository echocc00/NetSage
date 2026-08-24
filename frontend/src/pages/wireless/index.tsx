import React, { useState } from 'react'
import { Alert, Button, Card, Descriptions, InputNumber, Input, List, Segmented, Space, Spin, Table, Tag, Typography } from 'antd'
import { api, unwrap } from '../../services/api'

const { Title, Text, Paragraph } = Typography

interface ApPlan {
  ap_id: number
  ap_name: string
  floor: number
  channel_2g: number
  channel_5g: number
  power: number
}
interface PlanResult {
  plan: { total_aps: number; ap_per_floor: number; roaming_domain: string; ap_plan: ApPlan[]; capacity: { per_ap_users: number; total_capacity: number } }
  config: string
  template_used: string
  recommendations: string[]
}

const WirelessPage: React.FC = () => {
  const [vendor, setVendor] = useState<string>('huawei')
  const [area, setArea] = useState<number>(500)
  const [users, setUsers] = useState<number>(100)
  const [floors, setFloors] = useState<number>(1)
  const [ssid, setSsid] = useState<string>('Corp-WiFi')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<PlanResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const runPlan = async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await api.post('/wireless/plan', { area_sqm: area, users, floors, ssid, vendor })
      const data = await unwrap<PlanResult>(resp)
      setResult(data)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Title level={4}>无线专项（WirelessAgent）</Title>
      <Card title="AP 布放规划" size="small">
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          <Space wrap>
            <Text>厂商：</Text>
            <Segmented
              options={[
                { label: '华为 VRP', value: 'huawei' },
                { label: 'Cisco IOS-XE', value: 'cisco' },
                { label: 'H3C Comware', value: 'h3c' },
              ]}
              value={vendor}
              onChange={(v) => setVendor(v as string)}
            />
            <Text>面积(m²)：</Text>
            <InputNumber value={area} onChange={(v) => setArea(v ?? 500)} min={50} max={10000} />
            <Text>用户数：</Text>
            <InputNumber value={users} onChange={(v) => setUsers(v ?? 100)} min={10} max={1000} />
            <Text>楼层：</Text>
            <InputNumber value={floors} onChange={(v) => setFloors(v ?? 1)} min={1} max={10} />
          </Space>
          <Space>
            <Text>SSID：</Text>
            <Input value={ssid} onChange={(e) => setSsid(e.target.value)} style={{ width: 200 }} />
            <Button type="primary" loading={loading} onClick={runPlan}>规划 + 生成配置</Button>
          </Space>
        </Space>
      </Card>
      {error && <Alert type="error" message={error} />}
      {loading && <Spin tip="WirelessAgent 规划中..." />}
      {result && (
        <>
          <Card title="规划结果" size="small">
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="AP 总数">{result.plan.total_aps}</Descriptions.Item>
              <Descriptions.Item label="每层 AP">{result.plan.ap_per_floor}</Descriptions.Item>
              <Descriptions.Item label="漫游域">{result.plan.roaming_domain}</Descriptions.Item>
              <Descriptions.Item label="总容量">{result.plan.capacity.total_capacity} 用户</Descriptions.Item>
            </Descriptions>
          </Card>
          <Card title="AP 布放清单" size="small">
            <Table<ApPlan>
              dataSource={result.plan.ap_plan}
              rowKey="ap_id"
              size="small"
              pagination={{ pageSize: 15 }}
              columns={[
                { title: 'AP ID', dataIndex: 'ap_id', width: 70 },
                { title: '名称', dataIndex: 'ap_name', width: 100 },
                { title: '楼层', dataIndex: 'floor', width: 60 },
                { title: '2.4G 信道', dataIndex: 'channel_2g', width: 90, render: (c) => <Tag color="blue">{c}</Tag> },
                { title: '5G 信道', dataIndex: 'channel_5g', width: 90, render: (c) => <Tag color="green">{c}</Tag> },
                { title: '功率(%)', dataIndex: 'power', width: 80 },
              ]}
            />
          </Card>
          <Card title="建议" size="small">
            <List
              size="small"
              dataSource={result.recommendations}
              renderItem={(r) => <List.Item><Text>{r}</Text></List.Item>}
            />
          </Card>
          {result.config && (
            <Card title={`配置（${result.template_used}）`} size="small">
              <pre style={{ background: '#f5f5f5', padding: 12, fontSize: 12, overflow: 'auto', maxHeight: 300 }}>
                {result.config}
              </pre>
            </Card>
          )}
        </>
      )}
      <Card size="small">
        <Paragraph type="secondary" style={{ margin: 0 }}>
          Phase 4 M10：WirelessAgent（AP 布放/信道/功率/漫游域/安全策略）+ 3 厂商无线模板（ssid/roaming）。
          802.11r FT 漫游、802.1X 认证、WLC API 集成后续迭代。
        </Paragraph>
      </Card>
    </Space>
  )
}

export default WirelessPage
