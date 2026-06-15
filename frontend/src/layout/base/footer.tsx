import { userActions, userState } from '@/store/user'
import { storage } from '@/utils/storage'
import { Avatar } from 'antd'
import { LogOut } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useSnapshot } from 'valtio'
import './footer.scss'

export function Footer() {
  const user = useSnapshot(userState)
  const navigate = useNavigate()

  const handleLogout = () => {
    storage.clearAuth()
    userActions.setToken(null)
    userActions.setUsername(null)
    navigate('/login')
  }

  return (
    <div className="base-layout-footer">
      <Avatar className="base-layout-footer__avatar" size={36}>
        {user.username?.slice(0, 1).toUpperCase()}
      </Avatar>
      <div className="base-layout-footer__body">
        <div className="username">{user.username || '未登录用户'}</div>
        <div className="role">Knowledge User</div>
      </div>
      <button
        type="button"
        className="base-layout-footer__logout"
        onClick={handleLogout}
        aria-label="退出登录"
        title="退出登录"
      >
        <LogOut size={16} />
      </button>
    </div>
  )
}
