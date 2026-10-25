#!/bin/sh
# Bundled PG16 loader/libraries isolate client ABI from the API's Python runtime.
set -eu
case "$(basename "$0")" in pg_dump|pg_restore) client="$(basename "$0")";; *) exit 1;; esac
exec /opt/pg16/loader --library-path /opt/pg16/lib "/opt/pg16/bin/$client" "$@"
