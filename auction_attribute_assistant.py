import argparse
import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


TIME_POINTS = {
    "t_91930": "09:19:30",
    "t_920": "09:20:00",
    "t_923": "09:23:00",
    "t_final": "09:24:50",
    "t_925": "09:25:00",
}

ATTR_TYPE_WEIGHT = {
    "概念": 1.45,
    "方向": 1.5,
    "业绩": 1.4,
    "事件": 1.35,
    "行业": 1.25,
    "股权": 0.85,
    "身位": 0.8,
    "市值": 0.65,
    "价格": 0.45,
    "板块": 0.25,
}

DIRECTION_DISPLAY_NAMES = {
    "TOPCon": "光伏高效电池（TOPCon）",
    "HJT": "异质结电池（HJT）",
    "xBC": "背接触电池（xBC）",
    "CPO": "光电共封装（CPO）",
    "OCS": "光交换机（OCS）",
    "CPU": "中央处理器（CPU）",
    "AI服务器": "人工智能服务器（AI服务器）",
    "PCB设备": "电路板设备（PCB设备）",
    "LED": "发光二极管（LED）",
    "ST板块": "风险警示股（ST）",
    "X射线检测": "工业X光检测（X射线检测）",
}


def display_direction(tag):
    return DIRECTION_DISPLAY_NAMES.get(tag, tag)


def display_directions(tags):
    return [display_direction(tag) for tag in tags]


def parse_float(value, default=0.0):
    if value is None:
        return default
    text = str(value).strip().replace(",", "")
    if not text:
        return default
    if text.endswith("%"):
        text = text[:-1]
    try:
        return float(text)
    except ValueError:
        return default


def parse_bool(value):
    return str(value).strip().lower() in {"1", "true", "yes", "y", "是", "国资"}


def parse_time(value):
    text = str(value).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"无法识别时间: {value}")


def money_yi(value):
    return f"{value / 100000000:.2f}亿"


def pct(value):
    if value is None or math.isnan(value):
        return "--"
    return f"{value * 100:.2f}%"


def pct_raw(value):
    return f"{value:.2f}%"


def size_bucket(float_mv):
    yi = float_mv / 100000000
    if yi <= 30:
        return "小盘"
    if yi <= 100:
        return "中小盘"
    if yi <= 300:
        return "中盘"
    return "大盘"


def price_bucket(price):
    if price <= 0:
        return "未知价格"
    if price < 10:
        return "低价"
    if price < 30:
        return "中价"
    return "高价"


@dataclass
class StockProfile:
    code: str
    name: str
    industry: str
    concepts: list
    float_mv: float
    total_mv: float
    board: str
    is_state_owned: bool
    is_st: bool
    days_listed: float
    ret_5d: float
    ret_10d: float
    ret_20d: float
    ret_60d: float
    limitup_count_20d: float
    streak_limitup: float
    event_tags: list
    performance_tags: list
    direction_tags: list


def load_profiles(path):
    profiles = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            code = row["code"].strip()
            profiles[code] = StockProfile(
                code=code,
                name=row.get("name", "").strip(),
                industry=row.get("industry", "").strip() or "未知行业",
                concepts=[
                    item.strip()
                    for item in row.get("concepts", "").split("|")
                    if item.strip()
                ],
                float_mv=parse_float(row.get("float_mv")),
                total_mv=parse_float(row.get("total_mv")),
                board=row.get("board", "").strip() or "未知板块",
                is_state_owned=parse_bool(row.get("is_state_owned")),
                is_st=parse_bool(row.get("is_st")),
                days_listed=parse_float(row.get("days_listed")),
                ret_5d=parse_float(row.get("ret_5d")),
                ret_10d=parse_float(row.get("ret_10d")),
                ret_20d=parse_float(row.get("ret_20d")),
                ret_60d=parse_float(row.get("ret_60d")),
                limitup_count_20d=parse_float(row.get("limitup_count_20d")),
                streak_limitup=parse_float(row.get("streak_limitup")),
                event_tags=[
                    item.strip()
                    for item in row.get("event_tags", "").split("|")
                    if item.strip()
                ],
                performance_tags=[
                    item.strip()
                    for item in row.get("performance_tags", "").split("|")
                    if item.strip()
                ],
                direction_tags=[
                    item.strip()
                    for item in row.get("direction_tags", "").split("|")
                    if item.strip()
                ],
            )
    return profiles


