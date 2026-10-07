# -*- coding: utf-8 -*-
"""
发电机选型逻辑 —— Python 版，完全照搬前端 index.html 的算法。

原则：数值/取整/边界/排序/回退，与前端一行一行对齐，不做任何"优化"。
前端对应位置注释已标出（index.html 行号随版本变化，以函数名为准）。

⚠️ 改这里之前，必须先确认前端同样逻辑，两边必须一致。
"""


# ============================================================
# 取整工具 —— 对齐前端 Math.round（四舍五入，负数向 +∞）
# Python 内置 round() 是银行家舍入，不能用！
# ============================================================
def js_round(x):
    import math
    return math.floor(x + 0.5)


def js_round1(x):
    """前端 Math.round(x*10)/10 —— 保留1位小数"""
    import math
    return math.floor(x * 10 + 0.5) / 10


def js_round3(x):
    """前端 Math.round(x*1000)/1000"""
    import math
    return math.floor(x * 1000 + 0.5) / 1000


# ============================================================
# 品牌判定（对齐前端 isHVBrand / isAGG / isLeroy / isStanford）
# ============================================================
HV_BRANDS = {"利莱森玛 LSA 中高压", "斯坦福中高压", "铨一QYH中高压"}
AGG_BRANDS = {"AGG KI系列", "AGG KK系列"}
MECC_BRAND = "美奥迪 Mecc Alte"
STANFORD_BRAND = "斯坦福"


def is_hv(brand):
    return brand in HV_BRANDS


def is_agg(brand):
    return brand in AGG_BRANDS


def is_mecc(brand):
    return brand == MECC_BRAND


def is_stanford(brand):
    return brand == STANFORD_BRAND


# ============================================================
# 修正系数表（frontend: 底层逻辑，不可变）
# ============================================================
# 利莱森玛 LSA 海拔
ALT_FACTOR = [
    (1000, 1.0), (1500, 0.975), (2000, 0.949),
    (2500, 0.922), (3000, 0.894), (3500, 0.866), (4000, 0.837),
]
# 利莱森玛 LSA 温度（H/F/B 级）
TEMP_FACTOR_H = [(25, 1.076), (40, 1.0), (45, 0.973), (50, 0.946), (55, 0.918), (60, 0.889)]
TEMP_FACTOR_F = [(25, 1.095), (40, 1.0), (45, 0.966), (50, 0.931), (55, 0.894), (60, 0.856)]
TEMP_FACTOR_B = [(25, 1.14), (40, 1.0), (45, 0.949), (50, 0.894), (55, 0.837), (60, 0.775)]
TEMP_FACTORS = {"H": TEMP_FACTOR_H, "F": TEMP_FACTOR_F, "B": TEMP_FACTOR_B}

# 斯坦福
ST_ALT_FACTOR = [
    (1000, 1.0), (1500, 0.97), (2000, 0.94),
    (2500, 0.91), (3000, 0.88), (3500, 0.85), (4000, 0.82),
]

# AGG (KI/KK)
AGG_ALT_FACTOR = [
    (1000, 1.00), (1500, 0.97), (2000, 0.94), (2500, 0.91),
    (3000, 0.88), (3500, 0.85), (4000, 0.82), (4500, 0.79),
]
AGG_TEMP_FACTOR = [
    (25, 1.05), (40, 1.00), (45, 0.97), (50, 0.94), (55, 0.91), (60, 0.88),
]

# 美奥迪 Mecc Alte
MECC_ALT_FACTOR = [
    (1000, 1.00), (1500, 0.96), (2000, 0.91),
    (3000, 0.85), (4000, 0.78), (5000, 0.72), (6000, 0.65),
]
MECC_TEMP_FACTOR = [
    (25, 1.07), (40, 1.00), (45, 0.96), (50, 0.93),
    (55, 0.91), (60, 0.89), (65, 0.85), (70, 0.82),
]


def _lookup(tbl, v, first_is_floor=False, last_default=None):
    """
    按表查系数（对齐前端 for 循环：v <= max 命中即返回）。
    first_is_floor=True  → 前端「低于(含)第一档 max 按第一档」的写法。
    last_default         → 全部超出时返回的末档值。
    """
    if first_is_floor and v <= tbl[0][0]:
        return tbl[0][1]
    for mx, val in tbl:
        if v <= mx:
            return val
    return last_default if last_default is not None else tbl[-1][1]


