# 2026-06-15 Logo 驱动 UI 优化阶段记录

状态：完成

来源材料：[基于公司 Logo 的 UI 优化整体方向](../../design-docs/logo-driven-ui-optimization.md)

最近更新：2026-06-15

## 本次更新摘要

本次更新聚焦 Logo 驱动的前端主题最终收敛，不扩大到新页面重构：

| 范围 | 更新点 | 结果 |
| --- | --- | --- |
| Dashboard | KPI、趋势图容器、AI 性能环、质量快照、运营洞察 | 从通用蓝/sky/大圆角继续收敛到能源绿、电流青、阳光黄、中性浅底与 8px 工作台卡片 |
| 意图列表 | 筛选区、批量工具条、层级/状态徽章、路径节点、sticky 操作列 | 移除 Ant Design 旧蓝灰绿硬编码，表格 hover 与启用态统一使用品牌绿语义 |
| 知识库文档 | 文档状态、文件类型、上传投放区、预览 front matter、分块日志、批量操作浮层 | 深层文档管理区统一到品牌绿、充电橙、电流青和中性 token |
| Trace 观测 | Trace 详情、会话详情、会话列表、节点类型、复制入口、指标小面板 | 可追溯链路页面从残留 slate/emerald/amber/sky 收敛到品牌语义色 |
| 基础组件 | Dialog、AlertDialog、Dropdown、Textarea、登录页 SVG 与 Tabs 属性 | 弹窗 12px 例外保留，普通控件回到 8px 以内，登录页控制台警告收敛 |
| 最终验证 | 构建、lint 复查、旧色扫描、目标残留扫描、Chrome Playwright 路由回归 | 构建通过，旧主视觉关键词未检出，登录页和 10 个管理端路由在 1280px/375px 下无全局横向溢出 |
| 技术债 | Dashboard `finally` 分支 | 消除该文件的 `no-unsafe-finally`，剩余 lint 债务继续单独跟踪 |

## 阶段产出

- 前端主题入口已从蓝紫主色迁移到 Logo 驱动的品牌体系：能源绿、充电橙、电流青、字标墨蓝。
- Ant Design `ConfigProvider`、Tailwind HSL 变量、全局 CSS token 与旧变量兼容映射已统一到品牌语义。
- 新增正式品牌资产 `frontend/src/assets/logo-brand.png`，并接入登录页、用户端侧边栏和管理端侧边栏。
- 基础 Button、Input、Badge、Table、图表色序完成低噪声工作台风格收敛，默认主按钮改为深能源绿。
- 用户端 Chat 的发送按钮改为深充电橙，用户消息、引用、来源标签和文件选择浮层改为浅绿/绿灰体系。
- 登录页增加 Logo 与产品定位，背景和表单从蓝色渐变改为浅绿灰、白底、细边框和绿色主按钮。
- 管理端 Dashboard、知识库、Trace 列表与详情的高曝光蓝紫硬编码已迁移为绿色、青色、黄色和语义红。

## 追加实现

