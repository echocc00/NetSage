import React, { useRef, useState } from 'react'
import { Button, Card, Input, Space, Steps, Typography } from 'antd'
import { api, streamSession, unwrap } from '../../services/api'

const { Title, Text } = Typography
const { TextArea } = Input

const TroubleshootPage: React.FC = () => {
  const [symptom, setSymptom] = useState('')
  const [loading, setLoading] = useState(false)
  const [classified, setClassified] = useState<Record<string, unknown> | null>(null)
  const [events, setEvents] = useState<string[]>([])
  // 审查 C1 修复：SSE 连接用 ref 管理，卸载/重复点击时关闭
  const closeStreamRef = useRef<(() => void) | null>(null)
  const mountedRef = useRef(true)

  const start = async () => {
    setLoading(true)
    setEvents([])
    try {
      const resp = await api.post('/agents/sessions', { query: symptom })
      const data = await unwrap<{ session_id: string; intent: string; scenario: string; primary_agent: string }>(resp)
      // 关闭旧连接，避免泄漏（审查 C1）
      closeStreamRef.current?.()
      closeStreamRef.current = streamSession(data.session_id, (e) => {
        const raw = JSON.stringify(e)
        setEvents((prev) => [...prev, raw])
      })
      setClassified(data)
    } finally {
      setLoading(false)
    }
  }

  // 卸载时关闭 SSE
  React.useEffect(() => () => {
    mountedRef.current = false
    closeStreamRef.current?.()
  }, [])

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Title level={4}>排障工坊</Title>
      <Card>
        <TextArea
          rows={4}
          placeholder='描述症状，如 "两台 Spine 间 BGP 邻居反复抖动"'
          value={symptom}
          onChange={(e) => setSymptom(e.target.value)}
        />
        <div style={{ marginTop: 12 }}>
          <Button type="primary" loading={loading} onClick={start} disabled={!symptom}>
            开始排障
          </Button>
        </div>
      </Card>
      {classified && (
        <Card title="意图分类（Planner）">
          <Steps
            direction="vertical"
            size="small"
            current={0}
            items={[
              { title: `intent: ${classified.intent}` },
              { title: `scenario: ${classified.scenario}` },
              { title: `主责 Agent: ${classified.primary_agent}` },
            ]}
          />
          {events.length > 0 && (
            <Text code type="secondary">
              {events.join('\n')}
            </Text>
          )}
        </Card>
      )}
    </Space>
  )
}

export default TroubleshootPage