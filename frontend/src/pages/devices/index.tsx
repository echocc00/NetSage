import React, { useEffect, useState } from 'react'
import { Button, Card, Space, Table, Tag, Typography } from 'antd'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { health } from '../../services/api'

const { Title } = Typography

const DevicesPage: React.FC = () => {
  const [backend, setBackend] = useState<string>('checking...')

  useEffect(() => {
    // /health 为裸响应（探活端点，v2.0 统一信封不适用）
    health()
      .then((r) => setBackend(`${r.data.status} (v${r.data.version})`))
      .catch(() => setBackend('不可达'))
  }, [])

  const columns = [
    { title: '名称', dataIndex: 'name' },
    { title: '厂商', dataIndex: 'vendor', render: (v: string) => <Tag>{v}</Tag> },
    { title: '型号', dataIndex: 'model' },
    { title: '角色', dataIndex: 'role' },
    { title: '管理 IP', dataIndex: 'mgmt_ip' },
  ]

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Title level={4}>设备管理</Title>
      <Card size="small">
        后端连接：<Tag color={backend === '不可达' ? 'red' : 'green'}>{backend}</Tag>
      </Card>
      <Card
        title="设备列表"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />}>添加设备</Button>
          </Space>
        }
      >
        <Table rowKey="id" columns={columns} dataSource={[]} locale={{ emptyText: 'Phase 2 接入 NetBox/Nautobot SSoT 后显示' }} />
      </Card>
    </Space>
  )
}

export default DevicesPage