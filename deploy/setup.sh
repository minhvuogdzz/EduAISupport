#!/bin/sh
# Prepare .env for docker compose: copy the example and fill in the two secrets that must be random.
# Safe to run again: it never replaces a value that is already set.
set -eu
umask 077
cd "$(dirname "$0")/.."

[ -f .env ] || cp .env.example .env

random() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 24
  else
    head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n'
  fi
}

is_set() { grep -Eq "^$1=.+" .env; }

fill() {
  is_set "$1" && return 0
  value=$(random)
  if grep -Eq "^$1=" .env; then
    tmp=$(mktemp)
    sed "s|^$1=.*|$1=$value|" .env >"$tmp"
    cat "$tmp" >.env
    rm -f "$tmp"
  else
    printf '%s=%s\n' "$1" "$value" >>.env
  fi
  echo "  $1: đã tạo giá trị ngẫu nhiên"
}

fill MONGO_PASSWORD
fill AUTH_SECRET
chmod 600 .env

if is_set GROQ_API_KEY; then
  echo "Sẵn sàng. Chạy: docker compose up -d --build"
else
  echo "Còn thiếu GROQ_API_KEY: mở .env, dán khóa Groq (và GEMINI_API_KEY nếu có), rồi chạy:"
  echo "  docker compose up -d --build"
fi
