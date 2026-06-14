import uuid
import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from models.trace import TraceRun, TraceNode

logger = logging.getLogger(__name__)

def _uid() -> str:
    return str(uuid.uuid4()).replace("-", "")[:20]

class TraceTracker:
    def __init__(self, db: Session, trace_id: str = None):
        self.db = db
        self.trace_id = trace_id or str(uuid.uuid4())
        self.run_record = None
        self.start_time = None

    def start_run(self, question: str, conversation_id: str, user_id: str, user_name: str, trace_name: str = "Chat Flow", entry_method: str = "chat"):
        self.start_time = datetime.now()
        self.run_record = TraceRun(
            id=_uid(),
            trace_id=self.trace_id,
            trace_name=trace_name,
            entry_method=entry_method,
            conversation_id=conversation_id,
            user_name=user_name,
            user_id=user_id,
            question=question,
            status="running",
            start_time=self.start_time,
            created_at=datetime.now(),
            deleted=0
        )
        try:
            self.db.add(self.run_record)
            self.db.commit()
            logger.info(f"TraceRun created: trace_id={self.trace_id}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create TraceRun: {str(e)}")

    def record_node(self, node_type: str, node_name: str, start_time: datetime, end_time: datetime, 
                    status: str = "success", error_message: str = None, input_data: any = None, 
                    output_data: any = None, extra_data: any = None, parent_node_id: str = None, depth: int = 0):
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        def to_json(val):
            if val is None:
                return None
            if isinstance(val, (str, int, float, bool)):
                return json.dumps({"data": val}, ensure_ascii=False)
            try:
                return json.dumps(val, ensure_ascii=False)
            except Exception:
                return str(val)

        node = TraceNode(
            id=_uid(),
            trace_id=self.trace_id,
            node_id=node_type,
            parent_node_id=parent_node_id,
            depth=depth,
            node_type=node_type,
            node_name=node_name,
            status=status,
            error_message=error_message,
            duration_ms=duration_ms,
            input_json=to_json(input_data),
            output_json=to_json(output_data),
            extra_data_json=to_json(extra_data),
            start_time=start_time,
            end_time=end_time,
            created_at=datetime.now()
        )
        try:
            self.db.add(node)
            self.db.commit()
            logger.info(f"TraceNode created: trace_id={self.trace_id}, node_type={node_type}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create TraceNode: {str(e)}")

    def finish_run(self, status: str = "success", error_message: str = None, ttft_ms: int = None, duration_ms: int = None):
        if not self.run_record:
            logger.warning("No active TraceRun to finish")
            return
        
        end_time = datetime.now()
        if duration_ms is None and self.start_time:
            duration_ms = int((end_time - self.start_time).total_seconds() * 1000)
            
        try:
            # 重新获取以防 Session 中该对象过期/断开连接
            run = self.db.query(TraceRun).filter(TraceRun.trace_id == self.trace_id).first()
            if run:
                run.status = status
                run.error_message = error_message
                run.duration_ms = duration_ms
                run.end_time = end_time
                if ttft_ms is not None:
                    run.ttft_ms = ttft_ms
                self.db.commit()
                logger.info(f"TraceRun finished: trace_id={self.trace_id}, status={status}, duration={duration_ms}ms")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to finish TraceRun: {str(e)}")
