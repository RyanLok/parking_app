<script setup lang="ts">
/**
 * 单页配置：定位、目标选择、工作时间，全部在一个页面展示
 * 不再是 3 步向导，所有区块随时可编辑
 */
import { computed, unref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useConfigStore } from '@/stores/config'
import { useBotStore } from '@/stores/bot'
import { errMsg } from '@/api'
import { toastErr, toastOk } from '@/composables/useToast'

const router = useRouter()
const auth = useAuthStore()
const cfg = useConfigStore()
const bot = useBotStore()

const c = computed(() => unref(auth.config))
const hasCityId = computed(() => (c.value?.city_id ?? 0) > 0)

function updateField(field: string, value: string | number): void {
  cfg.patchConfig({ [field]: value })
}

async function handleSave(): Promise<void> {
  if (bot.status.is_running) {
    toastErr('请先停止机器人再修改配置')
    return
  }
  if (!cfg.canStart) {
    toastErr('请完成所有必填配置：' + cfg.missingFields.join('、'))
    return
  }
  try {
    const ok = await cfg.save()
    if (ok) {
      toastOk('配置已保存')
      await bot.fetchStatus()
      router.push('/')
    }
  } catch (e) {
    toastErr(errMsg(e))
  }
}
</script>

<template>
  <div class="config-page">
    <!-- ============ 1. 定位 ============ -->
    <section class="section card">
      <div class="section-head">
        <h2 class="section-title">
          <span class="section-num">1</span>
          定位坐标
        </h2>
        <span v-if="c?.lng && c?.lat" class="badge badge-ok">已填写</span>
        <span v-else class="badge badge-warn">未填写</span>
      </div>
      <p class="section-desc">从高德/百度地图获取目标位置坐标</p>
      <div class="row-2">
        <div class="field">
          <label class="label">经度</label>
          <input class="input" type="text" placeholder="113.430183" :value="c?.lng ?? ''" @input="updateField('lng', ($event.target as HTMLInputElement).value)" />
        </div>
        <div class="field">
          <label class="label">纬度</label>
          <input class="input" type="text" placeholder="23.181934" :value="c?.lat ?? ''" @input="updateField('lat', ($event.target as HTMLInputElement).value)" />
        </div>
      </div>
    </section>

    <!-- ============ 2. 城市 ============ -->
    <section class="section card">
      <div class="section-head">
        <h2 class="section-title">
          <span class="section-num">2</span>
          选择城市
        </h2>
        <span v-if="cfg.selectedCityName || hasCityId" class="badge badge-ok">{{ cfg.selectedCityName || '已配置' }}</span>
        <span v-else class="badge badge-warn">未选择</span>
      </div>

      <template v-if="cfg.selectedCityName || hasCityId">
        <div class="selected-row">
          <span class="selected-val">{{ cfg.selectedCityName || '城市 #' + c?.city_id }}</span>
          <button class="btn btn-ghost" @click="cfg.clearCity(); cfg.fetchCities()">换一个</button>
        </div>
      </template>
      <template v-else>
        <button class="btn btn-outline btn-block" :disabled="cfg.loadingCities || !c?.lng || !c?.lat" @click="cfg.fetchCities()">
          <span v-if="cfg.loadingCities" class="spinner" />
          {{ cfg.loadingCities ? '查询中…' : '根据定位查询城市' }}
        </button>
        <div v-if="cfg.cities.length" class="pick-list">
          <button v-for="city in cfg.cities" :key="city.id" class="pick-item" @click="cfg.selectCity(city)">
            {{ city.shortName }}
          </button>
        </div>
      </template>
    </section>

    <!-- ============ 3. 停车场 ============ -->
    <section class="section card" :class="{ 'section-disabled': !hasCityId }">
      <div class="section-head">
        <h2 class="section-title">
          <span class="section-num">3</span>
          选择停车场
        </h2>
        <span v-if="cfg.selectedParkName || (c?.park_id ?? 0) > 0" class="badge badge-ok">{{ cfg.selectedParkName || '已配置' }}</span>
        <span v-else class="badge badge-warn">{{ hasCityId ? '未选择' : '需先选城市' }}</span>
      </div>

      <template v-if="!hasCityId">
        <p class="section-desc">请先完成城市选择</p>
      </template>
      <template v-else-if="cfg.selectedParkName || (c?.park_id ?? 0) > 0">
        <div class="selected-row">
          <span class="selected-val">{{ cfg.selectedParkName || '停车场 #' + c?.park_id }}</span>
          <button class="btn btn-ghost" @click="cfg.clearPark(); cfg.fetchParks()">换一个</button>
        </div>
      </template>
      <template v-else>
        <button class="btn btn-outline btn-block" :disabled="cfg.loadingParks" @click="cfg.fetchParks()">
          <span v-if="cfg.loadingParks" class="spinner" />
          {{ cfg.loadingParks ? '加载中…' : '查询附近停车场' }}
        </button>
        <input v-if="cfg.parks.length" v-model="cfg.parkSearch" class="input search-input" type="text" placeholder="搜索停车场名称…" />
        <div v-if="cfg.filteredParks.length" class="park-grid">
          <button v-for="p in cfg.filteredParks" :key="p.id" class="park-card" @click="cfg.selectPark(p)">
            <div class="park-name">{{ p.name }}</div>
            <div class="park-addr">{{ p.shortAddress }}</div>
            <div class="park-meta">
              <span :class="{ 'meta-green': (p.availableSpaces ?? 0) > 0 }">余 {{ p.availableSpaces ?? 0 }}</span>
              <span>{{ Math.round(p.distance ?? 0) }}m</span>
            </div>
          </button>
        </div>
      </template>
    </section>

    <!-- ============ 4. 车牌 ============ -->
    <section class="section card">
      <div class="section-head">
        <h2 class="section-title">
          <span class="section-num">4</span>
          选择车牌
        </h2>
        <span v-if="cfg.selectedPlateNo || (c?.plate_id ?? 0) > 0" class="badge badge-ok">{{ cfg.selectedPlateNo || '已配置' }}</span>
        <span v-else class="badge badge-warn">未选择</span>
      </div>

      <template v-if="cfg.selectedPlateNo || (c?.plate_id ?? 0) > 0">
        <div class="selected-row">
          <span class="selected-val">{{ cfg.selectedPlateNo || '车牌 #' + c?.plate_id }}</span>
          <button class="btn btn-ghost" @click="cfg.clearPlate(); cfg.fetchPlates()">换一个</button>
        </div>
      </template>
      <template v-else>
        <button class="btn btn-outline btn-block" :disabled="cfg.loadingPlates || !c?.lng || !c?.lat" @click="cfg.fetchPlates()">
          <span v-if="cfg.loadingPlates" class="spinner" />
          {{ cfg.loadingPlates ? '加载中…' : '获取我的车牌' }}
        </button>
        <div v-if="cfg.plates.length" class="pick-list">
          <button v-for="p in cfg.plates" :key="p.bookPlateId" class="pick-item" @click="cfg.selectPlate(p)">
            {{ p.plateNo }}
          </button>
        </div>
      </template>
    </section>

    <!-- ============ 5. 工作时间 ============ -->
    <section class="section card">
      <div class="section-head">
        <h2 class="section-title">
          <span class="section-num">5</span>
          工作时间
        </h2>
      </div>
      <div class="row-2">
        <div class="field">
          <label class="label">开始</label>
          <input class="input" type="time" step="1" :value="c?.start_time ?? '08:00:00'" @input="updateField('start_time', ($event.target as HTMLInputElement).value)" />
        </div>
        <div class="field">
          <label class="label">结束</label>
          <input class="input" type="time" step="1" :value="c?.end_time ?? '10:30:00'" @input="updateField('end_time', ($event.target as HTMLInputElement).value)" />
        </div>
      </div>
      <div class="field" style="margin-top: 12px;">
        <label class="label">期望离开时间（过滤早于此释放的车位）</label>
        <input class="input" type="time" :value="c?.expect_leave_time ?? '19:00'" @input="updateField('expect_leave_time', ($event.target as HTMLInputElement).value)" />
      </div>
    </section>

    <!-- ============ 保存 ============ -->
    <div class="save-bar">
      <button class="btn btn-primary btn-block btn-lg" :disabled="cfg.saving" @click="handleSave">
        <span v-if="cfg.saving" class="spinner" />
        {{ cfg.saving ? '保存中…' : '保存配置' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.config-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section { padding: 20px; }
.section-disabled { opacity: .5; pointer-events: none; }

.section-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  flex: 1;
}
.section-num {
  width: 22px; height: 22px;
  background: var(--c-primary);
  color: #fff;
  border-radius: 50%;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.section-desc { font-size: 13px; color: var(--c-text2); margin-bottom: 12px; }

.row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.field { display: flex; flex-direction: column; }

.selected-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: #f0fdfa;
  border: 1px solid #99f6e4;
  border-radius: var(--r-sm);
}
.selected-val { color: var(--c-primary); font-weight: 600; font-size: 14px; }

.pick-list {
  margin-top: 10px;
  max-height: 180px;
  overflow-y: auto;
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
}
.pick-item {
  display: block;
  width: 100%;
  padding: 10px 14px;
  text-align: left;
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--c-border);
  font-size: 14px;
  cursor: pointer;
  transition: background .1s;
}
.pick-item:last-child { border-bottom: none; }
.pick-item:hover { background: #f0fdfa; color: var(--c-primary); }

.search-input { margin-top: 10px; }

.park-grid {
  margin-top: 10px;
  max-height: 320px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.park-card {
  text-align: left;
  padding: 12px 14px;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-sm);
  cursor: pointer;
  transition: border-color .15s;
}
.park-card:hover { border-color: var(--c-primary); }
.park-name { font-weight: 600; font-size: 14px; }
.park-addr { font-size: 12px; color: var(--c-text2); margin-top: 2px; }
.park-meta { font-size: 12px; color: var(--c-text3); margin-top: 4px; display: flex; gap: 12px; }
.meta-green { color: var(--c-green); font-weight: 500; }

.save-bar { padding-bottom: 20px; }
</style>
