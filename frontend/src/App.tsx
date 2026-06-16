import { Router } from '@/router'
import { App as AntdApp, ConfigProvider, Spin } from 'antd'
import zhCN from 'antd/es/locale/zh_CN'
import { useCallback, useRef, useState } from 'react'
import { Toast } from '@/components/common/Toast'
import { BRAND_COLORS } from '@/styles/brandTokens'
function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        cssVar: true,
        token: {
          colorPrimary: BRAND_COLORS.green700,
          colorInfo: BRAND_COLORS.cyan700,
          colorSuccess: BRAND_COLORS.green700,
          colorWarning: BRAND_COLORS.yellow500,
          colorError: BRAND_COLORS.error,
          colorLink: BRAND_COLORS.green700,
          colorBgLayout: BRAND_COLORS.neutral050,
          colorText: BRAND_COLORS.ink900,
          colorTextSecondary: BRAND_COLORS.ink700,
          colorBorder: BRAND_COLORS.neutral200,
          borderRadius: 8,
        },
      }}
    >
      <AntdApp>
        <Router />
        <Toast />
        <MountApi />
      </AntdApp>
    </ConfigProvider>
  )
}

function MountApi() {
  window.$app = AntdApp.useApp()

  const [loading, setLoading] = useState(false)
  const [loadingText, setLoadingText] = useState('')
  const loadingCount = useRef(0)
  window.$showLoading = useCallback(({ title }: { title?: string } = {}) => {
    loadingCount.current++
    setLoading(true)
    setLoadingText(title ?? '')
  }, [])
  window.$hideLoading = useCallback(() => {
    loadingCount.current--
    setTimeout(() => {
      if (loadingCount.current <= 0) {
        setLoading(false)
        setLoadingText('')
      }
    }, 100)
  }, [])

  return (
    <>
      <Spin
        spinning={loading}
        tip={loadingText}
        fullscreen
        style={{
          zIndex: 9999999,
        }}
      ></Spin>
    </>
  )
}

export default App
