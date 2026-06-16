# LLM 提供商管理功能 - 实现计划

> **For agentic workers:** 使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐步实现。

**目标：** 在管理后台新增 OpenAI 兼容大模型端点注册、模型自动发现、系统配置页可选择注册模型的功能。

**架构：** 后端新增 `t_llm_provider` 表 + CRUD API + `/v1/models` 代理调用；前端系统配置页改为 Tab 布局，「系统配置」Tab 保持不变，「模型提供商」Tab 做全量管理。后端 `load_settings()` 动态注入提供商模型到 `ai.chat.candidates`。

**技术栈：** FastAPI + SQLAlchemy + Alembic（后端），React + TypeScript + Antd 风格的 shadcn/ui（前端）

---

## 文件结构

| 操作 | 文件路径 | 职责 |
|------|----------|------|
| 新建 | `backend/app/utils/crypto.py` | AES 加密/解密 API Key |
| 新建 | `backend/app/models/llm_provider.py` | ORM 模型 |
| 新建 | `backend/app/schemas/llm_provider.py` | Pydantic 请求/响应 schema |
| 新建 | `backend/app/router/llm_provider_rt.py` | CRUD + fetch-models + test API |
| 新建 | `backend/app/alembic/versions/e5f6a7b8c9d0_add_llm_provider.py` | 数据库迁移 |
| 修改 | `backend/app/models/__init__.py` | 注册新模型 |
| 修改 | `backend/app/app_main.py` | 注册新路由 |
| 修改 | `backend/app/service/settings_service.py` | 动态注入提供商模型 |
| 新建 | `frontend/src/services/llmProviderService.ts` | 前端 API 服务 |
| 修改 | `frontend/src/pages/admin/settings/SystemSettingsPage.tsx` | Tab 布局 + 提供商管理卡片 |

---

### Task 1: 加密工具

**Files:**
- Create: `backend/app/utils/crypto.py`

- [ ] **Step 1: 创建加密/解密工具模块**

```python
import os
import base64
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger("crypto")


def _get_fernet() -> Fernet:
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("ENCRYPTION_KEY 环境变量未设置，无法加解密 API Key")
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        raise RuntimeError(f"ENCRYPTION_KEY 格式无效: {e}")


def encrypt_api_key(plaintext: str) -> str:
    f = _get_fernet()
    token = f.encrypt(plaintext.encode("utf-8"))
    return base64.urlsafe_b64encode(token).decode("ascii")


def decrypt_api_key(ciphertext: str) -> str:
    f = _get_fernet()
    token = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
    return f.decrypt(token).decode("utf-8")
```

- [ ] **Step 2: 生成 Fernet key 提示**

在 `backend/.env.example` 中追加一行注释：

```
# 用于加密数据库中 LLM 提供商的 API Key，用 python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 生成
# ENCRYPTION_KEY=
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/utils/crypto.py backend/.env.example
git commit -m "feat: 新增 AES 加密工具用于 API Key 存储"
```

---

### Task 2: 数据库模型

**Files:**
- Create: `backend/app/models/llm_provider.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 创建 LLMProvider ORM 模型**

```python
import json
from sqlalchemy import Column, String, Text, DateTime, SmallInteger
from datetime import datetime
from models.base import Base