def load_snapshots(path):
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            limit_up_price = parse_float(row.get("limit_up_price"))
            bid1_volume = parse_float(row.get("bid1_volume"))
            direct_seal = parse_float(row.get("seal_amount"))
            if direct_seal <= 0:
                direct_seal = limit_up_price * bid1_volume
            rows.append(
                {
                    "time": parse_time(row["time"]),
                    "time_text": row["time"].strip(),
                    "code": row["code"].strip(),
                    "name": row.get("name", "").strip(),
                    "last_price": parse_float(row.get("last_price")),
                    "limit_up_price": limit_up_price,
                    "bid1_price": parse_float(row.get("bid1_price")),
                    "bid1_volume": bid1_volume,
                    "change_pct": parse_float(row.get("change_pct")),
                    "turnover": parse_float(row.get("turnover")),
                    "seal_amount": direct_seal,
                }
            )
    return rows


def load_market_heat(path=Path("market_heat.csv")):
    heat = {}
    if not path.exists():
        return heat
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            direction = row.get("direction", "").strip()
            if not direction:
                continue
            heat[direction] = {
                "a_heat": parse_float(row.get("a_heat")),
                "us_heat": parse_float(row.get("us_heat")),
                "days_hot": parse_float(row.get("days_hot")),
                "notes": row.get("notes", "").strip(),
            }
    return heat


def nearest_snapshot(rows, code, target):
    target_time = parse_time(target)
    code_rows = [row for row in rows if row["code"] == code]
    if not code_rows:
        return None
    return min(
        code_rows,
        key=lambda row: abs(
            datetime.combine(datetime.today(), row["time"])
            - datetime.combine(datetime.today(), target_time)
        ),
    )


def is_auction_limitup(row):
    if row["seal_amount"] <= 0:
        return False
    if row["limit_up_price"] > 0 and row["bid1_price"] > 0:
        return row["bid1_price"] >= row["limit_up_price"] * 0.999 and row["change_pct"] >= 9.8
    return row["change_pct"] >= 9.8


def build_stock_metrics(rows, profiles, final_time=None):
    final_time = final_time or TIME_POINTS["t_final"]
    profiles_by_name = {profile.name: profile for profile in profiles.values() if profile.name}
    codes = sorted({row["code"] for row in rows})
    metrics = []
    for code in codes:
        final_row = nearest_snapshot(rows, code, final_time)
        if not final_row or not is_auction_limitup(final_row):
            continue

        profile = profiles.get(code) or profiles_by_name.get(final_row["name"])
        if is_st_stock(final_row["name"], profile):
            continue
        t_91930 = nearest_snapshot(rows, code, TIME_POINTS["t_91930"])
        t_920 = nearest_snapshot(rows, code, TIME_POINTS["t_920"])
        t_923 = nearest_snapshot(rows, code, TIME_POINTS["t_923"])

        final_seal = final_row["seal_amount"]
        seal_91930 = t_91930["seal_amount"] if t_91930 else 0
        seal_920 = t_920["seal_amount"] if t_920 else 0
        seal_923 = t_923["seal_amount"] if t_923 else 0
        float_mv = profile.float_mv if profile else 0
        retention = final_seal / seal_91930 if seal_91930 > 0 else math.nan
        seal_to_float_mv = final_seal / float_mv if float_mv > 0 else math.nan
        streak = profile.streak_limitup if profile else 0

        metrics.append(
            {
                "code": profile.code if profile else code,
                "name": (profile.name if profile and profile.name else final_row["name"]),
                "profile": profile,
                "final_seal": final_seal,
                "add_after_920": final_seal - seal_920,
                "add_after_923": final_seal - seal_923,
                "retention": retention,
                "seal_to_float_mv": seal_to_float_mv,
                "limit_up_price": final_row["limit_up_price"],
                "float_mv": float_mv,
                "stock_score": (
                    rankable(final_seal)
                    + rankable(final_seal - seal_920) * 1.2
                    + rankable(final_seal - seal_923) * 0.8
                    + rankable(seal_to_float_mv) * 1000000000
                    + streak * 10000000
                ),
            }
        )
    return metrics


