/**
 * API 客户端：统一请求、Session、错误处理
 *
 * VITE_API_BASE 由环境变量注入：
 *   - 开发环境：/api（Vite proxy 转发到 localhost:8000）
 *   - 生产环境：https://your-server.com/api（直连云服务器）
 */
import axios from 'axios'

const BASE = import.meta.env.VITE_API_BASE || '/api'

function sessionId(): string {
  const key = 'parking_session_id'
  let s = localStorage.getItem(key)
  if (!s) {
    s = crypto.randomUUID()
    localStorage.setItem(key, s)
  }
  return s
}

export const api = axios.create({
  baseURL: BASE,
  timeout: 15000,
  headers: { 'X-Session-Id': sessionId() },
})

export function errMsg(e: unknown): string {
  if (axios.isAxiosError(e)) {
    if (e.code === 'ERR_NETWORK') return '无法连接服务器，请检查网络'
    if (e.code === 'ECONNABORTED') return '请求超时，请稍后重试'
    return (e.response?.data?.detail as string) || e.message || '请求失败'
  }
  return String(e)
}
