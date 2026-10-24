#!/bin/sh
# Non-root, ephemeral limiter only. Never put a credential in argv or logs.
set -eu
umask 077
password=$(cat /run/secrets/redis_password)
case "$password" in *[!A-Za-z0-9_-]*|'') echo 'Redis credential format refused' >&2; exit 1;; esac
[ "${#password}" -ge 32 ] || { echo 'Redis credential length refused' >&2; exit 1; }
namespace=${RATE_LIMIT_NAMESPACE:?explicit rate-limit namespace required}
case "$namespace" in *[!A-Za-z0-9_.:-]*|'') echo 'Redis namespace refused' >&2; exit 1;; esac
# The application identity cannot enumerate keys, flush, configure, persist or
# access another namespace. All Lua subcommands are explicitly authorized.
printf 'user default off\nuser limiter on >%s ~%s* -@all +ping +eval +time +zremrangebyscore +zcard +zrange +zadd +expire\n' "$password" "$namespace" > /tmp/ask4mo-redis.acl
unset password
exec redis-server --bind 0.0.0.0 --protected-mode yes --port 6379 \
  --aclfile /tmp/ask4mo-redis.acl --save '' --appendonly no \
  --maxmemory 64mb --maxmemory-policy noeviction --loglevel warning
