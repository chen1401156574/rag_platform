import { Tag } from 'antd'
import Color from 'color'
import { useMemo } from 'react'
import { BRAND_COLORS } from '@/styles/brandTokens'

const map = {
  unparsed: {
    text: '未解析',
    color: BRAND_COLORS.warningText,
  },
  cancel: {
    text: '已取消',
    color: BRAND_COLORS.neutral600,
  },
  success: {
    text: '已完成',
    color: BRAND_COLORS.green700,
  },
  failed: {
    text: '异常',
    color: BRAND_COLORS.error,
  },
}

export function Status(props: { status: keyof typeof map }) {
  const { status } = props
  const { text, color } = useMemo(() => {
    return (
      map[status] ?? {
        color: BRAND_COLORS.neutral600,
        text: status,
      }
    )
  }, [status])

  const backgroundColor = useMemo(() => {
    return new Color(color).alpha(0.1).toString()
  }, [color])

  const borderColor = useMemo(() => {
    return new Color(color).alpha(0.3).toString()
  }, [color])

  return (
    <Tag style={{ borderColor, color, backgroundColor }}>{text}</Tag>
  )
}
