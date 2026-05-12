import argparse
import csv
import json
import re
import shutil
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import Tk, Canvas

from PIL import ImageGrab

from auction_attribute_assistant import (
    aggregate_attributes,
    build_stock_metrics,
    generate_early_report,
    generate_report,
    load_profiles,
    load_snapshots,
)


DEFAULT_TIMES = ["09:15:01", "09:19:30", "09:20:00", "09:23:00", "09:24:00", "09:24:50", "09:25:00"]
CONFIG_PATH = Path("screen_observer_config.json")
CAPTURE_DIR = Path("screen_captures")
RAW_OCR_CSV = Path("screen_ocr_raw.csv")
OBSERVED_SNAPSHOT_CSV = Path("auction_snapshot_observed.csv")
OBSERVED_REPORT = Path("auction_report_observed.txt")
EARLY_REPORT_0920 = Path("auction_report_0920.txt")
EARLY_REPORT_0924 = Path("auction_report_0924.txt")


def parse_clock(value):
    return datetime.strptime(value, "%H:%M:%S").time()


def next_datetime(clock_text):
    now = datetime.now()
    clock = parse_clock(clock_text)
    target = datetime.combine(now.date(), clock)
    return target


def load_config():
    if not CONFIG_PATH.exists():
        return None
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    configured_times = config.get("times") or []
    merged_times = []
    for item in DEFAULT_TIMES + configured_times:
        if item not in merged_times:
            merged_times.append(item)
    config["times"] = merged_times
    return config


def save_config(config):
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def calibrate_region():
    root = Tk()
    root.attributes("-fullscreen", True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.25)
    root.configure(bg="black")

    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    canvas = Canvas(root, width=screen_w, height=screen_h, cursor="cross", bg="black")
    canvas.pack(fill="both", expand=True)

    state = {"start": None, "rect": None, "region": None}

    def on_down(event):
        state["start"] = (event.x, event.y)
        if state["rect"]:
            canvas.delete(state["rect"])
        state["rect"] = canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="red", width=3)

    def on_move(event):
        if not state["start"] or not state["rect"]:
            return
        x0, y0 = state["start"]
        canvas.coords(state["rect"], x0, y0, event.x, event.y)

    def on_up(event):
        if not state["start"]:
            return
        x0, y0 = state["start"]
        x1, y1 = event.x, event.y
        left, right = sorted([x0, x1])
        top, bottom = sorted([y0, y1])
        state["region"] = {"left": left, "top": top, "right": right, "bottom": bottom}
        root.quit()

    canvas.create_text(
        30,
        30,
        anchor="nw",
        fill="white",
        font=("Microsoft YaHei", 18),
        text="请拖拽框选通达信竞价表格区域，松开鼠标后完成校准。按 Esc 取消。",
    )
    root.bind("<Escape>", lambda _: root.quit())
    canvas.bind("<ButtonPress-1>", on_down)
    canvas.bind("<B1-Motion>", on_move)
    canvas.bind("<ButtonRelease-1>", on_up)
    root.mainloop()
    root.destroy()

    if not state["region"]:
        raise SystemExit("未完成区域校准。")
    width = state["region"]["right"] - state["region"]["left"]
    height = state["region"]["bottom"] - state["region"]["top"]
    if width < 50 or height < 50:
        raise SystemExit("框选区域太小，请按住鼠标左键拖出一个完整表格区域后再松开。")
    config = {"region": state["region"], "times": DEFAULT_TIMES}
    save_config(config)
    print(f"已保存观察区域: {CONFIG_PATH.resolve()}")


def capture_region(label, config):
    region = config["region"]
    bbox = (region["left"], region["top"], region["right"], region["bottom"])
    CAPTURE_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = CAPTURE_DIR / f"{label}_{stamp}.png"
    img = ImageGrab.grab(bbox=bbox)
    img.save(image_path)

    prepared_path = prepare_for_ocr(image_path)
    ocr_path = run_ocr(prepared_path)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 已截图: {image_path}")
    if ocr_path and ocr_path.exists():
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 已OCR: {ocr_path}")
        append_ocr_rows(label, image_path, ocr_path)
        parsed_count = append_parsed_snapshot(label, ocr_path)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 解析到 {parsed_count} 行候选数据")
    return image_path


