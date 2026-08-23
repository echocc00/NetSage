import React, { useState } from 'react'
import { Alert, Button, Card, Descriptions, Input, Segmented, Space, Spin, Table, Tag, Typography } from 'antd'
import { api, unwrap } from '../../services/api'

const { Title, Text, Paragraph } = Typography

interface Diagnosis {
  bottleneck: string
  category: string
  confidence: number
  causes: { cause_id: string; cause: string; probability: number; category: string; verify: string; fix: string }[]
}
interface Tuning {
  pfc_priority: number
  pfc_headroom: string
  ecn_threshold: string
  ecn_ce_threshold: string
  dcqcn_params: Record<string, number>
  mtu: number
}
interface DiagnoseResult {
  diagnosis: Diagnosis
  tuning: Tuning
  config: string
  template_used: string
}

const SAMPLE = 'RoCEv2 丢包，GPU 间 allreduce 延迟从 5μs 升到 50μs，PFC pause 风暴'

const RdmaPage: React.FC = () => {
  const [vendor, setVendor] = useState<string>('huawei')
  const [symptom, setSymptom] = useState<string>(SAMPLE)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<DiagnoseResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const runDiagnose = async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await api.post('/rdma/diagnose', { symptom, vendor, interface: '10GE1/0/1' })
      const data = await unwrap<DiagnoseResult>(resp)
      setResult(data)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Title level={4}>RDMA 专项（RdmAgent · 差异化护城河）</Title>
      <Card title="RoCE 诊断" size="small">
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          <Space>
            <Text>厂商：</Text>
            <Segmented
              options={[
                { label: '华为 VRP', value: 'huawei' },
                { label: 'Cisco IOS-XE', value: 'cisco' },
                { label: 'Arista EOS', value: 'arista' },
              ]}
              value={vendor}
              onChange={(v) => setVendor(v as string)}
            />
          </Space>
          <Input.TextArea value={symptom} onChange={(e) => setSymptom(e.target.value)} rows={3} />
          <Button type="primary" loading={loading} onClick={runDiagnose}>诊断 + 调优建议</Button>
        </Space>
      </Card>
      {error && <Alert type="error" message={error} />}
      {loading && <Spin tip="RdmAgent 诊断中..." />}
      {result && (
        <>
          <Card title="诊断结果" size="small">
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="瓶颈">
                <Tag color={result.diagnosis.category === 'pfc' ? 'red' : result.diagnosis.category === 'ecn' ? 'orange' : 'default'}>
                  {result.diagnosis.bottleneck}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="置信度">
                {(result.diagnosis.confidence * 100).toFixed(0)}%
              </Descriptions.Item>
            </Descriptions>
          </Card>
          <Card title="候选根因" size="small">
            <Table
              dataSource={result.diagnosis.causes}
              rowKey="cause_id"
              size="small"
              pagination={false}
              columns={[
                { title: '根因', dataIndex: 'cause' },
                { title: '概率', dataIndex: 'probability', width: 80, render: (p) => `${(p * 100).toFixed(0)}%` },
                { title: '验证', dataIndex: 'verify' },
                { title: '修复', dataIndex: 'fix' },
              ]}
            />
          </Card>
          <Card title="调优参数 + 配置" size="small">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="PFC 优先级">{result.tuning.pfc_priority}</Descriptions.Item>
              <Descriptions.Item label="PFC headroom">{result.tuning.pfc_headroom}</Descriptions.Item>
              <Descriptions.Item label="ECN 阈值">{result.tuning.ecn_threshold} / CE {result.tuning.ecn_ce_threshold}</Descriptions.Item>
              <Descriptions.Item label="DCQCN">{JSON.stringify(result.tuning.dcqcn_params)}</Descriptions.Item>
              <Descriptions.Item label="MTU">{result.tuning.mtu}</Descriptions.Item>
              <Descriptions.Item label="模板">{result.template_used}</Descriptions.Item>
            </Descriptions>
            {result.config && (
              <pre style={{ background: '#f5f5f5', padding: 12, marginTop: 12, fontSize: 12, overflow: 'auto' }}>
                {result.config}
              </pre>
            )}
          </Card>
        </>
      )}
      <Card size="small">
        <Paragraph type="secondary" style={{ margin: 0 }}>
          Phase 4 RDMA 专项：OpenSM 容器化（GPL 法务隔离）+ RdmAgent 配置诊断（PFC/ECN/DCQCN）+ 6 RoCE 模板（华为/Cisco/Arista）。
          性能验证需真实硬件测试床 + perftest（Phase 4 M10+）。
        </Paragraph>
      </Card>
    </Space>
  )
}

export default RdmaPage
