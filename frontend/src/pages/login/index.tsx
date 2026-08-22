import React, { useState } from 'react'
import { Button, Card, Form, Input, Select, Space, Typography, message } from 'antd'
import { LockOutlined, UserOutlined } from '@ant-design/icons'
import { devLogin } from '../../services/api'

const { Title, Text } = Typography

const ROLES = [
  { value: 2, label: '工程师（engineer）— 拟变更 + 发起审批' },
  { value: 1, label: '运维（operator）— 可读 + 排障' },
  { value: 3, label: '主管（admin）— 审批 + 回滚' },
  { value: 4, label: '审计员（auditor）— 只读审计' },
  { value: 0, label: '访客（viewer）— 只读' },
]

interface LoginForm {
  name: string
  role: number
}

const LoginPage: React.FC = () => {
  const [loading, setLoading] = useState(false)

  const onFinish = async (values: LoginForm) => {
    setLoading(true)
    try {
      const result = await devLogin(1, values.name || 'dev', values.role)
      localStorage.setItem('nsc_token', result.token)
      localStorage.setItem('nsc_role', result.role)
      message.success(`登录成功（${result.role}）`)
      window.location.href = '/devices'
    } catch (e) {
      message.error(`登录失败：${(e as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f0f2f5' }}>
      <Card style={{ width: 400 }}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Title level={3} style={{ marginBottom: 0 }}>NetSage</Title>
          <Text type="secondary">AI 网络工程师平台 · 开发态登录</Text>
          <Form<LoginForm> layout="vertical" onFinish={onFinish} initialValues={{ role: 2 }}>
            <Form.Item name="name" label="用户名">
              <Input prefix={<UserOutlined />} placeholder="dev" />
            </Form.Item>
            <Form.Item name="role" label="角色" rules={[{ required: true, message: '请选择角色' }]}>
              <Select options={ROLES} />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" loading={loading} block icon={<LockOutlined />}>
                登录
              </Button>
            </Form.Item>
          </Form>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Phase 3 将替换为 OIDC（Keycloak）统一认证
          </Text>
        </Space>
      </Card>
    </div>
  )
}

export default LoginPage