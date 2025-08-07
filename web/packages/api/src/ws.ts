import type { WSOptions, WsPath } from './utils'
import { WebSocketClient } from './utils'

export interface WsHRMConnectionState {
  connected: boolean
}

export interface WsHRMData {
  t: number
  r: number
  s: boolean | null | undefined
}

// eslint-disable-next-line ts/consistent-type-definitions
export type ws = {
  '/api/v1/ws': {
    path: never
    params: never
    send: never
    recv: WsHRMConnectionState | WsHRMData
  }
}

export function createWs<P extends WsPath<ws>>(
  baseUrl: string,
  path: P,
  options: WSOptions<ws, P>,
): WebSocketClient<ws, P> {
  return new WebSocketClient<ws, P>(baseUrl, path, options)
}
