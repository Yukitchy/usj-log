#!/usr/bin/env python3
"""runnable check: com.yuki.parklog-collect が壊れていないかの最小診断。
スケジュール: 11:05/13:05/15:05/17:05/19:05 (StartCalendarInterval)。
使い方: python3 check.py / exit 0=PASS 1=FAIL
"""
import datetime
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    # 1) 設定ファイルの存在
    last_success = HERE / ".last-success"
    history = HERE / "history.json"
    assert last_success.exists(), f"missing {last_success}"
    assert history.exists(), f"missing {history}"

    # 2) 直近実行の新鮮さ（最長の無実行ギャップは19:05→翌11:05=16h。余裕を見て20h）
    ts = datetime.datetime.fromisoformat(last_success.read_text().strip())
    now = datetime.datetime.now(ts.tzinfo) if ts.tzinfo else datetime.datetime.now()
    age_h = (now - ts).total_seconds() / 3600
    assert age_h < 20, f".last-success stale: {age_h:.1f}h ago ({ts})"

    # 3) history.jsonに今日のデータが積まれているか
    d = json.loads(history.read_text())
    today = datetime.date.today().isoformat()
    has_today = any(today in d.get(park, {}) for park in d)
    assert has_today, f"history.json has no entry for {today}"

    print(f"PASS: last success {ts} ({age_h:.1f}h ago), history has {today}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
