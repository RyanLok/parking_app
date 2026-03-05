/**
 * 认证状态：登录态、配置
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as api from '@/api'
import type { Config } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const config = ref<Config | null>(null)

  const isLoggedIn = computed(() => {
    const c = config.value
    return !!(c?.mobile?.trim() && c?.password_md5?.trim())
  })

  const hasLocation = computed(() => {
    const c = config.value
    return !!(c?.lng?.trim() && c?.lat?.trim())
  })

  async function loadConfig(): Promise<void> {
    try {
      config.value = await api.getConfig()
    } catch {
      config.value = null
    }
  }

  /**
   * @returns 登录后 bot 是否正在运行（同一手机号可能已有 bot）
   */
  async function doLogin(mobile: string, password: string): Promise<{ is_running: boolean }> {
    const res = await api.login(mobile, password)
    await loadConfig()
    return { is_running: res.is_running }
  }

  async function doLogout(): Promise<void> {
    await api.logout()
    config.value = null
  }

  return { config, isLoggedIn, hasLocation, loadConfig, doLogin, doLogout }
})
