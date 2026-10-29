#!/bin/sh
# Import the private handoff once, into an empty database and storage volume.
set -eu
cd "$(dirname "$0")/.."
[ "$#" -le 1 ] || { echo 'Dùng: sh deploy/import.sh [gói bàn giao]' >&2; exit 1; }
if [ "$#" -eq 1 ]; then
  python3 deploy/unpack_handoff.py "$1"
elif [ ! -f db-dump/cavat-db.tar.gz ] && [ -f db-dump/cavat-handoff-latest.tar.gz ]; then
  python3 deploy/unpack_handoff.py db-dump/cavat-handoff-latest.tar.gz
fi

[ -f db-dump/cavat-db.tar.gz ] && [ -f db-dump/cavat-storage.tar.gz ] && [ -f db-dump/SHA256SUMS ] || {
  echo 'Cần cavat-db.tar.gz, cavat-storage.tar.gz và SHA256SUMS trong db-dump/.' >&2; exit 1;
}
if command -v sha256sum >/dev/null 2>&1; then
  (cd db-dump && sha256sum -c SHA256SUMS)
else
  (cd db-dump && shasum -a 256 -c SHA256SUMS)
fi
docker compose stop app
docker compose up -d --wait --wait-timeout 180 mongo
# Archives may be mode 0600 and owned by the operator, not container uid 10001.
# Copy as root inside the temporary container, then validate/import as the unprivileged app user.
run_import() {
  docker compose run --rm --no-deps --user 0 --entrypoint sh app -c '
    set -eu
    cp "$1" /tmp/cavat-import.tar.gz
    chown cavat:cavat /tmp/cavat-import.tar.gz
    shift
    exec su -s /bin/sh cavat -c "$1"
  ' sh "$1" "$2"
}
run_import /dump/cavat-db.tar.gz 'python -m cavat.restore /tmp/cavat-import.tar.gz --dry-run'
run_import /dump/cavat-storage.tar.gz 'python -m cavat.storage_transfer restore /tmp/cavat-import.tar.gz --dry-run'
run_import /dump/cavat-db.tar.gz 'python -m cavat.restore /tmp/cavat-import.tar.gz'
run_import /dump/cavat-storage.tar.gz 'python -m cavat.storage_transfer restore /tmp/cavat-import.tar.gz'
docker compose up -d --wait --wait-timeout 180 app
echo 'Đã nhập database và storage. Không chạy lại trên dữ liệu đã có.'
