<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useBotStore } from '@/stores/bot'
import { useConfigStore } from '@/stores/config'
import { useAuthStore } from '@/stores/auth'
import { errMsg, cancelOrder, sendSmsCode, loginWithSms } from '@/api'
import { toastErr, toastOk } from '@/composables/useToast'
import LogPanel from '@/components/LogPanel.vue'

const router = useRouter()
const bot = useBotStore()
const cfg = useConfigStore()
const auth = useAuthStore()

const canStart = computed(() => cfg.canStart && bot.connected === true)

const statusClass = computed(() => {
  const s = bot.status.status || ''
  if (s.includes('寻找') || s.includes('运行')) return 'badge-ok'
  if (s.includes('抢到') || s.includes('锁定')) return 'badge-info'
  if (s.includes('休眠')) return 'badge-warn'
  if (s.includes('过期') || s.includes('失败') || s.includes('异常')) return 'badge-err'
  return 'badge-muted'
})

async function handleToggle(): Promise<void> {
  // token 过期 → 跳到登录页
  if (bot.status.token_expired) {
    router.push('/login')
    return
  }
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

// ======= SMS 续登 =======
const smsCode = ref('')
const smsSending = ref(false)
const smsLogging = ref(false)
const smsCooldown = ref(0)
let smsCdTimer = 0

async function handleSendSms(): Promise<void> {
  if (smsSending.value || smsCooldown.value > 0) return
  const mobileB64 = auth.config?.mobile
  if (!mobileB64) {
    toastErr('未找到手机号，请重新登录')
    return
  }
  smsSending.value = true
  try {
    const mobile = atob(mobileB64)
    await sendSmsCode(mobile)
    toastOk('验证码已发送')
    smsCooldown.value = 60
    smsCdTimer = window.setInterval(() => {
      smsCooldown.value--
      if (smsCooldown.value <= 0) clearInterval(smsCdTimer)
    }, 1000)
  } catch (e) {
    toastErr(errMsg(e))
  } finally {
    smsSending.value = false
  }
}

async function handleSmsRenew(): Promise<void> {
  if (smsLogging.value || !smsCode.value.trim()) return
  const mobileB64 = auth.config?.mobile
  if (!mobileB64) {
    toastErr('未找到手机号，请重新登录')
    return
  }
  smsLogging.value = true
  try {
    const mobile = atob(mobileB64)
    await loginWithSms(mobile, smsCode.value.trim())
    toastOk('续登成功！')
    smsCode.value = ''
    await bot.fetchStatus()
  } catch (e) {
    toastErr(errMsg(e))
  } finally {
    smsLogging.value = false
  }
}

onMounted(() => bot.startPolling())
onUnmounted(() => {
  bot.stopPolling()
  clearInterval(smsCdTimer)
})
</script>

<template>
  <div class="dashboard">
    <!-- Token 过期续登提示 -->
    <div v-if="bot.status.token_expired" class="alert-bar alert-expired card">
      <div class="expired-title">
        <span class="alert-icon">🔑</span>
        <span>登录已过期，请重新登录</span>
      </div>
      <div class="sms-renew-row">
        <input
          v-model="smsCode"
          class="sms-input"
          type="text"
          maxlength="6"
          placeholder="6位验证码"
          @keyup.enter="handleSmsRenew"
        />
        <button
          class="btn btn-outline btn-sm"
          :disabled="smsSending || smsCooldown > 0"
          @click="handleSendSms"
        >
          {{ smsCooldown > 0 ? `${smsCooldown}s` : smsSending ? '发送中' : '发送验证码' }}
        </button>
        <button
          class="btn btn-primary btn-sm"
          :disabled="smsLogging || !smsCode.trim()"
          @click="handleSmsRenew"
        >
          {{ smsLogging ? '续登中…' : '续登' }}
        </button>
      </div>
    </div>

    <!-- 警告条 -->
    <div v-if="!canStart && !bot.status.is_running && !bot.status.token_expired" class="alert-bar card">
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
        <span class="badge" :class="statusClass">{{ bot.status.token_expired ? '登录已过期' : (bot.status.status || '未启动') }}</span>
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

      <!-- 主操作按钮 -->
      <button
        v-if="bot.status.token_expired"
        class="btn btn-block btn-lg btn-danger"
        @click="handleToggle"
      >
        🔑 请重新登录
      </button>
      <button
        v-else
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
.dashboard { display: flex; flex-direction: column; gap: 16px; flex: 1; min-height: 0; }

.alert-bar {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  background: #fffbeb; border: 1px solid #fde68a; font-size: 14px; color: #92400e;
}
.alert-icon { font-size: 16px; }
.alert-bar .btn-sm { height: 32px; padding: 0 12px; font-size: 13px; margin-left: auto; }

.alert-expired {
  background: #fef2f2; border-color: #fca5a5; color: #991b1b;
  flex-direction: column; align-items: stretch; gap: 10px;
}
.expired-title { display: flex; align-items: center; gap: 8px; font-weight: 600; }
.sms-renew-row {
  display: flex; gap: 8px; align-items: center;
}
.sms-input {
  flex: 1; height: 36px; padding: 0 12px;
  border: 1px solid #d1d5db; border-radius: var(--r-sm);
  font-size: 14px; outline: none;
  letter-spacing: 4px; text-align: center;
}
.sms-input:focus { border-color: var(--c-blue); }
.sms-renew-row .btn-sm { white-space: nowrap; margin-left: 0; }

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
