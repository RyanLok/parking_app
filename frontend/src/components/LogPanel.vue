<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'

const props = defineProps<{ logs: string[] }>()

const expanded = ref(true)
const autoScroll = ref(true)
const containerRef = ref<HTMLElement | null>(null)

watch(() => props.logs.length, async () => {
  if (!autoScroll.value || !containerRef.value) return
  await nextTick()
  containerRef.value.scrollTop = containerRef.value.scrollHeight
})

function lineClass(line: string): string {
  if (/✅|成功|\[\+]/.test(line)) return 'l-ok'
  if (/\[-]|失败|过期|错误/.test(line)) return 'l-err'
  if (/🚗|⭐|抢到/.test(line)) return 'l-hit'
  if (/😴|⏰|休眠/.test(line)) return 'l-time'
  return ''
}
</script>

<template>
  <div class="log-panel card">
    <div class="log-header">
      <span>运行日志</span>
      <span class="log-meta">
        <span v-if="logs.length" class="log-count">{{ logs.length }} 条</span>
      </span>
    </div>

    <div v-if="expanded" class="log-body-wrap">
      <label class="auto-scroll-label">
        <input v-model="autoScroll" type="checkbox" /> 自动滚动
      </label>
      <div ref="containerRef" class="log-body">
        <div v-if="!logs.length" class="log-empty">暂无日志</div>
        <div v-for="(line, i) in logs" :key="i" class="log-line" :class="lineClass(line)">{{ line }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.log-panel { padding: 0; overflow: hidden; }
.log-header {
  width: 100%; padding: 14px 20px;
  display: flex; justify-content: space-between; align-items: center;
  background: transparent; border: none;
  font-size: 14px; font-weight: 600; color: var(--c-text);
}
.log-meta { display: flex; align-items: center; gap: 8px; }
.log-count { font-size: 12px; font-weight: 400; color: var(--c-text3); }


.log-body-wrap { border-top: 1px solid var(--c-border); padding: 12px 20px 20px; }
.auto-scroll-label {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--c-text3); margin-bottom: 8px; cursor: pointer;
}

.log-body {
  height: 220px;
  overflow-y: auto;
  padding: 12px;
  background: #0f172a;
  border-radius: var(--r-sm);
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.7;
}
.log-empty { color: #64748b; text-align: center; padding: 40px 0; }
.log-line { word-break: break-all; color: #94a3b8; }
.log-line.l-ok { color: #4ade80; }
.log-line.l-err { color: #f87171; }
.log-line.l-hit { color: #60a5fa; }
.log-line.l-time { color: #fbbf24; }
</style>
