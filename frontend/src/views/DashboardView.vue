<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useBotStore } from '@/stores/bot'
import { useConfigStore } from '@/stores/config'
import { errMsg, cancelOrder } from '@/api'
import { toastErr, toastOk } from '@/composables/useToast'
import LogPanel from '@/components/LogPanel.vue'

const bot = useBotStore()
const cfg = useConfigStore()

const canStart = computed(() => cfg.canStart && bot.connected === true)

const statusClass = computed(() => {
  const s = bot.status.status || ''
  if (s.includes('寻找') || s.includes('运行')) return 'badge-ok'
  if (s === '已抢到车位') return 'badge-info'
  if (s.includes('休眠')) return 'badge-warn'
  if (s === '异常停止') return 'badge-err'
  return 'badge-muted'
})

async function handleToggle(): Promise<void> {
  if (!bot.status.is_running && !canStart.value) {
    toastErr('配置未完成，无法启动')
    return
  }
  try {
    const wasRunning = bot.status.is_running
    await bot.toggle()
    toastOk(wasRunning ? '已停止' : '已启动')
  } catch (e) {
    toastErr(errMsg(e))
  }
}

const cancelling = ref(false)
async function handleCancel(): Promise<void> {
  if (cancelling.value) return
  cancelling.value = true
  try {
    await cancelOrder()
    toastOk('订单已取消，车位已释放')
    await bot.fetchStatus()
    await bot.fetchLogs()
  } catch (e) {
    toastErr(errMsg(e))
  } finally {
    cancelling.value = false
  }
}

onMounted(() => bot.startPolling())
onUnmounted(() => bot.stopPolling())
</script>

<template>
  <div class="dashboard">
    <!-- 警告条 -->
    <div v-if="!canStart && !bot.status.is_running" class="alert-bar card">
      <template v-if="bot.connected !== true">
        <span class="alert-icon">⚠</span>
        <span>引擎未连接，请确认后端已启动</span>
      </template>
      <template v-else>
        <span class="alert-icon">📋</span>
        <span>还需完成 <strong>{{ cfg.missingFields.join('、') }}</strong> 配置</span>
        <router-link to="/config" class="btn btn-outline btn-sm">去配置</router-link>
      </template>
    </div>

    <!-- 状态卡片 -->
    <div class="status-card card">
      <!-- 当前状态 badge -->
      <div class="status-top">
        <span class="badge" :class="statusClass">{{ bot.status.status || '未启动' }}</span>
      </div>

      <!-- 已抢到车位：显示订单信息和取消按钮 -->
      <div v-if="bot.status.current_trade_no" class="booked-block">
        <div class="booked-label">🚗 已锁定车位</div>
        <div class="booked-order">订单号 #{{ bot.status.current_trade_no }}</div>
        <div v-if="bot.countdown" class="booked-countdown">{{ bot.countdown }}</div>
        <button
          class="btn btn-outline btn-block btn-cancel-order"
          :disabled="cancelling"
          @click="handleCancel"
        >
          {{ cancelling ? '取消中…' : '主动释放车位' }}
        </button>
      </div>

      <!-- 主操作按钮：开始/停止 -->
      <button
        class="btn btn-block btn-lg"
        :class="bot.status.is_running ? 'btn-danger' : 'btn-primary'"
        :disabled="bot.loading || (!canStart && !bot.status.is_running)"
        @click="handleToggle"
      >
        <span v-if="bot.loading" class="spinner" />
        {{ bot.status.is_running ? '停 止' : '开始抢位' }}
      </button>
    </div>

    <!-- 日志 -->
    <LogPanel :logs="bot.logs" />
  </div>
</template>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: 16px; }

.alert-bar {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  background: #fffbeb; border: 1px solid #fde68a; font-size: 14px; color: #92400e;
}
.alert-icon { font-size: 16px; }
.alert-bar .btn-sm { height: 32px; padding: 0 12px; font-size: 13px; margin-left: auto; }

.status-card { text-align: center; padding: 28px 20px; }
.status-top { margin-bottom: 16px; }

.booked-block {
  margin: 0 auto 16px;
  padding: 16px;
  max-width: 300px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: var(--r-sm);
}
.booked-label { font-size: 14px; font-weight: 600; color: #1d4ed8; }
.booked-order { font-size: 12px; color: var(--c-text2); margin-top: 4px; }
.booked-countdown {
  font-size: 28px; font-weight: 700;
  font-family: 'SF Mono', monospace;
  color: var(--c-blue); margin-top: 6px;
}
.btn-cancel-order {
  margin-top: 12px;
  color: var(--c-danger);
  border-color: var(--c-danger);
  font-size: 13px;
}
.btn-cancel-order:hover { background: #fef2f2; }
</style>
