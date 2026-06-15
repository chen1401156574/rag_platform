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

_XXH64_PRIME_1 = 11400714785074694791
_XXH64_PRIME_2 = 14029467366897019727
_XXH64_PRIME_3 = 1609587929392839161
_XXH64_PRIME_4 = 9650029242287828579
_XXH64_PRIME_5 = 2870177450012600261
_XXH64_MASK = 0xFFFFFFFFFFFFFFFF

_ES_CHUNK_FIELDS = [
    "content_with_weight",
    "content_ltks",
    "doc_id",
    "docnm",
    "docnm_kwd",
    "kb_id",
    "chunk_index",
    "chunk_index_int",
    "available_int",
    "create_time",
    "create_timestamp_flt",
    "update_time",
    "update_timestamp_flt",
    "token_count",
    "token_count_int",
    "char_count",
    "char_count_int",
]


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


def _rotl64(value: int, count: int) -> int:
    return ((value << count) | (value >> (64 - count))) & _XXH64_MASK


def _xxh64_round(acc: int, lane: int) -> int:
    acc = (acc + lane * _XXH64_PRIME_2) & _XXH64_MASK
    acc = _rotl64(acc, 31)
    return (acc * _XXH64_PRIME_1) & _XXH64_MASK


def _xxh64_merge_round(acc: int, value: int) -> int:
    acc ^= _xxh64_round(0, value)
    return (acc * _XXH64_PRIME_1 + _XXH64_PRIME_4) & _XXH64_MASK


def _xxh64_hexdigest(value: str) -> str:
    try:
        import xxhash

        return xxhash.xxh64(value.encode("utf-8")).hexdigest()
    except Exception:
        data = value.encode("utf-8")
        length = len(data)
        offset = 0

        if length >= 32:
            v1 = (_XXH64_PRIME_1 + _XXH64_PRIME_2) & _XXH64_MASK
            v2 = _XXH64_PRIME_2
            v3 = 0
            v4 = (-_XXH64_PRIME_1) & _XXH64_MASK

            limit = length - 32
            while offset <= limit:
                v1 = _xxh64_round(v1, int.from_bytes(data[offset:offset + 8], "little"))
                offset += 8
                v2 = _xxh64_round(v2, int.from_bytes(data[offset:offset + 8], "little"))
                offset += 8
                v3 = _xxh64_round(v3, int.from_bytes(data[offset:offset + 8], "little"))
                offset += 8
                v4 = _xxh64_round(v4, int.from_bytes(data[offset:offset + 8], "little"))
                offset += 8

            acc = (
                _rotl64(v1, 1)
                + _rotl64(v2, 7)
                + _rotl64(v3, 12)
                + _rotl64(v4, 18)
            ) & _XXH64_MASK
            acc = _xxh64_merge_round(acc, v1)
            acc = _xxh64_merge_round(acc, v2)
            acc = _xxh64_merge_round(acc, v3)
            acc = _xxh64_merge_round(acc, v4)
        else:
            acc = _XXH64_PRIME_5

        acc = (acc + length) & _XXH64_MASK

        while offset + 8 <= length:
            lane = _xxh64_round(0, int.from_bytes(data[offset:offset + 8], "little"))
            acc ^= lane
            acc = (_rotl64(acc, 27) * _XXH64_PRIME_1 + _XXH64_PRIME_4) & _XXH64_MASK
            offset += 8

        if offset + 4 <= length:
            acc ^= (int.from_bytes(data[offset:offset + 4], "little") * _XXH64_PRIME_1) & _XXH64_MASK
            acc = (_rotl64(acc, 23) * _XXH64_PRIME_2 + _XXH64_PRIME_3) & _XXH64_MASK
            offset += 4

        while offset < length:
            acc ^= (data[offset] * _XXH64_PRIME_5) & _XXH64_MASK
            acc = (_rotl64(acc, 11) * _XXH64_PRIME_1) & _XXH64_MASK
            offset += 1

        acc ^= acc >> 33
        acc = (acc * _XXH64_PRIME_2) & _XXH64_MASK
        acc ^= acc >> 29
        acc = (acc * _XXH64_PRIME_3) & _XXH64_MASK
        acc ^= acc >> 32
        return f"{acc & _XXH64_MASK:016x}"


