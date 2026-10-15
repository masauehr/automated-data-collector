#!/opt/homebrew/bin/python3
"""Bluesky 日次投稿の「B版」: 事実はコードで取得し、LLM は文章化だけを行う。

OpenClaw 版（A版: 取得・判断・文章化をLLMエージェントに任せる）との比較用。
既定は【シャドーモード】= 投稿せず、結果を shadow/ に保存するだけ。--post で実投稿。

流れ:
  1. 気象庁MCP(server.py)の関数をコードで直接呼び、台風・津波・地震・警報・観測値を取得
  2. 天気図VLM解説を vlm_status.py と同じ基準で判定（失敗なら VLM なし）
  3. claude CLI（サブスク経由, haiku）に「取得済みの事実だけで3行に要約」させる
  4. コードで検証（台風番号が実在するか・3行か・内部IDが出ていないか）
  5. shadow/YYYY-MM-DD_B.json に保存（--post なら bsky_post.py で投稿）
"""
import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHADOW = HERE.parent / "shadow"
JMA_MCP = Path.home() / "projects" / "jma_mcp"
CLAUDE = Path.home() / ".local" / "bin" / "claude"
MODEL = "claude-haiku-4-5"
JST = timezone(timedelta(hours=9))

sys.path.insert(0, str(JMA_MCP))
sys.path.insert(0, str(HERE))
import server as jma  # noqa: E402  気象庁MCPの関数をそのまま使う
from areas import AREA_CODE_MAP  # noqa: E402
import vlm_status  # noqa: E402
import tsunami_guard  # noqa: E402


async def gather_facts():
    """事実の取得（LLMは介在しない）"""
    out = {}
    out["typhoon"] = fix_td_name(await jma._get_typhoon())
    out["tsunami"] = await jma._get_tsunami_info()
    out["quake_m4plus"] = await jma._get_earthquake_info(4, 5)
    out["ranking"] = (await jma._get_daily_ranking("", "mxtem"))[:900]
    # 天気の主役を決める材料（VLMなしでも天気が書けるように常に取得する）
    ov, cm, failed_ov = [], [], []
    for label, code in OFFICES.items():
        try:
            o = await jma._get_overview(code)
            c = await jma._get_forecaster_comment(code)
        except Exception:
            o = c = "エラー"
        if o.startswith("エラー") and c.startswith("エラー"):
            failed_ov.append(label)
            continue
        if not o.startswith("エラー"):
            ov.append(f"■{label}\n" + _body(o)[:650])
        if not c.startswith("エラー"):
            cm.append(f"■{label}\n" + _body(c)[:520])
    out["overview"] = "\n".join(ov) or "（取得できませんでした）"
    out["comment"] = "\n".join(cm) or "（取得できませんでした）"
    out["rain"] = _rain_sections(await jma._get_daily_ranking("", "pre1h"))
    if failed_ov:
        out["overview"] += f"\n※取得に失敗: {', '.join(failed_ov)}"
    # 警報（注意報は除く）: 全府県を回し、「■ 発表中」の区画にある警報だけを集める。
    # 解除通知・過去の発表履歴・暫定基準の注記は拾わない（拾うと「発表中」と誤解される）。
    warn, failed, raw = [], [], {}
    for code, name in AREA_CODE_MAP.items():
        try:
            txt = await jma._get_warning(code)
        except Exception:
            txt = "エラー"
        if txt.startswith("エラー"):
            failed.append(name)
            continue
        active, in_active = [], False
        for ln in txt.splitlines():
            if ln.startswith("■"):
                in_active = ln.startswith("■ 発表中")
                continue
            ln = ln.strip()
            if in_active and "警報" in ln and "解除" not in ln:
                active.append(ln)
        if active:
            warn.append(f"{name}: " + " / ".join(active[:4]))
            raw[name] = txt  # 後から検証できるよう、警報のある地域の取得原文を残す
    out["warnings"] = "\n".join(warn) if warn else "（警報・特別警報の発表中なし）"
    if failed:
        out["warnings"] += f"\n※取得に失敗した地域（警報の有無は不明。『なし』と書かない）: {', '.join(failed)}"
    out["warnings_raw"] = raw
    out["facts_at"] = datetime.now(JST).strftime("%H:%M")  # 警報取得の完了時刻（投稿の「○時点」に使う）
    # 今日の降水確率（地域キーワードと突き合わせて「雨」表記を検査するため）
    out["pop"] = {}
    for code in sorted({c for codes in POP_REGIONS.values() for c in codes}):
        try:
            out["pop"][code] = _today_pop(await jma._get_forecast(code))
        except Exception:
            out["pop"][code] = None
    return out


