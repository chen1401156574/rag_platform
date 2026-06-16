import logging
import time
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from router import chat_rt
from router import user_rt
from router import history_rt
from router import intent_rt
from router import user_admin_rt
from router import ragent_admin_rt
from router import settings_rt
from router import knowledge_admin_rt
from router import ingestion_rt
from router import trace_rt
from router import llm_provider_rt
from router import dashboard_rt
from service.auth import require_admin
from utils.database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app_main")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Startup: retry database table creation until success or max retries."""
    max_retries = 6
    for attempt in range(1, max_retries + 1):
        try:
            init_db()
            logger.info("数据库表初始化成功")
            
            # 执行旧知识库数据的桥接同步
            try:
                from utils.database import SessionLocal
                from service.knowledge_sync import sync_knowledge_data
                db = SessionLocal()
                try:
                    sync_knowledge_data(db)
                finally:
                    db.close()
            except Exception as sync_e:
                logger.error(f"启动时旧知识库数据同步失败: {sync_e}")
                
            break
        except Exception as e:
            logger.warning(f"数据库初始化尝试 {attempt}/{max_retries} 失败: {e}")
            if attempt < max_retries:
                time.sleep(5)
    else:
        logger.error("数据库表初始化最终失败，部分新表可能不可用")
    yield


# 从环境变量获取 root_path
root_path = os.getenv("ROOT_PATH", "http://localhost:8000")

app = FastAPI(root_path=root_path, lifespan=lifespan)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有源，生产环境中应该设置具体的源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头
)

app.include_router(chat_rt.router)
app.include_router(user_rt.router)
app.include_router(history_rt.router)

ragent_admin_dependencies = [Depends(require_admin)]
app.include_router(intent_rt.router, dependencies=ragent_admin_dependencies)
app.include_router(user_admin_rt.router, dependencies=ragent_admin_dependencies)

# Ragent 统一前端 API 前缀路由兼容
app.include_router(chat_rt.router, prefix="/api/ragent")
app.include_router(user_rt.router, prefix="/api/ragent")

app.include_router(intent_rt.router, prefix="/api/ragent", dependencies=ragent_admin_dependencies)
app.include_router(user_admin_rt.router, prefix="/api/ragent", dependencies=ragent_admin_dependencies)
app.include_router(settings_rt.router, prefix="/api/ragent", dependencies=ragent_admin_dependencies)
app.include_router(knowledge_admin_rt.router, prefix="/api/ragent", dependencies=ragent_admin_dependencies)
app.include_router(ingestion_rt.router, prefix="/api/ragent", dependencies=ragent_admin_dependencies)
app.include_router(trace_rt.router, prefix="/api/ragent", dependencies=ragent_admin_dependencies)
app.include_router(dashboard_rt.router, prefix="/api/ragent", dependencies=ragent_admin_dependencies)
app.include_router(llm_provider_rt.router, prefix="/api/ragent", dependencies=ragent_admin_dependencies)
app.include_router(ragent_admin_rt.router, prefix="/api/ragent", dependencies=ragent_admin_dependencies)

if __name__=='__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

