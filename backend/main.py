# -*- coding: utf-8 -*-
"""
AI 售前工程师 · 后端服务（MVP）
- 用 DeepSeek function calling：LLM 决定是否调用"选型工具"
- 选型工具完全复用 selection.py（已与前端 16/16 一致性验证）
- API key 只从环境变量读，绝不落前端

启动：
  export DEEPSEEK_API_KEY=sk-xxxx
  uvicorn main:app --host 0.0.0.0 --port 8010

前端：AI_API.endpoint = https://<你的域名>/api/ai-sales
"""
import os
import json
import re
from pathlib import Path
from typing import Optional, List, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import selection

BASE_DIR = Path(__file__).resolve().parent.parent

# 品牌 → 数据文件（与前端 BRAND_FILES 完全一致）
BRAND_FILES = {
    "leroysomer": "leroysomer.json",
    "利莱森玛 TAL": "leroysomer-tal.json",
    "利莱森玛 LSA 中高压": "leroysomer-hv.json",
    "斯坦福": "stanford.json",
    "斯坦福中高压": "stanford-hv.json",
    "AGG KI系列": "agg-ki.json",
    "AGG KK系列": "agg-kk.json",
    "美奥迪 Mecc Alte": "mecc-alte.json",
    "马拉松低压": "marathon.json",
    "英格N系列": "inger-n.json",
    "英格N3系列": "inger-n3.json",
    "铨一QYK": "qyk.json",
    "铨一QYI": "qyi.json",
    "铨一QYH中高压": "qyh.json",
    "顶一DINGOL": "dingol.json",
}

# 品牌别名（方便 LLM/用户口语命中）
# ⚠️ resolve_brand 用「别名 in key」模糊匹配，所以中高压别名必须比低压更具体、
#    且要放在前面优先命中（如「利莱森玛中高压」不能被「利莱森玛」抢先命中）
BRAND_ALIASES = {
    # ---- 中高压（必须优先，否则会被低压同名别名抢走）----
    "利莱森玛中高压": "利莱森玛 LSA 中高压",
    "利莱森玛 lsa 中高压": "利莱森玛 LSA 中高压",
    "lsa中高压": "利莱森玛 LSA 中高压",
    "lsa中压": "利莱森玛 LSA 中高压",
    "利莱森玛hv": "利莱森玛 LSA 中高压",
    "斯坦福中高压": "斯坦福中高压",
    "stamford中高压": "斯坦福中高压",
    "stanford中高压": "斯坦福中高压",
    "斯坦福hv": "斯坦福中高压",
    "qyh": "铨一QYH中高压",
    "铨一qyh": "铨一QYH中高压",
    "铨一 qyh": "铨一QYH中高压",
    "铨一中高压": "铨一QYH中高压",
    "qyh中高压": "铨一QYH中高压",
    # ---- 低压 ----
    "利莱森玛": "leroysomer",
    "利莱森玛lsa": "leroysomer",
    "lsa": "leroysomer",
    "leroy": "leroysomer",
    "利莱森玛tal": "利莱森玛 TAL",
    "tal": "利莱森玛 TAL",
    "斯坦福": "斯坦福",
    "stamford": "斯坦福",
    "stanford": "斯坦福",
    "ki": "AGG KI系列",
    "kk": "AGG KK系列",
    "agg": "AGG KK系列",
    "美奥迪": "美奥迪 Mecc Alte",
    "mecc": "美奥迪 Mecc Alte",
    "meccalte": "美奥迪 Mecc Alte",
    "马拉松": "马拉松低压",
    "marathon": "马拉松低压",
    "英格": "英格N系列",
    "inger": "英格N系列",
    "qyk": "铨一QYK",
    "qyi": "铨一QYI",
    "铨一": "铨一QYK",
    "订高": "顶一DINGOL",
    "顶一": "顶一DINGOL",
    "dingol": "顶一DINGOL",
}

_DATA_CACHE = {}

# 销售经验知识库（由 knowledge/*.md 生成，见 build_knowledge.py）
_KNOWLEDGE = []