# 天気概況・予報官コメントを取る官署（全国の主役と、沖縄・九州の雨を拾うため）
OFFICES = {"北海道(札幌)": "016000", "関東(東京)": "130000", "近畿(大阪)": "270000", "九州北部(福岡)": "400000",
           "九州南部(鹿児島)": "460100", "奄美": "460040", "沖縄本島": "471000"}


# 「雨」と書いてよいか検査する地域。キーワードは上から順に最初に合致したものだけを使う（「沖縄先島」は先島として判定）
POP_REGIONS = {
    "先島": ("473000", "474000"), "八重山": ("474000",), "宮古": ("473000",), "大東": ("472000",),
    "沖縄": ("471000",), "奄美": ("460040",), "九州南部": ("460100",), "鹿児島": ("460100",),
    "九州": ("400000", "460100"), "関東": ("130000",), "近畿": ("270000",),
    "北海道": ("011000", "012000", "016000"),
}
POP_LIMIT = 50  # 今日の降水確率（最大）がこれ未満なら卓越雨ではないので「雨」と書かない（%）


def _today_pop(txt):
    """get_forecast の結果から、今日の降水確率の最大値(%)。取れなければ None"""
    in_pop = False
    for ln in txt.splitlines():
        if ln.startswith("■"):
            in_pop = "降水確率" in ln
            continue
        if in_pop and ln.strip():
            v = [int(x) for x in re.findall(r"(\d+)%", ln)]
            return max(v) if v else None  # 最初の日付行が今日
    return None


def _body(txt):
    """ツール出力から見出し・出典行を除いた本文だけにする"""
    lines = [ln.strip() for ln in txt.splitlines() if ln.strip() and not ln.startswith("出典") and not ln.startswith("【")]
    return "\n".join(lines)


def _rain_sections(txt):
    """降水量ランキングから降水の区画だけを抜き出す（上位のみ）"""
    out, keep, n = [], False, 0
    for ln in txt.splitlines():
        if ln.startswith("■"):
            keep, n = "降水" in ln, 0
            if keep:
                out.append(ln)
            continue
        if keep and ln.strip() and n < 6:
            out.append(ln.rstrip())
            n += 1
    return "\n".join(out) or "（降水量ランキングを取得できませんでした）"


def fix_td_name(text):
    """気象庁MCPは台風になる前の熱帯低気圧を「台風a号」と出力する。台風ではないので「熱帯低気圧」に直す"""
    return re.sub(r"台風[a-zA-Z]号", "熱帯低気圧", text)


def typhoon_numbers(text):
    """get_typhoon の結果に実在する台風番号"""
    return set(re.findall(r"台風(\d+)号", text))