def is_st_stock(name, profile=None):
    text = str(name or "").upper()
    if "ST" in text or "*ST" in text:
        return True
    if profile and profile.is_st:
        return True
    return False


def rankable(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0
    return value


def attributes_for_metric(metric):
    profile = metric["profile"]
    attrs = []
    if not profile:
        return attrs
    attrs.append(("行业", profile.industry))
    for concept in profile.concepts:
        attrs.append(("概念", concept))
    for tag in profile.event_tags:
        attrs.append(("事件", tag))
    for tag in profile.performance_tags:
        attrs.append(("业绩", tag))
    for tag in profile.direction_tags:
        attrs.append(("方向", tag))
    attrs.append(("市值", size_bucket(profile.float_mv)))
    attrs.append(("价格", price_bucket(metric["limit_up_price"])))
    attrs.append(("股权", "国资" if profile.is_state_owned else "民企"))
    attrs.append(("板块", profile.board))
    attrs.append(("身位", "连板" if profile.streak_limitup >= 2 else "首板"))
    return attrs


def aggregate_attributes(metrics):
    groups = defaultdict(list)
    for metric in metrics:
        for attr_type, attr_name in attributes_for_metric(metric):
            groups[(attr_type, attr_name)].append(metric)

    results = []
    for (attr_type, attr_name), items in groups.items():
        final_sum = sum(item["final_seal"] for item in items)
        add_920_sum = sum(item["add_after_920"] for item in items)
        add_923_sum = sum(item["add_after_923"] for item in items)
        avg_seal_to_float = average(
            item["seal_to_float_mv"] for item in items if not math.isnan(item["seal_to_float_mv"])
        )
        base_score = (
            len(items) * 25
            + final_sum / 100000000 * 20
            + max(add_920_sum, 0) / 100000000 * 25
            + max(add_923_sum, 0) / 100000000 * 15
            + avg_seal_to_float * 100 * 10
        )
        score = base_score * ATTR_TYPE_WEIGHT.get(attr_type, 1.0)
        results.append(
            {
                "attr_type": attr_type,
                "attr_name": attr_name,
                "items": sorted(items, key=lambda item: item["final_seal"], reverse=True),
                "count": len(items),
                "final_sum": final_sum,
                "add_920_sum": add_920_sum,
                "add_923_sum": add_923_sum,
                "avg_seal_to_float": avg_seal_to_float,
                "score": score,
            }
        )
    return sorted(results, key=lambda row: row["score"], reverse=True)


def average(values):
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / len(values)


def related_high_momentum(best_attr, profiles):
    if not best_attr:
        return []
    attr_type = best_attr["attr_type"]
    attr_name = best_attr["attr_name"]
    candidates = []
    for profile in profiles.values():
        match = False
        if attr_type == "行业" and profile.industry == attr_name:
            match = True
        elif attr_type == "概念" and attr_name in profile.concepts:
            match = True
        elif attr_type == "事件" and attr_name in profile.event_tags:
            match = True
        elif attr_type == "业绩" and attr_name in profile.performance_tags:
            match = True
        elif attr_type == "方向" and attr_name in profile.direction_tags:
            match = True
        elif attr_type == "市值" and size_bucket(profile.float_mv) == attr_name:
            match = True
        elif attr_type == "股权" and ("国资" if profile.is_state_owned else "民企") == attr_name:
            match = True
        elif attr_type == "板块" and profile.board == attr_name:
            match = True
        elif attr_type == "身位":
            current = "连板" if profile.streak_limitup >= 2 else "首板"
            match = current == attr_name
        if not match:
            continue

        role = classify_role(profile)
        score = (
            profile.ret_10d * 2
            + profile.ret_20d * 1.5
            + profile.limitup_count_20d * 8
            + profile.streak_limitup * 10
        )
        candidates.append((score, role, profile))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[:8]


def classify_role(profile):
    if profile.streak_limitup >= 3 or profile.limitup_count_20d >= 5:
        return "高度锚"
    if profile.float_mv >= 15000000000 and profile.ret_20d >= 20:
        return "趋势中军"
    if profile.ret_10d >= 40 or profile.ret_20d >= 70:
        return "风险参照"
    return "补涨映射"


def judge_state(best_attr, related):
    if not best_attr:
        return "样本不足", "没有识别到有效竞价涨停样本。"
    strong_group = best_attr["count"] >= 2 and best_attr["add_920_sum"] > 0
    hot_related = [item for item in related if item[2].ret_10d >= 40 or item[2].ret_20d >= 70]
    high_anchor = [item for item in related if item[1] == "高度锚"]
    if best_attr["count"] <= 1:
        return "单票事件", "封单个股较强，但同属性竞价涨停聚合不足。"
    if strong_group and len(hot_related) >= 3:
        return "高潮一致", "同属性近期高涨幅品种较多，竞价端仍在集中加单，需要防范一致后分化。"
    if strong_group and high_anchor:
        return "补涨扩散", "近期已有同属性高度锚，今日竞价资金继续向同属性封单和加单扩散。"
    if strong_group:
        return "主线加强", "同属性多只竞价涨停且9:20后合计加单为正，竞价共识在增强。"
    return "分歧预警", "最强属性有封单表现，但9:20后合计加单不强或转弱。"


def format_stock_line(metric):
    profile = metric["profile"]
    concepts = "|".join(profile.concepts[:4]) if profile else "未知概念"
    catalysts = []
    if profile:
        catalysts = profile.performance_tags[:2] + profile.event_tags[:2]
    catalyst_text = f", 催化:{'|'.join(catalysts)}" if catalysts else ""
    industry = profile.industry if profile else "未知行业"
    ret_10d = pct_raw(profile.ret_10d) if profile else "--"
    ret_20d = pct_raw(profile.ret_20d) if profile else "--"
    streak = int(profile.streak_limitup) if profile else 0
    return (
        f"{metric['name']}({metric['code']}): 封单{money_yi(metric['final_seal'])}, "
        f"9:20后{money_yi(metric['add_after_920'])}, 9:23后{money_yi(metric['add_after_923'])}, "
        f"封单/流通市值{pct(metric['seal_to_float_mv'])}, {industry}, {concepts}, "
        f"近10日{ret_10d}, 近20日{ret_20d}, 连板{streak}{catalyst_text}"
    )


def driver_mechanism(profile):
    if not profile:
        return ("未知驱动", "属性资料不足，暂时只能确认封单强度。")

    concepts = set(profile.concepts)
    events = set(profile.event_tags)
    performance = set(profile.performance_tags)
    directions = set(profile.direction_tags)
    all_tags = concepts | events | performance | directions | {profile.industry}

    if any("归母净利同比增" in tag or "扣非高增" in tag or "一季报增长" in tag for tag in all_tags):
        return (
            "业绩超预期驱动",
            "封单背后可能是财报或业绩预告带来的盈利重估，重点看增长是否可持续、是否有量价齐升或订单支撑。",
        )
    if any("涨价" in tag or "供给偏紧" in tag or "资源" in tag for tag in all_tags):
        return (
            "资源涨价驱动",
            "封单背后可能是上游价格上涨和供需紧张带来的利润弹性，重点看商品价格、中军强度和同资源品种扩散。",
        )
    if any(tag in all_tags for tag in ["算力", "CPO", "光模块", "AI服务器", "人工智能", "机器人", "高端制造"]):
        return (
            "产业趋势驱动",
            "封单背后可能是产业链景气或技术主线扩散，重点看中军、趋势核心和同链条补涨是否共振。",
        )
    if any("国资" in tag or "央企" in tag or "国企改革" in tag for tag in all_tags) or profile.is_state_owned:
        return (
            "国资重估驱动",
            "封单背后可能是央国企资产重估、资源整合或改革预期，重点看同集团、同资源和大市值中军是否配合。",
        )
    if profile.streak_limitup >= 2 or profile.limitup_count_20d >= 4:
        return (
            "情绪身位驱动",
            "封单背后可能是短线辨识度和连板情绪，重点看开板承接、同身位晋级率和炸板率。",
        )
    return (
        "补涨扩散驱动",
        "封单背后可能是同属性低位补涨，重点看高位锚是否继续强、后排是否快速掉队。",
    )


def summarize_driver_mechanisms(metrics):
    rows = []
    for metric in sorted(metrics, key=lambda item: item["final_seal"], reverse=True)[:5]:
        mechanism, reason = driver_mechanism(metric["profile"])
        rows.append((metric, mechanism, reason))
    return rows


def generate_report(metrics, attr_results, profiles):
    if not metrics:
        return "没有识别到符合条件的竞价涨停封单股票。请检查快照字段和时间点。"

    final_rank = sorted(metrics, key=lambda item: item["final_seal"], reverse=True)
    add_920_rank = sorted(metrics, key=lambda item: item["add_after_920"], reverse=True)
    add_923_rank = sorted(metrics, key=lambda item: item["add_after_923"], reverse=True)
    best_attr = pick_primary_attribute(attr_results)
    heat_map = load_market_heat()
    diffusion_dirs = score_diffusion_directions(metrics, heat_map)
    related = related_high_momentum(best_attr, profiles)
    state, reason = judge_state(best_attr, related)
    seal_king = final_rank[0]

    profile = seal_king["profile"]
    core_attrs = []
    if profile:
        core_attrs.extend(profile.concepts[:4])
        core_attrs.extend(profile.performance_tags[:2])
        core_attrs.extend(profile.event_tags[:2])
        core_attrs.append(size_bucket(profile.float_mv))
        core_attrs.append("国资" if profile.is_state_owned else "民企")
        core_attrs.append("连板" if profile.streak_limitup >= 2 else "首板")

    lines = []
    lines.append("【9:25 竞价属性映射报告】")
    lines.append("")
    lines.append("一、今日竞价封单王")
    lines.append(format_stock_line(seal_king))
    lines.append(f"核心属性: {' + '.join(core_attrs) if core_attrs else '属性资料不足'}")
    lines.append("")
    lines.append("二、今日加单最强")
    lines.append("9:20后净加单: " + format_stock_line(add_920_rank[0]))
    lines.append("9:23后冲刺加单: " + format_stock_line(add_923_rank[0]))
    lines.append("")
    lines.append("三、最强竞价属性")
    if best_attr:
        reps = "、".join(item["name"] for item in best_attr["items"][:5])
        lines.append(
            f"{best_attr['attr_type']}:{best_attr['attr_name']} - "
            f"竞价涨停{best_attr['count']}只, 最终合计封单{money_yi(best_attr['final_sum'])}, "
            f"9:20后合计加单{money_yi(best_attr['add_920_sum'])}, "
            f"9:23后冲刺{money_yi(best_attr['add_923_sum'])}。"
        )
        lines.append(f"代表股: {reps}")
    lines.append("")
    lines.append("四、同属性近期高涨幅锚")
    if related:
        for _, role, profile in related[:5]:
            lines.append(
                f"{profile.name}({profile.code}): 近5日{pct_raw(profile.ret_5d)}, "
                f"近10日{pct_raw(profile.ret_10d)}, 近20日{pct_raw(profile.ret_20d)}, "
                f"20日涨停{int(profile.limitup_count_20d)}次, 连板{int(profile.streak_limitup)}, 角色:{role}"
            )
    else:
        lines.append("未找到明显同属性高涨幅锚。")
    lines.append("")
    lines.append("五、潜在扩散方向")
    lines.append("封单股方向标签:")
    for metric, tags in summarize_direction_tags(metrics):
        tag_text = " / ".join(display_directions(tags)) if tags else "暂无方向标签"
        lines.append(f"{metric['name']}({metric['code']}): {tag_text}")
    lines.append("")
    lines.append("最可能扩散方向:")
    if diffusion_dirs:
        for row in diffusion_dirs[:8]:
            reps = "、".join(item["name"] for item in row["items"][:4])
            heat_text = []
            if row["a_heat"]:
                heat_text.append(f"A股热度{row['a_heat']:.1f}")
            if row["us_heat"]:
                heat_text.append(f"美股映射{row['us_heat']:.1f}")
            if row["days_hot"]:
                heat_text.append(f"持续{int(row['days_hot'])}天")
            notes = f"，线索:{row['notes']}" if row["notes"] else ""
            lines.append(
                f"{display_direction(row['direction'])}: 评分{row['score']:.1f}，封单{money_yi(row['final_sum'])}，"
                f"9:20后加单{money_yi(row['add_920_sum'])}，覆盖{row['count']}只，代表:{reps}，"
                f"{' / '.join(heat_text) if heat_text else '暂无外部热度'}{notes}"
            )
    else:
        lines.append("暂无可排序方向。")
    return "\n".join(lines)


def generate_early_report(metrics, profiles, label="09:20"):
    if not metrics:
        return f"【{label} 竞价扩散初判】\n未识别到有效封单样本。"

    heat_map = load_market_heat()
    ranked = sorted(metrics, key=lambda item: item["final_seal"], reverse=True)
    top5 = ranked[:5]
    diffusion_dirs = score_diffusion_directions(top5, heat_map)
    sentiment = early_sentiment(top5)

    lines = [f"【{label} 竞价扩散初判】", ""]
    lines.append("一、封单前五")
    for idx, metric in enumerate(top5, start=1):
        tags = " / ".join(display_directions(potential_direction_tags(metric["profile"])[:6])) or "暂无方向"
        lines.append(
            f"{idx}. {metric['name']}: 封单{money_yi(metric['final_seal'])}，方向:{tags}"
        )
    lines.append("")
    lines.append("二、前五关联共振")
    for row in diffusion_dirs[:5]:
        reps = "、".join(item["name"] for item in row["items"][:5])
        heat_bits = []
        if row["a_heat"]:
            heat_bits.append(f"A股{row['a_heat']:.1f}")
        if row["us_heat"]:
            heat_bits.append(f"美股{row['us_heat']:.1f}")
        heat_text = f"，热度:{'/'.join(heat_bits)}" if heat_bits else ""
        lines.append(
            f"{display_direction(row['direction'])}: 关联{row['count']}只，封单{money_yi(row['final_sum'])}，代表:{reps}{heat_text}"
        )
    lines.append("")
    lines.append(f"三、{label}情绪")
    lines.append(sentiment)
    lines.append("")
    lines.append("四、初判最可能扩散")
    for idx, row in enumerate(diffusion_dirs[:3], start=1):
        lines.append(f"{idx}. {display_direction(row['direction'])}，代表:{'、'.join(item['name'] for item in row['items'][:3])}")
    return "\n".join(lines)


def early_sentiment(top_items):
    st_count = 0
    total = len(top_items)
    total_seal = sum(item["final_seal"] for item in top_items)
    strong_count = sum(1 for item in top_items if item["final_seal"] >= 300000000)
    if total == 0:
        return "样本不足。"
    if strong_count >= 3 and total_seal >= 1500000000:
        return "封单情绪强，前排资金一致性较高；继续看09:23后是否加单。"
    if strong_count >= 2:
        return "封单情绪偏强，但仍需看09:23后是否扩散到同方向。"
    return "封单情绪一般，先按试探看待，重点等09:23和09:24:50确认。"


def pick_primary_attribute(attr_results):
    primary_types = {"方向", "概念", "事件", "业绩", "行业"}
    for attr in attr_results:
        if attr["attr_type"] in primary_types:
            return attr
    return attr_results[0] if attr_results else None


def potential_direction_tags(profile):
    if not profile:
        return []
    tags = []
    tags.extend(profile.direction_tags)
    tags.extend(profile.concepts)
    tags.extend(profile.event_tags)
    tags.extend(profile.performance_tags)
    tags.append(profile.industry)
    if profile.is_state_owned:
        tags.append("央国企")
    if profile.streak_limitup >= 2:
        tags.append("连板情绪")

    normalized = []
    for tag in tags:
        tag = tag.strip()
        if not tag:
            continue
        for child in split_direction_tag(tag):
            if child and child not in normalized:
                normalized.append(child)
    return normalized[:10]


def split_direction_tag(tag):
    aliases = {
        "AI服务器": ["AI服务器", "算力硬件"],
        "液冷服务器": ["液冷", "服务器散热"],
        "CPO": ["CPO", "光模块"],
        "光模块": ["光模块", "CPO"],
        "钨": ["钨", "小金属", "资源涨价"],
        "硬质合金": ["硬质合金", "刀具", "高端制造"],
        "一季报增长": ["一季报增长", "业绩高增"],
        "实控人变更": ["实控人变更", "控制权变更"],
        "重组": ["重组", "资产注入"],
        "存储芯片": ["存储芯片", "半导体"],
        "半导体设备": ["半导体设备", "设备国产替代"],
        "PCB设备": ["PCB设备", "先进封装设备"],
        "OCS": ["OCS", "光通信"],
    }
    return aliases.get(tag, [tag])


def summarize_direction_tags(metrics):
    rows = []
    for metric in sorted(metrics, key=lambda item: item["final_seal"], reverse=True)[:8]:
        rows.append((metric, potential_direction_tags(metric["profile"])))
    return rows


def score_diffusion_directions(metrics, heat_map):
    groups = defaultdict(list)
    for metric in metrics:
        for tag in potential_direction_tags(metric["profile"]):
            groups[tag].append(metric)

    results = []
    for direction, items in groups.items():
        final_sum = sum(item["final_seal"] for item in items)
        add_920_sum = sum(item["add_after_920"] for item in items)
        add_923_sum = sum(item["add_after_923"] for item in items)
        count = len(items)
        top_item = max(items, key=lambda item: item["final_seal"])
        heat = heat_map.get(direction, {})
        a_heat = heat.get("a_heat", 0)
        us_heat = heat.get("us_heat", 0)
        days_hot = heat.get("days_hot", 0)
        score = (
            final_sum / 100000000 * 22
            + max(add_920_sum, 0) / 100000000 * 28
            + max(add_923_sum, 0) / 100000000 * 18
            + count * 12
            + a_heat * 10
            + us_heat * 8
            + min(days_hot, 5) * 4
        )
        results.append(
            {
                "direction": direction,
                "items": sorted(items, key=lambda item: item["final_seal"], reverse=True),
                "count": count,
                "final_sum": final_sum,
                "add_920_sum": add_920_sum,
                "add_923_sum": add_923_sum,
                "top_item": top_item,
                "a_heat": a_heat,
                "us_heat": us_heat,
                "days_hot": days_hot,
                "notes": heat.get("notes", ""),
                "score": score,
            }
        )
    return sorted(results, key=lambda row: row["score"], reverse=True)


def main():
    parser = argparse.ArgumentParser(description="竞价属性映射助手")
    parser.add_argument("--snapshot", default="auction_snapshot.csv", help="竞价快照CSV")
    parser.add_argument("--profile", default="stock_profile.csv", help="股票属性CSV")
    parser.add_argument("--output", default="auction_report.txt", help="报告输出路径")
    args = parser.parse_args()

    snapshot_path = Path(args.snapshot)
    profile_path = Path(args.profile)
    output_path = Path(args.output)

    profiles = load_profiles(profile_path)
    snapshots = load_snapshots(snapshot_path)
    metrics = build_stock_metrics(snapshots, profiles)
    attr_results = aggregate_attributes(metrics)
    report = generate_report(metrics, attr_results, profiles)

    output_path.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
