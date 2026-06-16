import iconNewchat from '@/assets/layout/newchat.svg'
import iconRepository from '@/assets/layout/repository.svg'
import logo from '@/assets/logo-brand.png'
import { CHAT_SESSION_STORAGE_KEY } from '@/pages/chat/shared'
import { deviceState } from '@/store/device'
import { useAuthStore } from '@/stores/authStore'
import { decodeJwtSubject, isAdminSubject } from '@/utils/auth'
import { useNavigate } from 'react-router-dom'
import { useSnapshot } from 'valtio'
import { Background } from './background'
import { Footer } from './footer'
import './index.scss'
import { Nav } from './nav'

const TITLE = import.meta.env.VITE_TITLE || '企业知识问答'

export function BaseLayout({ children }: { children?: React.ReactNode }) {
  const navigate = useNavigate()
  const device = useSnapshot(deviceState)
  const { user: ragentUser, token } = useAuthStore()
  const jwtSubject = decodeJwtSubject(token)
  const showAdminEntry = isAdminSubject({
    role: ragentUser?.role ?? jwtSubject?.role,
    status: ragentUser?.status ?? jwtSubject?.status,
  })

  const startNewChat = () => {
    if (device.chatting) return
    localStorage.removeItem(CHAT_SESSION_STORAGE_KEY)
    navigate('/chat/', {
      state: { resetSessionAt: Date.now() },
    })
  }

  return (
    <div className="base-layout">
      <div className="base-layout__sidebar">
        <button
          type="button"
          className="base-layout__logo"
          onClick={startNewChat}
          aria-label="返回新对话"
        >
          <img
            className="logo"
            src={logo}
            alt="小桔充电 Logo"
          />
          <span className="base-layout__logo-copy">
            <span className="title">{TITLE}</span>
            <span className="subtitle">RAG Knowledge Hub</span>
          </span>
        </button>

        <div className="base-layout__sidebar-main scrollbar-style">
          <div className="base-layout__sidebar-main-content">
            <button
              type="button"
              className="base-layout__nav-header"
              onClick={startNewChat}
              disabled={device.chatting}
            >
              <img className="base-layout__nav-header-icon" src={iconNewchat} alt="" />
              <span className="base-layout__nav-header-title">新对话</span>
            </button>

            <Nav />

            <button
              type="button"
              className="base-layout__nav-header"
              onClick={() => (device.chatting ? null : navigate('/repository'))}
              disabled={device.chatting}
            >
              <img
                className="base-layout__nav-header-icon"
                src={iconRepository}
                alt=""
              />
              <span className="base-layout__nav-header-title">知识库</span>
            </button>

            {showAdminEntry ? (
              <button
                type="button"
                className="base-layout__nav-header"
                onClick={() => (device.chatting ? null : navigate('/admin'))}
                disabled={device.chatting}
              >
                <img
                  className="base-layout__nav-header-icon"
                  src={iconNewchat}
                  alt=""
                />
                <span className="base-layout__nav-header-title">管理后台</span>
              </button>
            ) : null}
          </div>

          <Footer />
        </div>
      </div>

      <div className="base-layout__content">{children}</div>

      <Background />
    </div>
  )
}
