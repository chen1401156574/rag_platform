"""旧实验检索路径。

主问答链路已收敛到 ``retrieval.py -> search_v2.py``。本文件仅保留为历史导入
的明确失败哨兵，禁止新增业务代码引用。
"""


def generate_embedding(*_, **__):
    raise RuntimeError("retrieval2.py 是旧实验路径，请改用 service.core.retrieval.retrieve_content")


def retrieve_content(*_, **__):
    raise RuntimeError("retrieval2.py 是旧实验路径，请改用 service.core.retrieval.retrieve_content")


if __name__ == "__main__":
    raise SystemExit("retrieval2.py 是旧实验路径，禁止直接运行")