def load_knowledge():
    global _KNOWLEDGE
    if _KNOWLEDGE:
        return _KNOWLEDGE
    p = BASE_DIR / "backend" / "knowledge.json"
    if not p.exists():
        p = BASE_DIR / "knowledge.json"
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            _KNOWLEDGE = json.load(f)
    return _KNOWLEDGE


def load_brand(brand):
    """按品牌读数据（懒加载 + 缓存）"""
    if brand in _DATA_CACHE:
        return _DATA_CACHE[brand]
    fn = BRAND_FILES.get(brand)
    if not fn:
        return []
    p = BASE_DIR / fn
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        raw = json.load(f)
    recs = [r for r in raw if r.get("type") == "generator"]
    _DATA_CACHE[brand] = recs
    return recs


def search_knowledge(query, limit=6):
    """在销售经验库里做关键词检索（无需外部依赖）。
    中文按「单字命中 + 短语整体命中」加权打分，返回最相关条目。
    """
    entries = load_knowledge()
    if not entries:
        return []
    q = (query or "").strip().lower()
    if not q:
        return entries[:limit]
    # 提取查询片段：按空白/标点切，再补 2~4 字滑窗
    segs = set()
    for tok in re.split(r"[\s,，。/、；;：:？?！!（）()\[\]\"']+", q):
        tok = tok.strip()
        if len(tok) >= 2:
            segs.add(tok)
            # 长片段再拆 2-4 字子串，提升召回
            for n in (2, 3, 4):
                for i in range(len(tok) - n + 1):
                    segs.add(tok[i:i + n])
    scored = []
    for e in entries:
        hay = (e.get("title", "") + " " + e.get("body", "")).lower()
        score = 0
        for s in segs:
            if s in hay:
                score += len(s) * (3 if s in e.get("title", "").lower() else 1)
        if score > 0:
            scored.append((score, e))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored[:limit]]


def resolve_brand(name):
    """把用户/LLM 给的品牌名解析成前端 option value"""
    if not name:
        return None
    if name in BRAND_FILES:
        return name
    key = str(name).strip().lower()
    if key in BRAND_ALIASES:
        return BRAND_ALIASES[key]
    for alias, real in BRAND_ALIASES.items():
        if alias in key or key in alias:
            return real
    return None


