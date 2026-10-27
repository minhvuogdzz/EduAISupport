#!/bin/sh
# First deployment: build, wait for Mongo, validate/import the private transfer, start the single app.
# Arguments are filenames inside db-dump/, never arbitrary shell commands or paths.
set -eu
cd "$(dirname "$0")/.."

if [ "$#" -gt 2 ]; then
  echo "Dùng: sh deploy/start.sh [cavat-db-XXX.tar.gz [cavat-storage-XXX.tar.gz]]" >&2
  exit 1
fi
for name in "$@"; do
  case "$name" in
    ''|*[!A-Za-z0-9._-]*|.*) echo "Chỉ truyền tên tệp trong db-dump/: $name" >&2; exit 1 ;;
  esac
  [ -f "db-dump/$name" ] || { echo "Thiếu db-dump/$name" >&2; exit 1; }
done
[ -f .env ] || { echo "Chạy sh deploy/setup.sh và điền khóa trong .env trước." >&2; exit 1; }

CAVAT_REVISION=$(git rev-parse HEAD 2>/dev/null || echo unknown)
export CAVAT_REVISION
docker compose build app
docker compose up -d --wait --wait-timeout 120 mongo

if [ "$#" -ge 1 ]; then
  docker compose run --rm --no-deps app python -m cavat.restore "/dump/$1" --dry-run
fi
if [ "$#" -eq 2 ]; then
  docker compose run --rm --no-deps app python -m cavat.storage_transfer restore "/dump/$2" --dry-run
fi
if [ "$#" -ge 1 ]; then
  docker compose run --rm --no-deps app python -m cavat.restore "/dump/$1"
fi
if [ "$#" -eq 2 ]; then
  docker compose run --rm --no-deps app python -m cavat.storage_transfer restore "/dump/$2"
fi

docker compose up -d --wait --wait-timeout 180 app
docker compose exec -T app python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8000/health/db").read().decode())'
echo "Đã chạy bản $CAVAT_REVISION. Cổng theo PORT trong .env (mặc định 8080)."
