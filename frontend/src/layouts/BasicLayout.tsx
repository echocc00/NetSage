import React from 'react'
import { Button, Layout, Menu, Space, Tag } from 'antd'
import {
  AppstoreOutlined,
  ApartmentOutlined,
  BugOutlined,
  CheckCircleOutlined,
  DashboardOutlined,
  LogoutOutlined,
  SafetyOutlined,
  ThunderboltOutlined,
  WifiOutlined,
} from '@ant-design/icons'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'

const { Sider, Content } = Layout

const MENU_ITEMS = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '运营大屏' },
  { key: '/devices', icon: <AppstoreOutlined />, label: '设备管理' },
  { key: '/design', icon: <ApartmentOutlined />, label: '设计工坊' },
  { key: '/troubleshoot', icon: <BugOutlined />, label: '排障工坊' },
  { key: '/changes', icon: <CheckCircleOutlined />, label: '变更审批' },
  { key: '/audit', icon: <SafetyOutlined />, label: '配置审计' },
  { key: '/rdma', icon: <ThunderboltOutlined />, label: 'RDMA 专项' },
  { key: '/wireless', icon: <WifiOutlined />, label: '无线专项' },
]

function getStoredRole(): string {
  return localStorage.getItem('nsc_role') ?? 'unknown'
}

const BasicLayout: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => {
    localStorage.removeItem('nsc_token')
    localStorage.removeItem('nsc_role')
    navigate('/login')
  }

  return (
    <Layout style={{ height: '100vh' }}>
      <Sider theme="dark" width={200}>
        <div style={{ padding: 16, color: '#fff', fontSize: 16, fontWeight: 600 }}>
          NetSage
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={MENU_ITEMS}
          onClick={({ key }) => navigate(key)}
        />
        <div style={{ position: 'absolute', bottom: 16, left: 16, right: 16 }}>
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Tag>{getStoredRole()}</Tag>
            <Button size="small" block icon={<LogoutOutlined />} onClick={handleLogout}>
              退出
            </Button>
          </Space>
        </div>
      </Sider>
      <Layout>
        <Content style={{ padding: 16, overflow: 'auto' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}

export default BasicLayout