def _es_doc_id(doc_name: str) -> str:
    return _xxh64_hexdigest(doc_name or "")


def _collection_name(kb: KnowledgeBaseAdmin) -> str:
    return str(kb.collection_name or kb.user_id or kb.id)


def _get_document_and_kb(
    db: Session,
    doc_id: str,
) -> tuple[Optional[KnowledgeDocumentAdmin], Optional[KnowledgeBaseAdmin], Optional[dict[str, Any]]]:
    doc_rows = _safe_scalars(
        db,
        select(KnowledgeDocumentAdmin).where(
            KnowledgeDocumentAdmin.id == doc_id,
            KnowledgeDocumentAdmin.deleted == 0,
        ),
    )
    if not doc_rows:
        return None, None, error_result(code="404", message="文档不存在")

    doc = doc_rows[0]
    kb_rows = _safe_scalars(
        db,
        select(KnowledgeBaseAdmin).where(
            KnowledgeBaseAdmin.id == doc.kb_id,
            KnowledgeBaseAdmin.deleted == 0,
        ),
    )
    if not kb_rows:
        return doc, None, error_result(code="404", message="知识库不存在")
    return doc, kb_rows[0], None


def _as_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _es_total(res: dict[str, Any]) -> int:
    total = res.get("hits", {}).get("total", 0)
    if isinstance(total, dict):
        return int(total.get("value") or 0)
    return int(total or 0)


def _empty_es_result() -> dict[str, Any]:
    return {"hits": {"total": {"value": 0}, "hits": []}}


def _is_missing_index_error(exc: Exception) -> bool:
    return "index_not_found_exception" in str(exc) or "NotFoundError" in exc.__class__.__name__


def _get_es_client():
    from service.core.rag.utils.es_conn import ESConnection

    return ESConnection().es


def _chunk_query_body(
    es_doc_id: str,
    current: int,
    size: int,
    collection_name: Optional[str] = None,
    enabled: Optional[int] = None,
) -> dict[str, Any]:
    filters: list[dict[str, Any]] = [{"term": {"doc_id": es_doc_id}}]
    must_not: list[dict[str, Any]] = []
    if collection_name:
        filters.append({"term": {"kb_id": collection_name}})
    if enabled == 0:
        filters.append({"range": {"available_int": {"lt": 1}}})
    elif enabled == 1:
        must_not.append({"range": {"available_int": {"lt": 1}}})

    bool_query: dict[str, Any] = {"filter": filters}
    if must_not:
        bool_query["must_not"] = must_not

    return {
        "query": {"bool": bool_query},
        "from": (current - 1) * size,
        "size": size,
        "_source": _ES_CHUNK_FIELDS,
        "sort": [
            {"create_timestamp_flt": {"order": "asc", "unmapped_type": "float"}},
            {"_doc": {"order": "asc"}},
        ],
        "track_total_hits": True,
    }


def _search_es_chunks(
    index_name: str,
    es_doc_id: str,
    current: int,
    size: int,
    collection_name: Optional[str] = None,
    enabled: Optional[int] = None,
) -> dict[str, Any]:
    es = _get_es_client()
    body = _chunk_query_body(es_doc_id, current, size, collection_name, enabled)
    try:
        return es.search(index=index_name, body=body, timeout="600s")
    except Exception as exc:
        if _is_missing_index_error(exc):
            return _empty_es_result()
        raise


def _chunk_content(source: dict[str, Any]) -> str:
    content = source.get("content_with_weight")
    if content is None:
        content = source.get("content_ltks")
    return "" if content is None else str(content)


