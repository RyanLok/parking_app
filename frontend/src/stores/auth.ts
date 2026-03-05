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
    return !!c?.mobile?.trim()
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
   * 密码登录
   */
  async function doLogin(mobile: string, password: string): Promise<{ is_running: boolean }> {
    const res = await api.login(mobile, password)
    await loadConfig()
    return { is_running: res.is_running }
  }

  /**
   * 验证码登录
   */
  async function doLoginWithSms(mobile: string, smsCode: string): Promise<{ is_running: boolean }> {
    const res = await api.loginWithSms(mobile, smsCode)
    await loadConfig()
    return { is_running: res.is_running }
  }

  async function doLogout(): Promise<void> {
    await api.logout()
    config.value = null
  }

  function setConfig(val: Config | null): void {
    config.value = val
  }

  return { config, isLoggedIn, hasLocation, loadConfig, doLogin, doLoginWithSms, doLogout, setConfig }
})
