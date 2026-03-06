/**
 * Bot 运行状态、日志、倒计时
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api'
import type { BotStatus } from '@/types'

/** 视为「正常/有效」的状态文案，失败时不应被单次异常覆盖 */
const HEALTHY_STATUS_PATTERN = /寻找|运行|抢到|锁定|休眠|已停止|待机/

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
  /** 防止 fetchStatus 并发，避免响应乱序导致状态闪烁 */
  let statusFetching = false
  /** 连续失败次数，多次失败才覆写为「未连接」避免单次抖动闪烁 */
  let statusFailCount = 0

  /**
   * 拉取状态；串行执行防乱序，失败有宽限，可疑回退需二次确认
   */
  async function fetchStatus(): Promise<void> {
    if (statusFetching) return
    statusFetching = true
    try {
      const next = await api.getStatus()
      statusFailCount = 0
      connected.value = true
      const prev = status.value
      // 可疑回退：新值「未启动」但当前显示运行中 → 可能是错误实例/乱序，再拉一次确认
      if (
        !next.is_running &&
        (next.status === '未启动' || !next.status?.trim()) &&
        prev.is_running &&
        HEALTHY_STATUS_PATTERN.test(prev.status || '')
      ) {
        const confirm = await api.getStatus()
        if (confirm.is_running || HEALTHY_STATUS_PATTERN.test(confirm.status || '')) {
          status.value = confirm
          return
        }
      }
      status.value = next
    } catch {
      statusFailCount++
      connected.value = false
      const prev = status.value
      const hasHealthyStatus = HEALTHY_STATUS_PATTERN.test(prev.status || '')
      if (!hasHealthyStatus || statusFailCount >= 2) {
        status.value = { ...prev, status: '未连接' }
      }
    } finally {
      statusFetching = false
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
    // 暂停轮询，防止旧的 status 响应覆盖 toggle 后的最新状态
    stopPolling()
    try {
      if (status.value.is_running) {
        await api.stopBot()
      } else {
        await api.startBot()
      }
      await fetchStatus()
      await fetchLogs()
    } finally {
      loading.value = false
      // 恢复轮询
      startPolling()
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
    statusFailCount = 0
  }

  return {
    status, logs, countdown, loading, connected,
    fetchStatus, fetchLogs, toggle,
    startPolling, stopPolling,
  }
})
