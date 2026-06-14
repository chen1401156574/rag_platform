from fastapi import APIRouter, Depends, HTTPException, Security, status
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from typing import List
import uuid
import json
from datetime import datetime

from utils.database import get_db
from service.auth import access_security
from fastapi_jwt import JwtAuthorizationCredentials
from models.intent import IntentNode
from schemas.intent import (
    IntentNodeCreateRequest, 
    IntentNodeUpdateRequest, 
    IntentNodeBatchRequest
)
from utils.response import success_result, error_result

router = APIRouter()

def get_children_map(db: Session) -> dict:
    stmt = select(IntentNode).where(IntentNode.deleted == 0)
    nodes = db.scalars(stmt).all()
    children_map = {}
    for node in nodes:
        parent = node.parent_code or "ROOT"
        if parent not in children_map:
            children_map[parent] = []
        children_map[parent].append(node)
    return children_map

def collect_descendants(intent_code: str, children_map: dict) -> List[IntentNode]:
    if not intent_code:
        return []
    result = []
    stack = list(children_map.get(intent_code, []))
    while stack:
        current = stack.pop(0)
        result.append(current)
        children = children_map.get(current.intent_code, [])
        stack.extend(children)
    return result

@router.get("/intent-tree/trees")
async def get_intent_tree(
    db: Session = Depends(get_db),
    credentials: JwtAuthorizationCredentials = Security(access_security)
):
    try:
        stmt = select(IntentNode).where(IntentNode.deleted == 0).order_by(IntentNode.sort_order.asc(), IntentNode.id.asc())
        nodes = db.scalars(stmt).all()

        parent_map = {}
        for node in nodes:
            parent = node.parent_code
            if not parent:
                parent = "ROOT"
            if parent not in parent_map:
                parent_map[parent] = []
            parent_map[parent].append(node)

        roots = parent_map.get("ROOT", [])

        def build_tree_vo(node: IntentNode) -> dict:
            children = parent_map.get(node.intent_code, [])
            return {
                "id": node.id,
                "intentCode": node.intent_code,
                "name": node.name,
                "level": node.level,
                "parentCode": node.parent_code,
                "description": node.description,
                "examples": node.examples,
                "collectionName": node.collection_name,
                "topK": node.top_k,
                "kind": node.kind,
                "sortOrder": node.sort_order,
                "enabled": node.enabled,
                "mcpToolId": node.mcp_tool_id,
                "promptSnippet": node.prompt_snippet,
                "promptTemplate": node.prompt_template,
                "paramPromptTemplate": node.param_prompt_template,
                "children": [build_tree_vo(child) for child in children]
            }

        tree_data = [build_tree_vo(r) for r in roots]
        return success_result(data=tree_data)
    except Exception as e:
        return error_result(code="500", message=str(e))

@router.post("/intent-tree")
async def create_node(
    payload: IntentNodeCreateRequest,
    db: Session = Depends(get_db),
    credentials: JwtAuthorizationCredentials = Security(access_security)
):
    try:
        username = credentials.subject.get("user_name", "admin")
        
        stmt = select(IntentNode).where(
            and_(IntentNode.intent_code == payload.intentCode, IntentNode.deleted == 0)
        )
        existing = db.scalars(stmt).first()
        if existing:
            return error_result(code="400", message=f"意图标识已存在: {payload.intentCode}")

        if payload.level == 2 and payload.kind == 0 and not (payload.kbId or payload.collectionName):
            return error_result(code="400", message="TOPIC level KB intents must bind a kbId or collectionName")

        node_id = str(uuid.uuid4()).replace("-", "")[:20]

        examples_str = None
        if payload.examples is not None:
            examples_str = json.dumps(payload.examples, ensure_ascii=False)

        new_node = IntentNode(
            id=node_id,
            kb_id=payload.kbId,
            intent_code=payload.intentCode,
            name=payload.name,
            level=payload.level,
            parent_code=payload.parentCode,
            description=payload.description,
            examples=examples_str,
            collection_name=payload.collectionName,
            mcp_tool_id=payload.mcpToolId,
            top_k=payload.topK,
            kind=payload.kind if payload.kind is not None else 0,
            sort_order=payload.sortOrder if payload.sortOrder is not None else 0,
            enabled=payload.enabled if payload.enabled is not None else 1,
            prompt_snippet=payload.promptSnippet,
            prompt_template=payload.promptTemplate,
            param_prompt_template=payload.paramPromptTemplate,
            create_by=username,
            update_by=username,
            deleted=0
        )

        db.add(new_node)
        db.commit()

        return success_result(data=node_id)
    except Exception as e:
        db.rollback()
        return error_result(code="500", message=str(e))

@router.put("/intent-tree/{id}")
async def update_node(
    id: str,
    payload: IntentNodeUpdateRequest,
    db: Session = Depends(get_db),
    credentials: JwtAuthorizationCredentials = Security(access_security)
):
    try:
        username = credentials.subject.get("user_name", "admin")
        
        stmt = select(IntentNode).where(
            and_(IntentNode.id == id, IntentNode.deleted == 0)
        )
        node = db.scalars(stmt).first()
        if not node:
            return error_result(code="404", message=f"节点不存在或已删除: id={id}")

        if payload.name is not None:
            node.name = payload.name
        if payload.level is not None:
            node.level = payload.level
        if payload.parentCode is not None:
            node.parent_code = payload.parentCode
        if payload.description is not None:
            node.description = payload.description
        if payload.examples is not None:
            node.examples = json.dumps(payload.examples, ensure_ascii=False)
        if payload.collectionName is not None:
            node.collection_name = payload.collectionName
        if payload.mcpToolId is not None:
            node.mcp_tool_id = payload.mcpToolId
        if payload.topK is not None:
            node.top_k = payload.topK
        if payload.kind is not None:
            node.kind = payload.kind
        if payload.sortOrder is not None:
            node.sort_order = payload.sortOrder
        if payload.enabled is not None:
            node.enabled = payload.enabled
        if payload.promptSnippet is not None:
            node.prompt_snippet = payload.promptSnippet
        if payload.promptTemplate is not None:
            node.prompt_template = payload.promptTemplate
        if payload.paramPromptTemplate is not None:
            node.param_prompt_template = payload.paramPromptTemplate

        node.update_by = username
        node.update_time = datetime.now()
        
        db.commit()
        return success_result(data=None)
    except Exception as e:
        db.rollback()
        return error_result(code="500", message=str(e))

