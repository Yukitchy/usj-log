#!/bin/sh
# launchdはスリープ中に発火時刻を過ぎると起床直後に流すため、Wi-Fi未接続でDNSが即死する。
# 本体の前にネット到達を待たせる（insight_launchd_wake_dns_fail）。
/Users/yuki/bin/wait-for-net.sh api.themeparks.wiki 120
exec /usr/bin/python3 /Users/yuki/usj-log/collect.py