def get_af(a):
    """LSA 海拔系数"""
    if a <= 0:
        return 1
    return _lookup(ALT_FACTOR, a, last_default=0.837)


def get_temp_factor(t, grade="H"):
    """LSA 温度系数（按温升等级）"""
    tbl = TEMP_FACTORS.get(grade, TEMP_FACTOR_H)
    return _lookup(tbl, t, first_is_floor=True)


def get_stanford_temp(t):
    """斯坦福温度系数（40℃及以下=1.0；40-45按45档）"""
    if t <= 40:
        return 1
    if t < 45:
        return 0.97
    if t < 50:
        return 0.94
    if t < 55:
        return 0.94
    if t < 60:
        return 0.91
    return 0.88


def get_stanford_af(a):
    if a <= 0:
        return 1
    return _lookup(ST_ALT_FACTOR, a, last_default=0.82)


def get_agg_temp(t):
    return _lookup(AGG_TEMP_FACTOR, t, first_is_floor=True, last_default=0.88)


def get_agg_af(a):
    if a <= 0:
        return 1
    return _lookup(AGG_ALT_FACTOR, a, last_default=0.79)


def get_mecc_temp(t):
    return _lookup(MECC_TEMP_FACTOR, t, first_is_floor=True, last_default=0.82)


def get_mecc_af(a):
    if a <= 0:
        return 1
    return _lookup(MECC_ALT_FACTOR, a, last_default=0.65)


def get_tf(brand, t):
    """温度修正系数（对齐前端步骤2 的三元表达式）"""
    if is_hv(brand):
        return 1
    if is_agg(brand):
        return get_agg_temp(t)
    if is_mecc(brand):
        return get_mecc_temp(t)
    if is_stanford(brand):
        return get_stanford_temp(t)
    return get_temp_factor(t, "H")


def get_af_by_brand(brand, a):
    """海拔修正系数（对齐前端步骤3 的三元表达式）"""
    if is_hv(brand):
        return 1
    if is_agg(brand):
        return get_agg_af(a)
    if is_mecc(brand):
        return get_mecc_af(a)
    if is_stanford(brand):
        return get_stanford_af(a)
    return get_af(a)


# ============================================================
# 电压 / 接线解析（对齐前端 getConnVoltPairs / parseVoltPairs / voltRange）
# ============================================================
import re


def _parse_float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def volt_range(volt_str):
    """
    解析电压字段 → (lo, hi)；解析不出返回 None。
    对齐前端 voltRange：'380V' / '3.3kV' / '380-440V' / '190V-208V' / '660-690V'
    """
    if volt_str is None:
        return None
    s = str(volt_str).strip()
    is_kv = bool(re.search(r"kV", s, re.I))
    s = re.sub(r"[kK]?V", "", s).strip()
    parts = []
    for x in s.split("-"):
        clean = re.sub(r"[^\d.]", "", x)
        v = _parse_float(clean)
        if v is not None and v > 0:
            parts.append(v)
    if not parts:
        return None
    lo, hi = min(parts), max(parts)
    if is_kv:
        lo *= 1000
        hi *= 1000
    return (lo, hi)


def volt_hit_range(rec, volt):
    """用户电压是否落该记录电压区间内"""
    rg = volt_range(rec.get("voltage"))
    if rg is None:
        return False
    return volt >= rg[0] - 0.01 and volt <= rg[1] + 0.01


def parse_volt_pairs(label):
    """
    解析 winding_label → [{conn, volt}]（对齐前端 parseVoltPairs）
    例："Y-400/Δ-230/YY-200V" → [{Y,400},{Δ,230},{YY,200}]
    """
    out = []
    if label is None:
        return out
    s = str(label)
    s = re.sub(r"[（(][^）)]*[）)]", "", s)       # 去括号备注
    s = re.sub(r"^\s*(三相|单相)\s*[·•]\s*", "", s)  # 去「三相 · 」前缀
    s = s.replace("V", "")                        # 去 V 后缀
    for seg in s.split("/"):
        seg = seg.strip()
        if not seg:
            continue
        m = re.match(r"^(.*?)[\s-]*([\d.]+)\s*$", seg)
        if not m:
            continue
        conn = re.sub(r"[\s-]+$", "", m.group(1)).strip()
        v = _parse_float(m.group(2))
        if v is None or v <= 0:
            continue
        out.append({"conn": conn, "volt": v})
    return out


