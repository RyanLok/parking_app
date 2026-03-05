<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useBotStore } from '@/stores/bot'
import { useToasts } from '@/composables/useToast'
import { errMsg } from '@/api'
import { toastErr, toastOk } from '@/composables/useToast'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const bot = useBotStore()
const toasts = useToasts()

const showChrome = computed(() => route.name !== 'login')

const connClass = computed(() => {
  if (bot.connected === true) return 'dot-on'
  if (bot.connected === false) return 'dot-off'
  return 'dot-unknown'
})
const connLabel = computed(() => {
  if (bot.connected === true) return '引擎在线'
  if (bot.connected === false) return '未连接'
  return '检测中'
})

async function handleLogout(): Promise<void> {
  try {
    await auth.doLogout()
    bot.stopPolling()
    toastOk('已退出')
    router.push('/login')
  } catch (e) {
    toastErr(errMsg(e))
  }
}
</script>

<template>
  <div class="app-shell">
    <header v-if="showChrome" class="topbar">
      <div class="topbar-inner">
        <h1 class="brand">停车抢单</h1>

        <div class="conn" :class="connClass">
          <span class="conn-dot" />
          <span class="conn-text">{{ connLabel }}</span>
        </div>

        <nav class="nav-links">
          <router-link to="/" class="nav-link" active-class="active" :class="{ active: route.name === 'dashboard' }">控制台</router-link>
          <router-link to="/config" class="nav-link" active-class="active">配置</router-link>
        </nav>

        <button class="btn btn-ghost btn-logout" @click="handleLogout">退出</button>
      </div>
    </header>

    <main class="main-area">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <div class="toast-wrap">
      <div
        v-for="t in toasts"
        :key="t.id"
        class="toast-item"
        :class="`toast-${t.type}`"
      >{{ t.message }}</div>
    </div>
  </div>
</template>

<style scoped>
.app-shell { min-height: 100vh; display: flex; flex-direction: column; }

.topbar {
  background: var(--c-surface);
  border-bottom: 1px solid var(--c-border);
  box-shadow: var(--shadow);
  position: sticky; top: 0; z-index: 100;
}
.topbar-inner {
  max-width: 640px;
  margin: 0 auto;
  padding: 0 16px;
  height: 52px;
  display: flex;
  align-items: center;
  gap: 8px; /* Reduced gap for smaller screens */
}
.brand { 
  font-size: 16px; 
  font-weight: 700; 
  margin-right: auto;
  white-space: nowrap; /* Prevent title wrapping */
  flex-shrink: 0; 
}

.conn {
  display: flex; align-items: center; gap: 4px;
  font-size: 12px; color: var(--c-text3);
  white-space: nowrap;
}
.conn-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--c-text3); }
.dot-on .conn-dot { background: var(--c-green); }
.dot-off .conn-dot { background: var(--c-danger); }

.nav-links { display: flex; gap: 4px; }
.nav-link {
  padding: 6px 12px;
  border-radius: var(--r-sm);
  font-size: 13px;
  font-weight: 500;
  color: var(--c-text2);
  transition: background .15s, color .15s;
}
.nav-link:hover { background: #f3f4f6; color: var(--c-text); }
.nav-link.active { background: #f0fdfa; color: var(--c-primary); }

.btn-logout { font-size: 13px; color: var(--c-text3); }
.btn-logout:hover { color: var(--c-danger); }

.main-area {
  flex: 1;
  max-width: 640px;
  width: 100%;
  margin: 0 auto;
  padding: 20px 16px 40px;
}

.fade-enter-active, .fade-leave-active { transition: opacity .15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
