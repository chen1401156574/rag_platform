import { BaseLayout } from '@/layout/base'
import NotFound from '@/pages/404'
import Chat from '@/pages/chat'
import Index from '@/pages/index'
import Login from '@/pages/login'
import Repository from '@/pages/repository'
import { useEffect } from 'react'
import {
  Navigate,
  Outlet,
  RouteObject,
  createBrowserRouter,
  useLocation,
  useNavigate,
  useParams,
} from 'react-router-dom'
import { RouterGuard } from './guard'
import { AdminLayout } from '@/pages/admin/AdminLayout'
import { DashboardPage } from '@/pages/admin/dashboard/DashboardPage'
import { IngestionPage } from '@/pages/admin/ingestion/IngestionPage'
import { IntentEditPage } from '@/pages/admin/intent-tree/IntentEditPage'
import { IntentListPage } from '@/pages/admin/intent-tree/IntentListPage'
import { IntentTreePage } from '@/pages/admin/intent-tree/IntentTreePage'
import { KnowledgeChunksPage } from '@/pages/admin/knowledge/KnowledgeChunksPage'
import { KnowledgeDocumentsPage } from '@/pages/admin/knowledge/KnowledgeDocumentsPage'
import { KnowledgeListPage } from '@/pages/admin/knowledge/KnowledgeListPage'
import { QueryTermMappingPage } from '@/pages/admin/query-term-mapping/QueryTermMappingPage'
import { SampleQuestionPage } from '@/pages/admin/sample-questions/SampleQuestionPage'
import { SystemSettingsPage } from '@/pages/admin/settings/SystemSettingsPage'
import { RagTraceDetailPage } from '@/pages/admin/traces/RagTraceDetailPage'
import { RagTracePage } from '@/pages/admin/traces/RagTracePage'
import { UserListPage } from '@/pages/admin/users/UserListPage'
import { CHAT_SESSION_STORAGE_KEY } from '@/pages/chat/shared'
import { decodeJwtSubject, isAdminSubject } from '@/utils/auth'
import { storage } from '@/utils/storage'

export type IRouteObject = {
  children?: IRouteObject[]
  name?: string
  auth?: boolean
  pure?: boolean
  meta?: any
} & Omit<RouteObject, 'children'>

export const routes: IRouteObject[] = [
  {
    path: '/',
    Component: Index,
  },
  {
    path: '/chat/',
    Component: Chat,
  },
  {
    path: '/chat/:id',
    Component: LegacyChatRedirect,
  },
  {
    path: '/repository',
    Component: Repository,
  },
]

function Layout() {
  const location = useLocation()
  return (
    <BaseLayout>
      <RouterGuard>
        <Outlet key={location.pathname} />
      </RouterGuard>
    </BaseLayout>
  )
}

function LegacyChatRedirect() {
  const { id } = useParams()
  const navigate = useNavigate()

  useEffect(() => {
    if (id) {
      localStorage.setItem(CHAT_SESSION_STORAGE_KEY, id)
    }
    navigate('/chat/', {
      replace: true,
      state: id ? { sessionId: id, selectedAt: Date.now() } : undefined,
    })
  }, [id, navigate])

  return null
}

function AdminRoute() {
  const user = storage.getUser()
  const tokenSubject = decodeJwtSubject(storage.getToken())
  const subject = {
    role: user?.role ?? tokenSubject?.role,
    status: user?.status ?? tokenSubject?.status,
  }
  if (!isAdminSubject(subject)) {
    return <Navigate to="/" replace />
  }
  return (
    <RouterGuard>
      <AdminLayout />
    </RouterGuard>
  )
}

export const router = createBrowserRouter(
  [
    helper({
      path: '/',
      Component: Layout,
      children: routes,
    }),
    helper({
      path: '/login',
      Component: Login,
      auth: false,
    }),
    helper({
      path: '404',
      Component: NotFound,
      pure: true,
    }),
    helper({
      path: '/admin',
      Component: AdminRoute,
      children: [
        {
          index: true,
          element: <Navigate to="/admin/dashboard" replace />,
        },
        {
          path: 'dashboard',
          Component: DashboardPage,
        },
        {
          path: 'knowledge',
          Component: KnowledgeListPage,
        },
        {
          path: 'knowledge/:kbId',
          Component: KnowledgeDocumentsPage,
        },
        {
          path: 'knowledge/:kbId/docs/:docId',
          Component: KnowledgeChunksPage,
        },
        {
          path: 'intent-tree',
          Component: IntentTreePage,
        },
        {
          path: 'intent-list',
          Component: IntentListPage,
        },
        {
          path: 'intent-list/:id/edit',
          Component: IntentEditPage,
        },
        {
          path: 'ingestion',
          Component: IngestionPage,
        },
        {
          path: 'mappings',
          Component: QueryTermMappingPage,
        },
        {
          path: 'traces',
          Component: RagTracePage,
        },
        {
          path: 'traces/:traceId',
          Component: RagTraceDetailPage,
        },
        {
          path: 'users',
          Component: UserListPage,
        },
        {
          path: 'sample-questions',
          Component: SampleQuestionPage,
        },
        {
          path: 'settings',
          Component: SystemSettingsPage,
        },
      ]
    }),
    helper({
      path: '*',
      Component: NotFound,
    }),
  ],
  {
    basename: import.meta.env.BASE_URL,
  },
)

function helper(route: IRouteObject) {
  const _route = {
    ...route,
  }

  if (_route.children) {
    _route.children = _route.children.map((child: any) => helper(child))
  }

  if (_route.auth === undefined) {
    _route.auth = true
  }

  return _route as RouteObject
}
