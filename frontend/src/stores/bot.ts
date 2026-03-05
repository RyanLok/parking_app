/**
 * Bot 运行状态、日志、倒计时
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api'
import type { BotStatus } from '@/types'

export const useBotStore = defineStore('bot', () => {
  const status = ref<BotStatus>({
    is_running: false,
    status: '加载中…',
    current_trade_no: null,
    deadline_ts: 0,
  })
  const logs = ref<string[]>([])
  const countdown = ref('')
  const loading = ref(false)
  const connected = ref<boolean | null>(null)

  let statusTid = 0
  let cdTid = 0

  async function fetchStatus(): Promise<void> {
    try {
      status.value = await api.getStatus()
      connected.value = true
    } catch {
      status.value = { ...status.value, status: '未连接' }
      connected.value = false
    }
  }

  /**
   * 拉取日志；若本次返回空且已有日志，则不覆盖，避免闪烁
   */
  async function fetchLogs(): Promise<void> {
    try {
      const newLogs = await api.getLogs()
      // 避免空响应覆盖已有日志导致「暂无日志」与正常内容交替闪烁
      if (newLogs.length > 0 || logs.value.length === 0) {
        logs.value = newLogs
      }
    } catch { /* ignore */ }
  }

  function updateCountdown(): void {
    const ts = status.value.deadline_ts
    if (ts > 0) {
      const rem = ts - Date.now() / 1000
      countdown.value = rem > 0
        ? `${Math.floor(rem / 60)}分${Math.floor(rem % 60)}秒`
        : '即将释放'
    } else {
      countdown.value = ''
    }
  }

  async function toggle(): Promise<void> {
    if (loading.value) return
    loading.value = true
    try {
      if (status.value.is_running) {
        await api.stopBot()
      } else {
        await api.startBot()
      }
      await fetchStatus()
    } finally {
      loading.value = false
    }
  }

  /** 仅当页面可见时轮询，避免多标签页互相干扰 */
  function _tick(): void {
    if (document.visibilityState !== 'visible') return
    fetchStatus()
    fetchLogs()
    updateCountdown()
  }

  function _onVisibilityChange(): void {
    if (document.visibilityState === 'visible' && statusTid) _tick()
  }

  function startPolling(): void {
    stopPolling()
    _tick()
    statusTid = window.setInterval(_tick, 3000)
    cdTid = window.setInterval(updateCountdown, 1000)
    document.addEventListener('visibilitychange', _onVisibilityChange)
  }

  function stopPolling(): void {
    window.clearInterval(statusTid)
    window.clearInterval(cdTid)
    document.removeEventListener('visibilitychange', _onVisibilityChange)
    statusTid = 0
  }

  return {
    status, logs, countdown, loading, connected,
    fetchStatus, fetchLogs, toggle,
    startPolling, stopPolling,
  }
})