def get_conn_volt_pairs(rec):
    """
    对齐前端 getConnVoltPairs：
    1) 新库：conn 非空且不含 '/' → 单接线，voltage 解析出唯一电压
    2) 中高压：conn 为空 → 用 voltage 区间 lo 构造一条 {conn:'', volt:lo}
    3) 兜底：解析 winding_label
    """
    if not rec:
        return []
    conn = "" if rec.get("winding_conn") is None else str(rec.get("winding_conn")).strip()
    volt = "" if rec.get("voltage") is None else str(rec.get("voltage")).strip()
    if conn and "/" not in conn:
        is_kv = bool(re.search(r"kV", volt, re.I))
        v = _parse_float(re.sub(r"[^\d.]", "", re.sub(r"kV|V", "", volt, flags=re.I)))
        if v is not None and v > 0:
            return [{"conn": conn, "volt": v * 1000 if is_kv else v}]
    rg = volt_range(volt)
    if rg:
        return [{"conn": "", "volt": rg[0]}]
    return parse_volt_pairs(rec.get("winding_label"))


def volt_eq(a, b):
    try:
        return abs(float(a) - float(b)) < 0.01
    except (TypeError, ValueError):
        return False


# ============================================================
# 相数 / 极数（对齐前端 phaseMatch / poleMatch / isSinglePhase）
# ============================================================
def is_single_phase_code(w, label=""):
    if str(w).startswith("1ph-"):
        return True
    if re.match(r"^[A-Z]+\d+-1ph-", str(w)):
        return True
    if re.search(r"(单相|1ph)", str(label or ""), re.I):
        return True
    return False


def rec_phase(rec):
    """对齐前端 recPhase：phase 字段为唯一依据，绝不用接线名反推"""
    v = rec.get("phase")
    if v is None or v == "":
        return None
    try:
        n = int(float(v))
        if n in (1, 3):
            return n
    except (TypeError, ValueError):
        pass
    t = str(v).strip()
    if t in ("单相", "1", "1ph"):
        return 1
    if t in ("三相", "3", "3ph"):
        return 3
    return None


def phase_match(rec, user_phase):
    """user_phase: 3 或 1"""
    rp = rec_phase(rec)
    if rp is not None:
        return rp == user_phase
    lab = str(rec.get("winding_label") or "")
    code = str(rec.get("winding_code") or "")
    is_1b = ("单相" in lab) or bool(re.match(r"^1ph", code, re.I))
    if user_phase == 1:
        return is_1b
    return not is_1b


def pole_match(rec, user_pole):
    """user_pole: '4' / '6' / 'all'"""
    if user_pole == "all":
        return True
    if rec.get("poles") is None:
        return True
    try:
        return int(float(rec["poles"])) == int(user_pole)
    except (TypeError, ValueError):
        return True


