/**
 * 全局 toast 通知
 */
import { reactive } from 'vue'

interface Toast {
  id: number
  message: string
  type: 'success' | 'error' | 'info'
}

let _id = 0
const toasts = reactive<Toast[]>([])

function push(message: string, type: Toast['type'], ms = 3000): void {
  const id = ++_id
  toasts.push({ id, message, type })
  setTimeout(() => {
    const i = toasts.findIndex((t) => t.id === id)
    if (i >= 0) toasts.splice(i, 1)
  }, ms)
}

export function toast(msg: string): void { push(msg, 'info') }
export function toastOk(msg: string): void { push(msg, 'success') }
export function toastErr(msg: string): void { push(msg, 'error') }
export function useToasts() { return toasts }