def _estimate_token_count(content: str) -> int:
    if not content:
        return 0
    return max(1, len(content) // 2)


def _chunk_record(
    hit: dict[str, Any],
    doc_id: str,
    es_doc_id: str,
    chunk_index: int,
    matched_by_fallback: bool = False,
) -> dict[str, Any]:
    source = hit.get("_source") or {}
    content = _chunk_content(source)
    token_count = _as_int(source.get("token_count"), None)
    if token_count is None:
        token_count = _as_int(source.get("token_count_int"), None)
    if token_count is None:
        token_count = _estimate_token_count(content)

    char_count = _as_int(source.get("char_count"), None)
    if char_count is None:
        char_count = _as_int(source.get("char_count_int"), len(content))

    source_chunk_index = _as_int(source.get("chunk_index"), None)
    if source_chunk_index is None:
        source_chunk_index = _as_int(source.get("chunk_index_int"), chunk_index)

    enabled = _as_int(source.get("available_int"), 1)
    if enabled is None:
        enabled = 1

    return {
        "id": hit.get("_id"),
        "docId": doc_id,
        "esDocId": source.get("doc_id") or es_doc_id,
        "kbId": source.get("kb_id"),
        "chunkIndex": source_chunk_index,
        "content": content,
        "charCount": char_count,
        "tokenCount": token_count,
        "enabled": enabled,
        "createTime": source.get("create_time"),
        "updateTime": source.get("update_time") or source.get("create_time"),
        "docName": source.get("docnm") or source.get("docnm_kwd"),
        "matchedByFallback": matched_by_fallback,
    }


def _query_document_chunks(
    doc_id: str,
    doc: KnowledgeDocumentAdmin,
    kb: KnowledgeBaseAdmin,
    current: int,
    size: int,
    enabled: Optional[int] = None,
) -> tuple[list[dict[str, Any]], int, bool, str, str]:
    collection_name = _collection_name(kb)
    es_doc_id = _es_doc_id(doc.doc_name)

    res = _search_es_chunks(collection_name, es_doc_id, current, size, collection_name, enabled)
    matched_by_fallback = False
    if _es_total(res) == 0:
        res = _search_es_chunks(collection_name, es_doc_id, current, size, None, enabled)
        matched_by_fallback = _es_total(res) > 0

    hits = res.get("hits", {}).get("hits", [])
    offset = (current - 1) * size
    records = [
        _chunk_record(hit, doc_id, es_doc_id, offset + index + 1, matched_by_fallback)
        for index, hit in enumerate(hits)
    ]
    return records, _es_total(res), matched_by_fallback, es_doc_id, collection_name


def _retrieval_hit_record(chunk: dict[str, Any], rank: int, fallback_score: Optional[float] = None) -> dict[str, Any]:
    score = _as_float(chunk.get("similarity"))
    if score is None:
        score = _as_float(chunk.get("score"))
    if score is None:
        score = fallback_score

    return {
        "rank": rank,
        "chunkId": chunk.get("chunk_id") or chunk.get("id"),
        "content": chunk.get("content_with_weight") or chunk.get("content") or "",
        "score": score,
        "similarity": _as_float(chunk.get("similarity")) if chunk.get("similarity") is not None else score,
        "vectorSimilarity": _as_float(chunk.get("vector_similarity")),
        "termSimilarity": _as_float(chunk.get("term_similarity")),
        "highlight": chunk.get("highlight"),
        "docName": chunk.get("docnm_kwd") or chunk.get("docnm"),
        "docId": chunk.get("doc_id"),
    }


def _run_document_retrieval(
    question: str,
    top_k: int,
    collection_name: str,
    es_doc_id: str,
) -> list[dict[str, Any]]:
    from service.core.rag.nlp.search_v2 import Dealer
    from service.core.rag.utils.es_conn import ESConnection

    dealer = Dealer(dataStore=ESConnection())
    result = dealer.retrieval(
        question=question,
        embd_mdl=None,
        tenant_ids=collection_name,
        kb_ids=[collection_name],
        doc_ids=[es_doc_id],
        page=1,
        page_size=top_k,
        vector_similarity_weight=0.6,
        top=max(top_k, 128),
        highlight=True,
    )
    chunks = [
        chunk
        for chunk in result.get("chunks", [])
        if str(chunk.get("doc_id") or "") == es_doc_id
    ]
    if chunks:
        return chunks[:top_k]

    fallback = dealer.retrieval(
        question=question,
        embd_mdl=None,
        tenant_ids=collection_name,
        kb_ids=[],
        doc_ids=[es_doc_id],
        page=1,
        page_size=top_k,
        vector_similarity_weight=0.6,
        top=max(top_k, 128),
        highlight=True,
        rank_feature=None,
    )
    return [
        chunk
        for chunk in fallback.get("chunks", [])
        if str(chunk.get("doc_id") or "") == es_doc_id
    ][:top_k]


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


# ── Chunk read-only diagnostics ──

@router.get("/knowledge-base/docs/{doc_id}/chunks")
async def list_chunks(
    doc_id: str,
    current: int = 1,
    size: int = 10,
    enabled: Optional[int] = None,
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        page = max(current, 1)
        page_size = min(max(size, 1), 100)
        enabled_filter = enabled if enabled in (0, 1) else None
        doc, kb, err = _get_document_and_kb(db, doc_id)
        if err:
            return err
        assert doc is not None and kb is not None

        records, total, matched_by_fallback, es_doc_id, collection_name = _query_document_chunks(
            doc_id=doc_id,
            doc=doc,
            kb=kb,
            current=page,
            size=page_size,
            enabled=enabled_filter,
        )
        data = _page(records, total, page, page_size)
        data["esDocId"] = es_doc_id
        data["collectionName"] = collection_name
        data["matchedByFallback"] = matched_by_fallback
        return success_result(data=data)
    except Exception as e:
        return error_result(code="500", message=f"查询 ES Chunk 失败: {e}")


@router.post("/knowledge-base/docs/{doc_id}/retrieval-test")
async def retrieval_test(
    doc_id: str,
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    _: JwtAuthorizationCredentials = Security(access_security),
):
    try:
        question = str(payload.get("question") or "").strip()
        if not question:
            return error_result(code="400", message="测试问题不能为空")

        try:
            top_k = int(payload.get("topK") or 5)
        except (TypeError, ValueError):
            top_k = 5
        top_k = min(max(top_k, 1), 50)

        doc, kb, err = _get_document_and_kb(db, doc_id)
        if err:
            return err
        assert doc is not None and kb is not None

        collection_name = _collection_name(kb)
        es_doc_id = _es_doc_id(doc.doc_name)
        chunks = _run_document_retrieval(question, top_k, collection_name, es_doc_id)
        records = [
            _retrieval_hit_record(chunk, index + 1)
            for index, chunk in enumerate(chunks)
        ]
        return success_result(
            data={
                "question": question,
                "docId": doc_id,
                "esDocId": es_doc_id,
                "kbId": kb.id,
                "collectionName": collection_name,
                "topK": top_k,
                "records": records,
            }
        )
    except Exception as e:
        return error_result(code="500", message=f"相似度测试失败: {e}")


@router.post("/knowledge-base/docs/{doc_id}/chunks")
async def create_chunk(doc_id: str, payload: dict[str, Any], _: JwtAuthorizationCredentials = Security(access_security)):
    return error_result(code="400", message="第一阶段暂不支持新增 Chunk")


@router.put("/knowledge-base/docs/{doc_id}/chunks/{chunk_id}")
async def update_chunk(doc_id: str, chunk_id: str, _payload: dict[str, Any], _: JwtAuthorizationCredentials = Security(access_security)):
    return error_result(code="400", message="第一阶段暂不支持编辑 Chunk")


@router.delete("/knowledge-base/docs/{doc_id}/chunks/{chunk_id}")
async def delete_chunk(doc_id: str, chunk_id: str, _: JwtAuthorizationCredentials = Security(access_security)):
    return error_result(code="400", message="第一阶段暂不支持删除 Chunk")


@router.patch("/knowledge-base/docs/{doc_id}/chunks/{chunk_id}/enable")
async def toggle_chunk(doc_id: str, chunk_id: str, value: bool = True, _: JwtAuthorizationCredentials = Security(access_security)):
    return error_result(code="400", message="第一阶段暂不支持启用或禁用 Chunk")


@router.patch("/knowledge-base/docs/{doc_id}/chunks/batch-enable")
async def batch_toggle_chunks(doc_id: str, payload: dict[str, Any], value: bool = True, _: JwtAuthorizationCredentials = Security(access_security)):
    return error_result(code="400", message="第一阶段暂不支持批量操作 Chunk")
