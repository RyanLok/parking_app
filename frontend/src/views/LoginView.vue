<script setup lang="ts">
/**
 * 登录页：支持密码登录、验证码登录
 */
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useBotStore } from '@/stores/bot'
import { errMsg, sendSmsCode } from '@/api'
import { toastErr, toastOk } from '@/composables/useToast'

const router = useRouter()
const auth = useAuthStore()
const bot = useBotStore()

const mode = ref<'password' | 'sms'>('sms')
const mobile = ref('')
const password = ref('')
const smsCode = ref('')
const busy = ref(false)
const countdown = ref(0)
let countdownTid = 0

const canSendSms = computed(() => {
  const m = mobile.value.trim()
  return m.length === 11 && countdown.value === 0 && !busy.value
})

async function sendCode(): Promise<void> {
  const m = mobile.value.trim()
  if (m.length !== 11) {
    toastErr('请输入正确的11位手机号')
    return
  }
  busy.value = true
  try {
    await sendSmsCode(m)
    toastOk('验证码已发送')
    countdown.value = 60
    countdownTid = window.setInterval(() => {
      countdown.value--
      if (countdown.value <= 0) {
        window.clearInterval(countdownTid)
      }
    }, 1000)
  } catch (e) {
    toastErr(errMsg(e))
  } finally {
    busy.value = false
  }
}

async function submit(): Promise<void> {
  const m = mobile.value.trim()
  if (!m || m.length !== 11) {
    toastErr('请输入正确的11位手机号')
    return
  }

  if (mode.value === 'password') {
    const p = password.value.trim()
    if (!p) {
      toastErr('请输入密码')
      return
    }
    busy.value = true
    try {
      const { is_running } = await auth.doLogin(m, p)
      toastOk(is_running ? '登录成功，机器人正在运行中' : '登录成功')
      bot.startPolling()
      router.push('/')
    } catch (e) {
      toastErr(errMsg(e))
    } finally {
      busy.value = false
    }
  } else {
    const code = smsCode.value.trim()
    if (!code || code.length !== 6) {
      toastErr('请输入6位验证码')
      return
    }
    busy.value = true
    try {
      const { is_running } = await auth.doLoginWithSms(m, code)
      toastOk(is_running ? '登录成功，机器人正在运行中' : '登录成功')
      bot.startPolling()
      router.push('/')
    } catch (e) {
      toastErr(errMsg(e))
    } finally {
      busy.value = false
    }
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card card">
      <div class="login-header">
        <h1>共享停车抢单</h1>
        <p>使用共享停车账号登录</p>
      </div>

      <div class="mode-tabs">
        <button
          type="button"
          class="mode-tab"
          :class="{ active: mode === 'sms' }"
          @click="mode = 'sms'"
        >
          验证码登录
        </button>
        <button
          type="button"
          class="mode-tab"
          :class="{ active: mode === 'password' }"
          @click="mode = 'password'"
        >
          密码登录
        </button>
      </div>

      <form class="login-form" @submit.prevent="submit">
        <div class="field">
          <label class="label" for="mobile">手机号</label>
          <input
            id="mobile"
            v-model="mobile"
            class="input"
            type="tel"
            maxlength="11"
            placeholder="请输入11位手机号"
            autocomplete="tel"
          />
        </div>

        <template v-if="mode === 'sms'">
          <div class="field field-row">
            <label class="label" for="sms">验证码</label>
            <div class="input-with-btn">
              <input
                id="sms"
                v-model="smsCode"
                class="input"
                type="text"
                inputmode="numeric"
                maxlength="6"
                placeholder="请输入6位验证码"
              />
              <button
                type="button"
                class="btn btn-outline btn-sms"
                :disabled="!canSendSms"
                @click="sendCode"
              >
                {{ countdown > 0 ? `${countdown}秒后重发` : '获取验证码' }}
              </button>
            </div>
          </div>
        </template>

        <template v-else>
          <div class="field">
            <label class="label" for="pwd">密码</label>
            <input
              id="pwd"
              v-model="password"
              class="input"
              type="password"
              placeholder="请输入密码"
              autocomplete="current-password"
            />
          </div>
        </template>

        <button
          type="submit"
          class="btn btn-primary btn-block btn-lg"
          :disabled="busy"
        >
          <span v-if="busy" class="spinner" />
          {{ busy ? '登录中…' : '登 录' }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.login-card {
  width: 100%;
  max-width: 380px;
  padding: 36px 28px;
}
.login-header {
  text-align: center;
  margin-bottom: 24px;
}
.login-header h1 {
  font-size: 22px;
  font-weight: 700;
}
.login-header p {
  font-size: 14px;
  color: var(--c-text2);
  margin-top: 4px;
}

.mode-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 24px;
  background: var(--c-bg2);
  padding: 4px;
  border-radius: var(--r-sm);
}
.mode-tab {
  flex: 1;
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  color: var(--c-text2);
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}
.mode-tab:hover {
  color: var(--c-text);
}
.mode-tab.active {
  background: var(--c-surface);
  color: var(--c-primary);
  box-shadow: var(--shadow);
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.field {
  display: flex;
  flex-direction: column;
}
.field-row .label {
  margin-bottom: 6px;
}
.input-with-btn {
  display: flex;
  gap: 8px;
}
.input-with-btn .input {
  flex: 1;
}
.btn-sms {
  flex-shrink: 0;
  min-width: 100px;
  white-space: nowrap;
}
</style>
