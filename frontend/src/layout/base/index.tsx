import iconNewchat from '@/assets/layout/newchat.svg'
import iconRepository from '@/assets/layout/repository.svg'
import logo from '@/assets/logo.png'
import { CHAT_SESSION_STORAGE_KEY } from '@/pages/chat/shared'
import { deviceState } from '@/store/device'
import { decodeJwtSubject, isAdminSubject } from '@/utils/auth'
import { storage as ragentStorage } from '@/utils/storage'
import { useNavigate } from 'react-router-dom'
import { useSnapshot } from 'valtio'
import { Background } from './background'
import { Footer } from './footer'
import './index.scss'
import { Nav } from './nav'

const TITLE = import.meta.env.VITE_TITLE

export function BaseLayout({ children }: { children?: React.ReactNode }) {
  const navigate = useNavigate()
  const device = useSnapshot(deviceState)
  const ragentUser = ragentStorage.getUser()
  const jwtSubject = decodeJwtSubject(ragentStorage.getToken())
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
        <div className="base-layout__logo">
          <img
            className="logo"
            src={logo}
            onClick={startNewChat}
          />
          <span className="title">{TITLE}</span>
        </div>

        <div className="base-layout__sidebar-main scrollbar-style">
          <div className="base-layout__sidebar-main-content">
            <div
              className="base-layout__nav-header"
              onClick={startNewChat}
            >
              <img className="base-layout__nav-header-icon" src={iconNewchat} />
              <span className="base-layout__nav-header-title">新对话</span>
            </div>

            <Nav />

            <div
              className="base-layout__nav-header"
              onClick={() => (device.chatting ? null : navigate('/repository'))}
            >
              <img
                className="base-layout__nav-header-icon"
                src={iconRepository}
              />
              <span className="base-layout__nav-header-title">知识库</span>
            </div>

            {showAdminEntry ? (
              <div
                className="base-layout__nav-header"
                onClick={() => (device.chatting ? null : navigate('/admin'))}
              >
                <img
                  className="base-layout__nav-header-icon"
                  src={iconNewchat}
                />
                <span className="base-layout__nav-header-title">管理后台</span>
              </div>
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