- 用户端知识库上传投放区继续收敛到品牌绿：上传图标、虚线边框、hover/拖拽浅底和“点击上传”文案不再使用旧蓝色。
- 用户端文档状态标签按品牌语义重新映射：未解析为等待黄，已取消为中性灰，已完成为能源绿，异常为语义红。
- 管理端入库任务的“新建通道任务”和“上传文件并进入通道”弹窗统一使用文件投放区，支持点击、拖拽、键盘 Enter/Space 触发、可见焦点、文件大小提示和重新选择。
- Trace 列表行内操作按钮移除残留靛蓝，改为能源绿文字与浅绿 hover 背景。
- Dashboard 面积图残留旧蓝色渐变已改为能源绿填充，意图列表层级徽章移除 Ant Design 旧蓝，改为能源绿、深电流青和等待黄的层级语义。
- Trace 详情瀑布图节点行支持键盘 Enter/Space 选中，并增加可见焦点环；节点输入、输出和额外数据 JSON 块新增复制入口，代码块限制最大高度并内部滚动。
- Trace 长表格恢复容器内部横向滚动，设置稳定最小宽度，避免九列数据在小屏被压缩；Trace Id 复制按钮支持键盘聚焦显现，hover/focus 状态收敛为浅绿底。
- Trace 列表样式中未定义的私有 CSS 变量已替换为现有 Trace token，避免意图名称和编码在浏览器中出现不可预期回退。
- 管理端意图列表继续收敛表格细节：筛选壳、批量工具条、意图编码徽章、路径节点、sticky 操作列和启用/禁用状态徽章统一使用中性 token、能源绿 hover 与品牌绿启用态，移除 Ant Design 旧灰绿硬编码。
- Dashboard 工作台继续收敛到 Logo 语义：主卡片圆角从 16px 收至 8px，时间窗口选中态改为深能源绿，KPI 内部面板、趋势图容器、质量快照和运营洞察统一使用浅绿灰/中性 token。
- Dashboard AI 性能状态色按品牌语义重映射：成功率环使用能源绿，关注态环使用阳光黄但数字文字使用深黄褐保证可读性，错误态保留语义红；慢响应率从通用 sky 蓝改为电流青。
- Dashboard 数据加载的 `finally` 分支移除 `return`，保留请求过期保护并消除该文件中的 `no-unsafe-finally` lint 问题。
- 管理端文档页深层区域完成补齐：文档状态点、文件类型图标、上传投放区、预览 front matter、分块日志状态/耗时卡片、批量操作浮层统一使用品牌 token。
- Trace 详情页补齐端到端链路卡、意图分类卡、瀑布图状态色、节点详情 JSON 块、指标条和时间线表头的品牌语义，节点详情保留可复制、可滚动的代码块。
- Trace 会话页、会话摘要、会话运行时间线、筛选栏、会话表格和运行表格继续收敛状态色、hover、复制 ID 和指标小面板，避免残留 sky/emerald/amber 语义漂移。
- 意图树节点选中态改为浅绿底和绿色边框，层级/类型徽章与意图列表、知识库 collection 徽章保持一致的品牌语义。
- 管理端布局、用户列表、Dashboard 高曝光残留色继续收敛；基础 Dialog/AlertDialog 遮罩、Textarea、Dropdown 圆角按“普通 8px、弹窗 12px”约束统一。
- 登录页 SVG 图标属性改为 React 写法，Ant Design Tabs 从 `destroyInactiveTabPane` 迁移到 `destroyOnHidden`，移除本轮 Playwright 中暴露的登录页控制台警告。
- 管理端顶栏移除 GitHub Star 外链与外部仓库请求，改为企业后台更需要的系统在线状态；顶栏保留知识库/文档搜索、返回聊天和用户菜单。
- 管理端全局搜索支持 `Ctrl+K` / `Meta+K` 聚焦，搜索占位文案从“筛选知识库”扩展为“搜索知识库或文档”，与实际搜索范围一致。
- 基础 `Input`、`Textarea` 和页面布局组件的空接口改为类型别名，减少本轮已触达 UI 组件的低风险 lint 噪声。

## 验证结果

- `npm run build` 通过。
- `frontend/src` 中旧蓝紫主色关键字扫描通过，未发现 `#1F70FE`、`#3b82f6`、`#2563eb`、`indigo`、`purple`、`violet` 等残留主视觉用法。
- 追加扫描通过，未发现 `#409EFF`、`#4f46e5`、`#6366f1`、`#8b5cf6`、`#7c3aed` 以及 `from-blue`、`from-indigo`、`from-purple` 等残留旧强调色。
- 本轮追加旧色扫描通过，`frontend/src` 未发现 `#91d5ff`、`#e6f7ff`、`#1890ff`、`#1677ff`、`#3b82f6`、`#2563eb`、`#1f70fe`、`#4f46e5`、`#6366f1`、`#8b5cf6`、`#7c3aed`、`indigo`、`purple`、`violet`、`from-blue`、`from-indigo`、`from-purple`、`text-blue`、`bg-blue`、`border-blue`、`ring-blue`、`blue-` 等旧主视觉关键词。
- Trace CSS 变量扫描通过，未发现 `--trace-font-xs`、`--trace-c-slate-*` 等未定义变量残留。
- 前期登录页浏览器检查通过：
  - 桌面宽度下登录卡片约 450px，无横向溢出。
  - 375px 移动宽度下登录卡片约 335px，无横向溢出。
  - 登录按钮计算背景色为 `rgb(0, 122, 54)`。
