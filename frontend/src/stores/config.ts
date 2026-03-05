/**
 * 配置向导状态：城市、停车场、车牌选择
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as api from '@/api'
import { useAuthStore } from './auth'
import type { City, Park, Plate, Config } from '@/types'

export const useConfigStore = defineStore('config', () => {
  const auth = useAuthStore()

  const cities = ref<City[]>([])
  const parks = ref<Park[]>([])
  const plates = ref<Plate[]>([])
  const selectedCityName = ref('')
  const selectedParkName = ref('')
  const selectedPlateNo = ref('')
  const parkSearch = ref('')
  const loadingCities = ref(false)
  const loadingParks = ref(false)
  const loadingPlates = ref(false)
  const saving = ref(false)

  /** @returns 当前配置快捷引用 */
  function cfg(): Config | null { return auth.config }

  const filteredParks = computed(() => {
    const q = parkSearch.value.trim().toLowerCase()
    if (!q) return parks.value
    return parks.value.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        (p.shortAddress || '').toLowerCase().includes(q)
    )
  })

  const canStart = computed(() => {
    const c = cfg()
    if (!c) return false
    const ok = (v: unknown) => v !== '' && v != null && String(v).trim() !== ''
    const okId = (v: unknown) => typeof v === 'number' && v > 0
    const hasAuth = ok(c.mobile) && (ok(c.password_md5) || ok(c.token))
    return (
      hasAuth &&
      ok(c.lng) && ok(c.lat) &&
      okId(c.city_id) && okId(c.park_id) && okId(c.plate_id)
    )
  })

  const missingFields = computed(() => {
    const c = cfg()
    const list: string[] = []
    if (!c) return ['定位', '城市', '停车场', '车牌']
    const ok = (v: unknown) => v !== '' && v != null && String(v).trim() !== ''
    const okId = (v: unknown) => typeof v === 'number' && v > 0
    if (!ok(c.lng) || !ok(c.lat)) list.push('定位')
    if (!okId(c.city_id)) list.push('城市')
    if (!okId(c.park_id)) list.push('停车场')
    if (!okId(c.plate_id)) list.push('车牌')
    return list
  })

  function patchConfig(patch: Partial<Config>): void {
    const c = cfg()
    if (!c) return
    auth.config = { ...c, ...patch }
  }

  async function fetchCities(): Promise<void> {
    const c = cfg()
    if (!c?.lng?.trim() || !c?.lat?.trim()) return
    loadingCities.value = true
    try { cities.value = await api.getCities(c.lng, c.lat) }
    finally { loadingCities.value = false }
  }

  async function fetchParks(): Promise<void> {
    const c = cfg()
    if (!c || !(c.city_id > 0) || !c.lng?.trim() || !c.lat?.trim()) return
    loadingParks.value = true
    try { parks.value = await api.getParks(c.city_id, c.lng, c.lat) }
    finally { loadingParks.value = false }
  }

  async function fetchPlates(): Promise<void> {
    const c = cfg()
    if (!c?.lng?.trim() || !c?.lat?.trim()) return
    loadingPlates.value = true
    try { plates.value = await api.getPlates(c.lng, c.lat) }
    finally { loadingPlates.value = false }
  }

  function selectCity(city: City): void {
    patchConfig({ city_id: city.id, park_id: 0, city_name: city.shortName, park_name: '' })
    selectedCityName.value = city.shortName
    selectedParkName.value = ''
    cities.value = []
    parks.value = []
  }

  function selectPark(park: Park): void {
    patchConfig({ park_id: park.id, park_name: park.name })
    selectedParkName.value = park.name
    parks.value = []
    parkSearch.value = ''
  }

  function selectPlate(plate: Plate): void {
    patchConfig({ plate_id: plate.bookPlateId, plate_no: plate.plateNo })
    selectedPlateNo.value = plate.plateNo
    plates.value = []
  }

  function clearCity(): void {
    patchConfig({ city_id: 0, park_id: 0, city_name: '', park_name: '' })
    selectedCityName.value = ''
    selectedParkName.value = ''
    parks.value = []
  }

  function clearPark(): void {
    patchConfig({ park_id: 0, park_name: '' })
    selectedParkName.value = ''
    parkSearch.value = ''
  }

  function clearPlate(): void {
    patchConfig({ plate_id: 0, plate_no: '' })
    selectedPlateNo.value = ''
  }

  /** 从 config 恢复显示名称（页面刷新后调用） */
  function restoreNames(): void {
    const c = cfg()
    if (!c) return
    if (c.city_name && !selectedCityName.value) selectedCityName.value = c.city_name
    if (c.park_name && !selectedParkName.value) selectedParkName.value = c.park_name
    if (c.plate_no && !selectedPlateNo.value) selectedPlateNo.value = c.plate_no
  }

  async function save(): Promise<boolean> {
    const c = cfg()
    if (!c) return false
    saving.value = true
    try {
      await api.saveConfig(c)
      return true
    } finally {
      saving.value = false
    }
  }

  return {
    cities, parks, plates,
    selectedCityName, selectedParkName, selectedPlateNo,
    parkSearch, filteredParks,
    loadingCities, loadingParks, loadingPlates, saving,
    canStart, missingFields,
    patchConfig,
    fetchCities, fetchParks, fetchPlates,
    selectCity, selectPark, selectPlate,
    clearCity, clearPark, clearPlate,
    restoreNames, save,
  }
})
