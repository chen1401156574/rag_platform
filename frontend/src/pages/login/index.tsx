import * as api from '@/api'
import brandLogo from '@/assets/logo-brand.png'
import { Background } from '@/layout/base/background'
import { useAuthStore } from '@/stores/authStore'
import { Button, Flex, Form, Input, Tabs, TabsProps } from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import styles from './index.module.scss'

const IconUser = (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="rgba(0, 0, 0, 0.45)"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
    <circle cx="12" cy="7" r="4"></circle>
  </svg>
)

export default function Login() {
  const { user, login: loginWithPassword, isLoading } = useAuthStore()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<'login' | 'register'>('login')

  const [form] = Form.useForm<{
    username: string
    password: string
    repeatPassword: string
  }>()
  useEffect(() => {
    if (user?.username) {
      form.setFieldValue('username', user.username)
    }
  }, [form, user?.username])

  async function login() {
    const { username, password } = form.getFieldsValue()
    await loginWithPassword(username, password)
    navigate('/')
  }
  async function register() {
    const { username, password } = form.getFieldsValue()
    await api.user.register({ username, password })
    window.$app.message.success('注册成功，请登录')
    form.setFieldValue('password', '')
    form.setFieldValue('repeatPassword', '')
    setActiveTab('login')
  }

  const tabs: TabsProps['items'] = [
    {
      key: 'login',
      label: '登录',
      children: (
        <Form form={form} onFinish={login} layout="vertical">
          <div className={styles['login-title']}>欢迎回来</div>
          <Form.Item
            label="邮箱或用户名"
            name="username"
            rules={[{ required: true, message: '请输入邮箱或用户名' }]}
          >
            <Input
              className={styles['login-input']}
              value={form.getFieldValue('username')}
              onChange={(e) => form.setFieldValue('username', e.target.value)}
              placeholder="请输入邮箱或用户名"
              size="large"
              suffix={IconUser}
            />
          </Form.Item>
          <Form.Item
            label="密码"
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password
              className={styles['login-input']}
              value={form.getFieldValue('password')}
              onChange={(e) => {
                form.setFieldValue('password', e.target.value)
                form.setFieldValue('repeatPassword', '')
              }}
              placeholder="请输入密码"
              size="large"
            />
          </Form.Item>

          <Form.Item>
            <Button
              className={styles['login-button']}
              type="primary"
              htmlType="submit"
              size="large"
              loading={isLoading}
            >
              登录
            </Button>
          </Form.Item>
        </Form>
      ),
    },
    {
      key: 'register',
      label: '注册',
      children: (
        <Form form={form} onFinish={register} layout="vertical">
          <div className={styles['login-title']}>创建账户</div>
          <Form.Item
            label="邮箱或用户名"
            name="username"
            rules={[{ required: true, message: '请输入邮箱或用户名' }]}
          >
            <Input
              className={styles['login-input']}
              value={form.getFieldValue('username')}
              onChange={(e) => form.setFieldValue('username', e.target.value)}
              placeholder="请输入邮箱或用户名"
              size="large"
              suffix={IconUser}
            />
          </Form.Item>
          <Form.Item
            label="密码"
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password
              className={styles['login-input']}
              value={form.getFieldValue('password')}
              onChange={(e) => {
                form.setFieldValue('password', e.target.value)
                form.setFieldValue('repeatPassword', '')
              }}
              placeholder="请输入密码"
              size="large"
            />
          </Form.Item>
          <Form.Item
            label="重复密码"
            name="repeatPassword"
            rules={[
              { required: true, message: '请重复输入密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (value !== getFieldValue('password')) {
                    return Promise.reject(new Error('两次密码不一致'))
                  }
                  return Promise.resolve()
                },
              }),
            ]}
          >
            <Input.Password
              className={styles['login-input']}
              value={form.getFieldValue('repeatPassword')}
              onChange={(e) =>
                form.setFieldValue('repeatPassword', e.target.value)
              }
              placeholder="请重复输入密码"
              size="large"
            />
          </Form.Item>

          <Form.Item>
            <Button
              className={styles['login-button']}
              type="primary"
              htmlType="submit"
              size="large"
            >
              注册
            </Button>
          </Form.Item>
        </Form>
      ),
    },
  ]

  return (
    <Flex
      className={styles['login-page']}
      justify="center"
      align="center"
      style={{ minHeight: '100vh' }}
    >
      <Background />
      <div className={styles['login-shell']}>
        <section
          className={styles['login-copy']}
          aria-label="平台能力概览"
        >
          <div className={styles['login-copy__brand']}>
            <img src={brandLogo} alt="小桔充电 Logo" />
            <span>企业知识问答平台</span>
          </div>
          <div>
            <p className={styles['login-copy__eyebrow']}>RAG Knowledge Hub</p>
            <h1>让知识问答可引用、可追溯、可运营</h1>
            <p className={styles['login-copy__desc']}>
              面向员工的连续问答入口，也面向管理员提供知识库、入库任务、Prompt 与 Trace 的统一工作台。
            </p>
          </div>
          <div className={styles['login-copy__metrics']}>
            <div>
              <strong>引用</strong>
              <span>文档来源清晰可点</span>
            </div>
            <div>
              <strong>Trace</strong>
              <span>问答链路全程可查</span>
            </div>
            <div>
              <strong>Admin</strong>
              <span>运营配置集中管理</span>
            </div>
          </div>
        </section>

        <div className={styles['login-card']}>
          <div className={styles['login-brand']}>
            <img src={brandLogo} alt="小桔充电 Logo" />
            <span>企业知识问答平台</span>
          </div>
          <Tabs
            className={styles['login-tabs']}
            items={tabs}
            activeKey={activeTab}
            onChange={(key) => setActiveTab(key as 'login' | 'register')}
            destroyOnHidden
          />
        </div>
      </div>
    </Flex>
  )
}
