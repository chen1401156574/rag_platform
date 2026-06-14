import classNames from 'classnames'
import React, { PropsWithChildren, ReactNode } from 'react'
import './index.scss'

interface ComPageLayoutProps extends PropsWithChildren<{
  className?: string
  right?: ReactNode
  sender?: ReactNode
  contentRef?: React.RefObject<HTMLDivElement>
}> {}

export default function ComPageLayout(props: ComPageLayoutProps) {
  const { children, className, right, sender, contentRef, ...rest } = props
  return (
    <div className={classNames('com-page-layout', className)} {...rest}>
      <div className="com-page-layout__main">
        <div
          ref={contentRef}
          className="com-page-layout__main-content scrollbar-style"
        >
          {children}
        </div>

        <div className="com-page-layout__sender">{sender}</div>
      </div>
      {right ? <div className="com-page-layout__right">{right}</div> : null}
    </div>
  )
}
