import React from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import BasicLayout from './layouts/BasicLayout'
import DashboardPage from './pages/dashboard'
import DevicesPage from './pages/devices'
import DesignPage from './pages/design'
import TroubleshootPage from './pages/troubleshoot'
import ChangesPage from './pages/changes'
import AuditPage from './pages/audit'
import RdmaPage from './pages/rdma'
import WirelessPage from './pages/wireless'
import LoginPage from './pages/login'

const AuthGuard: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const token = localStorage.getItem('nsc_token')
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

const App: React.FC = () => {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <AuthGuard>
            <BasicLayout />
          </AuthGuard>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="devices" element={<DevicesPage />} />
        <Route path="design" element={<DesignPage />} />
        <Route path="troubleshoot" element={<TroubleshootPage />} />
        <Route path="changes" element={<ChangesPage />} />
        <Route path="audit" element={<AuditPage />} />
        <Route path="rdma" element={<RdmaPage />} />
        <Route path="wireless" element={<WirelessPage />} />
      </Route>
    </Routes>
  )
}

export default App