#!/usr/bin/env bash
# Runs a network command again after a transient failure.
#   bash factory/tools/net_retry.sh <command> [args...]     e.g.  net_retry.sh gh release download TAG -p NAME -O FILE
#                                                                  net_retry.sh curl -fsSL -o FILE URL
# Transient: timeouts, stalled transfers, refused / reset / closed connections, DNS, TLS, HTTP 408 425 429 5xx and
# rate limits. Pauses of 1, 2, 4 ... 32 s plus up to 1 s of jitter; no attempt starts later than NET_DEADLINE seconds
# (default 300) after the first one, and one attempt may last NET_TIMEOUT seconds (default 1800).
# Any other failure (not found, no matching asset, another HTTP 4xx, bad usage) ends at once with the command's code.
# stdout of the attempt that succeeds is passed on whole (a half answer of a failed attempt is never mixed in); the
# command's stderr is printed after each attempt.
# A "gh release create" that finds its release already there after a transient failure of its own counts as done.
set -u
[ $# -gt 0 ] || { echo "usage: net_retry.sh <command> [args...]" >&2; exit 2; }
deadline=${NET_DEADLINE:-300}
limit=${NET_TIMEOUT:-1800}
transient='bytes missing|end of response|rate limit|secondary rate|HTTP (408|425|429|5[0-9][0-9])|error: (408|425|429|5[0-9][0-9])|gateway|service unavailable|internal server error|timed out|timeout|time-out|too slow|deadline exceeded|connection (refused|reset|closed|aborted)|failed to connect|could not connect|could not resolve|no such host|temporary failure|network is unreachable|empty reply|partial file|transfer closed|unexpected eof|broken pipe|tls|ssl|stream error|http2|http/2|send failure|recv failure|failure when receiving'
start=$(date +%s)
n=0
err=$(mktemp)
out=$(mktemp)
trap 'rm -f "$err" "$out"' EXIT
while :; do
  timeout -k 15 "$limit" "$@" >"$out" 2>"$err"
  rc=$?
  cat "$err" >&2
  if [ $rc -eq 0 ]; then cat "$out"; exit 0; fi
  if [ $n -gt 0 ] && [ "$#" -ge 3 ] && [ "$1" = gh ] && [ "$2" = release ] && [ "$3" = create ] && grep -qi "already exists" "$err"; then
    echo "net_retry: the release was made by the earlier attempt" >&2
    exit 0
  fi
  if [ $rc -eq 126 ] || [ $rc -eq 127 ]; then
    exit $rc                                                  # the command itself cannot run
  elif [ $rc -eq 124 ] || [ $rc -eq 137 ]; then
    why="no answer within $limit s"
  elif [ "$1" = curl ] && [[ " 5 6 7 16 18 28 35 52 55 56 92 " == *" $rc "* ]]; then
    why="transient (curl $rc)"                                # resolve, connect, HTTP/2, partial, timeout, TLS, send/recv
  elif grep -qiE "$transient" "$err"; then
    why="transient"
  elif [ ! -s "$err" ]; then
    why="failed without a message"
  else
    cat "$out"; exit $rc
  fi
  now=$(date +%s)
  p=$(( n < 5 ? 1 << n : 32 ))
  if [ $(( now - start + p + 1 )) -gt "$deadline" ]; then
    echo "net_retry: giving up after $((n + 1)) attempts in $((now - start)) s ($why): $1 ${2:-} ${3:-}" >&2
    cat "$out"; exit $rc
  fi
  j=$(printf '%03d' $(( RANDOM % 1000 )))
  echo "net_retry: attempt $((n + 1)) failed ($why, exit $rc) - again in $p.$j s" >&2
  sleep "$p.$j"
  n=$((n + 1))
done
