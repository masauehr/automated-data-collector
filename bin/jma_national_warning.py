#!/usr/bin/env python3
"""JMA 全国 警報・注意報 まとめ（現在発表中のみ）。

気象庁の警報システム（2026-05-28 新体系, data/r8/ 配下）は都道府県（実際には
58の予報区＝office）ごとに別ファイルだが、map.json に全予報区分の最新の報が
まとまっている。これを集計して、全国の「現在発表中」の警報・注意報だけを
都道府県別・現象別にまとめて出力する。

HTML はスクレイプしない。公開 JSON のみを使う。標準ライブラリのみ依存。

使い方:
  python3 jma_national_warning.py            # 警報以上は全件、注意報は都道府県別に要約
  python3 jma_national_warning.py --all      # 注意報も含めて地域単位で全件表示

出力は JSON ではなく、そのまま報告に使えるテキスト（日本語）。
"""
import json
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict

HEADERS = {"User-Agent": "Mozilla/5.0"}
WARNING_BASE = "https://www.jma.go.jp/bosai/warning"
AREA_MASTER_URL = "https://www.jma.go.jp/bosai/common/const/area.json"

# 警報・注意報コード → (名称, レベル) マッピング
# 出典: 気象庁 TELOPS コード管理表。レベルは 2=注意報 3=警報 4=危険警報 5=特別警報
WARNING_CODE_MAP = {
    "2": ("暴風雪警報", 3),
    "3": ("大雨警報", 3),
    "4": ("洪水警報", 3),
    "5": ("暴風警報", 3),
    "6": ("大雪警報", 3),
    "7": ("波浪警報", 3),
    "8": ("高潮警報", 3),
    "9": ("土砂災害警報", 3),
    "10": ("大雨注意報", 2),
    "12": ("大雪注意報", 2),
    "13": ("風雪注意報", 2),
    "14": ("雷注意報", 2),
    "15": ("強風注意報", 2),
    "16": ("波浪注意報", 2),
    "17": ("融雪注意報", 2),
    "18": ("洪水注意報", 2),
    "19": ("高潮注意報", 2),
    "20": ("濃霧注意報", 2),
    "21": ("乾燥注意報", 2),
    "22": ("なだれ注意報", 2),
    "23": ("低温注意報", 2),
    "24": ("霜注意報", 2),
    "25": ("着氷注意報", 2),
    "26": ("着雪注意報", 2),
    "27": ("その他の注意報", 2),
    "29": ("土砂災害注意報", 2),
    "32": ("暴風雪特別警報", 5),
    "33": ("大雨特別警報", 5),
    "35": ("暴風特別警報", 5),
    "36": ("大雪特別警報", 5),
    "37": ("波浪特別警報", 5),
    "38": ("高潮特別警報", 5),
    "39": ("土砂災害特別警報", 5),
    "43": ("大雨危険警報", 4),
    "48": ("高潮危険警報", 4),
    "49": ("土砂災害危険警報", 4),
}
ACTIVE_STATUS = ("発表", "継続", "更新")
LEVEL_LABEL = {5: "特別警報", 4: "危険警報", 3: "警報", 2: "注意報"}


def _get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def _get_json(url):
    return json.loads(_get(url))


def _discover_version():
    try:
        html = _get(WARNING_BASE + "/").decode("utf-8", "ignore")
    except Exception:
        return None
    found = re.findall(r"data/(r\d+)/", html)
    return max(set(found), key=found.count) if found else None


