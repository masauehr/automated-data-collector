#!/usr/bin/env python3
"""天気図VLM解説（weather_chart_vlm）の当日分を読み、使えるかどうかを判定して JSON で出力する。

Bluesky 投稿 cron が「VLM を参照し、失敗していたら独自に書く」ために使う。
判定は機械的に行う（LLM に任せない）:
  fail: ファイルなし／日付が今日(JST)でない／確信度 0.5 未満／ガードレールに NG／JSON 読込失敗
  ok  : 上記以外（台風に触れる文は today/tomorrow から除外する）。ガードレールが「注意」の項目は cautions に入れる（その話題は VLM を根拠にしない）
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path.home() / "projects" / "weather_chart_vlm" / "webui" / "history"
MIN_CONFIDENCE = 0.5


TYPHOON_RE = re.compile(r"台風|台\d+号|熱帯低気圧|TC\d+")


def strip_typhoon(text):
    """VLM の文章から台風に触れる文を取り除く（台風は get_typhoon の結果だけを正とするため）。
    句点「。」で文を区切り、台風の語を含む文は丸ごと除く。"""
    if not text:
        return text
    sents = [x for x in re.split(r"(?<=。)", text) if x]
    return "".join(x for x in sents if not TYPHOON_RE.search(x)).strip()


def main():
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
    path = ROOT / today / "data.json"
    try:
        d = json.loads(path.read_text())
    except FileNotFoundError:
        return {"status": "fail", "reason": f"当日分のファイルがない（{today}）"}
    except Exception as e:  # 壊れたJSONなど
        return {"status": "fail", "reason": f"読込失敗: {type(e).__name__}"}

    if d.get("date") != today:
        return {"status": "fail", "reason": f"日付が今日でない（{d.get('date')}）"}
    conf = d.get("confidence")
    if not isinstance(conf, (int, float)) or conf < MIN_CONFIDENCE:
        return {"status": "fail", "reason": f"確信度が低い・不明（{conf}）"}
    checks = d.get("guardrail_checks", [])
    ng = [g.get("label") for g in checks if g.get("verdict") == "NG"]
    if ng:
        return {"status": "fail", "reason": f"ガードレールNG: {', '.join(map(str, ng))}"}

    g = d.get("general", {})
    return {
        "status": "ok",
        "chart_time_jst": d.get("chart_time_jst"),
        "updated_jst": d.get("updated_jst"),
        "pattern": d.get("pattern"),
        "confidence": conf,
        # 台風に触れる文は除外済み。台風は気象庁MCP(get_typhoon)の結果だけを使うこと
        "today": strip_typhoon(g.get("today")),
        "tomorrow": strip_typhoon(g.get("tomorrow")),
        "typhoon_sentences_removed": True,
        "troughs": d.get("troughs"),
        # 「注意」の項目＝VLMの記述が気象庁データと突合しきれていない話題
        "cautions": [g_.get("label") for g_ in checks if g_.get("verdict") == "注意"],
    }


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
    sys.exit(0)
