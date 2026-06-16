# LLM 提供商管理功能 - 设计文档

**日期：** 2026-06-16
**状态：** 待审核

---

## 1. 概述

在管理后台新增 LLM 提供商管理功能。管理员可录入兼容 OpenAI 接口的大模型端点（base_url + API key），系统自动通过 `/v1/models` 获取可用模型列表，管理员勾选要启用的模型后，这些模型自动出现在系统配置页面的模型选择下拉框中。

---

## 2. 数据库设计

### 2.1 新表：`t_llm_provider`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(20) | PK | UUID 风格主键 |
| name | String(128) | NOT NULL | 提供商名称 |
| base_url | String(512) | NOT NULL | OpenAI 兼容 API 地址 |
| encrypted_api_key | Text | NOT NULL | AES-256-CBC 加密存储的 API Key |
| enabled_models | JSON Text | NOT NULL, 默认 `[]` | 用户勾选的可用模型 ID 列表 |
| is_active | SmallInteger | 默认 1 | 是否启用 |
| created_at | DateTime | 默认 now | |
| updated_at | DateTime | 默认 now | |

### 2.2 迁移策略

在 `backend/app/alembic/versions/` 下新建 Alembic 迁移文件，创建 `t_llm_provider` 表。

---

## 3. 后端设计

### 3.1 加密工具 — `backend/app/utils/crypto.py`（新建）

- `encrypt_api_key(plaintext: str) -> str`：AES-256-CBC 加密，密钥从环境变量 `ENCRYPTION_KEY` 读取
- `decrypt_api_key(ciphertext: str) -> str`：AES-256-CBC 解密

### 3.2 ORM 模型 — `backend/app/models/llm_provider.py`（新建）

`LLMProvider` 类，映射到 `t_llm_provider` 表。遵循现有管理端模型的命名规范（字符串 ID、create_time/update_time）。

### 3.3 API 路由 — `backend/app/router/llm_provider_rt.py`（新建）

挂载路径：`/api/ragent/llm-providers`，全部需要 `require_admin` 鉴权。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/list` | 返回所有提供商（不含解密后的 API Key，显示 `****`） |
| POST | `/create` | 新增提供商 |
| PUT | `/{provider_id}` | 修改提供商信息 |
| DELETE | `/{provider_id}` | 删除提供商 |
| POST | `/{provider_id}/fetch-models` | 调用 `GET {base_url}/v1/models`，返回可用模型列表 |
| POST | `/{provider_id}/test` | 用已有模型调用 `GET {base_url}/v1/models` 测试连通性 |

请求/响应 schema 定义在 `backend/app/schemas/llm_provider.py`（新建）。

### 3.4 集成到系统配置 — 修改 `backend/app/service/settings_service.py`

修改 `load_settings()` 函数：
- 读完 `t_system_config` 后，查询所有 `is_active=1` 的 `LLMProvider`
- 将每个提供商下的 `enabled_models` 动态注入到 `ai.chat.candidates` 中，每条候选形如：
  ```json
  { "id": "deepseek-chat", "provider": "我的 DeepSeek", "model": "deepseek-chat", "enabled": true }
  ```

修改 `get_chat_openai_config()` 函数：
- 当选择的模型属于某个注册的提供商时，从该提供商读取 `base_url` 和解密后的 `api_key`

---

## 4. 前端设计

### 4.1 页面布局

系统配置页面 `SystemSettingsPage.tsx` 改为 **Tab 页签**布局：

- **Tab 1：系统配置** — 保留现有的所有卡片（RAG 参数、查询改写、限流、记忆管理、模型候选表格等）
- **Tab 2：模型提供商** — 全新的提供商管理界面

### 4.2 Tab 1：系统配置

现有页面的所有内容保持不变，放入第一个 Tab 中。

### 4.3 Tab 2：模型提供商

**列表视图：**
- 表格展示已录入的提供商：名称、地址、启用模型数、启用状态
- 操作按钮：编辑、删除、获取模型、测试连接
- 「添加提供商」按钮

**添加/编辑弹窗（Modal）：**
- 表单字段：名称（Input）、API 地址（Input, placeholder: `https://api.example.com/v1`）、API Key（Input.Password）
- 保存后自动关闭弹窗并刷新列表

**获取模型流程：**
- 点击「获取模型」→ 调用后端 fetch-models 接口 → 返回可用模型列表
- 弹窗展示可用模型列表，每行一个 checkbox，已勾选的为当前启用模型
- 用户可重新勾选/取消勾选，点击保存后更新 `enabled_models`

**测试连接流程：**
- 点击「测试连接」→ 调用后端 test 接口 → 显示成功/失败提示

### 4.4 后端集成说明

- 新增前端 API 服务文件：`llmProviderService.ts`
- 模型候选下拉框逻辑无需修改——后端已在 `load_settings()` 中动态注入

---

## 5. 数据流

```
管理员录入提供商(base_url + API key)
        ↓
后端 AES 加密 API key → 存入 t_llm_provider
        ↓
管理员点击「获取模型」→ 后端调用 /v1/models
        ↓
返回模型列表 → 管理员勾选要启用的模型 → 更新 enabled_models
        ↓
系统配置页加载时 → load_settings() 读取所有激活的提供商
        ↓
提供商模型动态注入 ai.chat.candidates
        ↓
用户在模型下拉框中看到所有注册的模型并选择
```

---

## 6. 安全考量

- API Key 使用 AES-256-CBC 加密存储，密钥通过环境变量 `ENCRYPTION_KEY` 注入
- 列表接口不返回解密后的 API Key
- 系统配置接口 `sanitize_for_response()` 继续移除敏感信息
- 所有管理接口需要 `require_admin` 鉴权

---

## 7. 错误处理

- fetch-models 时如果 base_url 不可达，返回明确错误提示
- 加密/解密失败时记录日志并返回通用错误
- `ENCRYPTION_KEY` 未配置时，应用启动给出警告并在首次使用时报错
