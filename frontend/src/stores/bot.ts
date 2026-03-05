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
  let logsTid = 0
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

  async function fetchLogs(): Promise<void> {
    try { logs.value = await api.getLogs() } catch { /* ignore */ }
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

  function startPolling(): void {
    stopPolling()
    fetchStatus()
    fetchLogs()
    statusTid = window.setInterval(fetchStatus, 3000)
    logsTid = window.setInterval(fetchLogs, 2000)
    cdTid = window.setInterval(updateCountdown, 1000)
  }

  function stopPolling(): void {
    window.clearInterval(statusTid)
    window.clearInterval(logsTid)
    window.clearInterval(cdTid)
  }

  return {
    status, logs, countdown, loading, connected,
    fetchStatus, fetchLogs, toggle,
    startPolling, stopPolling,
  }
})