app = FastAPI(title="Generator AI Sales API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 生产可收敛到 bob-agg.github.io
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# DeepSeek 调用
# ============================================================
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

SYSTEM_PROMPT = """你是发电机组选型专家（售前工程师）。语言精简、专业，不寒暄、不啰嗦。

你有工具，可查真实产品库做选型计算，并检索销售经验库。规则：

1. 用户给出选型需求（功率/电压/频率/用途/海拔/温度等）时，调用 run_selection 工具，用真实数据给结论。
2. 涉及报价差价、认证（CE/UL/欧五/船级等）、防护等级、出线数/接线体系、降额曲线、动力特性、启动方式、尺寸参考、双频率/双轴等非纯选型问题，先调用 search_knowledge 检索经验库，按经验库口径回答（经验库是本厂实际做法，优先于通用知识）。
3. 如果用户要做"选型"，但缺关键参数（频率 50/60Hz、电压、功率、主用还是备用），先问最缺的那一两项，别一次问一堆。
4. 工具返回结果后，用语术给出结论：推荐型号 + 关键参数 + 一句理由。不要罗列全部候选。
5. 功率口径：主用=持续功率(H级)；备用=应急功率(27℃或40℃)。海拔>1000m 或温度>40℃ 会降额。
   - ⚠️ 用户未说明现场温度时，温度一律默认 **40℃**（调用工具时 temperature 传 40），不要自己假设更低温度；只有用户明确给出其他温度才用其值。
6. 不确定的数据不要编。工具没返回匹配就如实说"当前库中无满足条件的型号，建议降低功率或换品牌"；经验库没覆盖的，按通用知识答但要说明。
7. 【职责边界】你只做"产品选型"和"售前经验问答"两件事。报价、开询价单、下订单、合同、交期、发货等业务动作都不是你的职责：用户若要求这些，只回一句"具体报价/下单请联系销售处理"，不要追问、不要反复询问是否要报价或发询价单、不要主动引导下单。
8. 回答用中文，2-5 行，关键数字要准。不要暴露"工具/函数/JSON/经验库"等实现细节，直接给结论。"""

TOOLS = [{
    "type": "function",
    "function": {
        "name": "run_selection",
        "description": "在真实发电机产品库中做选型匹配，返回推荐型号与候选。需要品牌、频率、电压、功率等参数。",
        "parameters": {
            "type": "object",
            "properties": {
                "brand": {"type": "string", "description": "品牌，如 利莱森玛LSA(低压) / 利莱森玛中高压 / 斯坦福 / 斯坦福中高压 / AGG KK / AGG KI / 美奥迪 / 马拉松 / 英格N / 铨一QYK / 铨一QYI / 铨一QYH中高压 / 订高。中高压电压(3300/6600/10000/11000V等)必须用带「中高压」的品牌名"},
                "frequency": {"type": "string", "enum": ["50Hz", "60Hz"], "description": "频率"},
                "voltage": {"type": "number", "description": "额定电压（V）。中高压用 3300/6600/11000 等"},
                "winding": {"type": "string", "description": "接线方式，如 Y / Δ / YY；中高压用绕组代码（工具会自动尝试）。不确定可留空"},
                "main_power": {"type": "number", "description": "① 主用功率（持续，H级口径）"},
                "standby_power": {"type": "number", "description": "② 备用功率"},
                "power_unit": {"type": "string", "enum": ["kW", "kVA"], "default": "kW", "description": "功率单位"},
                "standby_temp": {"type": "string", "enum": ["27c", "40c"], "default": "27c", "description": "备用功率的温度基准"},
                "altitude": {"type": "number", "default": 0, "description": "安装海拔（米）"},
                "temperature": {"type": "number", "default": 40, "description": "环境温度（℃）。用户未说明现场温度时必须用 40；仅当用户明确给了其他温度才填其他值"},
                "phase": {"type": "integer", "enum": [1, 3], "default": 3, "description": "相数"},
                "option": {"type": "string", "enum": ["none", "ip44", "c5"], "default": "none", "description": "特殊选配：none=无；ip44=IP44防护（选型需求÷0.9放大）；c5=C5高防腐（暂不降额）。用户提到IP44/防护/防雨时传 ip44"},
            },
            "required": ["brand", "frequency"],
        },
    },
}, {
    "type": "function",
    "function": {
        "name": "search_knowledge",
        "description": "检索本厂销售经验库（实战经验/话术/认证/差价/防护/降额/尺寸/启动等）。当问题涉及选型以外的工厂实际口径（报价、认证、配置、流程、动力特性）时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索关键词，如 CE认证 / 双轴电机 差价 / 防护等级 IP54 / 断路器 并联"},
            },
            "required": ["query"],
        },
    },
}]


def _auto_winding(brand, freq, voltage, records, phase=3, pole="4", pf=0.8):
    """用户没给接线时，返回该电压下**所有**命中的接线（逗号分隔）。
    如美奥迪 400V 同时有 Y / YY 两个接线档（覆盖不同型号段）——
    只取第一个（Y）会导致 YY 型号永远不进候选，所以全部返回。
    """
    hits = selection.find_volt_matches(records, brand, freq, voltage, pf, pole, phase)
    conns = []
    for h in hits:
        c = h["conn"]
        if c and c not in conns:
            conns.append(c)
    return ",".join(conns)


