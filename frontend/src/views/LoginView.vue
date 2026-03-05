<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useBotStore } from '@/stores/bot'
import { errMsg } from '@/api'
import { toastErr, toastOk } from '@/composables/useToast'

const router = useRouter()
const auth = useAuthStore()
const bot = useBotStore()

const mobile = ref('')
const password = ref('')
const busy = ref(false)

async function submit(): Promise<void> {
  const m = mobile.value.trim()
  const p = password.value.trim()
  if (!m || !p) { toastErr('请输入手机号和密码'); return }
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
}
</script>

<template>
  <div class="login-page">
    <div class="login-card card">
      <div class="login-header">
        <h1>共享停车抢单</h1>
        <p>使用共享停车账号登录</p>
      </div>

      <form class="login-form" @submit.prevent="submit">
        <div class="field">
          <label class="label" for="mobile">手机号</label>
          <input id="mobile" v-model="mobile" class="input" type="tel" placeholder="请输入手机号" autocomplete="tel" />
        </div>
        <div class="field">
          <label class="label" for="pwd">密码</label>
          <input id="pwd" v-model="password" class="input" type="password" placeholder="请输入密码" autocomplete="current-password" />
        </div>
        <button type="submit" class="btn btn-primary btn-block btn-lg" :disabled="busy">
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
.login-card { width: 100%; max-width: 380px; padding: 36px 28px; }
.login-header { text-align: center; margin-bottom: 28px; }
.login-header h1 { font-size: 22px; font-weight: 700; }
.login-header p { font-size: 14px; color: var(--c-text2); margin-top: 4px; }
.login-form { display: flex; flex-direction: column; gap: 16px; }
.field { display: flex; flex-direction: column; }
</style>
