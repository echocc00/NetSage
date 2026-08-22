import React, { useState } from 'react'
import { Alert, Button, Card, Input, Progress, Segmented, Space, Table, Tag, Typography } from 'antd'
import { api, unwrap } from '../../services/api'

const { Title, Text, Paragraph } = Typography

interface Finding {
  rule_id: string
  severity: string
  description: string
  passed: boolean
  remediation: string
  standard_ref: string
}
interface ScanResult {
  vendor: string
  total: number
  passed: number
  failed: number
  score: number
  findings: Finding[]
}

const SAMPLE_CONFIG = `stelnet server enable
undo telnet server enable
authentication-scheme default
info-center loghost 10.0.0.2
ntp-service unicast-server 10.0.0.1`

const AuditPage: React.FC = () => {
  const [vendor, setVendor] = useState<string>('huawei_vrp')
  const [config, setConfig] = useState<string>(SAMPLE_CONFIG)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ScanResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const runScan = async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await api.post('/compliance/scan', { config, vendor })
      const data = await unwrap<ScanResult>(resp)
      setResult(data)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const generateReport = async () => {
    if (!config) return
    setLoading(true)
    setError(null)
    try {
      const resp = await api.post('/compliance/report', { config, vendor })
      const data = await unwrap<{ score: number; markdown: string; csv: string }>(resp)
      setResult((prev) => prev ? { ...prev, score: data.score } : null)
      const blob = new Blob([data.markdown], { type: 'text/markdown' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `compliance-report-${vendor}.md`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Title level={4}>配置审计（SecurityAuditor Agent）</Title>
      <Card title="基线扫描（CIS + 厂商加固，30 条规则）" size="small">
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          <Space>
            <Text>厂商：</Text>
            <Segmented
              options={[
                { label: '华为 VRP', value: 'huawei_vrp' },
                { label: 'Cisco IOS-XE', value: 'cisco_iosxe' },
              ]}
              value={vendor}
              onChange={(v) => setVendor(v as string)}
            />
          </Space>
          <Input.TextArea
            value={config}
            onChange={(e) => setConfig(e.target.value)}
            rows={8}
            placeholder="粘贴 running-config..."
          />
          <Space>
            <Button type="primary" loading={loading} onClick={runScan}>
              扫描基线
            </Button>
            <Button loading={loading} onClick={generateReport}>
              生成合规报告（Markdown）
            </Button>
          </Space>
        </Space>
      </Card>
      {error && <Alert type="error" message={error} />}
      {result && (
        <>
          <Card title="合规得分" size="small">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Progress
                percent={result.score}
                status={result.score >= 80 ? 'success' : result.score >= 60 ? 'normal' : 'exception'}
                format={(p) => `${p}/100`}
              />
              <Text>
                共 {result.total} 条规则：通过 {result.passed}，未通过 {result.failed}
              </Text>
            </Space>
          </Card>
          <Card title="基线检查详情" size="small">
            <Table<Finding>
              dataSource={result.findings}
              rowKey="rule_id"
              size="small"
              pagination={{ pageSize: 20 }}
              columns={[
                {
                  title: '规则', dataIndex: 'rule_id', width: 160,
                  render: (id, r) => (
                    <Space direction="vertical" size={0}>
                      <Text strong>{id}</Text>
                      <Text type="secondary" style={{ fontSize: 11 }}>{r.standard_ref}</Text>
                    </Space>
                  ),
                },
                {
                  title: '严重度', dataIndex: 'severity', width: 90,
                  render: (s) => (
                    <Tag color={s === 'critical' ? 'red' : s === 'high' ? 'orange' : s === 'medium' ? 'gold' : 'default'}>
                      {s}
                    </Tag>
                  ),
                },
                { title: '检查项', dataIndex: 'description' },
                {
                  title: '状态', dataIndex: 'passed', width: 80,
                  render: (p) => <Tag color={p ? 'green' : 'red'}>{p ? '通过' : '未通过'}</Tag>,
                },
                { title: '整改建议', dataIndex: 'remediation' },
              ]}
            />
          </Card>
        </>
      )}
      <Card size="small">
        <Paragraph type="secondary" style={{ margin: 0 }}>
          Phase 3：基线 30 条（Cisco 15 + 华为 15）+ Batfish ACL 分析（reachability / shadowed / unused）。
          华为 ACL 走 Cisco 等价转换（loose validation），USG 防火墙部分语法建议人工复核。
        </Paragraph>
      </Card>
    </Space>
  )
}

export default AuditPage
