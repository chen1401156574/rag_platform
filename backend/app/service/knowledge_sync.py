import uuid
import logging
import os
from datetime import datetime
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from models.knowledge_admin import KnowledgeBaseAdmin, KnowledgeDocumentAdmin
from models.user import User

logger = logging.getLogger("knowledge_sync")

def sync_knowledge_data(db: Session):
    """
    将旧的 `knowledgebases` 表中的历史文件数据同步到新的 `t_knowledge_base` 和 `t_knowledge_document` 中，
    以便管理员在后台能够看到全局知识库、文档以及进行大盘统计。
    """
    try:
        # 1. 查询所有已有的旧知识库文件
        try:
            records = db.execute(text("SELECT id, user_id, file_name, created_at, updated_at FROM knowledgebases")).all()
        except Exception as e:
            logger.warning(f"无法读取 knowledgebases 表，可能表尚未创建: {e}")
            return

        if not records:
            logger.info("未发现需要同步的旧知识库数据")
            return

        logger.info(f"发现 {len(records)} 条旧知识库文件数据，开始进行同步...")

        for rec in records:
            # rec 结构: (id, user_id, file_name, created_at, updated_at)
            user_id_str = str(rec[1])
            file_name = rec[2]
            created_at = rec[3] or datetime.now()
            updated_at = rec[4] or datetime.now()

            # 根据 user_id 寻找用户名
            user_stmt = select(User).where(User.id == int(user_id_str) if user_id_str.isdigit() else 0)
            user_obj = db.execute(user_stmt).scalar_one_or_none()
            username = user_obj.username if user_obj else f"user_{user_id_str}"

            # 2. 检查或创建该用户的默认知识库
            kb_stmt = select(KnowledgeBaseAdmin).where(
                KnowledgeBaseAdmin.user_id == user_id_str,
                KnowledgeBaseAdmin.collection_name == user_id_str,
                KnowledgeBaseAdmin.deleted == 0
            )
            kb = db.execute(kb_stmt).scalar_one_or_none()

            if not kb:
                new_kb_id = str(uuid.uuid4()).replace("-", "")[:20]
                kb = KnowledgeBaseAdmin(
                    id=new_kb_id,
                    name="默认知识库",
                    user_id=user_id_str,
                    embedding_model="text-embedding-v3",
                    collection_name=user_id_str,
                    description="系统自动同步的默认知识库",
                    document_count=0,
                    created_by=username,
                    created_at=created_at,
                    updated_at=updated_at,
                    deleted=0
                )
                db.add(kb)
                db.flush()
                logger.info(f"为用户 {username} (ID: {user_id_str}) 创建默认知识库: {new_kb_id}")
            
            # 3. 检查或创建该文件对应的文档记录
            doc_stmt = select(KnowledgeDocumentAdmin).where(
                KnowledgeDocumentAdmin.kb_id == kb.id,
                KnowledgeDocumentAdmin.doc_name == file_name,
                KnowledgeDocumentAdmin.deleted == 0
            )
            doc = db.execute(doc_stmt).scalar_one_or_none()

            if not doc:
                file_type = file_name.split(".")[-1].lower() if "." in file_name else None
                new_doc_id = str(uuid.uuid4()).replace("-", "")[:20]
                
                # 尝试获取物理文件大小
                file_size = 0
                from service.core.api.utils.file_utils import get_project_base_directory
                physical_path = os.path.join(get_project_base_directory(), "storage/file", user_id_str, file_name)
                if os.path.exists(physical_path):
                    file_size = os.path.getsize(physical_path)
                
                doc = KnowledgeDocumentAdmin(
                    id=new_doc_id,
                    kb_id=kb.id,
                    doc_name=file_name,
                    source_type="file",
                    file_type=file_type,
                    file_size=file_size,
                    status="success",
                    enabled=1,
                    chunk_count=0,
                    created_by=username,
                    updated_by=username,
                    created_at=created_at,
                    updated_at=updated_at,
                    deleted=0
                )
                db.add(doc)
                kb.document_count += 1
                logger.info(f"同步文档 {file_name} 到知识库 {kb.id} 中")
        
        db.commit()
        logger.info("旧知识库数据同步完毕")
    except Exception as e:
        db.rollback()
        logger.error(f"旧知识库数据同步失败: {e}", exc_info=True)


def add_document_to_admin_kb(db: Session, user_id: str, file_name: str, file_size: int = 0):
    """
    当用户成功上传文档时，自动同步往 `t_knowledge_base` 和 `t_knowledge_document` 表中插入对应记录。
    新上传的文档即可立刻在后台管理中显示。
    """
    try:
        user_stmt = select(User).where(User.id == int(user_id) if user_id.isdigit() else 0)
        user_obj = db.execute(user_stmt).scalar_one_or_none()
        username = user_obj.username if user_obj else f"user_{user_id}"

        # 检查或创建默认知识库
        kb_stmt = select(KnowledgeBaseAdmin).where(
            KnowledgeBaseAdmin.user_id == user_id,
            KnowledgeBaseAdmin.collection_name == user_id,
            KnowledgeBaseAdmin.deleted == 0
        )
        kb = db.execute(kb_stmt).scalar_one_or_none()

        if not kb:
            new_kb_id = str(uuid.uuid4()).replace("-", "")[:20]
            kb = KnowledgeBaseAdmin(
                id=new_kb_id,
                name="默认知识库",
                user_id=user_id,
                embedding_model="text-embedding-v3",
                collection_name=user_id,
                description="系统自动生成的默认知识库",
                document_count=0,
                created_by=username,
                deleted=0
            )
            db.add(kb)
            db.flush()
            logger.info(f"创建默认知识库: {new_kb_id}")

        # 检查或创建文档记录
        doc_stmt = select(KnowledgeDocumentAdmin).where(
            KnowledgeDocumentAdmin.kb_id == kb.id,
            KnowledgeDocumentAdmin.doc_name == file_name,
            KnowledgeDocumentAdmin.deleted == 0
        )
        doc = db.execute(doc_stmt).scalar_one_or_none()

        if not doc:
            file_type = file_name.split(".")[-1].lower() if "." in file_name else None
            new_doc_id = str(uuid.uuid4()).replace("-", "")[:20]
            doc = KnowledgeDocumentAdmin(
                id=new_doc_id,
                kb_id=kb.id,
                doc_name=file_name,
                source_type="file",
                file_type=file_type,
                file_size=file_size,
                status="success",
                enabled=1,
                chunk_count=0,
                created_by=username,
                updated_by=username,
                deleted=0
            )
            db.add(doc)
            kb.document_count += 1
            db.commit()
            logger.info(f"同步新文档 {file_name} 到知识库 {kb.id} 中")
    except Exception as e:
        db.rollback()
        logger.error(f"同步新文档到管理员知识库失败: {e}", exc_info=True)
