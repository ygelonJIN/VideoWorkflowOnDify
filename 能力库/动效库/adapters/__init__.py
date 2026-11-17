# -*- coding: utf-8 -*-
"""进件适配器：把不同来源形态翻译成"能渲的候选工程"。

每个适配器提供两个函数：
    can_handle(path, kind) -> bool
    prepare(src_unit, dst_dir) -> dict | None
返回 dict：{"composition": <相对文件名>, "width": w, "height": h, "duration": sec, "note": str}
返回 None 表示这个单元交给下一个适配器。

新增来源 = 新增一个文件 + 在 REGISTRY 里排进去，不改 admit.py 主流程。
"""
from . import generic_html  # noqa: F401

REGISTRY = [generic_html]
