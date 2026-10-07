# -*- coding: utf-8 -*-
"""
把 knowledge/*.md 转成结构化 knowledge.json，供后端 search_knowledge 工具检索。

条目格式（约定）：每条以 "### 标题" 开头，正文含 "- 要点：/- 结论：/- 来源日期："
（或 - 场景/- 处理/- 结果/- 经验点）。模板示例（含 <!-- 投喂格式 -->）不计入。

用法：python3 build_knowledge.py <knowledge_dir> <out_json>
"""
import os
import re
import sys
import json

FILE_TOPIC = {
    "产品与品牌认知.md": "产品与品牌认知",
    "销售话术与沟通.md": "销售话术与沟通",
    "客户需求与画像.md": "客户需求与画像",
    "选型实战案例.md": "选型实战案例",
    "销售管理与其他.md": "销售管理与其他",
}


def parse_md(path, topic):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    # 去掉 HTML 注释块（投喂格式模板、说明）
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    lines = text.split("\n")
    entries = []
    cur = None
    for ln in lines:
        m = re.match(r"^###\s+(.+?)\s*$", ln)
        if m:
            title = m.group(1).strip()
            # 跳过纯说明性标题
            if title in ("[分类标签] 一句话主题",):
                cur = None
                continue
            cur = {"topic": topic, "title": title, "body": []}
            entries.append(cur)
        else:
            if cur is not None:
                cur["body"].append(ln)
    out = []
    for e in entries:
        body = "\n".join(e["body"]).strip()
        if not body:
            continue
        # 来源日期
        dm = re.search(r"来源日期：\s*(\d{4}-\d{2}-\d{2})", body)
        e["date"] = dm.group(1) if dm else ""
        # 去掉空 body 与重复空白
        e["body"] = re.sub(r"\n{3,}", "\n\n", body)
        out.append(e)
    return out


def main():
    kd = sys.argv[1]
    out_path = sys.argv[2]
    all_entries = []
    for fn, topic in FILE_TOPIC.items():
        p = os.path.join(kd, fn)
        if os.path.exists(p):
            all_entries.extend(parse_md(p, topic))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=1)
    print("entries:", len(all_entries))
    for e in all_entries[:3]:
        print(" -", e["topic"], "|", e["title"][:40])


if __name__ == "__main__":
    main()
