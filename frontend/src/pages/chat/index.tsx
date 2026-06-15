import * as api from '@/api'
import IconEdit from '@/assets/chat/edit.svg'
import Markdown from '@/components/markdown'
import ComPageLayout from '@/components/page-layout'
import ComSender from '@/components/sender'
import { ChatRole, ChatType } from '@/configs'
import { deviceActions } from '@/store/device'
import { usePageTransport } from '@/utils'
import { useMount, useRequest, useUnmount } from 'ahooks'
import { Button, Drawer } from 'antd'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { proxy, useSnapshot } from 'valtio'
import { sessionActions } from '../../store/session'
import ChatMessage from './component/chat-message'
import Citations from './component/citations'
import Contracts from './component/contracts'
import ChatDrawer from './component/drawer'
import Source from './component/source'
import styles from './index.module.scss'
import {
  CHAT_SESSION_STORAGE_KEY,
  createChatId,
  createChatIdText,
  transportToChatEnter,
} from './shared'

function scrollToBottom(
  container: HTMLDivElement | null,
  behavior: ScrollBehavior = 'auto',
) {
  if (!container) return

  const threshold = 200
  const distanceToBottom =
    container.scrollHeight -
    container.scrollTop -
    container.clientHeight

  if (distanceToBottom <= threshold) {
    container.scrollTo({
      top: container.scrollHeight,
      behavior,
    })
  }
}

type ChatRouteState = {
  sessionId?: string
  resetSessionAt?: number
  selectedAt?: number
}

type HistoryMessage = {
  user_question?: string
  model_answer?: string
  think?: string
  documents?: string
  recommended_questions?: string
  message_type?: string
  original_question?: string
  clarifications?: string
  clarifying_questions?: string[]
  legacy_merged_clarification?: boolean
}

function parseJsonArray<T>(value?: string): T[] {
  if (!value) return []
  try {
    const data = JSON.parse(value)
    return Array.isArray(data) ? (data as T[]) : []
  } catch (error) {
    console.error(error)
    return []
  }
}

function normalizeReferences(list?: API.Reference[]): API.Reference[] {
  return (list ?? []).map((item, index) => ({
    ...item,
    id: item.id ?? index + 1,
    document_id: item.document_id,
    document_name: item.document_name,
    content_with_weight: item.content_with_weight,
    positions: item.positions ?? [],
    page_num_int: item.page_num_int ?? [],
  }))
}

function documentsFromReferences(reference?: API.Reference[]): API.Document[] {
  const map = new Map<string, API.Document>()
  reference?.forEach((chunk) => {
    if (!chunk.document_id) return
    map.set(chunk.document_id, {
      document_id: chunk.document_id,
      document_name: chunk.document_name,
      content_with_weight: chunk.content_with_weight,
    })
  })
  return Array.from(map.values())
}