- 本轮登录页回归通过：
  - 桌面 1280px 下 `bodyScrollWidth` 等于 `bodyClientWidth`，无横向溢出。
  - 375px 移动宽度下 `bodyScrollWidth` 等于 `bodyClientWidth`，登录卡片约 335px，登录按钮高度约 54px。
  - 桌面和移动宽度下登录按钮计算背景色均为 `rgb(0, 122, 54)`，文字为白色。
- 本轮 Dashboard 与意图列表精确扫描通过，未发现 `#10B981`、`#F59E0B`、`#EF4444`、`sky-`、`rounded-2xl`、`rounded-xl`、`bg-slate-50`、`#d9d9d9`、`#fafafa`、`#8c8c8c`、`#b7eb8f`、`#f6ffed`、`#52C41A`、`#F9FAFB`、`rgba(226,232,240,1)` 等本轮目标残留。
- 本地 Vite 开发服务已在 `http://127.0.0.1:5173` 监听，`/admin/dashboard` 与 `/admin/intent-list` 均返回 200，且包含应用根节点 `#root`。
- 最终旧色扫描通过，`frontend/src` 未发现 `#91d5ff`、`#e6f7ff`、`#1890ff`、`#1677ff`、`#3b82f6`、`#2563eb`、`#1f70fe`、`#4f46e5`、`#6366f1`、`#8b5cf6`、`#7c3aed`、`indigo`、`purple`、`violet`、`from-blue`、`from-indigo`、`from-purple`、`text-blue`、`bg-blue`、`border-blue`、`ring-blue`、`blue-` 等旧主视觉关键词。
- 最终管理端残留扫描通过，`pages/admin`、`components/admin`、`components/ui` 与 `admin.css` 未发现 `bg-slate-50`、`rounded-2xl`、`rounded-3xl`、`bg-emerald`、`text-emerald`、`border-emerald`、`bg-amber`、`text-amber`、`border-amber`、`is-sky`、`is-emerald`、`is-rose`、`sky`、`emerald`、`amber` 等目标残留。
- `rounded-xl` 最终仅保留在 `admin.css` 弹窗内容层、`dialog.tsx` 和 `alert-dialog.tsx`，符合设计文档“弹窗可使用 12px”的例外约束。
- 使用本机 Chrome `149.0.7827.103` 执行 Playwright 回归，通过本地 mock 管理接口覆盖 `/login`、`/admin/dashboard`、`/admin/intent-tree`、`/admin/intent-list`、`/admin/knowledge`、`/admin/knowledge/kb-1`、`/admin/traces`、`/admin/traces/conversations/session-001`、`/admin/traces/runs/trace-001`、`/admin/ingestion`、`/admin/users`。
- Playwright 1280px 桌面与 375px 移动宽度均未发现全局横向溢出；登录页卡片宽度分别约 450px 与 335px，登录按钮计算背景色为 `rgb(0, 122, 54)`、文字为白色。
- Playwright 管理端路由均成功停留在目标路径并渲染 `admin-layout`；桌面与 375px 宽度下 `bodyScrollWidth`、`documentElement.scrollWidth` 均等于对应 clientWidth。
- 登录页复测后，SVG 属性与 Ant Design Tabs 弃用属性警告已消除；当前仅剩 React Router v7 future flag 提示，属于依赖升级提示。
- 本次继续收口后，`npm run build` 通过；`/login`、`/chat/`、`/admin/dashboard` 在 `Accept: text/html` 下均返回 200。
- 本次继续收口后，业务文件 raw hex 扫描、旧蓝紫主视觉关键词扫描和目标残留扫描均未命中；管理端顶栏已无 `GitHub`、`Star`、`stargazers`、`GitFork` 等外部仓库入口残留。
- 本次尝试连接 Browser 插件的内置浏览器 `iab` 仍不可用，因此未新增截图级回归；本轮以构建、HTTP 路由和静态扫描作为可执行验证范围。
- `npm run lint` 尚未通过，最新复查为 76 个问题（45 个 error、31 个 warning），失败仍集中在既有 TypeScript/ESLint 债务，包括 `any`、Hook 依赖、其他页面的 `no-unsafe-finally`、Fast Refresh 导出约束和少量未使用变量等，未作为本轮 UI 阶段完成门禁。