def build_prompt(facts, vlm):
    if vlm["status"] != "ok":
        vlm_part = "（VLMなし。気圧配置・雨域は【天気概況】【予報官コメント】から言える範囲に限る）"
    else:
        soft = ", ".join(vlm.get("soft_ng", [])) or "なし"
        vlm_part = (f"天気図VLM解説（気圧配置・気圧の谷・雨域の根拠。台風・警報は他の事実を優先）:\n"
                    f"型: {vlm['pattern']}\n今日: {vlm['today']}\n明日: {vlm['tomorrow']}\n気圧の谷: {json.dumps(vlm['troughs'], ensure_ascii=False)}\n"
                    f"VLMが突合しきれていない話題（根拠にしない・他の情報で裏取り）: {', '.join(vlm['cautions']) or 'なし'}\n"
                    f"VLMの実況突合でNGだった話題（降水・風などのVLMの記述は使わず、【降水ランキング】【予報官コメント】で裏取りする）: {soft}")
    return f"""以下の【取得済みの事実】だけを使い、Bluesky 投稿の本文を書いてください。

【書式】日本語・3行（改行2回）・全体250字以内・1行80字以内
1行目: 「🤖AIによる自動生成」で始め、日付と【今日の天気の主役】（全国の気圧配置・前線・気圧の谷）。【天気概況】【天気図VLM解説】を根拠にする
2行目: 地域ごとの特徴と今日→明日の変化。雨・雷の地域（沖縄・奄美・九州の気圧の谷、前線が通過する地域など）は、原因と一緒に必ず入れる
3行目: 注意点。優先順位は 発表中の警報 > 大雨・雷・高波・強風 > 台風 > 地震（震度4以上）。該当なしなら「特に警戒すべき情報なし」。【津波には一切触れない】（津波の文はコードが別に付ける）
- 台風が存在するなら必ず1文入れる。【台風情報】に載っているものだけ。表記は「台風29号（コグマ）」。位置・進路と、日本への影響の有無（離れていくか、どの地域にいつ近づくか）を書く
- 【台風の影響の書き方】本土から離れている・警報が出ていないときは「厳重警戒」「暴風」「猛烈」を使わない。影響は【予報官コメント】や警報に書かれた範囲（例: うねり・高波）に限る
- 【風の表現】風の強弱は平均風速（10分間平均）で判断し、書く。最大瞬間風速（突風）で強弱を分類しない。瞬間風速に触れる場合は「瞬間風速」と明記する。気象庁の区分（平均風速）: やや強い風=10以上15未満m/s、強い風=15以上20未満、非常に強い風=20以上30未満、猛烈な風=30以上（10m/s未満に予報用語はない）。
- 「大雨」は、大雨に関する警報・注意報が発表中、または1時間30mm以上の観測があるときだけ使う（「可能性は低い」程度の話を大雨注意と書かない）
- 【概況・予報官コメントに「明日」以降の記述がある場合、それを今日のこととして書かない】
- 台風を先頭に置かない。天気の主役（高気圧・気圧の谷・前線）が先、台風は注意点として短く
- ハッシュタグ・URL・内部IDは書かない。絵文字は🤖のほか最大1個。推測や数値の創作は禁止
- 本文だけを出力する（前置き・説明・コードブロック不要）

【台風情報】
{facts['typhoon']}

【天気概況（各官署）】
{facts['overview']}

【予報官コメント（警報等の可能性）】
{facts['comment']}

【降水ランキング（1時間降水量・上位）】
{facts['rain']}

【地震（震度4以上）】
{facts['quake_m4plus']}

【警報・特別警報（発表中）】
{facts['warnings']}

【観測値ランキング（最高気温・抜粋）】
{facts['ranking']}

【天気図VLM解説】
{vlm_part}
"""


