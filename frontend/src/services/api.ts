import axios from 'axios'

export const api = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
})

// JWT 注入（OIDC Phase 3 接入，开发态 localStorage）
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('nsc_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 统一响应信封解包（v2.0 patterns.md）
export interface Envelope<T = unknown> {
  success: boolean
  data: T | null
  error: string | null
  meta: { trace_id?: string; page?: number; limit?: number; total?: number } | null
}

export async function unwrap<T>(resp: { data: Envelope<T> }): Promise<T> {
  if (!resp.data.success) throw new Error(resp.data.error ?? '请求失败')
  if (resp.data.data == null) throw new Error('响应 data 为空')  // 审查 M6：null 守卫
  return resp.data.data
}

// 创建排障会话响应（POST /agents/sessions，stream_ticket 为一次性票据 120s）
export interface AgentSession {
  session_id: string
  intent: string
  scenario: string
  primary_agent: string
  stream_ticket: string
}

// SSE 流事件载荷（默认 message 事件，data 为 JSON）
export interface AgentStreamEvent {
  event: 'start' | 'step' | 'state' | 'done' | 'error'
  node?: string
  error?: string
  [key: string]: unknown
}

// SSE 流式 DAG 进度（v2.0 十二章）；EventSource 无法带 Authorization 头，改走 ?ticket= 一次性票据
export function streamSession(sessionId: string, ticket: string, onEvent: (e: AgentStreamEvent) => void): () => void {
  const es = new EventSource(`/api/v1/agents/sessions/${sessionId}/stream?ticket=${encodeURIComponent(ticket)}`)
  es.onmessage = (e) => onEvent(JSON.parse(e.data))
  return () => es.close()
}

// 统一错误文案提取：信封 error 优先，兼容非 2xx 的 AxiosError（FastAPI detail）
export function errorMessage(e: unknown): string {
  const err = e as { response?: { data?: { error?: string; detail?: string } }; message?: string }
  const d = err?.response?.data
  return d?.error ?? d?.detail ?? err?.message ?? '请求失败'
}

// 健康检查（探活端点裸响应，不走信封——v2.0 patterns 例外）
export const health = () =>
  api.get<{ status: string; version: string; env: string }>('/health')

// 开发态登录（Phase 3 OIDC 前过渡；生产无此端点）
export interface DevLoginResult {
  token: string
  role: string
}

export const devLogin = async (userId: number, name: string, roleId: number): Promise<DevLoginResult> => {
  const resp = await api.post<DevLoginResult>('/auth/dev-token', {
    user_id: userId,
    name,
    role: roleId,
  })
  return resp.data
}

export const logout = () => {
  localStorage.removeItem('nsc_token')
  localStorage.removeItem('nsc_role')
  window.location.href = '/login'
}