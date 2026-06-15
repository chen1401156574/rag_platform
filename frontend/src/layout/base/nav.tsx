import * as api from '@/api'
import { CHAT_SESSION_STORAGE_KEY } from '@/pages/chat/shared'
import { sessionActions, sessionState } from '@/store/session'
import { useRequest } from 'ahooks'
import { Collapse } from 'antd'
import dayjs from 'dayjs'
import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSnapshot } from 'valtio'
import './nav.scss'

export function Nav() {
  const navigate = useNavigate()

  const session = useSnapshot(sessionState)

  useRequest(
    async () => {
      const { data } = await api.session.list(
        {},
        {
          loading: session.list.length ? false : true,
        },
      )
      return data
    },
    {
      refreshDeps: [sessionState.updateKey],
      onSuccess(data) {
        sessionActions.setList(data?.sessions || [])
      },
    },
  )

  const items = useMemo(
    () => [
      {
        key: '1',
        label: '历史会话',
        children: (
          <div>
            {session.list?.length ? (
              session.list.map((item) => (
                <button
                  type="button"
                  className="base-layout-nav__item"
                  key={item.session_id}
                  onClick={() => {
                    localStorage.setItem(CHAT_SESSION_STORAGE_KEY, item.session_id)
                    navigate('/chat/', {
                      state: {
                        sessionId: item.session_id,
                        selectedAt: Date.now(),
                      },
                    })
                  }}
                >
                  <span className="time">
                    {dayjs(item.created_at).format('HH:mm YYYY/MM/DD')}
                  </span>
                  <span className="title">{item.session_name}</span>
                </button>
              ))
            ) : (
              <div className="base-layout-nav__empty">暂无历史会话</div>
            )}
          </div>
        ),
      },
    ],
    [navigate, session.list],
  )

  return (
    <div className="base-layout-nav">
      <Collapse items={items} accordion />
    </div>
  )
}