def call_deepseek(messages):
    import urllib.request
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise HTTPException(status_code=500, detail="服务端未配置 DEEPSEEK_API_KEY")
    payload = {
        "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        "messages": messages,
        "tools": TOOLS,
        "temperature": 0.3,
        "stream": False,
    }
    req = urllib.request.Request(
        DEEPSEEK_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_tool(args):
    """执行 run_selection 工具"""
    brand = resolve_brand(args.get("brand"))
    if not brand:
        return {"ok": False, "reason": "未识别的品牌：" + str(args.get("brand"))}
    freq = args.get("frequency")
    voltage = args.get("voltage")
    records = load_brand(brand)
    if not records:
        return {"ok": False, "reason": "该品牌暂无数据"}

    unit = args.get("power_unit", "kW")
    phase = int(args.get("phase", 3) or 3)
    main_p = args.get("main_power")
    stdby_p = args.get("standby_power")

    winding = (args.get("winding") or "").strip()
    if not winding and voltage is not None:
        winding = _auto_winding(brand, freq, voltage, records, phase=phase)
    # 中高压：winding 传的不是 code 时，尝试用电压档 code
    if selection.is_hv(brand) and voltage is not None:
        codes = {r.get("winding_code") for r in records
                 if r.get("frequency") == freq and selection.volt_hit_range(r, voltage)}
        if codes and winding not in codes:
            winding = sorted(codes)[0]

    res = selection.select(
        records, brand, freq, voltage, winding, 0.8,
        main_power=main_p, main_unit=unit,
        standby_power=stdby_p, standby_unit=unit,
        standby_temp=args.get("standby_temp", "27c"),
        altitude=args.get("altitude", 0) or 0,
        temp=args.get("temperature") if args.get("temperature") is not None else 40,
        user_phase=phase, user_pole="4", opt_code=(args.get("option") or "none"),
    )
    # 精简给 LLM 的信息
    out = {
        "ok": res["ok"], "reason": res["reason"],
        "brand": brand, "frequency": freq, "voltage": voltage, "winding": winding,
        "option": (args.get("option") or "none"),
        "af": res["af"], "tf": res["tf"], "tot": res["tot"],
        "goalMain": res["goalM"], "goalStandby": res["goalS"],
        "totalCandidates": res["total"], "passed": res["passed"],
        "recommended": None, "top5": [],
    }
    if res["top"]:
        t = res["top"]
        out["recommended"] = {
            "model": t["model"], "winding": t["winding_label"],
            "grade": t["grade"], "pf": t["pf"], "wires": t["wires"], "exc": t["exc"],
            "mainBase": t["baseM"], "mainCorrected": t["cpM"],
            "standby27": t["s27"], "standby40": t["s40"],
        }
    for c in res["candidates"][:5]:
        out["top5"].append({"model": c["model"], "winding": c["winding_label"],
                            "ok": c["ok"], "cp": c["cp"], "s27": c["s27"], "s40": c["s40"]})
    return out


class AskReq(BaseModel):
    question: str
    history: Optional[List[Any]] = None


@app.get("/health")
def health():
    return {"ok": True, "brands": len(BRAND_FILES), "keyConfigured": bool(os.environ.get("DEEPSEEK_API_KEY")),
            "knowledge": len(load_knowledge())}


@app.post("/api/ai-sales")
def ai_sales(req: AskReq):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if req.history:
        for h in req.history[-8:]:
            if h.get("role") in ("user", "assistant") and h.get("content"):
                messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": req.question})

    # 第一轮：可能触发工具
    resp = call_deepseek(messages)
    msg = resp["choices"][0]["message"]

    tool_trace = []
    # 最多三轮工具调用（选型 + 经验检索可能混合），防止死循环
    for _ in range(3):
        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            break
        messages.append(msg)
        for tc in tool_calls:
            fn = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            if fn == "run_selection":
                result = run_tool(args)
                tool_trace.append({"fn": fn, "args": args, "result": result})
            elif fn == "search_knowledge":
                hits = search_knowledge(args.get("query", ""))
                result = {"ok": True, "count": len(hits), "entries": [
                    {"topic": h["topic"], "title": h["title"], "content": h["body"], "date": h.get("date", "")}
                    for h in hits
                ]}
                tool_trace.append({"fn": fn, "args": args, "result": {"ok": True, "count": len(hits)}})
            else:
                result = {"ok": False, "reason": "未知工具"}
            messages.append({
                "role": "tool", "tool_call_id": tc["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })
        resp = call_deepseek(messages)
        msg = resp["choices"][0]["message"]

    return JSONResponse({
        "reply": msg.get("content") or "",
        "toolUsed": len(tool_trace) > 0,
        "trace": tool_trace,
    })
