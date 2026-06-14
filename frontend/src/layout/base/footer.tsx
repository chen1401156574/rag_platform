import iconEdit from '@/assets/layout/edit.svg'
import footerBg from '@/assets/layout/footer-bg.svg'
import { userActions, userState } from '@/store/user'
import { storage } from '@/utils/storage'
import { Avatar } from 'antd'
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
      <img className="base-layout-footer__bg" src={footerBg} />
      <div className="base-layout-footer__main">
        <div className="header">
          <Avatar className="avatar" size="large">
            {user.username?.slice(0, 1).toUpperCase()}
          </Avatar>

          <img className="edit" src={iconEdit} onClick={handleLogout} />
        </div>

        <div className="body scrollbar-style">
          <div className="username">{user.username}</div>
        </div>

        <div className="footer"></div>
      </div>
    </div>
  )
}
