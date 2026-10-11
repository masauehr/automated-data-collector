#!/usr/bin/env python3
"""OpenClaw の cron ジョブ定義を git で管理するための同期ツール（標準ライブラリのみ）。

cron の指示文（message）や実行時刻・モデルは OpenClaw 側（~/.openclaw）にしか無く、git では管理されない。
このツールで cron/<ジョブ名>.md（指示文）と cron/<ジョブ名>.json（時刻・モデル等）に書き出して git で管理し、
必要なら git の内容を OpenClaw に反映する。

  python3 bin/cron_sync.py export   # OpenClaw → cron/ に書き出す（git に残す）
  python3 bin/cron_sync.py diff     # cron/ と OpenClaw の差を表示（変更しない）
  python3 bin/cron_sync.py apply [ジョブ名]  # cron/ の内容を OpenClaw に反映（指示文・時刻・モデル・有効/無効）

個人情報の扱い: Slack の送信先ユーザーID は <OWNER> に置き換えて保存する。apply は配信先（delivery）を変更しない。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

CRON_DIR = Path(__file__).resolve().parent.parent / "cron"
SLACK_ID = re.compile(r"U[0-9A-Z]{8,}")  # Slack ユーザーID（マスク対象）


def oc(*args):
    r = subprocess.run(["openclaw", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"openclaw {' '.join(args)} 失敗: {r.stderr.strip()[:200]}")
    return r.stdout


def live_jobs():
    out = oc("cron", "list", "--all", "--json")
    d = json.loads(out[min(i for i in (out.find("{"), out.find("[")) if i >= 0):])
    return d if isinstance(d, list) else d.get("jobs", d.get("entries", []))


def mask(s):
    return SLACK_ID.sub("<OWNER>", s) if isinstance(s, str) else s


def to_meta(j):
    p = j.get("payload", {})
    dl = j.get("delivery", {}) or {}
    meta = {
        "name": j["name"],
        "description": j.get("description", ""),
        "enabled": j.get("enabled", True),
        "schedule": {"expr": j["schedule"].get("expr"), "tz": j["schedule"].get("tz")},
        "model": p.get("model"),
        "fallbacks": p.get("fallbacks", []),
        "timeoutSeconds": p.get("timeoutSeconds"),
        "delivery": {"mode": dl.get("mode"), "channel": dl.get("channel"), "to": mask(dl.get("to", ""))},
        "id": j["id"],
    }
    if p.get("toolsAllow"):
        meta["toolsAllow"] = p["toolsAllow"]
    return meta


def export():
    CRON_DIR.mkdir(exist_ok=True)
    keep = set()
    for j in live_jobs():
        name = j["name"]
        keep |= {f"{name}.md", f"{name}.json"}
        (CRON_DIR / f"{name}.md").write_text(mask(j["payload"].get("message", "")).rstrip("\n") + "\n")
        (CRON_DIR / f"{name}.json").write_text(json.dumps(to_meta(j), ensure_ascii=False, indent=2) + "\n")
        print(f"export: {name}")
    for f in CRON_DIR.glob("*"):
        if f.name not in keep and f.suffix in (".md", ".json") and f.name != "README.md":
            print(f"注意: OpenClaw に無いジョブのファイル: {f.name}（削除済みジョブなら手動で消す）")


def compare():
    """cron/ と OpenClaw の差を {ジョブ名: [差分の説明]} で返す"""
    live = {j["name"]: j for j in live_jobs()}
    res = {}
    for f in sorted(CRON_DIR.glob("*.json")):
        meta = json.loads(f.read_text())
        name = meta["name"]
        msg = (CRON_DIR / f"{name}.md").read_text().rstrip("\n")
        if name not in live:
            res[name] = ["OpenClaw に存在しない（apply は新規作成しない）"]
            continue
        j = live[name]
        lm = to_meta(j)
        diffs = []
        if mask(j["payload"].get("message", "")).rstrip("\n") != msg:
            diffs.append("指示文")
        for k in ("enabled", "schedule", "model", "fallbacks", "timeoutSeconds", "description"):
            if lm.get(k) != meta.get(k):
                diffs.append(f"{k}: 実機={lm.get(k)!r} / git={meta.get(k)!r}")
        res[name] = diffs
    for name in live:
        if not (CRON_DIR / f"{name}.json").exists():
            res[name] = ["git に未登録（export で追加）"]
    return res


def diff():
    bad = 0
    for name, d in compare().items():
        print(f"{'差あり' if d else '一致  '} {name}", *(f"\n    - {x}" for x in d))
        bad += bool(d)
    print(f"\n{bad} 件に差があります" if bad else "\nすべて一致しています")


def apply(only=None):
    live = {j["name"]: j for j in live_jobs()}
    for f in sorted(CRON_DIR.glob("*.json")):
        meta = json.loads(f.read_text())
        name = meta["name"]
        if only and name != only:
            continue
        if name not in live:
            print(f"skip: {name}（OpenClaw に存在しない）")
            continue
        jid = live[name]["id"]
        if any(x.startswith("OpenClaw に存在") for x in compare().get(name, [])):
            continue
        msg = (CRON_DIR / f"{name}.md").read_text().rstrip("\n")
        if SLACK_ID.search(msg) or "<OWNER>" in msg:
            print(f"skip: {name}（指示文に送信先IDのマスクがあり、反映できない）")
            continue
        args = ["cron", "edit", jid, "--message", msg, "--cron", meta["schedule"]["expr"], "--tz", meta["schedule"]["tz"],
                "--model", meta["model"], "--timeout-seconds", str(meta["timeoutSeconds"])]
        if meta.get("fallbacks"):
            args += ["--fallbacks", ",".join(meta["fallbacks"])]
        if meta.get("description"):
            args += ["--description", meta["description"]]
        oc(*args)
        oc("cron", "enable" if meta.get("enabled", True) else "disable", jid)
        print(f"apply: {name}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "apply":
        apply(sys.argv[2] if len(sys.argv) > 2 else None)  # 名前を渡すとそのジョブだけ反映
    else:
        {"export": export, "diff": diff}.get(cmd, lambda: sys.exit(__doc__))()
