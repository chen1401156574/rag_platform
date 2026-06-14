import sys
import os
import uuid
import json
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)
from datetime import datetime

# 确保当前目录及父目录加入 Python 搜索路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from utils.database import SessionLocal
from models.intent import IntentNode

def generate_stable_id(code: str) -> str:
    """基于意图标识生成固定的 20 位字符 ID，实现幂等插入"""
    import hashlib
    h = hashlib.md5(code.encode('utf-8')).hexdigest()
    return h[:20]

# 意图树结构定义
intents = [
    # LEVEL 0 (DOMAIN)
    {
        "intent_code": "group-info",
        "name": "集团信息化",
        "level": 0,
        "parent_code": None,
        "description": "集团信息化相关意图",
        "kind": 0,
        "sort_order": 10
    },
    {
        "intent_code": "biz-sys",
        "name": "业务系统",
        "level": 0,
        "parent_code": None,
        "description": "业务系统相关意图",
        "kind": 0,
        "sort_order": 20
    },
    {
        "intent_code": "sales-stat",
        "name": "销售数据统计",
        "level": 0,
        "parent_code": None,
        "description": "销售数据统计相关意图",
        "kind": 2,
        "sort_order": 30
    },
    {
        "intent_code": "sys-interact",
        "name": "系统交互",
        "level": 0,
        "parent_code": None,
        "description": "系统交互相关意图",
        "kind": 1,
        "sort_order": 40
    },

    # LEVEL 1 (CATEGORY)
    # 集团信息化
    {
        "intent_code": "group-hr",
        "name": "人事",
        "level": 1,
        "parent_code": "group-info",
        "description": "招聘、入职、转正、离职、绩效、薪资、考勤、请假等 HR 问题",
        "kind": 0,
        "sort_order": 11,
        "examples": ["招聘流程是什么", "怎么办理入职", "如何申请转正", "离职需要提前多久申请", "绩效怎么算", "年假怎么休", "薪资发放时间"]
    },
    {
        "intent_code": "group-it",
        "name": "IT支持",
        "level": 1,
        "parent_code": "group-info",
        "description": "VPN、邮箱、打印机、网络、账号密码、办公软件等 IT 支持问题",
        "kind": 0,
        "sort_order": 12,
        "examples": ["VPN怎么连接", "邮箱登不上去了", "打印机怎么配置", "网络很慢怎么办", "修改账号密码", "办公软件无法启动"]
    },
    {
        "intent_code": "group-finance",
        "name": "财务",
        "level": 1,
        "parent_code": "group-info",
        "description": "获取公司发票抬头等相关信息",
        "kind": 0,
        "sort_order": 13
    },
    # 业务系统
    {
        "intent_code": "biz-oa",
        "name": "OA系统",
        "level": 1,
        "parent_code": "biz-sys",
        "description": "OA 系统整体功能说明、主要模块与典型使用场景",
        "kind": 0,
        "sort_order": 21
    },
    {
        "intent_code": "biz-ins",
        "name": "保险系统",
        "level": 1,
        "parent_code": "biz-sys",
        "description": "保险系统相关意图",
        "kind": 0,
        "sort_order": 22
    },
    # 销售数据统计
    {
        "intent_code": "sales-data",
        "name": "销售数据统计",
        "level": 1,
        "parent_code": "sales-stat",
        "description": "销售额、销售量、趋势和预测等实时数据统计",
        "kind": 2,
        "sort_order": 31,
        "examples": ["今天的销售额是多少", "本月销售量走势", "预测下个季度的销售额", "销售额对比分析"]
    },
    # 系统交互
    {
        "intent_code": "sys-welcome",
        "name": "欢迎与问候",
        "level": 1,
        "parent_code": "sys-interact",
        "description": "用户与助手招呼闲聊，如“你好”、“在吗”等",
        "kind": 1,
        "sort_order": 41,
        "examples": ["你好", "早上好", "在吗", "哈喽", "下午好"]
    },
    {
        "intent_code": "sys-about-bot",
        "name": "关于助手",
        "level": 1,
        "parent_code": "sys-interact",
        "description": "询问助手身份、功能及能帮用户做什么等",
        "kind": 1,
        "sort_order": 42,
        "examples": ["你是谁", "你能做什么", "你的功能是什么", "介绍一下你自己"]
    },

    # LEVEL 2 (TOPIC)
    # 财务 -> 发票相关
    {
        "intent_code": "group-finance-invoice",
        "name": "发票相关",
        "level": 2,
        "parent_code": "group-finance",
        "description": "获取公司发票抬头等相关信息",
        "kind": 0,
        "sort_order": 131,
        "examples": ["公司的发票抬头是什么", "怎么开专票", "发票税号是多少", "财务报销发票规范"]
    },
    # OA系统
    {
        "intent_code": "biz-oa-intro",
        "name": "系统介绍",
        "level": 2,
        "parent_code": "biz-oa",
        "description": "OA 系统整体功能说明、主要模块与典型使用场景",
        "kind": 0,
        "sort_order": 211,
        "examples": ["OA系统有什么功能", "怎么提交审批", "OA系统怎么用", "OA系统使用手册"]
    },
    {
        "intent_code": "biz-oa-security",
        "name": "数据安全",
        "level": 2,
        "parent_code": "biz-oa",
        "description": "OA 系统的数据权限、访问控制与安全审计等说明",
        "kind": 0,
        "sort_order": 212,
        "examples": ["OA系统的权限怎么申请", "数据安全审计报告在哪看", "OA账号被锁定了", "访问控制策略"]
    },
    # 保险系统
    {
        "intent_code": "biz-ins-flow",
        "name": "业务流程",
        "level": 2,
        "parent_code": "biz-ins",
        "description": "保险系统核心业务流程相关说明",
        "kind": 0,
        "sort_order": 221,
        "examples": ["保险投保流程", "理赔申请流程", "如何进行保单退保", "保险契约变更流程"]
    },
    {
        "intent_code": "biz-ins-arch",
        "name": "架构设计",
        "level": 2,
        "parent_code": "biz-ins",
        "description": "保险系统的架构设计、部署图、组件等说明",
        "kind": 0,
        "sort_order": 222,
        "examples": ["保险系统的部署图", "系统架构设计说明", "有哪些微服务组件", "数据流向图"]
    },
    {
        "intent_code": "biz-ins-security",
        "name": "数据安全",
        "level": 2,
        "parent_code": "biz-ins",
        "description": "保险系统的数据权限、访问控制与安全审计等说明",
        "kind": 0,
        "sort_order": 223,
        "examples": ["保险系统的安全防护措施", "敏感数据怎么脱敏", "保险系统的访问控制策略", "保险数据合规规范"]
    }
]

