import csv
import json
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from PIL import ImageGrab

from auction_attribute_assistant import (
    display_direction,
    load_market_heat,
    load_profiles,
    money_yi,
    potential_direction_tags,
)
from screen_observer import prepare_for_ocr, run_ocr


CONFIG_PATH = Path("screen_observer_config.json")
CAPTURE_DIR = Path("opening_captures")
RAW_CSV = Path("opening_momentum_raw.csv")
REPORT_PATH = Path("opening_momentum_report.txt")
OPENING_TIMES = ["09:30:10", "09:31:00", "09:32:00", "09:33:00"]


def parse_time(value):
    return datetime.strptime(value, "%H:%M:%S").time()


def target_datetime(clock):
    return datetime.combine(datetime.now().date(), parse_time(clock))


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))


def capture_ocr(label, config):
    region = config["region"]
    bbox = (region["left"], region["top"], region["right"], region["bottom"])
    CAPTURE_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = CAPTURE_DIR / f"{label}_{stamp}.png"
    img = ImageGrab.grab(bbox=bbox)
    img.save(image_path)
    prepared = prepare_for_ocr(image_path)
    ocr_path = run_ocr(prepared)
    return image_path, ocr_path


def compact_text(value):
    return re.sub(r"\s+", "", value.strip())


def extract_codes_names(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    codes = []
    for line in lines:
        compact = compact_text(line)
        if re.fullmatch(r"[03668]\d{5}", compact):
            codes.append(compact)
        elif re.fullmatch(r"[03668]\d{4,5}", compact):
            codes.append(compact)

    names = []
    in_name_column = False
    for line in lines:
        compact = compact_text(line)
        if compact == "名称":
            in_name_column = True
            continue
        if not in_name_column:
            continue
        if compact in {"R", "K"}:
            break
        if re.fullmatch(r"[RKS\d\.\-一，％%]+", compact):
            continue
        if re.search(r"[\u4e00-\u9fff]", compact):
            names.append(compact)

    profiles = load_profiles(Path("stock_profile.csv"))
    by_name = {profile.name: profile.code for profile in profiles.values()}
    rows = []
    count = max(len(codes), len(names))
    for idx in range(count):
        name = names[idx] if idx < len(names) else ""
        code = by_name.get(name) or (codes[idx] if idx < len(codes) else "")
        if code or name:
            rows.append({"rank": idx + 1, "code": code, "name": name})
    return rows


def append_rows(sample_time, rows):
    is_new = not RAW_CSV.exists()
    with RAW_CSV.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["time", "rank", "code", "name"])
        if is_new:
            writer.writeheader()
        for row in rows:
            writer.writerow({"time": sample_time, **row})


def watch():
    if not CONFIG_PATH.exists():
        raise SystemExit("缺少观察区域配置，请先完成竞价表格区域校准。")
    if RAW_CSV.exists():
        RAW_CSV.unlink()
    if REPORT_PATH.exists():
        REPORT_PATH.unlink()

    config = load_config()
    now = datetime.now()
    schedule = [(clock, target_datetime(clock)) for clock in OPENING_TIMES]
    schedule = [(clock, target) for clock, target in schedule if target > now]
    if not schedule:
        print("今天09:30-09:35观察窗口已过。")
        return

    print("开盘五分钟拉升观察已启动。请切到涨速榜/快速涨幅榜，并保持区域不被遮挡。")
    for clock, target in schedule:
        print(f"等待 {clock} 采样")
        while datetime.now() < target:
            time.sleep(min(1.0, max(0.05, (target - datetime.now()).total_seconds())))
        image_path, ocr_path = capture_ocr(clock.replace(":", ""), config)
        rows = []
        if ocr_path and ocr_path.exists():
            rows = extract_codes_names(ocr_path.read_text(encoding="utf-8", errors="ignore"))
            append_rows(clock, rows)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 已截图:{image_path}，解析到{len(rows)}行")
    build_report()


def build_report():
    if not RAW_CSV.exists():
        REPORT_PATH.write_text("没有开盘拉升样本。", encoding="utf-8")
        return
    profiles = load_profiles(Path("stock_profile.csv"))
    heat = load_market_heat()
    rows = list(csv.DictReader(RAW_CSV.open("r", encoding="utf-8-sig")))

    stock_scores = defaultdict(lambda: {"score": 0, "count": 0, "best_rank": 999, "first_time": "", "name": "", "code": ""})
    direction_scores = defaultdict(lambda: {"score": 0, "stocks": set(), "names": []})

    for row in rows:
        rank = int(row["rank"])
        code = row["code"]
        name = row["name"]
        key = code or name
        if not key:
            continue
        rank_score = max(0, 30 - rank)
        data = stock_scores[key]
        data["score"] += rank_score
        data["count"] += 1
        data["best_rank"] = min(data["best_rank"], rank)
        data["first_time"] = data["first_time"] or row["time"]
        data["name"] = profiles.get(code).name if code in profiles else name
        data["code"] = code

        profile = profiles.get(code)
        if not profile:
            continue
        for tag in potential_direction_tags(profile)[:10]:
            h = heat.get(tag, {})
            direction_scores[tag]["score"] += rank_score + h.get("a_heat", 0) * 5 + h.get("us_heat", 0) * 3
            direction_scores[tag]["stocks"].add(key)
            if data["name"] not in direction_scores[tag]["names"]:
                direction_scores[tag]["names"].append(data["name"])

    top_stocks = sorted(stock_scores.values(), key=lambda x: (x["score"], -x["best_rank"]), reverse=True)[:8]
    top_dirs = sorted(direction_scores.items(), key=lambda kv: (kv[1]["score"], len(kv[1]["stocks"])), reverse=True)[:5]

    leader = top_stocks[0] if top_stocks else None
    mainline = top_dirs[0][0] if top_dirs else "暂无主线"

    lines = ["【开盘五分钟快速拉升报告】", ""]
    lines.append("一、快速拉升前排")
    for idx, item in enumerate(top_stocks[:5], start=1):
        lines.append(f"{idx}. {item['name']}: 出现{item['count']}次，最佳排名{item['best_rank']}，首次{item['first_time']}")
    lines.append("")
    lines.append("二、当日主线初判")
    if top_dirs:
        for idx, (direction, data) in enumerate(top_dirs[:3], start=1):
            reps = "、".join(data["names"][:4])
            lines.append(f"{idx}. {display_direction(direction)}，代表:{reps}")
    else:
        lines.append("暂无可判断主线。")
    lines.append("")
    lines.append("三、龙头初判")
    if leader:
        lines.append(f"{leader['name']}，原因: 开盘五分钟出现频率和排名强度最高。")
    else:
        lines.append("暂无。")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"已生成开盘五分钟报告: {REPORT_PATH.resolve()}")


if __name__ == "__main__":
    watch()