@router.delete("/intent-tree/{id}")
async def delete_node(
    id: str,
    db: Session = Depends(get_db),
    credentials: JwtAuthorizationCredentials = Security(access_security)
):
    try:
        stmt = select(IntentNode).where(
            and_(IntentNode.id == id, IntentNode.deleted == 0)
        )
        node = db.scalars(stmt).first()
        if not node:
            return error_result(code="404", message=f"节点不存在或已删除: id={id}")

        node.deleted = 1
        node.update_time = datetime.now()
        db.commit()
        return success_result(data=None)
    except Exception as e:
        db.rollback()
        return error_result(code="500", message=str(e))

@router.post("/intent-tree/batch/enable")
async def batch_enable(
    payload: IntentNodeBatchRequest,
    db: Session = Depends(get_db),
    credentials: JwtAuthorizationCredentials = Security(access_security)
):
    try:
        username = credentials.subject.get("user_name", "admin")
        ids = list(set(payload.ids))
        if not ids:
            return error_result(code="400", message="请至少选择一个节点")

        stmt = select(IntentNode).where(
            and_(IntentNode.id.in_(ids), IntentNode.deleted == 0)
        )
        target_nodes = db.scalars(stmt).all()
        if len(target_nodes) != len(ids):
            return error_result(code="400", message="部分节点不存在或已删除")

        for node in target_nodes:
            node.enabled = 1
            node.update_by = username
            node.update_time = datetime.now()

        db.commit()
        return success_result(data=None)
    except Exception as e:
        db.rollback()
        return error_result(code="500", message=str(e))

@router.post("/intent-tree/batch/disable")
async def batch_disable(
    payload: IntentNodeBatchRequest,
    db: Session = Depends(get_db),
    credentials: JwtAuthorizationCredentials = Security(access_security)
):
    try:
        username = credentials.subject.get("user_name", "admin")
        ids = list(set(payload.ids))
        if not ids:
            return error_result(code="400", message="请至少选择一个节点")

        stmt = select(IntentNode).where(
            and_(IntentNode.id.in_(ids), IntentNode.deleted == 0)
        )
        target_nodes = db.scalars(stmt).all()
        if len(target_nodes) != len(ids):
            return error_result(code="400", message="部分节点不存在或已删除")

        children_map = get_children_map(db)
        target_id_set = set(ids)

        for target_node in target_nodes:
            descendants = collect_descendants(target_node.intent_code, children_map)
            enabled_but_not_selected = [
                d for d in descendants 
                if d.enabled == 1 and d.id not in target_id_set
            ]
            if enabled_but_not_selected:
                names = "、".join([d.name or d.intent_code for d in enabled_but_not_selected[:3]])
                return error_result(
                    code="400",
                    message=f"批量停用失败：节点 [{target_node.name}] 存在已启用的子节点未包含在本次操作中（如：{names}），请先选择全量子节点"
                )

        for node in target_nodes:
            node.enabled = 0
            node.update_by = username
            node.update_time = datetime.now()

        db.commit()
        return success_result(data=None)
    except Exception as e:
        db.rollback()
        return error_result(code="500", message=str(e))

@router.post("/intent-tree/batch/delete")
async def batch_delete(
    payload: IntentNodeBatchRequest,
    db: Session = Depends(get_db),
    credentials: JwtAuthorizationCredentials = Security(access_security)
):
    try:
        ids = list(set(payload.ids))
        if not ids:
            return error_result(code="400", message="请至少选择一个节点")

        stmt = select(IntentNode).where(
            and_(IntentNode.id.in_(ids), IntentNode.deleted == 0)
        )
        target_nodes = db.scalars(stmt).all()
        if len(target_nodes) != len(ids):
            return error_result(code="400", message="部分节点不存在或已删除")

        children_map = get_children_map(db)
        target_id_set = set(ids)

        for target_node in target_nodes:
            descendants = collect_descendants(target_node.intent_code, children_map)
            not_selected_descendants = [d for d in descendants if d.id not in target_id_set]
            if not_selected_descendants:
                enabled_descendants = [d for d in not_selected_descendants if d.enabled == 1]
                if enabled_descendants:
                    names = "、".join([d.name or d.intent_code for d in enabled_descendants[:3]])
                    return error_result(
                        code="400",
                        message=f"批量删除失败：节点 [{target_node.name}] 存在已启用的子节点未包含在本次操作中（如：{names}），请先选择全量子节点"
                    )
                names = "、".join([d.name or d.intent_code for d in not_selected_descendants[:3]])
                return error_result(
                    code="400",
                    message=f"批量删除失败：节点 [{target_node.name}] 未包含全量子节点（如：{names}），请先勾选完整子树后再删除"
                )

        for node in target_nodes:
            node.deleted = 1
            node.update_time = datetime.now()

        db.commit()
        return success_result(data=None)
    except Exception as e:
        db.rollback()
        return error_result(code="500", message=str(e))