# ============================================================
# 核心：选型（对齐前端 doSearch）
# ============================================================
def select(records, brand, freq, voltage, winding, pf_user,
           main_power=None, main_unit="kW",
           standby_power=None, standby_unit="kW",
           standby_temp="27c", altitude=0, temp=40,
           user_phase=3, user_pole="4", opt_code="none"):
    """
    返回结构（供 AI 组织话术）：
    {
      "ok": bool, "reason": str|None,
      "isHV": bool, "is1ph": bool,
      "af": float, "tf": float, "tot": float,
      "goalM": float, "goalS": float, "hasM": bool, "hasS": bool,
      "unitM": str, "unitS": str,
      "total": int, "passed": int,
      "top": {...}|None,
      "candidates": [ {...}, ... ]   # 前 N 个
    }

    ⚠️ 参数含义与前端一一对应：
      voltage   —— 用户输入额定电压（数字）或 None（旧模式按 winding 代码）
      winding   —— 接线名（模式A）或 winding_code（模式B/旧模式）
      main_power —— ①主用功率（H级口径），None/<=0 = 未启用
      standby_power —— ②备用功率，None/<=0 = 未启用
      standby_temp —— '27c' / '40c'
    """
    hv = is_hv(brand)
    agg = is_agg(brand)
    mecc = is_mecc(brand)
    stanford = is_stanford(brand)

    # ---- 归一化功率输入 ----
    has_m = main_power is not None and float(main_power) >= 1
    has_s = standby_power is not None and float(standby_power) >= 1
    if not has_m and not has_s:
        return {"ok": False, "reason": "请至少提供主用功率或备用功率"}
    p_m = float(main_power) if has_m else 0
    p_s = float(standby_power) if has_s else 0

    # 40℃ 备用仅低压；中高压防御性回落 27℃
    tr_key = "40c" if standby_temp == "40c" else "27c"
    if hv and tr_key == "40c":
        tr_key = "27c"

    opt_dec = 0.9 if opt_code == "ip44" else 1.0

    # ---- 单相判定（对齐前端 is1ph 块）----
    is_1ph = (user_phase == 1)
    if not is_1ph:
        if is_single_phase_code(winding):
            is_1ph = True
        elif voltage is not None:
            hits = find_volt_matches(records, brand, freq, voltage, pf_user, user_pole, user_phase)
            for h in hits:
                if h["conn"] == winding:
                    if is_single_phase_code(h["rec"].get("winding_code", ""),
                                            h["rec"].get("winding_label", "")):
                        is_1ph = True
                        break

    # ---- 目标功率（对齐前端 calcGoal）----
    def calc_goal(p, unit):
        tk = js_round1(p / pf_user) if unit == "kW" else p
        gb = p if is_1ph else tk
        return {"targetKVA": tk, "goal": js_round1(gb / opt_dec)}

    gm = calc_goal(p_m, main_unit) if has_m else None
    gs = calc_goal(p_s, standby_unit) if has_s else None
    goal_m = gm["goal"] if gm else 0
    goal_s = gs["goal"] if gs else 0
    goal = goal_m if has_m else goal_s

    # 单相候选按输入单位读列；三相恒 kVA
    u_key_m = main_unit if is_1ph else "kVA"
    u_key_s = standby_unit if is_1ph else "kVA"

    # ---- 修正系数 ----
    tf = get_tf(brand, temp)
    af = get_af_by_brand(brand, altitude)
    tot = js_round3(af * tf)

    # ---- 遍历记录（对齐前端 for 循环）----
    mode_a = voltage is not None
    w_set = winding.split(",") if (hv and winding and "," in str(winding)) else None

    lst = []
    for g in records:
        # 匹配模式判定
        if mode_a:
            if w_set:
                continue  # 模式A 不处理中高压 combo
            if not pole_match(g, user_pole):
                continue
            if not phase_match(g, user_phase):
                continue
            if hv:
                if g.get("winding_code") != winding:
                    continue
                w_match = volt_hit_range(g, voltage)
            elif volt_hit_range(g, voltage):
                pr = get_conn_volt_pairs(g)
                w_match = (pr[0]["conn"] == winding) if pr else (str(g.get("winding_conn") or "") == winding)
            else:
                pairs = get_conn_volt_pairs(g)
                v_hit = c_hit = False
                for pair in pairs:
                    if volt_eq(pair["volt"], voltage):
                        v_hit = True
                        if pair["conn"] == winding:
                            c_hit = True
                            break
                w_match = v_hit and c_hit
        else:
            if w_set:
                w_match = g.get("winding_code") in w_set
            else:
                w_match = g.get("winding_code") == winding

        if g.get("frequency") != freq or not w_match:
            continue
        # PF 过滤
        if g.get("pf") is not None and abs(float(g["pf"]) - pf_user) > 0.01:
            continue

        mk_m, mk_s = u_key_m, u_key_s
        # 主用列：低压 cont_h；中高压 cont_f，无则回退 cont_h
        if hv:
            main_col = "cont_f" if (g.get("cont_f_" + mk_m) or 0) > 0 else "cont_h"
        else:
            main_col = "cont_h"
        # 备用列
        if hv:
            standby_col = ("stdby_f_" + tr_key) if (g.get("stdby_f_" + tr_key + "_" + mk_s) or 0) > 0 else ("stdby_h_" + tr_key)
            col27 = ("stdby_f_27c") if (g.get("stdby_f_27c_" + mk_s) or 0) > 0 else "stdby_h_27c"
        else:
            standby_col = "stdby_h_" + tr_key
            col27 = "stdby_h_27c"
        col40 = "stdby_h_40c"

        # 低压 40℃ 反向异常数据剔除
        if has_s and tr_key == "40c" and not hv:
            ev27 = g.get("stdby_h_27c_" + mk_s) or 0
            ev40 = g.get("stdby_h_40c_" + mk_s) or 0
            if ev27 > 0 and ev40 > 0 and ev27 < ev40:
                continue

        # 双功率校核
        base_m = cp_m = ok_m = None
        if has_m:
            base_m = g.get(main_col + "_" + mk_m)
            if not base_m or base_m <= 0:
                continue
            cp_m = js_round1(base_m * tot)
            ok_m = cp_m >= goal_m
        base_s = cp_s = ok_s = None
        if has_s:
            base_s = g.get(standby_col + "_" + mk_s)
            if not base_s or base_s <= 0:
                continue
            cp_s = js_round1(base_s * tot)
            ok_s = cp_s >= goal_s

        ok = (ok_m and ok_s) if (has_m and has_s) else (ok_m if has_m else ok_s)
        best_grade = ("F" if main_col == "cont_f" else "H") if hv else "H"

        lst.append({
            "model": g.get("model"),
            "winding_label": g.get("winding_label") or g.get("winding_code"),
            "frequency": g.get("frequency"),
            "voltage": g.get("voltage"),
            "winding_conn": g.get("winding_conn"),
            "wires": g.get("wires"),
            "pf": g.get("pf"),
            "exc": g.get("exc_std") or "",
            "grade": best_grade,
            "baseM": base_m, "cpM": cp_m, "okM": ok_m,
            "baseS": base_s, "cpS": cp_s, "okS": ok_s,
            "s27": g.get(col27 + "_" + mk_s),
            "s40": g.get(col40 + "_" + mk_s),
            "cp": cp_m if has_m else cp_s,
            "ok": bool(ok),
            "uk": mk_m if has_m else mk_s,
            "rec": g,
        })

    # ---- 排序（对齐前端 list.sort）----
    def sort_key(x):
        grade_rank = 0
        if hv:
            grade_rank = 0 if x["grade"] == "F" else 1
        ok_rank = 0 if x["ok"] else 1
        dist = abs(x["cp"] - goal)
        return (grade_rank, ok_rank, dist)

    lst.sort(key=sort_key)

    top = None
    for x in lst:
        if x["ok"]:
            top = x
            break

    passed = sum(1 for x in lst if x["ok"])

    return {
        "ok": True, "reason": None,
        "isHV": hv, "is1ph": is_1ph,
        "brand": brand, "freq": freq, "voltage": voltage, "winding": winding,
        "af": af, "tf": tf, "tot": tot,
        "goalM": goal_m, "goalS": goal_s, "hasM": has_m, "hasS": has_s,
        "unitM": main_unit, "unitS": standby_unit,
        "standbyTemp": tr_key,
        "altitude": altitude, "temp": temp,
        "total": len(lst), "passed": passed,
        "top": _slim(top) if top else None,
        "candidates": [_slim(x) for x in lst[:20]],
    }


