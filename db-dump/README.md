# Gói bàn giao riêng cho DevOps

Đặt `cavat-db-<mốc>.tar.gz`, `cavat-storage-<mốc>.tar.gz` và `SHA256SUMS` tại đây. Repo công khai, các tệp này chứa tài khoản/lịch sử/tài liệu nên git bỏ qua, image không chứa chúng. Chuyển riêng tới DevOps.

Sau setup và điền khóa trong `.env`, chạy tại gốc repo:

```sh
(cd db-dump && sha256sum -c SHA256SUMS)
sh deploy/start.sh cavat-db-<mốc>.tar.gz cavat-storage-<mốc>.tar.gz
```

Chi tiết: `deploy/README.md`. Khi update không truyền archive để giữ dữ liệu hiện tại.
