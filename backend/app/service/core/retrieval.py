
from service.core.rag.nlp.search_v2 import Dealer
from service.core.rag.utils.es_conn import ESConnection

import json
from datetime import datetime
# 创建 ElasticsearchConnection 实例
es_connection = ESConnection()

# 创建 Dealer 实例
dealer = Dealer(dataStore=es_connection)


def retrieve_content(indexNames: str, question: str, top_k: int = 5, kb_ids=None, tracker=None):
    page_size = top_k if top_k and top_k > 0 else 5
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
                "top_k": page_size,
                "page": 1,
                "vector_similarity_weight": 0.6,
            },
        )

    # 执行搜索
    search_start = datetime.now()
    results = dealer.retrieval(question = question,
                               embd_mdl = None,
                               tenant_ids = indexNames,
                               kb_ids = kb_ids,
                               vector_similarity_weight=0.6,
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
                "vector_similarity_weight": 0.6,
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
            input_data={"candidate_count": len(results.get("chunks", [])), "top_k": page_size},
            output_data={
                "returned_count": len(extracted_data),
                "rerank_applied": True,
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
