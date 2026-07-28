#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""USJ / TDL / TDS の平均待ち時間を定点観測して history.json に貯める。

1日に数回叩いて日ごとに平均する。混雑予想カレンダーの係数を
実データから引き直すための素材。標準ライブラリだけで動く（/usr/bin/python3 = 3.9系）。
"""
import json, os, re, subprocess, sys, time, urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'history.json')
LOCK = os.path.join(HERE, '.collect.lock')
STAMP = os.path.join(HERE, '.last-success')
JST = timezone(timedelta(hours=9))

PARKS = {
    'usj': '47f61fac-7586-41ac-ae80-61c9257cf33e',
    'tdl': '3cc919f1-d16d-43e0-8c3f-1dd269bd1a42',
    'tds': '67b290d5-3478-4f23-b601-2f8fb71ba803',
}


def log(msg):
    print('%s  %s' % (datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S'), msg))
    sys.stdout.flush()


def get(url, timeout=25):
    req = urllib.request.Request(url, headers={'User-Agent': 'parklog-collector/1.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def sample(park_id):
    """稼働中アトラクションの待ち時間の平均。取れなければ None"""
    live = get('https://api.themeparks.wiki/v1/entity/%s/live' % park_id)
    waits = []
    for x in live.get('liveData', []):
        if x.get('entityType') != 'ATTRACTION' or x.get('status') != 'OPERATING':
            continue
        w = ((x.get('queue') or {}).get('STANDBY') or {}).get('waitTime')
        if isinstance(w, int):
            waits.append(w)
    if not waits:
        return None
    return {'avg': round(sum(waits) / float(len(waits))), 'open': len(waits)}


def schedule_of(park_id, day):
    """その日の営業時間（分）。係数を引き直す時の説明変数になる"""
    try:
        sch = get('https://api.themeparks.wiki/v1/entity/%s/schedule' % park_id)
    except Exception:
        return None
    for x in sch.get('schedule', []):
        if x.get('date') == day and x.get('type') == 'OPERATING':
            def mm(t):
                return int(t[11:13]) * 60 + int(t[14:16])
            return {'o': x['openingTime'][11:16], 'c': x['closingTime'][11:16],
                    'mins': (mm(x['closingTime']) - mm(x['openingTime'])) % 1440}
    return None


def main():
    # 多重起動よけ。前の実行が2時間以上前ならロックは死んでいるとみなす
    if os.path.exists(LOCK) and time.time() - os.path.getmtime(LOCK) < 7200:
        log('別の実行が動いているのでやめる')
        return 0
    open(LOCK, 'w').write(str(os.getpid()))
    try:
        now = datetime.now(JST)
        day = now.strftime('%Y-%m-%d')
        hour = now.hour
        # 開園前・閉園後は測っても意味がない（--force で検証用に無視できる）
        if (hour < 9 or hour >= 21) and '--force' not in sys.argv:
            log('営業時間外（%d時）なので測らない' % hour)
            return 0

        data = {}
        if os.path.exists(DATA):
            try:
                data = json.load(open(DATA))
            except ValueError:
                log('history.json が壊れていたので作り直す')
                data = {}

        changed = False
        for pk, pid in PARKS.items():
            try:
                s = sample(pid)
            except Exception as e:
                log('%s 取得失敗: %s' % (pk, e))
                continue
            if not s:
                log('%s 稼働中の待ち時間なし' % pk)
                continue
            d = data.setdefault(pk, {}).setdefault(day, {'n': 0, 'sum': 0, 'avg': 0, 'h': {}})
            # 同じ時間帯を二重に数えない（再実行しても壊れない）
            if str(hour) in d['h']:
                log('%s %d時はすでに記録済み' % (pk, hour))
                continue
            d['h'][str(hour)] = s['avg']
            d['n'] += 1
            d['sum'] += s['avg']
            d['avg'] = int(round(d['sum'] / float(d['n'])))
            d['open'] = s['open']
            if 'sch' not in d:
                sc = schedule_of(pid, day)
                if sc:
                    d['sch'] = sc
            changed = True
            log('%s %d時 平均%d分（稼働%d施設）→ その日の平均%d分'
                % (pk, hour, s['avg'], s['open'], d['avg']))

        if not changed:
            log('新しい記録なし')
            return 0

        tmp = DATA + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(data, f, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
        os.rename(tmp, DATA)          # 書き途中のファイルを残さない

        # 公開サイトへ反映。認証が通らない環境でも本体は失敗させない
        try:
            env = dict(os.environ, PATH='/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin')
            subprocess.check_call(['/usr/bin/git', '-C', HERE, 'add', 'history.json'], env=env)
            subprocess.check_call(['/usr/bin/git', '-C', HERE, 'commit', '-q', '-m',
                                   '定点観測 %s %d時' % (day, hour)], env=env)
            out = subprocess.run(['/usr/bin/git', '-C', HERE, 'push', '-q'],
                                 env=env, capture_output=True)
            if out.returncode == 0:
                log('公開サイトへ反映した')
            else:
                log('push できず（ローカルには残っている）: %s' % out.stderr.decode()[:200])
        except subprocess.CalledProcessError as e:
            log('git 失敗（ローカルには残っている）: %s' % e)

        open(STAMP, 'w').write(datetime.now(JST).isoformat())
        return 0
    finally:
        if os.path.exists(LOCK):
            os.remove(LOCK)


if __name__ == '__main__':
    sys.exit(main())
