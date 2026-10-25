import React, { useRef, useState } from 'react'
import { Alert, Button, Card, Input, Space, Steps, Typography } from 'antd'
import { api, streamSession, unwrap, errorMessage } from '../../services/api'
import type { AgentSession, AgentStreamEvent } from '../../services/api'

const { Title, Text } = Typography
const { TextArea } = Input

// SSE 事件转单行可读文本（step 显示节点名，done/error 显示终态）
interface EventLine {
  text: string
  kind: 'info' | 'done' | 'error'
}

function formatEvent(e: AgentStreamEvent): EventLine {
  switch (e.event) {
    case 'start':
      return { text: '会话已启动', kind: 'info' }
    case 'step':
      return { text: `执行节点：${e.node ?? JSON.stringify(e)}`, kind: 'info' }
    case 'state':
      return { text: `状态更新：${JSON.stringify(e)}`, kind: 'info' }
    case 'done':
      return { text: '排障完成', kind: 'done' }
    case 'error':
      return { text: `错误：${e.error ?? JSON.stringify(e)}`, kind: 'error' }
    default:
      // 后端新增事件类型时的兜底
      return { text: JSON.stringify(e), kind: 'info' }
  }
}

const TroubleshootPage: React.FC = () => {
  const [symptom, setSymptom] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [classified, setClassified] = useState<AgentSession | null>(null)
  const [events, setEvents] = useState<EventLine[]>([])
  // 审查 C1 修复：SSE 连接用 ref 管理，卸载/重复点击时关闭
  const closeStreamRef = useRef<(() => void) | null>(null)
  const mountedRef = useRef(true)

  const start = async () => {
    setLoading(true)
    setError(null)
    setEvents([])
    try {
      const resp = await api.post('/agents/sessions', { query: symptom })
      const data = await unwrap<AgentSession>(resp)
      // 关闭旧连接，避免泄漏（审查 C1）
      closeStreamRef.current?.()
      closeStreamRef.current = streamSession(data.session_id, data.stream_ticket, (e) => {
        setEvents((prev) => [...prev, formatEvent(e)])
      })
      setClassified(data)
    } catch (e) {
      // 后端不可达等异常兜底（此前仅 finally，会 unhandled rejection）
      setError(errorMessage(e))
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
      {error && <Alert type="error" message={error} showIcon closable onClose={() => setError(null)} />}
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
            <div style={{ marginTop: 12 }}>
              {events.map((line, i) => (
                <Text
                  key={i}
                  code
                  style={{ display: 'block' }}
                  type={line.kind === 'error' ? 'danger' : line.kind === 'done' ? 'success' : 'secondary'}
                >
                  {line.text}
                </Text>
              ))}
            </div>
          )}
        </Card>
      )}
    </Space>
  )
}

export default TroubleshootPage
