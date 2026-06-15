CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 前台用户
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(100) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'user',
    status SMALLINT NOT NULL DEFAULT 1,
    deleted SMALLINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 聊天会话
CREATE TABLE IF NOT EXISTS sessions (
    session_id VARCHAR(16) PRIMARY KEY,
    session_name VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at);

-- 聊天消息
CREATE TABLE IF NOT EXISTS messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(16) NOT NULL,
    user_question TEXT NOT NULL,
    model_answer TEXT NOT NULL,
    documents TEXT,
    recommended_questions TEXT,
    think TEXT,
    message_type VARCHAR(32) NOT NULL DEFAULT 'answer',
    metadata_json TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);

-- 用户知识库文件元数据
CREATE TABLE IF NOT EXISTS knowledgebases (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_knowledgebases_user_id ON knowledgebases(user_id);
CREATE INDEX IF NOT EXISTS idx_knowledgebases_created_at ON knowledgebases(created_at);

-- 单会话临时文档上传记录
CREATE TABLE IF NOT EXISTS document_uploads (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(16) NOT NULL,
    document_name VARCHAR(255) NOT NULL,
    document_type VARCHAR(50) NOT NULL,
    file_size INTEGER,
    upload_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_document_uploads_session_id ON document_uploads(session_id);
CREATE INDEX IF NOT EXISTS idx_document_uploads_upload_time ON document_uploads(upload_time);

-- 旧后台用户表，保留给兼容代码
CREATE TABLE IF NOT EXISTS t_user (
    id VARCHAR(20) PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    password VARCHAR(128) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'user',
    avatar VARCHAR(128),
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted SMALLINT NOT NULL DEFAULT 0
);

-- 动态意图树
CREATE TABLE IF NOT EXISTS t_intent_node (
    id VARCHAR(20) PRIMARY KEY,
    kb_id VARCHAR(20),
    intent_code VARCHAR(64) NOT NULL,
    name VARCHAR(64) NOT NULL,
    level SMALLINT NOT NULL,
    parent_code VARCHAR(64),
    description VARCHAR(512),
    examples TEXT,
    collection_name VARCHAR(128),
    top_k INTEGER,
    mcp_tool_id VARCHAR(128),
    kind SMALLINT NOT NULL DEFAULT 0,
    prompt_snippet TEXT,
    prompt_template TEXT,
    param_prompt_template TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    enabled SMALLINT NOT NULL DEFAULT 1,
    create_by VARCHAR(20),
    update_by VARCHAR(20),
    create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted SMALLINT NOT NULL DEFAULT 0
);

-- 系统配置
CREATE TABLE IF NOT EXISTS t_system_config (
    id SERIAL PRIMARY KEY,
    config_key VARCHAR(128) NOT NULL,
    config_value TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_t_system_config_config_key ON t_system_config(config_key);

-- 管理端知识库
CREATE TABLE IF NOT EXISTS t_knowledge_base (
    id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    embedding_model VARCHAR(128),
    collection_name VARCHAR(128),
    description TEXT,
    document_count INTEGER NOT NULL DEFAULT 0,
    created_by VARCHAR(64),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted SMALLINT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_t_knowledge_base_user_id ON t_knowledge_base(user_id);

CREATE TABLE IF NOT EXISTS t_knowledge_document (
    id VARCHAR(20) PRIMARY KEY,
    kb_id VARCHAR(20) NOT NULL,
    doc_name VARCHAR(255) NOT NULL,
    source_type VARCHAR(32) DEFAULT 'file',
    source_location VARCHAR(512),
    file_type VARCHAR(32),
    file_size INTEGER,
    file_url VARCHAR(512),
    process_mode VARCHAR(32) DEFAULT 'chunk',
    chunk_strategy VARCHAR(64),
    chunk_config TEXT,
    pipeline_id VARCHAR(20),
    status VARCHAR(32) DEFAULT 'pending',
    enabled SMALLINT NOT NULL DEFAULT 1,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    schedule_enabled SMALLINT NOT NULL DEFAULT 0,
    schedule_cron VARCHAR(64),
    chunks_edited SMALLINT NOT NULL DEFAULT 0,
    created_by VARCHAR(64),
    updated_by VARCHAR(64),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted SMALLINT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_t_knowledge_document_kb_id ON t_knowledge_document(kb_id);

-- 入库流水线与任务
CREATE TABLE IF NOT EXISTS t_ingestion_pipeline (
    id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    nodes_json TEXT,
    created_by VARCHAR(64),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted SMALLINT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS t_ingestion_task (
    id VARCHAR(20) PRIMARY KEY,
    pipeline_id VARCHAR(20) NOT NULL,
    source_type VARCHAR(32),
    source_location VARCHAR(512),
    source_file_name VARCHAR(255),
    status VARCHAR(32) DEFAULT 'pending',
    error_message TEXT,
    chunk_count INTEGER DEFAULT 0,
    logs_json TEXT,
    metadata_json TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_by VARCHAR(64),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted SMALLINT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_t_ingestion_task_pipeline_id ON t_ingestion_task(pipeline_id);

CREATE TABLE IF NOT EXISTS t_ingestion_task_node (
    id VARCHAR(20) PRIMARY KEY,
    task_id VARCHAR(20) NOT NULL,
    pipeline_id VARCHAR(20),
    node_id VARCHAR(64),
    node_type VARCHAR(32),
    node_order INTEGER,
    status VARCHAR(32) DEFAULT 'pending',
    duration_ms INTEGER,
    message TEXT,
    error_message TEXT,
    output_json TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_t_ingestion_task_node_task_id ON t_ingestion_task_node(task_id);

CREATE TABLE IF NOT EXISTS t_knowledge_document_chunk_log (
    id VARCHAR(20) PRIMARY KEY,
    doc_id VARCHAR(20) NOT NULL,
    status VARCHAR(32) DEFAULT 'pending',
    process_mode VARCHAR(32),
    chunk_strategy VARCHAR(64),
    pipeline_id VARCHAR(20),
    pipeline_name VARCHAR(128),
    extract_duration INTEGER,
    chunk_duration INTEGER,
    embed_duration INTEGER,
    persist_duration INTEGER,
    other_duration INTEGER,
    total_duration INTEGER,
    chunk_count INTEGER DEFAULT 0,
    error_message TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_t_knowledge_document_chunk_log_doc_id ON t_knowledge_document_chunk_log(doc_id);

-- RAG 链路追踪
CREATE TABLE IF NOT EXISTS t_rag_trace_run (
    id VARCHAR(20) PRIMARY KEY,
    trace_id VARCHAR(40) NOT NULL,
    trace_name VARCHAR(255),
    entry_method VARCHAR(64),
    conversation_id VARCHAR(40),
    task_id VARCHAR(40),
    user_name VARCHAR(64),
    user_id VARCHAR(64),
    status VARCHAR(32) DEFAULT 'running',
    error_message TEXT,
    duration_ms INTEGER,
    ttft_ms INTEGER,
    question TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted SMALLINT NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_t_rag_trace_run_trace_id ON t_rag_trace_run(trace_id);
CREATE INDEX IF NOT EXISTS ix_t_rag_trace_run_conversation_id ON t_rag_trace_run(conversation_id);

CREATE TABLE IF NOT EXISTS t_rag_trace_node (
    id VARCHAR(20) PRIMARY KEY,
    trace_id VARCHAR(40) NOT NULL,
    node_id VARCHAR(64) NOT NULL,
    parent_node_id VARCHAR(64),
    depth INTEGER DEFAULT 0,
    node_type VARCHAR(32),
    node_name VARCHAR(128),
    class_name VARCHAR(128),
    method_name VARCHAR(128),
    status VARCHAR(32) DEFAULT 'running',
    error_message TEXT,
    duration_ms INTEGER,
    input_json TEXT,
    output_json TEXT,
    extra_data_json TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_t_rag_trace_node_trace_id ON t_rag_trace_node(trace_id);