def init_intents():
    db = SessionLocal()
    try:
        print("开始初始化意图分类树数据...")
        
        for item in intents:
            intent_code = item["intent_code"]
            
            # 查找是否已存在
            node = db.query(IntentNode).filter(IntentNode.intent_code == intent_code, IntentNode.deleted == 0).first()
            
            examples_json = None
            if "examples" in item and item["examples"]:
                examples_json = json.dumps(item["examples"], ensure_ascii=False)
                
            if node:
                print(f"更新节点: {intent_code} ({item['name']})")
                node.name = item["name"]
                node.level = item["level"]
                node.parent_code = item["parent_code"]
                node.description = item["description"]
                node.kind = item["kind"]
                node.sort_order = item["sort_order"]
                if examples_json:
                    node.examples = examples_json
                node.update_time = datetime.now()
                node.update_by = "system"
            else:
                print(f"新增节点: {intent_code} ({item['name']})")
                node_id = generate_stable_id(intent_code)
                new_node = IntentNode(
                    id=node_id,
                    intent_code=intent_code,
                    name=item["name"],
                    level=item["level"],
                    parent_code=item["parent_code"],
                    description=item["description"],
                    examples=examples_json,
                    kind=item["kind"],
                    sort_order=item["sort_order"],
                    enabled=1,
                    deleted=0,
                    create_by="system",
                    update_by="system",
                    create_time=datetime.now(),
                    update_time=datetime.now()
                )
                db.add(new_node)
                
        db.commit()
        print("意图分类数据初始化完成！")
    except Exception as e:
        db.rollback()
        print(f"初始化失败: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    init_intents()
