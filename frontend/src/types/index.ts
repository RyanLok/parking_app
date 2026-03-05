/** 后端配置结构 */
export interface Config {
  mobile: string
  password_md5: string
  lng: string
  lat: string
  park_id: number
  city_id: number
  plate_id: number
  expect_leave_time: string
  start_time: string
  end_time: string
  poll_interval: number
  safe_cancel_advance: number
  /** 显示名称（随配置持久化，刷新后可回显） */
  city_name?: string
  park_name?: string
  plate_no?: string
}

/** 城市 */
export interface City {
  id: number
  shortName: string
}

/** 停车场 */
export interface Park {
  id: number
  name: string
  shortAddress?: string
  availableSpaces?: number
  distance?: number
}

/** 车牌 */
export interface Plate {
  bookPlateId: number
  plateNo: string
  id?: number
}

/** Bot 状态 */
export interface BotStatus {
  is_running: boolean
  status: string
  current_trade_no: string | null
  deadline_ts: number
}