def fetch_versioned(version_holder, filename):
    v = version_holder["v"]
    url = f"{WARNING_BASE}/data/{v}/{filename}"
    try:
        return _get_json(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            nv = _discover_version()
            if nv and nv != v:
                version_holder["v"] = nv
                return _get_json(f"{WARNING_BASE}/data/{nv}/{filename}")
        raise


def warning_name_level(code):
    try:
        key = str(int(str(code)))
    except (ValueError, TypeError):
        return (f"不明({code})", 2)
    return WARNING_CODE_MAP.get(key, (f"不明({code})", 2))


def main():
    show_all = "--all" in sys.argv

    version_holder = {"v": "r8"}
    try:
        reports = fetch_versioned(version_holder, "map.json")
    except Exception as e:
        print(f"エラー: 全国警報データの取得に失敗しました: {e}")
        sys.exit(1)

    try:
        map_time = fetch_versioned(version_holder, "map_time.json")
        system_updated = map_time.get("latestControlDatetime")
    except Exception:
        system_updated = None

    try:
        area = _get_json(AREA_MASTER_URL)
    except Exception as e:
        print(f"エラー: 地域マスターの取得に失敗しました: {e}")
        sys.exit(1)

    class10s = area.get("class10s", {})
    offices = area.get("offices", {})

    def pref_name(area_code10):
        c10 = class10s.get(area_code10)
        if not c10:
            return "不明", area_code10
        office_code = c10.get("parent", "")
        office = offices.get(office_code, {})
        return office.get("name", office_code), c10.get("name", area_code10)

    # (level, warning_name) -> list of "都道府県 地域名"
    by_phenomenon = defaultdict(list)
    # 都道府県名 -> set(level) 発表中のレベル（注意報要約用）
    pref_levels = defaultdict(set)
    affected_prefs = set()

    for rep in reports if isinstance(reports, list) else []:
        w = rep.get("warning") or {}
        for item in w.get("class10Items") or []:
            area_code = item.get("areaCode")
            for kind in item.get("kinds") or []:
                status = kind.get("status", "")
                code = kind.get("code")
                if status not in ACTIVE_STATUS or code in (None, ""):
                    continue
                name, level = warning_name_level(code)
                pname, rname = pref_name(area_code)
                by_phenomenon[(level, name)].append(f"{pname} {rname}")
                pref_levels[pname].add(level)
                affected_prefs.add(pname)

    lines = []
    lines.append("【全国 警報・注意報 まとめ（現在発表中のみ）】")
    if system_updated:
        lines.append(f"警報システム最終更新: {system_updated}")
    lines.append("")

    if not by_phenomenon:
        lines.append("現在、全国で発表中の警報・注意報はありません。")
        print("\n".join(lines))
        return

    # 特別警報・危険警報・警報（レベル3以上）は必ず個別に全件表示
    high = [(lvl, name) for (lvl, name) in by_phenomenon if lvl >= 3]
    high.sort(key=lambda x: (-x[0], x[1]))
    if high:
        lines.append("■ 警報級以上（特別警報・危険警報・警報）")
        for lvl, name in high:
            areas = by_phenomenon[(lvl, name)]
            uniq = sorted(set(areas))
            lines.append(f"  [{LEVEL_LABEL[lvl]}] {name}: {'・'.join(uniq)}")
        lines.append("")
    else:
        lines.append("■ 警報級以上（特別警報・危険警報・警報）: 発表なし")
        lines.append("")

    # 注意報（レベル2）は既定では都道府県単位で要約、--all なら現象別に全件表示
    advisory_prefs = sorted(p for p, levels in pref_levels.items() if 2 in levels)
    if show_all:
        low = [(lvl, name) for (lvl, name) in by_phenomenon if lvl == 2]
        low.sort(key=lambda x: x[1])
        if low:
            lines.append("■ 注意報（地域単位・全件）")
            for lvl, name in low:
                areas = by_phenomenon[(lvl, name)]
                uniq = sorted(set(areas))
                lines.append(f"  {name}: {'・'.join(uniq)}")
            lines.append("")
    else:
        if advisory_prefs:
            lines.append(f"■ 注意報: {len(advisory_prefs)}都道府県で発表中（詳細は --all オプション参照）")
            lines.append(f"  対象: {'・'.join(advisory_prefs)}")
            lines.append("")
        else:
            lines.append("■ 注意報: 発表なし")
            lines.append("")

    lines.append(f"（集計対象: 警報級以上={len([k for k in by_phenomenon if k[0]>=3])}現象 / "
                  f"注意報={len([k for k in by_phenomenon if k[0]==2])}現象 / "
                  f"警報級以上の発表都道府県数={len({p for p, lv in pref_levels.items() if max(lv)>=3})} / "
                  f"合計発表都道府県数={len(affected_prefs)}）")
    lines.append("出典: 気象庁 https://www.jma.go.jp/bosai/map.html#contents=warning")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
