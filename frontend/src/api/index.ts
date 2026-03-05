/**
 * API 模块：所有后端接口
 */
import { api, errMsg } from './client'
import type { Config, City, Park, Plate, BotStatus } from '@/types'

export { errMsg }

/**
 * @returns 登录后 bot 的实时状态（可能该手机号已有 bot 在跑）
 */
export async function login(mobile: string, password: string): Promise<{ is_running: boolean; status: string }> {
  const { data } = await api.post<{ success: boolean; is_running: boolean; status: string }>(
    '/auth/login',
    { mobile: mobile.trim(), password: password.trim() },
  )
  return data
}

export async function logout(): Promise<void> {
  await api.post('/auth/logout')
}

export async function getConfig(): Promise<Config> {
  const { data } = await api.get<Config>('/config')
  return data
}

export async function saveConfig(cfg: Partial<Config>): Promise<void> {
  await api.post('/config', cfg)
}

export async function getStatus(): Promise<BotStatus> {
  const { data } = await api.get<BotStatus>('/status')
  return data
}

export async function getLogs(): Promise<string[]> {
  const { data } = await api.get<{ logs: string[] }>('/logs')
  return data.logs || []
}

export async function startBot(): Promise<void> {
  await api.post('/action/start')
}

export async function stopBot(): Promise<void> {
  await api.post('/action/stop')
}

export async function getCities(lng: string, lat: string): Promise<City[]> {
  const { data } = await api.get<{ cities: City[] }>('/cities', { params: { lng, lat } })
  return data.cities || []
}

export async function getParks(cityId: number, lng: string, lat: string): Promise<Park[]> {
  const { data } = await api.get<{ parks: Park[] }>('/parks', {
    params: { city_id: cityId, lng, lat, size: 50 },
  })
  return data.parks || []
}

export async function getPlates(lng: string, lat: string): Promise<Plate[]> {
  const { data } = await api.get<{ plates: Plate[] }>('/plates', { params: { lng, lat } })
  return data.plates || []
}
