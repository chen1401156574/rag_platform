import { CHAT_SESSION_STORAGE_KEY } from '@/pages/chat/shared'
import { useMount } from 'ahooks'
import { useNavigate } from 'react-router-dom'

export default function Index() {
  const navigate = useNavigate()

  useMount(async () => {
    localStorage.removeItem(CHAT_SESSION_STORAGE_KEY)
    navigate('/chat/', {
      replace: true,
      state: { resetSessionAt: Date.now() },
    })
  })

  return null
}
