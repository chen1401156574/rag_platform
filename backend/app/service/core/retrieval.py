
from service.core.rag.nlp.search_v2 import Dealer
from service.core.rag.utils.es_conn import ESConnection

import json
from datetime import datetime
# 创建 ElasticsearchConnection 实例
es_connection = ESConnection()

# 创建 Dealer 实例
dealer = Dealer(dataStore=es_connection)


def _normalize_retrieval_config(top_k: int = 5, retrieval_config: dict | None = None) -> dict:
    config = retrieval_config or {}
    page_size = int(config.get("top_k") or top_k or 5)
    page_size = max(page_size, 1)
    vector_similarity_weight = float(config.get("vector_similarity_weight", 0.6))
    vector_similarity_weight = min(max(vector_similarity_weight, 0.0), 1.0)
    similarity_threshold = float(config.get("similarity_threshold", 0.1))
    similarity_threshold = min(max(similarity_threshold, 0.0), 1.0)
    candidate_top = int(config.get("candidate_top", 1024))
    candidate_top = min(max(candidate_top, page_size), 4096)
    return {
        "top_k": page_size,
        "vector_similarity_weight": vector_similarity_weight,
        "similarity_threshold": similarity_threshold,
        "candidate_top": candidate_top,
        "rerank_enabled": bool(config.get("rerank_enabled", False)),
    }


def retrieve_content(indexNames: str, question: str, top_k: int = 5, kb_ids=None, tracker=None, retrieval_config=None):
    effective_config = _normalize_retrieval_config(top_k=top_k, retrieval_config=retrieval_config)
    page_size = effective_config["top_k"]
    if isinstance(kb_ids, str):
        kb_ids = [kb_ids]

    if tracker:
        tracker.record_event(
            node_type="RetrievalQueryBuild",
            node_name="Retrieval Query Build",
            input_data={"question": question},
            output_data={
                "tenant_ids": indexNames,
                "kb_ids": kb_ids,
                "page": 1,
                "retrieval_params": effective_config,
            },
        )

    # 执行搜索
    search_start = datetime.now()
    results = dealer.retrieval(question = question,
                               embd_mdl = None,
                               tenant_ids = indexNames,
                               kb_ids = kb_ids,
                               vector_similarity_weight=effective_config["vector_similarity_weight"],
                               similarity_threshold=effective_config["similarity_threshold"],
                               top=effective_config["candidate_top"],
                               rerank_mdl="configured-rerank" if effective_config["rerank_enabled"] else None,
                               page = 1,
                               page_size = page_size
    )
    search_end = datetime.now()
    if tracker:
        chunks = results.get("chunks", [])
        tracker.record_node(
            node_type="ESHybridSearch",
            node_name="ES Hybrid Search",
            start_time=search_start,
            end_time=search_end,
            status="success",
            input_data={
                "question": question,
                "tenant_ids": indexNames,
                "kb_ids": kb_ids,
            },
            output_data={
                "total": results.get("total", 0),
                "returned_chunks": len(chunks),
                "doc_names": list({chunk.get("docnm_kwd", "") for chunk in chunks if chunk.get("docnm_kwd")})[:10],
                "fusion": "fulltext + dense vector",
                "retrieval_params": effective_config,
            },
        )

    # 提取 chunks 中的信息
    extracted_data = []


    for i, chunk in enumerate(results['chunks'], start=1):
        content_with_weight = chunk.get('content_with_weight', 'N/A')
        # similarity = chunk.get('similarity', 'N/A')
        # vector_similarity = chunk.get('vector_similarity', 'N/A')
        # term_similarity = chunk.get('term_similarity', 'N/A')
        doc_id = chunk.get('doc_id', 'N/A')
        docnm = chunk.get('docnm_kwd', 'N/A')
        docnm = docnm.split("/")[-1]

        message = {
            "id": i,
            "document_id": doc_id,
            "document_name": docnm,
            'content_with_weight': content_with_weight,
            "positions": chunk.get("positions") or chunk.get("position_int") or [],
            "page_num_int": chunk.get("page_num_int") or [],
        }
        
        extracted_data.append(message)

    if tracker:
        similarities = [
            chunk.get("similarity")
            for chunk in results.get("chunks", [])
            if isinstance(chunk.get("similarity"), (int, float))
        ]
        tracker.record_event(
            node_type="RerankChunks",
            node_name="Rerank Chunks",
            input_data={"candidate_count": len(results.get("chunks", [])), "retrieval_params": effective_config},
            output_data={
                "returned_count": len(extracted_data),
                "model_rerank_enabled": effective_config["rerank_enabled"],
                "max_similarity": max(similarities) if similarities else None,
                "min_similarity": min(similarities) if similarities else None,
                "documents": [
                    {"document_id": item["document_id"], "document_name": item["document_name"]}
                    for item in extracted_data
                ],
            },
        )

    return extracted_data


if __name__ == '__main__':
    res = retrieve_content(question="世运电路成长性如何", indexNames="test01")
    print(res)
    
    # 将提取的数据写入到文件
    # with open("output.txt", "w", encoding="utf-8") as file:
    #     for data in extracted_data:
    #         file.write(f"content_with_weight: {data['content_with_weight']}\n")
    #         file.write(f"similarity: {data['similarity']}\n")
    #         file.write(f"vector_similarity: {data['vector_similarity']}\n")
    #         file.write(f"term_similarity: {data['term_similarity']}\n")
    #         file.write("\n")
    
    # print("结果已写入到 output.txt 文件中")