def prepare_for_ocr(image_path):
    from PIL import Image, ImageOps, ImageFilter

    img = Image.open(image_path).convert("L")
    img = ImageOps.autocontrast(img)
    scale = 3
    img = img.resize((img.width * scale, img.height * scale))
    img = img.filter(ImageFilter.SHARPEN)
    prepared_path = image_path.with_name(image_path.stem + "_ocr.png")
    img.save(prepared_path)
    return prepared_path


def run_ocr(image_path):
    ocr_path = image_path.with_suffix(".txt")
    win_ocr = Path("windows_ocr.ps1")
    if win_ocr.exists():
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(win_ocr),
                "-ImagePath",
                str(image_path),
            ],
            check=False,
            capture_output=True,
        )
        text = decode_process_output(result.stdout).strip()
        ocr_path.write_text(text, encoding="utf-8")
        if result.returncode == 0:
            return ocr_path

    if shutil.which("tesseract"):
        subprocess.run(
            ["tesseract", str(image_path), str(ocr_path.with_suffix("")), "-l", "chi_sim+eng"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return ocr_path if ocr_path.exists() else None
    return None


def decode_process_output(data):
    for encoding in ["utf-8-sig", "utf-8", "gb18030", "gbk"]:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("gb18030", errors="replace")


def append_ocr_rows(label, image_path, ocr_path):
    is_new = not RAW_OCR_CSV.exists()
    with RAW_OCR_CSV.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["sample_time", "image_path", "line_text"])
        for line in ocr_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line:
                writer.writerow([format_label_time(label), str(image_path), line])


def append_parsed_snapshot(label, ocr_path):
    text = ocr_path.read_text(encoding="utf-8", errors="ignore")
    rows = parse_column_ocr_table(format_label_time(label), text)
    if not rows:
        for line in text.splitlines():
            parsed = parse_market_line(format_label_time(label), line)
            if parsed:
                rows.append(parsed)
    if not rows:
        return 0

    is_new = not OBSERVED_SNAPSHOT_CSV.exists()
    with OBSERVED_SNAPSHOT_CSV.open("a", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "time",
            "code",
            "name",
            "last_price",
            "limit_up_price",
            "bid1_price",
            "bid1_volume",
            "change_pct",
            "turnover",
            "seal_amount",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if is_new:
            writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def parse_column_ocr_table(sample_time, text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    raw_codes = []
    for line in lines:
        compact = compact_text(line)
        if re.fullmatch(r"[03668]\d{5}", compact):
            raw_codes.append(compact)
        elif re.fullmatch(r"[03668]\d{3}\d?", compact) and " " in line:
            raw_codes.append(compact)
    codes = raw_codes
    if not codes:
        return []

    names = extract_column_names(lines)
    seals = extract_seal_amounts(lines)
    codes = repair_codes(codes, names)
    count = min(len(codes), len(names), len(seals))
    rows = []
    for idx in range(count):
        rows.append(
            {
                "time": sample_time,
                "code": codes[idx],
                "name": names[idx],
                "last_price": 0,
                "limit_up_price": 0,
                "bid1_price": 0,
                "bid1_volume": 0,
                "change_pct": 10.0,
                "turnover": 0,
                "seal_amount": round(seals[idx], 2),
            }
        )
    return rows


def repair_codes(codes, names):
    profile_path = Path("stock_profile.csv")
    if not profile_path.exists():
        return codes
    try:
        profiles = load_profiles(profile_path)
    except Exception:
        return codes
    name_to_code = {profile.name: code for code, profile in profiles.items() if profile.name}
    repaired = []
    for idx, name in enumerate(names):
        mapped_code = name_to_code.get(name)
        if mapped_code:
            repaired.append(mapped_code)
            continue
        if idx < len(codes) and len(codes[idx]) == 6:
            repaired.append(codes[idx])
            continue
        repaired.append(codes[idx] if idx < len(codes) else "")
    return [code for code in repaired if code]


def extract_column_names(lines):
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
        if is_header_or_number(compact):
            continue
        if re.search(r"[\u4e00-\u9fff]", compact):
            names.append(compact)
    return names


def extract_seal_amounts(lines):
    seals = []
    for idx, line in enumerate(lines):
        compact = normalize_ocr_number(line)
        if "亿" in compact or "万" in compact:
            amount = parse_number_token(compact)
            if amount > 0:
                seals.append(amount)
            continue
        if compact in {"封单额4", "封单额", "封單額4", "封單額"}:
            for next_line in lines[idx + 1 :]:
                next_compact = normalize_ocr_number(next_line)
                if "亿" in next_compact or "万" in next_compact:
                    amount = parse_number_token(next_compact)
                    if amount > 0:
                        seals.append(amount)
    return seals


def compact_text(value):
    return re.sub(r"\s+", "", value)


def is_header_or_number(value):
    headers = {"代码", "名称", "涨幅％", "涨幅%", "涨速％", "涨速%", "换手％", "换手%", "开盘％", "开盘%", "封单额", "封單額"}
    if value in headers:
        return True
    return bool(re.fullmatch(r"[RKS\d\.\-一．％%]+", value))


def normalize_ocr_number(value):
    text = compact_text(value)
    text = text.replace("．", ".").replace("。", ".").replace("，", ".").replace(",", ".").replace("一", "-")
    text = text.replace("額", "额").replace("力.", "万").replace("力", "万")
    text = text.replace("亻乙", "亿").replace("乙", "亿").replace("到亿", "4亿")
    text = re.sub(r"^氐(?=\d)", "4.", text)
    text = text.replace("O", "0").replace("o", "0")
    return text


def append_parsed_snapshot_legacy(label, ocr_path):
    rows = []
    for line in ocr_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parsed = parse_market_line(format_label_time(label), line)
        if parsed:
            rows.append(parsed)
    if not rows:
        return 0

    is_new = not OBSERVED_SNAPSHOT_CSV.exists()
    with OBSERVED_SNAPSHOT_CSV.open("a", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "time",
            "code",
            "name",
            "last_price",
            "limit_up_price",
            "bid1_price",
            "bid1_volume",
            "change_pct",
            "turnover",
            "seal_amount",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if is_new:
            writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def format_label_time(label):
    if len(label) == 6 and label.isdigit():
        return f"{label[0:2]}:{label[2:4]}:{label[4:6]}"
    return datetime.now().strftime("%H:%M:%S")


def parse_market_line(sample_time, line):
    code_match = re.search(r"(?<!\d)([036]\d{5})(?!\d)", line)
    if not code_match:
        return None
    code = code_match.group(1)
    tail = line[code_match.end() :]
    number_matches = list(re.finditer(r"[-+]?\d+(?:[.,]\d+)?%?(?:万|亿)?", tail))
    if len(number_matches) < 4:
        return None

    name = tail[: number_matches[0].start()].strip()
    name = re.sub(r"[\s|,，;；:：]+", "", name) or code
    tokens = [m.group(0) for m in number_matches]
    values = [parse_number_token(token) for token in tokens]

    # 通达信截图常见列: 代码 名称 涨幅% 涨速% 换手% 开盘% 封单额
    # 如果最后一个数字带“万/亿”，优先把它当作直接封单金额。
    direct_seal = 0.0
    if tokens and ("万" in tokens[-1] or "亿" in tokens[-1]):
        direct_seal = values[-1]

    last_price = values[0]
    limit_up_price = values[1] if len(values) > 1 else last_price
    bid1_price = values[2] if len(values) > 2 else limit_up_price
    bid1_volume = values[3] if len(values) > 3 else 0
    change_pct = values[4] if len(values) > 4 else 10.0
    turnover = values[5] if len(values) > 5 else 0

    if direct_seal > 0:
        change_pct = values[0]
        last_price = 0
        limit_up_price = 0
        bid1_price = 0
        bid1_volume = 0
        turnover = 0

    # 如果 OCR 只读到“最新价、买一价、买一量、涨幅”，用涨停价近似买一价。
    if limit_up_price > 100000 and bid1_volume == 0:
        bid1_volume = limit_up_price
        limit_up_price = bid1_price

    return {
        "time": sample_time,
        "code": code,
        "name": name,
        "last_price": round(last_price, 4),
        "limit_up_price": round(limit_up_price, 4),
        "bid1_price": round(bid1_price, 4),
        "bid1_volume": round(bid1_volume, 2),
        "change_pct": round(change_pct, 4),
        "turnover": round(turnover, 2),
        "seal_amount": round(direct_seal, 2),
    }


def parse_number_token(token):
    text = normalize_ocr_number(token).replace("%", "").strip()
    multiplier = 1
    if text.endswith("万"):
        multiplier = 10000
        text = text[:-1]
    elif text.endswith("亿"):
        multiplier = 100000000
        text = text[:-1]
    try:
        return float(text) * multiplier
    except ValueError:
        return 0.0


def watch(config):
    reset_observed_files()
    times = config.get("times") or DEFAULT_TIMES
    now = datetime.now()
    schedule = [(clock, next_datetime(clock)) for clock in times]
    schedule = [(clock, target) for clock, target in schedule if target > now]
    if not schedule:
        print("今天的竞价观察时间已经全部过去。请用 --capture-now 测试，或明天竞价前再运行 --watch。")
        return
    print("屏幕观察已启动。请保持通达信窗口打开，并且不要遮挡已校准区域。")
    for clock, target in schedule:
        print(f"等待 {clock} 采样，目标时间: {target.strftime('%Y-%m-%d %H:%M:%S')}")
        while datetime.now() < target:
            time.sleep(min(1.0, max(0.05, (target - datetime.now()).total_seconds())))
        capture_region(clock.replace(":", ""), config)
        if clock == "09:20:00":
            build_observed_report(output_path=EARLY_REPORT_0920, report_time="09:20:00", early=True)
        if clock == "09:24:00":
            build_observed_report(output_path=EARLY_REPORT_0924, report_time="09:24:00", early=True)
    build_observed_report()
    print("采样完成。截图已保存到 screen_captures 文件夹。")


def reset_observed_files():
    for path in [RAW_OCR_CSV, OBSERVED_SNAPSHOT_CSV, OBSERVED_REPORT, EARLY_REPORT_0920, EARLY_REPORT_0924]:
        if path.exists():
            path.unlink()


def build_observed_report(output_path=OBSERVED_REPORT, report_time=None, early=False):
    profile_path = Path("stock_profile.csv")
    if not OBSERVED_SNAPSHOT_CSV.exists():
        print("没有解析到结构化快照，无法生成属性报告。请查看 screen_ocr_raw.csv 和截图。")
        return
    if not profile_path.exists():
        print("缺少 stock_profile.csv，无法补充概念、市值、区间涨幅。")
        return
    try:
        profiles = load_profiles(profile_path)
        snapshots = load_snapshots(OBSERVED_SNAPSHOT_CSV)
        metrics = build_stock_metrics(snapshots, profiles, final_time=report_time)
        attr_results = aggregate_attributes(metrics)
        if early:
            label = report_time[:5] if report_time else "09:20"
            report = generate_early_report(metrics, profiles, label=label)
        else:
            report = generate_report(metrics, attr_results, profiles)
        output_path.write_text(report, encoding="utf-8")
        print(f"已生成观察报告: {output_path.resolve()}")
    except Exception as exc:
        print(f"生成观察报告失败: {exc}")


def main():
    parser = argparse.ArgumentParser(description="通达信竞价屏幕观察器")
    parser.add_argument("--calibrate", action="store_true", help="框选通达信竞价表格区域")
    parser.add_argument("--capture-now", action="store_true", help="立即截取一次已校准区域")
    parser.add_argument("--watch", action="store_true", help="按配置时间自动截图")
    parser.add_argument("--report", action="store_true", help="用已解析的屏幕快照生成报告")
    args = parser.parse_args()

    if args.calibrate:
        calibrate_region()
        return

    config = load_config()
    if not config:
        raise SystemExit("请先运行校准: python screen_observer.py --calibrate")

    if args.capture_now:
        capture_region("manual", config)
        return

    if args.watch:
        watch(config)
        return

    if args.report:
        build_observed_report()
        return

    print("请选择一个动作: --calibrate、--capture-now、--watch 或 --report")


if __name__ == "__main__":
    main()
