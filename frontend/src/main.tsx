import 'normalize.css'
import './styles/brand-tokens.css'
import './index.css'
import './antd.scss'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(<App />)
