import { PageTransportKey } from '@/utils'

export type ChatEnterData = {
  message: string
}

export const transportToChatEnter = Symbol() as PageTransportKey<{
  data: ChatEnterData
}>

export const CHAT_SESSION_STORAGE_KEY = 'swxy-current-session-id'

let id = 0

export const createChatId = () => {
  return ++id
}

export function createChatIdText(id: number) {
  return `chat-item-${id}`
}