def _slim(x):
    """精简候选（去掉 rec 原记录，避免 JSON 过大）"""
    return {
        "model": x["model"],
        "winding_label": x["winding_label"],
        "voltage": x["voltage"],
        "frequency": x["frequency"],
        "winding_conn": x["winding_conn"],
        "wires": x["wires"],
        "pf": x["pf"],
        "exc": x["exc"],
        "grade": x["grade"],
        "baseM": x["baseM"], "cpM": x["cpM"], "okM": x["okM"],
        "baseS": x["baseS"], "cpS": x["cpS"], "okS": x["okS"],
        "s27": x["s27"], "s40": x["s40"],
        "cp": x["cp"], "ok": x["ok"], "uk": x["uk"],
    }


def find_volt_matches(records, brand, freq, volt, pf_user, user_pole, user_phase):
    """对齐前端 findVoltMatches"""
    hits = []
    for r in records:
        if r.get("frequency") != freq:
            continue
        if r.get("pf") is not None and abs(float(r["pf"]) - pf_user) > 0.01:
            continue
        if not pole_match(r, user_pole):
            continue
        if not phase_match(r, user_phase):
            continue
        if volt_hit_range(r, volt):
            pairs = get_conn_volt_pairs(r)
            conn = pairs[0]["conn"] if pairs else (r.get("winding_conn") or "")
            hits.append({"rec": r, "conn": conn, "volt": volt})
            continue
        pairs2 = get_conn_volt_pairs(r)
        for p in pairs2:
            if volt_eq(p["volt"], volt):
                hits.append({"rec": r, "conn": p["conn"], "volt": p["volt"]})
                break
    return hits