class LLMProvider(Base):
    __tablename__ = "t_llm_provider"

    id = Column(String(20), primary_key=True)
    name = Column(String(128), nullable=False)
    base_url = Column(String(512), nullable=False)
    encrypted_api_key = Column(Text, nullable=False)
    enabled_models = Column(Text, nullable=False, default="[]")
    is_active = Column(SmallInteger, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    def get_enabled_models(self) -> list[str]:
        try:
            models = json.loads(self.enabled_models)
            return models if isinstance(models, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_enabled_models(self, models: list[str]) -> None:
        self.enabled_models = json.dumps(models, ensure_ascii=False)
```

- [ ] **Step 2: 注册模型到 __init__.py**

在 `backend/app/models/__init__.py` 中添加：

```python
from models.llm_provider import LLMProvider
```

并在 `__all__` 列表末尾追加 `'LLMProvider'`。

- [ ] **Step 3: 提交**

```bash
git add backend/app/models/llm_provider.py backend/app/models/__init__.py
git commit -m "feat: 新增 LLMProvider 数据库模型"
```

---

### Task 3: 数据库迁移

**Files:**
- Create: `backend/app/alembic/versions/e5f6a7b8c9d0_add_llm_provider.py`

- [ ] **Step 1: 创建 Alembic 迁移文件**

```python
"""add llm provider table"""

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "t_llm_provider",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("base_url", sa.String(512), nullable=False),
        sa.Column("encrypted_api_key", sa.Text, nullable=False),
        sa.Column("enabled_models", sa.Text, nullable=False, server_default="[]"),
        sa.Column("is_active", sa.SmallInteger, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("t_llm_provider")
```

注意 `down_revision` 指向当前最新迁移 `d4e5f6a7b8c9`。

- [ ] **Step 2: 提交**

```bash
git add backend/app/alembic/versions/e5f6a7b8c9d0_add_llm_provider.py
git commit -m "feat: 添加 t_llm_provider 表迁移"
```

---

### Task 4: Pydantic Schema

**Files:**
- Create: `backend/app/schemas/llm_provider.py`

- [ ] **Step 1: 创建请求/响应 Schema**

```python
from pydantic import BaseModel
from typing import List, Optional


class LLMProviderCreateRequest(BaseModel):
    name: str
    base_url: str
    api_key: str


class LLMProviderUpdateRequest(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    enabled_models: Optional[List[str]] = None
    is_active: Optional[int] = None


class LLMProviderVO(BaseModel):
    id: str
    name: str
    base_url: str
    enabled_models: List[str]
    is_active: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/schemas/llm_provider.py
git commit -m "feat: 新增 LLM 提供商 Pydantic Schema"
```

---

### Task 5: API 路由

**Files:**
- Create: `backend/app/router/llm_provider_rt.py`

- [ ] **Step 1: 创建 LLM 提供商 CRUD + fetch-models + test 路由**

```python
import uuid
import httpx
from fastapi import APIRouter, Depends, Security
from fastapi_jwt import JwtAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select

from service.auth import access_security
from models.llm_provider import LLMProvider
from schemas.llm_provider import (
    LLMProviderCreateRequest,
    LLMProviderUpdateRequest,
    LLMProviderVO,
)
from utils.database import get_db
from utils.response import success_result, error_result
from utils.crypto import encrypt_api_key, decrypt_api_key

router = APIRouter()

MASKED_KEY = "****"


def _to_vo(provider: LLMProvider) -> dict:
    return {
        "id": provider.id,
        "name": provider.name,
        "base_url": provider.base_url,
        "api_key": MASKED_KEY,
        "enabled_models": provider.get_enabled_models(),
        "is_active": provider.is_active,
        "created_at": provider.created_at.isoformat() if provider.created_at else None,
        "updated_at": provider.updated_at.isoformat() if provider.updated_at else None,
    }


@router.get("/llm-providers/list")
async def list_providers(
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        rows = db.scalars(select(LLMProvider).order_by(LLMProvider.created_at.desc())).all()
        return success_result(data=[_to_vo(r) for r in rows])
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.post("/llm-providers/create")
async def create_provider(
    payload: LLMProviderCreateRequest,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        provider_id = str(uuid.uuid4()).replace("-", "")[:20]
        encrypted = encrypt_api_key(payload.api_key)
        provider = LLMProvider(
            id=provider_id,
            name=payload.name,
            base_url=payload.base_url.rstrip("/"),
            encrypted_api_key=encrypted,
        )
        db.add(provider)
        db.commit()
        return success_result(data=_to_vo(provider))
    except Exception as e:
        db.rollback()
        return error_result(code="500", message=str(e))


@router.put("/llm-providers/{provider_id}")
async def update_provider(
    provider_id: str,
    payload: LLMProviderUpdateRequest,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        provider = db.scalars(
            select(LLMProvider).where(LLMProvider.id == provider_id)
        ).first()
        if not provider:
            return error_result(code="404", message="提供商不存在")

        if payload.name is not None:
            provider.name = payload.name
        if payload.base_url is not None:
            provider.base_url = payload.base_url.rstrip("/")
        if payload.api_key is not None:
            provider.encrypted_api_key = encrypt_api_key(payload.api_key)
        if payload.enabled_models is not None:
            provider.set_enabled_models(payload.enabled_models)
        if payload.is_active is not None:
            provider.is_active = payload.is_active

        db.commit()
        return success_result(data=_to_vo(provider))
    except Exception as e:
        db.rollback()
        return error_result(code="500", message=str(e))


@router.delete("/llm-providers/{provider_id}")
async def delete_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        provider = db.scalars(
            select(LLMProvider).where(LLMProvider.id == provider_id)
        ).first()
        if not provider:
            return error_result(code="404", message="提供商不存在")
        db.delete(provider)
        db.commit()
        return success_result(message="已删除")
    except Exception as e:
        db.rollback()
        return error_result(code="500", message=str(e))


@router.post("/llm-providers/{provider_id}/fetch-models")
async def fetch_models(
    provider_id: str,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        provider = db.scalars(
            select(LLMProvider).where(LLMProvider.id == provider_id)
        ).first()
        if not provider:
            return error_result(code="404", message="提供商不存在")

        api_key = decrypt_api_key(provider.encrypted_api_key)
        url = f"{provider.base_url}/models"

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if resp.status_code != 200:
            detail = resp.text[:500]
            return error_result(code="400", message=f"获取模型列表失败 ({resp.status_code}): {detail}")

        data = resp.json()
        raw_models = data.get("data", []) if isinstance(data, dict) else []
        model_ids = sorted(
            {m["id"] for m in raw_models if isinstance(m, dict) and m.get("id")}
        )
        return success_result(data={"models": model_ids})
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.post("/llm-providers/{provider_id}/test")
async def test_connection(
    provider_id: str,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        provider = db.scalars(
            select(LLMProvider).where(LLMProvider.id == provider_id)
        ).first()
        if not provider:
            return error_result(code="404", message="提供商不存在")

        api_key = decrypt_api_key(provider.encrypted_api_key)
        url = f"{provider.base_url}/models"

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if resp.status_code == 200:
            return success_result(message="连接正常")
        return error_result(code="400", message=f"连接失败 ({resp.status_code})")
    except Exception as e:
        return error_result(code="500", message=str(e))
```

---

### Task 6: 注册路由和模型，集成 settings_service

**Files:**
- Modify: `backend/app/app_main.py`
- Modify: `backend/app/service/settings_service.py`

- [ ] **Step 1: 在 app_main.py 中注册路由**

添加 import（在现有 import 区域）：

```python
from router import llm_provider_rt
```

添加路由注册（在 `settings_rt` 注册行之后）：

```python
app.include_router(llm_provider_rt.router, prefix="/api/ragent", dependencies=ragent_admin_dependencies)
```

- [ ] **Step 2: 修改 load_settings() 动态注入提供商模型**

在 `backend/app/service/settings_service.py` 中，修改 `load_settings()` 函数，在 `ensure_default_chat_candidates(settings)` 之后添加：

```python
    # 从 t_llm_provider 动态注入模型候选
    try:
        from models.llm_provider import LLMProvider
        rows = db.scalars(
            select(LLMProvider).where(LLMProvider.is_active == 1)
        ).all()
        for p in rows:
            models = p.get_enabled_models()
            for model_id in models:
                settings["ai"]["chat"]["candidates"].append({
                    "id": model_id,
                    "provider": p.name,
                    "model": model_id,
                    "enabled": True,
                })
    except Exception:
        pass
```

- [ ] **Step 3: 修改 get_chat_openai_config() 支持提供商配置**

修改 `get_chat_openai_config()` 函数，在尝试 DeepSeek 环境变量之前，先检查当前选中的模型是否来自注册的提供商：

```python
def get_chat_openai_config(settings: dict[str, Any], fallback_model: str | None = None) -> dict[str, str | None]:
    model = fallback_model or get_chat_model(settings)

    # 优先查找注册的 LLM 提供商
    try:
        from models.llm_provider import LLMProvider
        from sqlalchemy import select as sa_select, create_engine
        from utils.database import engine
        from utils.crypto import decrypt_api_key
        with Session(engine) as db:
            rows = db.scalars(
                sa_select(LLMProvider).where(LLMProvider.is_active == 1)
            ).all()
            for p in rows:
                if model in p.get_enabled_models():
                    return {
                        "provider": p.name,
                        "base_url": p.base_url,
                        "api_key": decrypt_api_key(p.encrypted_api_key),
                        "model": model,
                    }
    except Exception:
        pass

    # 回退到 DeepSeek
    deepseek_config = _deepseek_chat_env_config()
    if deepseek_config:
        return deepseek_config

    # 最终回退到 DashScope
    return {
        "provider": "dashscope-openai-compatible",
        "base_url": _env_text("DASHSCOPE_BASE_URL"),
        "api_key": _env_text("DASHSCOPE_API_KEY"),
        "model": model,
    }
```

注意：需要在文件开头添加 `Session` 和 `engine` 的导入。但 `settings_service.py` 目前通过 db Session 参数访问数据库。对于 `get_chat_openai_config()` 来说，调用方可能没有传入 db session。我们需要另一种方式。

更好的做法是在 `get_chat_openai_config` 中自己创建数据库会话。需要修改函数签名来接受可选的 db session，或者在函数内部创建。

检查现有调用方式：

```python
def get_chat_openai_config(settings: dict[str, Any], fallback_model: str | None = None)
```

它不接收 db session。所以需要在函数内自己创建会话。

添加导入：
```python
from utils.database import SessionLocal
```

然后在函数中使用：
```python
db = SessionLocal()
try:
    # ... query providers
finally:
    db.close()
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/app_main.py backend/app/service/settings_service.py
git commit -m "feat: 注册 LLM 提供商路由，settings_service 集成动态模型注入"
```

---

### Task 7: 前端 API 服务层

**Files:**
- Create: `frontend/src/services/llmProviderService.ts`

- [ ] **Step 1: 创建前端 API 服务**

```typescript
import { api } from "@/services/api";

export interface LLMProvider {
  id: string;
  name: string;
  base_url: string;
  api_key: string;
  enabled_models: string[];
  is_active: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface FetchModelsResult {
  models: string[];
}

export async function listProviders(): Promise<LLMProvider[]> {
  return api.get<LLMProvider[], LLMProvider[]>("/llm-providers/list");
}

export async function createProvider(data: {
  name: string;
  base_url: string;
  api_key: string;
}): Promise<LLMProvider> {
  return api.post<LLMProvider, LLMProvider>("/llm-providers/create", data);
}

export async function updateProvider(
  id: string,
  data: {
    name?: string;
    base_url?: string;
    api_key?: string;
    enabled_models?: string[];
    is_active?: number;
  }
): Promise<LLMProvider> {
  return api.put<LLMProvider, LLMProvider>(`/llm-providers/${id}`, data);
}

export async function deleteProvider(id: string): Promise<void> {
  return api.delete<void, void>(`/llm-providers/${id}`);
}

export async function fetchProviderModels(id: string): Promise<FetchModelsResult> {
  return api.post<FetchModelsResult, FetchModelsResult>(
    `/llm-providers/${id}/fetch-models`
  );
}

export async function testProviderConnection(id: string): Promise<void> {
  return api.post<void, void>(`/llm-providers/${id}/test`);
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/services/llmProviderService.ts
git commit -m "feat: 新增 LLM 提供商前端 API 服务"
```

---

### Task 8: 前端系统配置页改造

**Files:**
- Modify: `frontend/src/pages/admin/settings/SystemSettingsPage.tsx`

- [ ] **Step 1: 添加 Tab 布局和模型提供商 Tab**

在文件顶部新增 import：

```typescript
import { Plus, Trash2, RefreshCw, Wifi, Settings2 } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import type { LLMProvider } from "@/services/llmProviderService";
import {
  listProviders,
  createProvider,
  updateProvider,
  deleteProvider,
  fetchProviderModels,
  testProviderConnection,
} from "@/services/llmProviderService";
```

- [ ] **Step 2: 将现有页面内容包裹在 Tabs 中**

将 `return` 中的整个 JSX 结构改为：

```tsx
return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <h1 className="admin-page-title">系统配置</h1>
          <p className="admin-page-subtitle">调整全局 RAG 检索、大模型参数与模型提供商</p>
        </div>
        <div className="admin-page-actions">
          <Button variant="outline" onClick={handleReset} disabled={saving}>
            <RotateCcw className="w-4 h-4 mr-2" />
            重置
          </Button>
          <Button className="admin-primary-gradient" onClick={handleSave} disabled={saving}>
            <Save className="w-4 h-4 mr-2" />
            {saving ? "保存中..." : "保存配置"}
          </Button>
        </div>
      </div>

      <Tabs defaultValue="settings" className="w-full">
        <TabsList className="mb-6">
          <TabsTrigger value="settings">
            <Settings2 className="w-4 h-4 mr-2" />
            系统配置
          </TabsTrigger>
          <TabsTrigger value="providers">
            <Wifi className="w-4 h-4 mr-2" />
            模型提供商
          </TabsTrigger>
        </TabsList>

        <TabsContent value="settings">
          {/* 现有的所有卡片内容保持不变，放在这里 */}
          ...
        </TabsContent>

        <TabsContent value="providers">
          <LLMProviderPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
```

- [ ] **Step 3: 实现 LLMProviderPanel 组件**

在同一文件内，`SystemSettingsPage` 函数之前，新增组件：

```tsx
function LLMProviderPanel() {
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formUrl, setFormUrl] = useState("");
  const [formKey, setFormKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [modelsModalId, setModelsModalId] = useState<string | null>(null);
  const [fetchedModels, setFetchedModels] = useState<string[]>([]);
  const [checkedModels, setCheckedModels] = useState<Set<string>>(new Set());
  const [fetchingModels, setFetchingModels] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      const data = await listProviders();
      setProviders(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const openCreate = () => {
    setEditingId(null);
    setFormName("");
    setFormUrl("");
    setFormKey("");
    setModalOpen(true);
  };

  const openEdit = (p: LLMProvider) => {
    setEditingId(p.id);
    setFormName(p.name);
    setFormUrl(p.base_url);
    setFormKey("");
    setModalOpen(true);
  };

  const handleSave = async () => {
    if (!formName.trim() || !formUrl.trim()) return;
    setSaving(true);
    try {
      if (editingId) {
        const data: Record<string, unknown> = { name: formName.trim(), base_url: formUrl.trim() };
        if (formKey.trim()) data.api_key = formKey.trim();
        await updateProvider(editingId, data);
      } else {
        if (!formKey.trim()) { toast.error("请输入 API Key"); setSaving(false); return; }
        await createProvider({ name: formName.trim(), base_url: formUrl.trim(), api_key: formKey.trim() });
      }
      setModalOpen(false);
      await load();
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteProvider(id);
      await load();
      toast.success("已删除");
    } catch (e) {
      console.error(e);
    }
  };

  const openModelsModal = async (p: LLMProvider) => {
    setModelsModalId(p.id);
    setFetchedModels([]);
    setCheckedModels(new Set(p.enabled_models));
    setFetchingModels(true);
    try {
      const result = await fetchProviderModels(p.id);
      setFetchedModels(result.models);
    } catch (e) {
      console.error(e);
    } finally {
      setFetchingModels(false);
    }
  };

  const saveModelSelection = async () => {
    if (!modelsModalId) return;
    try {
      await updateProvider(modelsModalId, { enabled_models: Array.from(checkedModels) });
      setModelsModalId(null);
      await load();
      toast.success("模型列表已更新");
    } catch (e) {
      console.error(e);
    }
  };

  const toggleModel = (modelId: string) => {
    setCheckedModels((prev) => {
      const next = new Set(prev);
      if (next.has(modelId)) next.delete(modelId);
      else next.add(modelId);
      return next;
    });
  };

  const handleTest = async (id: string) => {
    setTestingId(id);
    try {
      await testProviderConnection(id);
      toast.success("连接正常");
    } catch (e) {
      console.error(e);
    } finally {
      setTestingId(null);
    }
  };

  if (loading) return <div className="text-sm text-muted-foreground py-8">加载中...</div>;

  return (
    <>
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Wifi className="w-5 h-5" />
              模型提供商
            </CardTitle>
            <CardDescription>管理 OpenAI 兼容的大模型端点，自动发现可选模型</CardDescription>
          </div>
          <Button onClick={openCreate}>
            <Plus className="w-4 h-4 mr-2" />
            添加提供商
          </Button>
        </CardHeader>
        <CardContent>
          {providers.length === 0 ? (
            <div className="text-sm text-muted-foreground py-8 text-center">暂无提供商，点击上方按钮添加</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>名称</TableHead>
                  <TableHead>API 地址</TableHead>
                  <TableHead>启用模型</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="w-[280px]">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {providers.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium">{p.name}</TableCell>
                    <TableCell className="font-mono text-xs">{p.base_url}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {p.enabled_models.length === 0 ? (
                          <span className="text-xs text-muted-foreground">未配置</span>
                        ) : (
                          p.enabled_models.map((m) => (
                            <Badge key={m} variant="secondary" className="text-xs">{m}</Badge>
                          ))
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={p.is_active ? "default" : "secondary"}>
                        {p.is_active ? "启用" : "禁用"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Button variant="outline" size="sm" onClick={() => openEdit(p)}>编辑</Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openModelsModal(p)}
                        >
                          <RefreshCw className="w-3 h-3 mr-1" />
                          获取模型
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={testingId === p.id}
                          onClick={() => handleTest(p.id)}
                        >
                          {testingId === p.id ? "测试中..." : "测试"}
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => handleDelete(p.id)}>
                          <Trash2 className="w-3 h-3 text-red-500" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* 添加/编辑弹窗 */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingId ? "编辑提供商" : "添加提供商"}</DialogTitle>
            <DialogDescription>
              录入兼容 OpenAI 接口的大模型端点信息
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>名称</Label>
              <Input
                placeholder="例如：公司内部 DeepSeek"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>API 地址</Label>
              <Input
                placeholder="https://api.example.com/v1"
                value={formUrl}
                onChange={(e) => setFormUrl(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>API Key</Label>
              <Input
                type="password"
                placeholder={editingId ? "留空则不修改" : "请输入 API Key"}
                value={formKey}
                onChange={(e) => setFormKey(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setModalOpen(false)}>取消</Button>
            <Button disabled={saving} onClick={handleSave}>
              {saving ? "保存中..." : "保存"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 模型选择弹窗 */}
      <Dialog open={!!modelsModalId} onOpenChange={() => setModelsModalId(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>选择可用模型</DialogTitle>
            <DialogDescription>
              勾选需要启用的模型，系统将自动从该端点获取模型列表
            </DialogDescription>
          </DialogHeader>
          <div className="py-4 max-h-[400px] overflow-y-auto">
            {fetchingModels ? (
              <div className="text-sm text-muted-foreground text-center py-8">正在获取模型列表...</div>
            ) : fetchedModels.length === 0 ? (
              <div className="text-sm text-muted-foreground text-center py-8">未获取到模型</div>
            ) : (
              <div className="space-y-2">
                {fetchedModels.map((modelId) => (
                  <div key={modelId} className="flex items-center gap-3 rounded-lg border px-4 py-3">
                    <Checkbox
                      id={`model-${modelId}`}
                      checked={checkedModels.has(modelId)}
                      onCheckedChange={() => toggleModel(modelId)}
                    />
                    <Label htmlFor={`model-${modelId}`} className="font-mono text-sm cursor-pointer">
                      {modelId}
                    </Label>
                  </div>
                ))}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setModelsModalId(null)}>取消</Button>
            <Button disabled={fetchingModels} onClick={saveModelSelection}>保存选择</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
```

- [ ] **Step 4: 需要确认项目中是否存在 Tabs、Dialog、Checkbox、Badge 等 shadcn/ui 组件**

检查路径：
- `@/components/ui/tabs`
- `@/components/ui/dialog`
- `@/components/ui/checkbox`
- `@/components/ui/badge`

如果不存在，运行 `npx shadcn@latest add tabs dialog checkbox badge` 添加。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/admin/settings/SystemSettingsPage.tsx
git commit -m "feat: 系统配置页新增模型提供商 Tab"
```

---

### Task 9: 最终验证

- [ ] **Step 1: 启动后端验证 API**

```bash
cd backend && python -m app.app_main
```

验证端点：
- `GET /api/ragent/llm-providers/list` 返回空列表
- `POST /api/ragent/llm-providers/create` 创建提供商
- `POST /api/ragent/llm-providers/{id}/fetch-models` 获取模型
- `GET /api/ragent/rag/settings` 确认模型出现在 candidates 中

- [ ] **Step 2: 启动前端验证页面**

```bash
cd frontend && npm run dev
```

验证：
- 系统配置页有两个 Tab
- 模型提供商 Tab 可添加/编辑/删除提供商
- 获取模型功能正常
- 测试连接功能正常

- [ ] **Step 3: 提交最终修改**

```bash
git add -A
git commit -m "feat: LLM 提供商管理功能完成"
```
