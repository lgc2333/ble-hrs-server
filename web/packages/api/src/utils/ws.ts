import type { StringOnly } from './event'
import { TypedCustomEvent, TypedEventTarget  } from './event'

export interface WsInfo {
  path: Record<string, string> | never
  params: Record<string, any> | never
  send: any | never
  recv: any | never
}
export type WsInfoMap = Record<string, WsInfo>

export type WsPath<O extends WsInfoMap> = StringOnly<keyof O>
export type WsPathParams<O extends WsInfoMap, K extends WsPath<O>> = O[K]['path']
export type WsQueryParams<O extends WsInfoMap, K extends WsPath<O>> = O[K]['params']
export type WsSendData<O extends WsInfoMap, K extends WsPath<O>> = O[K]['send']
export type WsRecvData<O extends WsInfoMap, K extends WsPath<O>> = O[K]['recv']

// eslint-disable-next-line ts/consistent-type-definitions
export type WebSocketClientEvents<M> = {
  open: TypedCustomEvent<'open', { event: Event }>
  close: TypedCustomEvent<'close', { event: CloseEvent }>
  error: TypedCustomEvent<'error', { event: Event }>
  parseError: TypedCustomEvent<'parseError', { event: Event; error: unknown }>
  message: TypedCustomEvent<'message', { data: M; event: MessageEvent }>
}

export interface WSOptionsCommon {
  reconnectDelay?: number
  webSocketFactory?: (url: string, protocols?: string | string[]) => WebSocket
}

export type WSCPathOptions<O extends WsInfoMap, K extends WsPath<O>> =
  WsPathParams<O, K> extends never ? {} : { path: WsPathParams<O, K> }
export type WSCQueryOptions<O extends WsInfoMap, K extends WsPath<O>> =
  WsQueryParams<O, K> extends never ? {} : { query: WsQueryParams<O, K> }
// prettier-ignore
export type WSCParamOptions<O extends WsInfoMap, K extends WsPath<O>> =
  WSCPathOptions<O, K> & WSCQueryOptions<O, K>

export type WSOptions<O extends WsInfoMap, K extends WsPath<O>> = WSOptionsCommon &
  WSCParamOptions<O, K>

export class WebSocketClient<
  O extends WsInfoMap,
  P extends WsPath<O>,
> extends TypedEventTarget<WebSocketClientEvents<WsRecvData<O, P>>> {
  static readonly defaultConnectDelay = 5000

  protected $ws: WebSocket | null = null
  protected $stopped: boolean = true
  protected $reconnectTimer: ReturnType<typeof setTimeout> | null = null

  constructor(
    protected $baseUrl: string,
    protected $path: P,
    protected $options: WSOptions<O, P>,
  ) {
    super()
  }

  get stopped(): boolean {
    return this.$stopped
  }

  get connected(): boolean {
    return this.$ws !== null && this.$ws.readyState === WebSocket.OPEN
  }

  buildUrl(): string {
    let path: string = this.$path
    if ('path' in this.$options) {
      for (const [k, v] of Object.entries(this.$options.path)) {
        path = path.replace(`{${k}}`, encodeURIComponent(v))
      }
    }

    let url = `${this.$baseUrl.replace(/\/+$/, '')}${path}`
    if ('query' in this.$options) {
      const params = Object.entries(this.$options.query)
        .map(
          ([key, value]) =>
            `${encodeURIComponent(key)}=${encodeURIComponent(`${value}`)}`,
        )
        .join('&')
      const hasAnd = url.includes('?')
      url += `${hasAnd ? '&' : '?'}${params}`
    }
    return url
  }

  protected $createWs(): WebSocket {
    if (this.$options.webSocketFactory) {
      return this.$options.webSocketFactory(this.buildUrl())
    }
    return new globalThis.WebSocket(this.buildUrl())
  }

  protected $setupWs() {
    this.$ws = this.$createWs()

    this.$ws.addEventListener('open', (event) => {
      this.dispatchEvent(new TypedCustomEvent('open', { detail: { event } }))
    })

    this.$ws.addEventListener('close', (event) => {
      this.$ws = null
      if (this.$stopped) return
      this.$reconnectTimer = setTimeout(
        () => this.reconnect(),
        this.$options.reconnectDelay ?? WebSocketClient.defaultConnectDelay,
      )
      this.dispatchEvent(new TypedCustomEvent('close', { detail: { event } }))
    })

    this.$ws.addEventListener('error', (event) => {
      this.dispatchEvent(new TypedCustomEvent('error', { detail: { event } }))
    })

    this.$ws.addEventListener('message', (event) => {
      let data: any
      try {
        data = JSON.parse(event.data)
      } catch (error) {
        this.dispatchEvent(
          new TypedCustomEvent('parseError', { detail: { event, error } }),
        )
        return
      }
      this.dispatchEvent(new TypedCustomEvent('message', { detail: { data, event } }))
    })

    return this.$ws
  }

  send<T extends WsPath<O>>(data: WsSendData<O, T>) {
    if (!this.$ws) throw new Error('WebSocket is not connected')
    this.$ws.send(JSON.stringify(data))
  }

  stop() {
    this.$stopped = true
    if (this.$ws) {
      this.$ws.close()
      this.$ws = null
    }
    if (this.$reconnectTimer) {
      clearTimeout(this.$reconnectTimer)
      this.$reconnectTimer = null
    }
  }

  reconnect() {
    this.stop()
    this.$stopped = false
    this.$setupWs()
  }

  start() {
    this.reconnect()
  }
}