## 涉及文件

| 文件 | 说明 |
| --- | --- |
| `frontend/src/pages/admin/dashboard/DashboardPage.tsx` | Dashboard 工作台视觉语义、状态色与 `finally` lint 小修 |
| `frontend/src/pages/admin/intent-tree/IntentTreePage.tsx` | 意图树节点选中态、层级/类型徽章与品牌语义收敛 |
| `frontend/src/pages/admin/intent-tree/IntentListPage.tsx` | 意图列表筛选、徽章、路径节点、sticky 操作列和表格 hover 收敛 |
| `frontend/src/pages/admin/knowledge/KnowledgeDocumentsPage.tsx` | 文档状态、文件类型、上传投放区、预览、分块日志和批量浮层收敛 |
| `frontend/src/pages/admin/knowledge/KnowledgeListPage.tsx` | 知识库 collection 徽章品牌化 |
| `frontend/src/pages/admin/traces/RagTracePage.tsx` | Trace 会话列表统计、筛选与表格外壳品牌化 |
| `frontend/src/pages/admin/traces/RagTraceConversationPage.tsx` | Trace 会话详情指标、运行列表和复制入口品牌化 |
| `frontend/src/pages/admin/traces/RagTraceDetailPage.tsx` | Trace 详情瀑布图、端到端链路、意图卡、JSON 块和时间线表头收敛 |
| `frontend/src/pages/admin/traces/components/*` | 会话摘要、运行时间线、筛选栏、会话表格和运行表格状态语义统一 |
| `frontend/src/pages/admin/traces/traceUtils.ts` | Trace 状态、节点类型和徽章语义映射收敛 |
| `frontend/src/pages/admin/AdminLayout.tsx` | 管理端侧边栏、顶部工具与用户区域高曝光残留色收敛；移除 GitHub Star 外链并补齐全局搜索快捷键 |
| `frontend/src/pages/admin/users/UserListPage.tsx` | 用户列表状态和操作细节品牌化 |
| `frontend/src/components/ui/dialog.tsx`、`frontend/src/components/ui/alert-dialog.tsx` | 弹窗遮罩、边框和 12px 例外圆角统一 |
| `frontend/src/components/ui/dropdown-menu.tsx`、`frontend/src/components/ui/textarea.tsx` | 基础控件圆角回收 |
| `frontend/src/components/ui/input.tsx`、`frontend/src/components/page-layout/index.tsx` | 已触达基础 UI 组件的空接口 lint 噪声收敛 |
| `frontend/src/pages/login/index.tsx` | 登录页 React SVG 属性与 Tabs 弃用属性清理 |
| `frontend/src/admin.css` | 管理端 Trace、Dashboard、表格、下拉、侧边栏和统计卡 token 收敛 |
| `docs/exec-plans/completed/2026-06-15-logo-driven-ui-optimization.md` | 阶段记录、验证结果与后续衔接更新 |

## 后续衔接

- Logo 驱动 UI 优化的本轮范围已完成；后续新增页面和组件应继续按 `docs/design-docs/logo-driven-ui-optimization.md` 的 token、圆角、状态色和工作台密度约束落地。
- 可在后续独立任务补充截图基线或视觉快照，把登录页、Chat 页、Dashboard、意图列表、知识库列表、文档页、Trace 列表和 Trace 详情纳入持续回归。
- 现有 ESLint 债务建议单独登记或拆分修复，避免与 UI 主题迁移混在同一个变更面内。
