import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, Security, UploadFile
from fastapi_jwt import JwtAuthorizationCredentials
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from models.knowledge_admin import KnowledgeBaseAdmin, KnowledgeDocumentAdmin
from service.auth import access_security
from utils.database import get_db
from utils.response import error_result, success_result

router = APIRouter()


def _uid() -> str:
    return str(uuid.uuid4()).replace("-", "")[:20]


def _page(records: list[dict[str, Any]], total: int, current: int = 1, size: int = 10) -> dict[str, Any]:
    ps = max(size, 1)
    return {"records": records, "total": total, "size": size, "current": current, "pages": (total + ps - 1) // ps}


def _dt(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _safe_count(db: Session, model, *filters) -> int:
    try:
        q = select(func.count()).select_from(model)
        if filters:
            q = q.where(and_(*filters))
        return db.scalar(q) or 0
    except Exception:
        return 0


def _safe_scalars(db: Session, query):
    try:
        return db.scalars(query).all()
    except Exception:
        return []


def _safe_get(db: Session, model, pk):
    try:
        return db.get(model, pk)
    except Exception:
        return None


def _kb_record(kb: KnowledgeBaseAdmin) -> dict[str, Any]:
    return {
        "id": kb.id, "name": kb.name, "embeddingModel": kb.embedding_model,
        "collectionName": kb.collection_name, "createdBy": kb.created_by,
        "documentCount": kb.document_count or 0,
        "createTime": _dt(kb.created_at), "updateTime": _dt(kb.updated_at),
    }


def _doc_record(doc: KnowledgeDocumentAdmin) -> dict[str, Any]:
    return {
        "id": doc.id, "kbId": doc.kb_id, "docName": doc.doc_name,
        "sourceType": doc.source_type, "sourceLocation": doc.source_location,
        "scheduleEnabled": doc.schedule_enabled, "scheduleCron": doc.schedule_cron,
        "enabled": bool(doc.enabled), "chunkCount": doc.chunk_count or 0,
        "fileUrl": doc.file_url, "fileType": doc.file_type, "fileSize": doc.file_size,
        "processMode": doc.process_mode, "chunkStrategy": doc.chunk_strategy,
        "chunkConfig": doc.chunk_config, "pipelineId": doc.pipeline_id,
        "status": doc.status, "createdBy": doc.created_by, "updatedBy": doc.updated_by,
        "createTime": _dt(doc.created_at), "updateTime": _dt(doc.updated_at),
        "chunksEdited": bool(doc.chunks_edited),
    }


# ── Knowledge Base CRUD ──

@router.get("/knowledge-base/page")
@router.get("/knowledge-base")
async def list_knowledge_bases(
    current: int = 1, size: int = 10, name: Optional[str] = None,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        page = max(current, 1)
        page_size = max(size, 1)
        filters = [KnowledgeBaseAdmin.deleted == 0]
        if name:
            filters.append(KnowledgeBaseAdmin.name.ilike(f"%{name}%"))
        total = _safe_count(db, KnowledgeBaseAdmin, *filters)
        rows = _safe_scalars(
            db,
            select(KnowledgeBaseAdmin).where(and_(*filters))
            .order_by(KnowledgeBaseAdmin.updated_at.desc(), KnowledgeBaseAdmin.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )
        return success_result(data=_page([_kb_record(r) for r in rows], total, page, page_size))
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.get("/knowledge-base/{kb_id}")
async def get_knowledge_base(
    kb_id: str, db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        kb = _safe_scalars(db, select(KnowledgeBaseAdmin).where(KnowledgeBaseAdmin.id == kb_id, KnowledgeBaseAdmin.deleted == 0))
        if not kb:
            return error_result(code="404", message="知识库不存在")
        return success_result(data=_kb_record(kb[0]))
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.post("/knowledge-base")
async def create_knowledge_base(
    payload: dict[str, Any], db: Session = Depends(get_db),
    credentials: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        username = credentials.subject.get("user_name", "admin")
        kb = KnowledgeBaseAdmin(
            id=_uid(), name=payload.get("name", ""),
            user_id=str(credentials.subject.get("user_id", "")),
            embedding_model=payload.get("embeddingModel"),
            collection_name=payload.get("collectionName"),
            description=payload.get("description"), created_by=username,
        )
        db.add(kb); db.commit()
        return success_result(data=kb.id)
    except Exception as e:
        db.rollback(); return error_result(code="500", message=str(e))


@router.put("/knowledge-base/{kb_id}")
async def update_knowledge_base(
    kb_id: str, payload: dict[str, Any], db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        rows = _safe_scalars(db, select(KnowledgeBaseAdmin).where(KnowledgeBaseAdmin.id == kb_id, KnowledgeBaseAdmin.deleted == 0))
        if not rows:
            return error_result(code="404", message="知识库不存在")
        kb = rows[0]
        if "name" in payload: kb.name = payload["name"]
        if "embeddingModel" in payload: kb.embedding_model = payload["embeddingModel"]
        if "collectionName" in payload: kb.collection_name = payload["collectionName"]
        kb.updated_at = datetime.now(); db.commit()
        return success_result(data=None)
    except Exception as e:
        db.rollback(); return error_result(code="500", message=str(e))


@router.delete("/knowledge-base/{kb_id}")
async def delete_knowledge_base(
    kb_id: str, db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        rows = _safe_scalars(db, select(KnowledgeBaseAdmin).where(KnowledgeBaseAdmin.id == kb_id, KnowledgeBaseAdmin.deleted == 0))
        if not rows:
            return error_result(code="404", message="知识库不存在或已删除")
        kb = rows[0]
        kb.deleted = 1; kb.updated_at = datetime.now()
        doc_rows = _safe_scalars(db, select(KnowledgeDocumentAdmin).where(KnowledgeDocumentAdmin.kb_id == kb_id, KnowledgeDocumentAdmin.deleted == 0))
        
        from sqlalchemy import text
        for d in doc_rows:
            d.deleted = 1; d.updated_at = datetime.now()
            # 级联删除旧 knowledgebases 表对应记录
            try:
                db.execute(
                    text("DELETE FROM knowledgebases WHERE user_id = :user_id AND file_name = :file_name"),
                    {"user_id": kb.user_id, "file_name": d.doc_name}
                )
            except Exception:
                pass
                
        db.commit()
        return success_result(data=None)
    except Exception as e:
        db.rollback(); return error_result(code="500", message=str(e))


# ── Document CRUD ──

@router.get("/knowledge-base/{kb_id}/docs")
@router.get("/knowledge-base/{kb_id}/documents")
async def list_documents(
    kb_id: str, current: int = 1, size: int = 10,
    status: Optional[str] = None, keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        page = max(current, 1)
        page_size = max(size, 1)
        filters = [KnowledgeDocumentAdmin.kb_id == kb_id, KnowledgeDocumentAdmin.deleted == 0]
        if status: filters.append(KnowledgeDocumentAdmin.status == status)
        if keyword: filters.append(KnowledgeDocumentAdmin.doc_name.ilike(f"%{keyword}%"))
        total = _safe_count(db, KnowledgeDocumentAdmin, *filters)
        rows = _safe_scalars(
            db,
            select(KnowledgeDocumentAdmin).where(and_(*filters))
            .order_by(KnowledgeDocumentAdmin.updated_at.desc(), KnowledgeDocumentAdmin.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )
        return success_result(data=_page([_doc_record(r) for r in rows], total, page, page_size))
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.get("/knowledge-base/docs/search")
async def search_documents(
    keyword: str = "", limit: int = 8,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        filters = [KnowledgeDocumentAdmin.deleted == 0]
        if keyword: filters.append(KnowledgeDocumentAdmin.doc_name.ilike(f"%{keyword}%"))
        rows = _safe_scalars(db, select(KnowledgeDocumentAdmin).where(and_(*filters)).limit(limit))
        records = [{"id": d.id, "kbId": d.kb_id, "docName": d.doc_name, "kbName": d.kb_id} for d in rows]
        return success_result(data=records)
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.get("/knowledge-base/docs/{doc_id}")
async def get_document(
    doc_id: str, db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        rows = _safe_scalars(db, select(KnowledgeDocumentAdmin).where(KnowledgeDocumentAdmin.id == doc_id, KnowledgeDocumentAdmin.deleted == 0))
        if not rows:
            return error_result(code="404", message="文档不存在")
        return success_result(data=_doc_record(rows[0]))
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.post("/knowledge-base/{kb_id}/docs/upload")
async def upload_document(
    kb_id: str,
    sourceType: str = Form("file"),
    file: Optional[UploadFile] = File(None),
    sourceLocation: Optional[str] = Form(None),
    scheduleEnabled: Optional[str] = Form(None),
    scheduleCron: Optional[str] = Form(None),
    processMode: Optional[str] = Form("chunk"),
    chunkStrategy: Optional[str] = Form(None),
    chunkConfig: Optional[str] = Form(None),
    pipelineId: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    credentials: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        username = credentials.subject.get("user_name", "admin")
        doc_name = file.filename if file is not None else (sourceLocation or "untitled")
        file_type = None
        if file and file.filename and "." in file.filename:
            file_type = file.filename.rsplit(".", 1)[-1].lower()
        doc = KnowledgeDocumentAdmin(
            id=_uid(), kb_id=kb_id, doc_name=doc_name,
            source_type=sourceType, source_location=sourceLocation,
            file_type=file_type, process_mode=processMode,
            chunk_strategy=chunkStrategy, chunk_config=chunkConfig,
            pipeline_id=pipelineId,
            schedule_enabled=1 if scheduleEnabled in ("true", "True", "1") else 0,
            schedule_cron=scheduleCron, status="success",
            created_by=username, updated_by=username,
        )
        db.add(doc)
        kb_rows = _safe_scalars(db, select(KnowledgeBaseAdmin).where(KnowledgeBaseAdmin.id == kb_id))
        if kb_rows:
            kb_rows[0].document_count = (kb_rows[0].document_count or 0) + 1
        db.commit()
        return success_result(data=_doc_record(doc))
    except Exception as e:
        db.rollback(); return error_result(code="500", message=str(e))


@router.put("/knowledge-base/docs/{doc_id}")
async def update_document(
    doc_id: str, payload: dict[str, Any],
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        rows = _safe_scalars(db, select(KnowledgeDocumentAdmin).where(KnowledgeDocumentAdmin.id == doc_id, KnowledgeDocumentAdmin.deleted == 0))
        if not rows:
            return error_result(code="404", message="文档不存在")
        doc = rows[0]
        if "docName" in payload: doc.doc_name = payload["docName"]
        if "processMode" in payload: doc.process_mode = payload["processMode"]
        if "chunkStrategy" in payload: doc.chunk_strategy = payload["chunkStrategy"]
        if "chunkConfig" in payload: doc.chunk_config = payload["chunkConfig"]
        if "pipelineId" in payload: doc.pipeline_id = payload["pipelineId"]
        if "sourceLocation" in payload: doc.source_location = payload["sourceLocation"]
        if "scheduleEnabled" in payload: doc.schedule_enabled = 1 if payload["scheduleEnabled"] else 0
        if "scheduleCron" in payload: doc.schedule_cron = payload["scheduleCron"]
        doc.updated_at = datetime.now(); db.commit()
        return success_result(data=None)
    except Exception as e:
        db.rollback(); return error_result(code="500", message=str(e))


@router.patch("/knowledge-base/docs/{doc_id}/enable")
async def toggle_document(
    doc_id: str, value: bool = True,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        rows = _safe_scalars(db, select(KnowledgeDocumentAdmin).where(KnowledgeDocumentAdmin.id == doc_id, KnowledgeDocumentAdmin.deleted == 0))
        if rows:
            rows[0].enabled = 1 if value else 0; db.commit()
        return success_result(data={"id": doc_id, "enabled": value})
    except Exception as e:
        db.rollback(); return error_result(code="500", message=str(e))


@router.delete("/knowledge-base/docs/{doc_id}")
async def delete_document(
    doc_id: str, db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        rows = _safe_scalars(db, select(KnowledgeDocumentAdmin).where(KnowledgeDocumentAdmin.id == doc_id, KnowledgeDocumentAdmin.deleted == 0))
        if not rows:
            return error_result(code="404", message="文档不存在或已删除")
        doc = rows[0]
        doc.deleted = 1; doc.updated_at = datetime.now()
        
        kb_rows = _safe_scalars(db, select(KnowledgeBaseAdmin).where(KnowledgeBaseAdmin.id == doc.kb_id))
        if kb_rows:
            kb = kb_rows[0]
            if kb.document_count and kb.document_count > 0:
                kb.document_count -= 1
                
            # 级联删除旧 knowledgebases 表对应记录
            from sqlalchemy import text
            try:
                db.execute(
                    text("DELETE FROM knowledgebases WHERE user_id = :user_id AND file_name = :file_name"),
                    {"user_id": kb.user_id, "file_name": doc.doc_name}
                )
            except Exception:
                pass
                
        db.commit()
        return success_result(data=None)
    except Exception as e:
        db.rollback(); return error_result(code="500", message=str(e))


@router.post("/knowledge-base/docs/{doc_id}/chunk")
async def trigger_chunk(doc_id: str, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=doc_id)


@router.get("/knowledge-base/docs/{doc_id}/preview")
async def preview_document(
    doc_id: str, db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        rows = _safe_scalars(db, select(KnowledgeDocumentAdmin).where(KnowledgeDocumentAdmin.id == doc_id, KnowledgeDocumentAdmin.deleted == 0))
        if not rows:
            return error_result(code="404", message="文档不存在")
        return success_result(data=f"# {rows[0].doc_name}\n\n预览内容暂不可用。")
    except Exception as e:
        return error_result(code="500", message=str(e))


@router.get("/knowledge-base/docs/{doc_id}/chunk-logs")
async def get_chunk_logs(doc_id: str, current: int = 1, size: int = 10, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=_page([], 0, current, size))


# ── Chunk CRUD (stubs) ──

@router.get("/knowledge-base/docs/{doc_id}/chunks")
async def list_chunks(doc_id: str, current: int = 1, size: int = 10, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=_page([], 0, current, size))


@router.post("/knowledge-base/docs/{doc_id}/chunks")
async def create_chunk(doc_id: str, payload: dict[str, Any], _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data={"id": _uid(), "docId": doc_id, **payload})


@router.put("/knowledge-base/docs/{doc_id}/chunks/{chunk_id}")
async def update_chunk(doc_id: str, chunk_id: str, _payload: dict[str, Any], _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=None)


@router.delete("/knowledge-base/docs/{doc_id}/chunks/{chunk_id}")
async def delete_chunk(doc_id: str, chunk_id: str, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data=None)


@router.patch("/knowledge-base/docs/{doc_id}/chunks/{chunk_id}/enable")
async def toggle_chunk(doc_id: str, chunk_id: str, value: bool = True, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data={"docId": doc_id, "chunkId": chunk_id, "enabled": value})


@router.patch("/knowledge-base/docs/{doc_id}/chunks/batch-enable")
async def batch_toggle_chunks(doc_id: str, payload: dict[str, Any], value: bool = True, _: JwtAuthorizationCredentials = Security(access_security)):
    return success_result(data={"docId": doc_id, "chunkIds": payload.get("chunkIds", []), "enabled": value})