def call_claude(prompt):
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)  # サブスク認証を強制
    env.pop("ANTHROPIC_BASE_URL", None)
    t0 = time.monotonic()
    p = subprocess.run([str(CLAUDE), "--print", "--model", MODEL, "--output-format", "json", "--input-format", "text"],
                       input=prompt, text=True, capture_output=True, timeout=300, env=env)
    if p.returncode != 0:
        raise RuntimeError(f"claude CLI 失敗 rc={p.returncode}: {p.stderr[:200]}")
    d = json.loads(p.stdout)
    u = d.get("usage") or {}
    tokens = sum(int(u.get(k, 0)) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens"))
    return (d.get("result") or "").strip(), tokens, time.monotonic() - t0


def validate(text, facts, vlm=None):
    """コードでの機械検証。問題の一覧を返す（空なら合格）"""
    problems = []
    real = typhoon_numbers(facts["typhoon"])
    for n in typhoon_numbers(text):
        if n not in real:
            problems.append(f"存在しない台風: {n}号")
    if re.search(r"台風[a-zA-Z]号", text):
        problems.append("熱帯低気圧を「台風a号」と書いている（台風ではないので『熱帯低気圧』と書く）")
    if re.search(r"台風\d{4}|TC\d{4}|\b\d{4}号", text):
        problems.append("台風の内部IDらしき表記")
    if len([ln for ln in text.splitlines() if ln.strip()]) != 3:
        problems.append("3行になっていない")
    if not text.startswith("🤖AIによる自動生成"):
        problems.append("先頭のAI明記なし")
    if len(text) > 300:
        problems.append(f"300字超過({len(text)})")
    allfacts = "\n".join(str(v) for v in facts.values())
    for w in set(re.findall(r"大津波警報|津波警報|特別警報|[大雨暴風大雪波浪高潮]{1,2}警報", text)):
        if w not in allfacts.replace("警報・特別警報", "").replace("津波警報・注意報", ""):
            problems.append(f"事実にない警報名: {w}")
    if "台風情報なし" in text and real:
        problems.append("台風があるのに『台風情報なし』")
    problems += validate_tone(text, facts, vlm)
    problems += validate_rain_pop(text, facts)
    return problems


def _max_rain_1h(rain_txt):
    """降水ランキング抜粋の「1時間降水量」区画の最大値(mm)。取れなければ 0"""
    mx, in_1h = 0.0, False
    for ln in rain_txt.splitlines():
        if ln.startswith("■"):
            in_1h = "1時間" in ln
            continue
        m = re.search(r"\s(\d+(?:\.\d+)?)\s+\d{2}:\d{2}\s*$", ln)
        if in_1h and m:
            mx = max(mx, float(m.group(1)))
    return mx


# 事実に裏付けのない誇張表現を弾く。「厳重警戒」は警報が発表中のときだけ、「暴風」は暴風警報等があるときだけ許す
HEAVY_WORDS = {"厳重警戒": "警報", "暴風": "暴風", "猛烈": "猛烈", "非常に危険": "警報"}
RAIN_REGION_WORDS = ("気圧の谷", "沖縄", "奄美", "九州", "鹿児島", "トカラ", "南西諸島")


def validate_tone(text, facts, vlm=None):
    """内容のバランスの機械検査（誇張・要点のずれ）。2026-10-13 に台風へ引きずられた投稿が出たため追加"""
    problems = []
    warn = facts.get("warnings", "")
    active = not warn.startswith("（警報・特別警報の発表中なし）")
    for w, need in HEAVY_WORDS.items():
        if w in text and not (active and need in warn):
            problems.append(f"裏付けのない強い表現: 「{w}」（発表中の警報にその根拠がない）")
    # 「大雨」は、大雨に関する警報・注意報が発表中か、1時間30mm以上の観測がある場合だけ（可能性が低い話の誇張を防ぐ）
    if "大雨" in text and not ("大雨" in warn or _max_rain_1h(facts.get("rain", "")) >= 30):
        problems.append("裏付けのない「大雨」（発表中の警報にも30mm/h以上の観測にもない）")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    for i, ln in enumerate(lines, 1):
        if len(ln) > 100:
            problems.append(f"{i}行目が長すぎる({len(ln)}字。80字以内に要約する)")
    if lines and "台風" in lines[0]:
        problems.append("1行目が台風になっている（天気の主役を先に書く）")
    # VLM が気圧の谷を指摘している日は、その雨域（気圧の谷／沖縄・九州付近）に触れること
    if vlm and vlm.get("status") == "ok" and vlm.get("troughs") and not any(w in text for w in RAIN_REGION_WORDS):
        problems.append("VLMが指摘した気圧の谷・沖縄/九州付近の雨に触れていない")
    return problems


def validate_rain_pop(text, facts):
    """今日の降水確率が50%未満の地域に「雨」を書いていないか。明日・明後日の文は今日の確率で判定できないので対象外"""
    problems, pop = [], facts.get("pop") or {}
    today_d = datetime.now(JST).day

    def other_day(c):  # 「16日」のように今日以外の日付が書かれた文
        return any(int(d) != today_d for d in re.findall(r"(\d{1,2})日", c))

    for clause in re.split(r"[。、\n]", text):
        if "雨" not in clause or re.search(r"明日|明後日|あす|あさって", clause) or other_day(clause) or re.search(r"雨(は|の心配)?(なし|ない|降らない)", clause):
            continue
        # 「雨」の直前にいちばん近い地域名をその雨の地域とする（「北海道の雷雨と先島の高波」の先島を雨扱いしない）
        hit = set()
        for m in re.finditer("雨", clause):
            near = [(clause.rfind(kw, 0, m.start()), len(kw), kw) for kw in POP_REGIONS if kw in clause[:m.start()]]
            if near:
                hit.add(max(near)[2])  # 位置が後ろ→長い名前の順
        for kw in hit:
            vals = [pop[c] for c in POP_REGIONS[kw] if pop.get(c) is not None]
            if vals and max(vals) < POP_LIMIT:
                problems.append(f"{kw}の今日の降水確率が最大{max(vals)}%（{POP_LIMIT}%未満）なのに雨と書いている: 「{clause.strip()}」")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", action="store_true", help="実際に Bluesky へ投稿する（既定はシャドー）")
    ap.add_argument("--label", default="B", help="保存ファイル名のラベル（試験時は B 以外にして本番の記録を上書きしない）")
    a = ap.parse_args()

    today = datetime.now(JST).strftime("%Y-%m-%d")
    t0 = time.monotonic()
    facts = asyncio.run(gather_facts())
    t_facts = time.monotonic() - t0
    vlm = vlm_status.main()

    prompt = build_prompt(facts, vlm)
    text, tokens, t_llm = call_claude(prompt)
    # LLMが空行を入れても3行に正規化（コード側で保証する）
    tstate = tsunami_guard.current_state()
    facts["tsunami"] = tstate["sentence"] or "（津波情報なし）"

    def add_tsunami(t):
        """津波の固定文（あれば）を3行目の先頭に入れる。300字を超えるなら3行目は固定文のみ"""
        if not tstate["sentence"]:
            return t
        ls = t.splitlines()
        if len(ls) == 3:
            cand = "\n".join(ls[:2] + [tstate["sentence"] + ls[2]])
            ls[2] = cand.splitlines()[2] if len(cand) <= 300 else tstate["sentence"]
        return "\n".join(ls)

    norm = lambda t: "\n".join(ln.strip() for ln in t.splitlines() if ln.strip())
    asof = facts["facts_at"].lstrip("0") + "時点"  # 例: 9:40時点（警報は数分で切り替わるため、いつの情報かを明記する）
    raw_warnings = facts.pop("warnings_raw")

    def add_asof(t):
        """3行目の先頭に取得時刻を入れる（コード側で保証。LLMには任せない）"""
        ls = t.splitlines()
        if len(ls) == 3:
            ls[2] = f"（{asof}）{ls[2]}"
        return "\n".join(ls)

    text = add_tsunami(add_asof(norm(text)))
    problems = validate(text, facts, vlm) + tsunami_guard.check_text(text, tstate)
    retried = bool(problems)
    if problems:  # 機械検証に落ちたら、指摘を添えて1回だけ再生成
        text2, tk2, t2 = call_claude(prompt + "\n\n【前回の出力の問題。直して出力し直す】\n- " + "\n- ".join(problems) + "\n前回の出力:\n" + text)
        tokens, t_llm = tokens + tk2, t_llm + t2
        text = add_tsunami(add_asof(norm(text2)))
        problems = validate(text, facts, vlm) + tsunami_guard.check_text(text, tstate)

    rec = {
        "date": today, "generated_at": datetime.now(JST).isoformat(timespec="seconds"),
        "mode": "VLMあり" if vlm["status"] == "ok" else f"VLMなし({vlm.get('reason')})",
        "model": MODEL, "tokens": tokens, "sec_facts": round(t_facts, 1), "sec_llm": round(t_llm, 1),
        "text": text, "problems": problems, "retried": retried, "posted": False,
        "real_typhoons": sorted(typhoon_numbers(facts["typhoon"])),
        # 後から検証できるよう、投稿時点の事実を残す
        "facts_at": facts["facts_at"], "warnings": facts["warnings"], "warnings_raw": raw_warnings, "pop": facts["pop"],
    }
    if a.post:
        if problems:
            rec["post_skipped"] = "機械検証で不合格のため投稿しない"
        else:
            r = subprocess.run([sys.executable, str(HERE / "bsky_post.py"), "--text", text], capture_output=True, text=True)
            rec["posted"] = r.returncode == 0
            rec["post_result"] = (r.stdout or r.stderr).strip()[:200]
    SHADOW.mkdir(exist_ok=True)
    (SHADOW / f"{today}_{a.label}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2))
    print(json.dumps(rec, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