export default function Index() {
  const location = useLocation()
  const { data: ctx } = usePageTransport(transportToChatEnter)
  const contentRef = useRef<HTMLDivElement>(null)
  const initializedRef = useRef(false)
  const routeStateKeyRef = useRef<string | null>(null)
  const sessionIdRef = useRef<string | null>(null)

  const [chat] = useState(() => {
    return proxy({
      list: [] as API.ChatItem[],
    })
  })
  const { list } = useSnapshot(chat) as { list: API.ChatItem[] }
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [documents, setDocuments] = useState<API.Document[]>([])
  const [currentChatItem, setCurrentChatItem] = useState<API.ChatItem | null>(
    null,
  )
  const [read, setRead] = useState<API.Reference | null>(null)

  const history = useRequest(
    async (targetSessionId: string) => {
      const { data } = await api.session.detail({
        session_id: targetSessionId,
      })
      return data
    },
    {
      manual: true,
      onSuccess(data) {
        chat.list = []
        let lastDocuments: API.Document[] = []
        let lastAssistantItem: API.ChatItem | null = null

        data.forEach((item: HistoryMessage) => {
          const messageType = item.message_type || 'answer'
          const originalQuestion = item.original_question?.trim()
          const clarifications = item.clarifications?.trim()

          if (messageType === 'clarify') {
            const question = originalQuestion || item.user_question
            if (question) {
              chat.list.push({
                id: createChatId(),
                role: ChatRole.User,
                type: ChatType.Text,
                content: question,
              })
            }

            if (item.clarifying_questions?.length) {
              const assistantItem: API.ChatItem = {
                id: createChatId(),
                role: ChatRole.Assistant,
                type: ChatType.Document,
                clarifying_questions: item.clarifying_questions,
                original_question: question,
              }
              chat.list.push(assistantItem)
              lastAssistantItem = assistantItem
            }
            return
          }

          if (item.legacy_merged_clarification && originalQuestion) {
            chat.list.push({
              id: createChatId(),
              role: ChatRole.User,
              type: ChatType.Text,
              content: originalQuestion,
            })
            if (item.user_question) {
              chat.list.push({
                id: createChatId(),
                role: ChatRole.User,
                type: ChatType.Text,
                content: item.user_question,
                clarifications: clarifications || item.user_question,
                original_question: originalQuestion,
                legacy_merged_clarification: true,
              })
            }
          } else if (item.user_question) {
            chat.list.push({
              id: createChatId(),
              role: ChatRole.User,
              type: ChatType.Text,
              content: item.user_question,
              clarifications,
              original_question: originalQuestion,
            })
          }

          if (item.model_answer) {
            const reference = normalizeReferences(
              parseJsonArray<API.Reference>(item.documents),
            )
            const documents = documentsFromReferences(reference)
            const recommended_questions = parseJsonArray<string>(
              item.recommended_questions,
            )
            const assistantItem: API.ChatItem = {
              id: createChatId(),
              role: ChatRole.Assistant,
              type: ChatType.Document,
              content: item.model_answer,
              think: item.think,
              reference: reference,
              documents: documents?.length ? documents : undefined,
              recommended_questions: recommended_questions?.length
                ? recommended_questions
                : undefined,
            }
            chat.list.push(assistantItem)
            lastAssistantItem = assistantItem
            if (documents.length) {
              lastDocuments = documents
            }
          }
        })
        setDocuments(lastDocuments)
        setCurrentChatItem(lastAssistantItem)

        setTimeout(() => {
          if (contentRef.current) {
            contentRef.current.scrollTo({
              top: contentRef.current.scrollHeight,
            })
          }
        })
      },
    },
  )

  const loading = useMemo(() => {
    return list.some((o) => o.loading) || history.loading
  }, [list, history.loading])
  const loadingRef = useRef(loading)
  loadingRef.current = loading

  const resetChatView = useCallback(() => {
    chat.list = []
    setDocuments([])
    setCurrentChatItem(null)
    setRead(null)
  }, [chat])

  const setActiveSession = useCallback(
    (targetSessionId: string, loadHistory = true) => {
      sessionIdRef.current = targetSessionId
      localStorage.setItem(CHAT_SESSION_STORAGE_KEY, targetSessionId)
      setSessionId(targetSessionId)
      resetChatView()
      if (loadHistory) {
        history.run(targetSessionId)
      }
    },
    [history, resetChatView],
  )

  const ensureSession = useCallback(async () => {
    const storedSessionId = localStorage.getItem(CHAT_SESSION_STORAGE_KEY)
    if (sessionIdRef.current) {
      return sessionIdRef.current
    }
    if (storedSessionId) {
      sessionIdRef.current = storedSessionId
      setSessionId(storedSessionId)
      return storedSessionId
    }

    const { data } = await api.session.create()
    sessionIdRef.current = data.session_id
    localStorage.setItem(CHAT_SESSION_STORAGE_KEY, data.session_id)
    setSessionId(data.session_id)
    return data.session_id
  }, [])

  const activateSession = useCallback(
    async (routeState?: ChatRouteState | null, loadHistory = true) => {
      let targetSessionId = routeState?.sessionId
      let createdNew = false

      if (routeState?.resetSessionAt) {
        localStorage.removeItem(CHAT_SESSION_STORAGE_KEY)
        targetSessionId = undefined
      }

      if (!targetSessionId) {
        targetSessionId = localStorage.getItem(CHAT_SESSION_STORAGE_KEY) || undefined
      }

      if (!targetSessionId) {
        const { data } = await api.session.create()
        targetSessionId = data.session_id
        createdNew = true
      }

      setActiveSession(targetSessionId, loadHistory && !createdNew)
      return targetSessionId
    },
    [setActiveSession],
  )
  useEffect(() => {
    deviceActions.setChatting(loading)
  }, [loading])
  useUnmount(() => {
    deviceActions.setChatting(false)
  })

  const sendChat = useCallback(
    async (target: API.ChatItem, message: string, targetSessionId: string, clarify?: { clarifications: string; original_question: string }) => {
      setCurrentChatItem(target)
      target.loading = true
      let pendingContent = ''
      let pendingThinking = ''
      let flushFrame: number | null = null
      let scrollFrame: number | null = null

      const requestFrame = (callback: FrameRequestCallback) => {
        if (typeof window === 'undefined') {
          return setTimeout(() => callback(Date.now()), 16) as unknown as number
        }
        return window.requestAnimationFrame(callback)
      }

      const scheduleScroll = () => {
        if (scrollFrame !== null) return
        scrollFrame = requestFrame(() => {
          scrollFrame = null
          scrollToBottom(contentRef.current)
        })
      }

      const flushPending = () => {
        flushFrame = null
        if (pendingThinking) {
          target.think = `${target.think || ''}${pendingThinking}`
          pendingThinking = ''
        }
        if (pendingContent) {
          target.content = `${target.content || ''}${pendingContent}`
          pendingContent = ''
        }
        scheduleScroll()
      }

      const scheduleFlush = () => {
        if (flushFrame !== null) return
        flushFrame = requestFrame(flushPending)
      }

      try {
        //后端接口
        const res = await api.session.chat({
          id: targetSessionId,
          message,
          clarifications: clarify?.clarifications,
          original_question: clarify?.original_question,
        })
        sessionActions.updateKey()

        const reader = res.data.getReader()
        if (!reader) return

        await read(reader)
      } catch (error: unknown) {
        target.error = error instanceof Error ? error.message : 'Unknown error'
        throw error
      } finally {
        target.loading = false
      }

      async function read(reader: ReadableStreamDefaultReader<Uint8Array>) {
        let temp = ''
        const decoder = new TextDecoder('utf-8')
        while (true) {
          const { value, done } = await reader.read()
          if (value) {
            temp += decoder.decode(value, { stream: !done })
          } else if (done) {
            temp += decoder.decode()
          }

          while (true) {
            const index = temp.indexOf('\n')
            if (index === -1) break

            const slice = temp.slice(0, index)
            temp = temp.slice(index + 1)
            //我们只需要data开头的数据，流式数据
            if (slice.startsWith('data: ')) {
              parseData(slice)
            }
          }

          if (done) {
            temp
              .split('\n')
              .filter(Boolean)
              .forEach((slice) => {
                if (slice.startsWith('data: ')) {
                  parseData(slice)
                }
              })
            flushPending()
            console.debug('数据接受完毕', temp)
            target.loading = false
            break
          }
        }
      }

      function parseData(slice: string) {
        try {
          const str = slice
            .trim()
            .replace(/^data: /, '')
            .trim()
          if (str === '[DONE]') {
            return
          }

          const json = JSON.parse(str)
          if (json?.content) {
            if (json.thinking) {
              pendingThinking += json.content || ''
            } else {
              pendingContent += json.content || ''
            }
            scheduleFlush()
          }

          if (json?.documents?.length) {
            flushPending()
            const reference = normalizeReferences(json.documents)
            target.reference = reference

            const documents = documentsFromReferences(reference)
            target.documents = documents
            setDocuments(documents)
            scheduleScroll()
          }

          if (json?.clarifying_questions?.length) {
            flushPending()
            target.clarifying_questions = json.clarifying_questions
            target.original_question = json.original_question
            scheduleScroll()
          }

          if (json?.recommended_questions?.length) {
            flushPending()
            target.recommended_questions = json.recommended_questions
            scheduleScroll()
          }
        } catch {
          console.debug('解析失败')
          console.debug(slice)
        }
      }
    },
    [],
  )

  const send = useCallback(
    async (message: string, activeSessionId?: string) => {
      if (loadingRef.current) return
      if (!message) return

      const targetSessionId = activeSessionId || (await ensureSession())

      // 检测上一轮是否有待回答的追问
      const lastItem = chat.list[chat.list.length - 1]
      const pendingClarify =
        lastItem?.clarifying_questions?.length && lastItem?.original_question
          ? { clarifications: message, original_question: lastItem.original_question }
          : undefined

      if (chat.list.length === 0) {
        chat.list.push({
          id: createChatId(),
          role: ChatRole.User,
          type: ChatType.Text,
          content: message,
        })

        chat.list.push({
          id: createChatId(),
          role: ChatRole.Assistant,
          type: ChatType.Document,
          documents: [],
        })

        const target = chat.list[chat.list.length - 1]

        await sendChat(target, message, targetSessionId, pendingClarify)
      } else {
        chat.list.push({
          id: createChatId(),
          role: ChatRole.User,
          type: ChatType.Text,
          content: message,
        })

        chat.list.push({
          id: createChatId(),
          role: ChatRole.Assistant,
          type: ChatType.Document,
          content: '',
        })
        scrollToBottom(contentRef.current)

        const target = chat.list[chat.list.length - 1]

        await sendChat(target, message, targetSessionId, pendingClarify)
      }
    },
    [chat, ensureSession, sendChat],
  )
  useMount(async () => {
    const routeState = (location.state || null) as ChatRouteState | null
    routeStateKeyRef.current = routeState
      ? `${routeState.sessionId || ''}:${routeState.resetSessionAt || ''}:${routeState.selectedAt || ''}`
      : null
    const targetSessionId = await activateSession(routeState, !ctx?.data.message)
    initializedRef.current = true

    if (ctx?.data.message) {
      send(ctx.data.message, targetSessionId)
    }
  })

  useEffect(() => {
    if (!initializedRef.current) return

    const routeState = (location.state || null) as ChatRouteState | null
    if (!routeState?.sessionId && !routeState?.resetSessionAt) return
    const routeStateKey = `${routeState.sessionId || ''}:${routeState.resetSessionAt || ''}:${routeState.selectedAt || ''}`
    if (routeStateKeyRef.current === routeStateKey) return
    routeStateKeyRef.current = routeStateKey

    activateSession(routeState)
  }, [activateSession, location.state])

  useEffect(() => {
    const handleScroll = () => {
      const container = contentRef.current
      if (!container) return

      const anchors: {
        id: string
        top: number
        item: API.ChatItem
      }[] = []

      chat.list
        .filter((o) => o.type === ChatType.Document)
        .forEach((item, index) => {
          const id = createChatIdText(item.id)
          const dom = document.getElementById(id)
          if (!dom) return

          const domRect = dom.getBoundingClientRect()
          const containerRect = container.getBoundingClientRect()
          const relativeTop = domRect.top - containerRect.top

          if (index === 0 || relativeTop <= 80) {
            anchors.push({ id, top: relativeTop, item })
          }
        })

      if (anchors.length) {
        const current = anchors.reduce((prev, curr) =>
          curr.top > prev.top ? curr : prev,
        )

        setCurrentChatItem(current.item)
      }
    }

    const container = contentRef.current
    if (container) {
      container.addEventListener('scroll', handleScroll)
    }

    return () => {
      if (container) {
        container.removeEventListener('scroll', handleScroll)
      }
    }
  }, [])

  const title = useMemo(() => {
    return list[0]?.content ?? '新对话'
  }, [list[0]])

  return (
    <ComPageLayout
      contentRef={contentRef}
      sender={
        <>
          {documents.length > 0 && <Source list={documents} />}
          <ComSender
            loading={loading}
            sessionId={sessionId || undefined}
            onSend={send}
            onContract={() => setCurrentChatItem(null)}
          />
        </>
      }
      right={
        <>
          {currentChatItem && currentChatItem.reference?.length ? (
            <ChatDrawer title="引文">
              <Citations list={currentChatItem.reference} />
            </ChatDrawer>
          ) : (
            <ChatDrawer title="文档">
              <Contracts list={documents} />
            </ChatDrawer>
          )}
        </>
      }
    >
      <div className={styles['chat-page']}>
        <div className={styles['chat-page__header']}>
          <div className={styles['chat-page__header-title']}>{title}</div>
          <Button type="text" shape="circle">
            <img src={IconEdit} />
          </Button>
        </div>

        <ChatMessage
          list={list}
          onSend={send}
          onOpenCiations={setCurrentChatItem}
          onRefrence={setRead}
        />

        <Drawer
          title={read?.document_name ?? ''}
          width={800}
          onClose={() => setRead(null)}
          open={!!read}
          destroyOnClose
        >
          <Markdown value={read?.content_with_weight ?? ''} />
        </Drawer>
      </div>
    </ComPageLayout>
  )
}
