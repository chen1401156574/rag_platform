import { useAuthStore } from '@/stores/authStore'
import { Navigate } from 'react-router-dom'
import { useRoute } from '../hook'

export function AuthGuard({ children }: { children?: React.ReactNode }) {
  const route = useRoute()
  const token = useAuthStore((state) => state.token)
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)

  if (!route?.auth) return children

  if (token || isAuthenticated) {
    return children
  }

  return <Navigate to="/login" />
}
