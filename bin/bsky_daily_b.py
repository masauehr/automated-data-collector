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
    out["typhoon"] = await jma._get_typhoon()
    out["tsunami"] = await jma._get_tsunami_info()
    out["quake_m4plus"] = await jma._get_earthquake_info(4, 5)
    out["ranking"] = (await jma._get_daily_ranking("", "mxtem"))[:900]
    # 警報（注意報は除く）: 全府県を回し、「■ 発表中」の区画にある警報だけを集める。
    # 解除通知・過去の発表履歴・暫定基準の注記は拾わない（拾うと「発表中」と誤解される）。
    warn, failed = [], []
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
    out["warnings"] = "\n".join(warn) if warn else "（警報・特別警報の発表中なし）"
    if failed:
        out["warnings"] += f"\n※取得に失敗した地域（警報の有無は不明。『なし』と書かない）: {', '.join(failed)}"
    return out


def typhoon_numbers(text):
    """get_typhoon の結果に実在する台風番号"""
    return set(re.findall(r"台風(\d+)号", text))


def build_prompt(facts, vlm):
    vlm_part = "（VLMなし。気圧配置は他の情報から言える範囲に限る）" if vlm["status"] != "ok" else (
        f"天気図VLM解説（気圧配置・気圧の谷・雨域の根拠。台風・警報は下の事実を優先）:\n"
        f"型: {vlm['pattern']}\n今日: {vlm['today']}\n明日: {vlm['tomorrow']}\n気圧の谷: {json.dumps(vlm['troughs'], ensure_ascii=False)}\n"
        f"VLMが突合しきれていない話題（根拠にしない）: {', '.join(vlm['cautions']) or 'なし'}")
    return f"""以下の【取得済みの事実】だけを使い、Bluesky 投稿の本文を書いてください。

【書式】日本語・3行（改行2回）・全体250字以内・1行80字以内
1行目: 「🤖AIによる自動生成」で始め、日付と全国の天気概況（気圧配置）。気圧の谷などで雨の原因が分かれば短く書く
2行目: 地域ごとの特徴と今日→明日の変化
3行目: 注意点。優先順位は 台風 > 警報 > 大雨・高波・強風 > 地震（震度4以上）。該当なしなら「特に警戒すべき情報なし」。【津波には一切触れない】（津波の文はコードが別に付ける）
- 台風は【台風情報】に載っているものだけ。表記は「台風29号（コグマ）」。いつ・どの地域に接近するか（離れるか）を書く
- ハッシュタグ・URL・内部IDは書かない。絵文字は🤖のほか最大1個。推測や数値の創作は禁止
- 本文だけを出力する（前置き・説明・コードブロック不要）

【台風情報】
{facts['typhoon']}

【地震（震度4以上）】
{facts['quake_m4plus']}

【警報・特別警報】
{facts['warnings']}

【観測値ランキング（抜粋）】
{facts['ranking']}

【{vlm_part}
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


def validate(text, facts):
    """コードでの機械検証。問題の一覧を返す（空なら合格）"""
    problems = []
    real = typhoon_numbers(facts["typhoon"])
    for n in typhoon_numbers(text):
        if n not in real:
            problems.append(f"存在しない台風: {n}号")
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
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", action="store_true", help="実際に Bluesky へ投稿する（既定はシャドー）")
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
    text = add_tsunami(norm(text))
    problems = validate(text, facts) + tsunami_guard.check_text(text, tstate)
    retried = bool(problems)
    if problems:  # 機械検証に落ちたら、指摘を添えて1回だけ再生成
        text2, tk2, t2 = call_claude(prompt + "\n\n【前回の出力の問題。直して出力し直す】\n- " + "\n- ".join(problems) + "\n前回の出力:\n" + text)
        tokens, t_llm = tokens + tk2, t_llm + t2
        text = add_tsunami(norm(text2))
        problems = validate(text, facts) + tsunami_guard.check_text(text, tstate)

    rec = {
        "date": today, "generated_at": datetime.now(JST).isoformat(timespec="seconds"),
        "mode": "VLMあり" if vlm["status"] == "ok" else f"VLMなし({vlm.get('reason')})",
        "model": MODEL, "tokens": tokens, "sec_facts": round(t_facts, 1), "sec_llm": round(t_llm, 1),
        "text": text, "problems": problems, "retried": retried, "posted": False,
        "real_typhoons": sorted(typhoon_numbers(facts["typhoon"])),
    }
    if a.post:
        if problems:
            rec["post_skipped"] = "機械検証で不合格のため投稿しない"
        else:
            r = subprocess.run([sys.executable, str(HERE / "bsky_post.py"), "--text", text], capture_output=True, text=True)
            rec["posted"] = r.returncode == 0
            rec["post_result"] = (r.stdout or r.stderr).strip()[:200]
    SHADOW.mkdir(exist_ok=True)
    (SHADOW / f"{today}_B.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2))
    print(json.dumps(rec, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
