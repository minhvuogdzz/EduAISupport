# EduAISupport — CAVAT AI Tutor (Grade 5)

Nền tảng **AI-managed Learning Session** cho học sinh lớp 5. Ba vai trò: Teacher, Student (trung tâm), Parent/Guardian.

- Giáo viên thiết kế bài học.
- Scheduler kích hoạt buổi học.
- **Tutor Contract** ràng buộc buổi học, **Tutor Orchestrator** điều phối.
- **Socratic AI Tutor** trực tiếp dạy: hỏi → chẩn đoán → gợi ý → thử lại → xác minh → tiến tiếp.
- Mọi tương tác sinh **evidence**, được đánh giá tất định. Kết quả cập nhật Student Model và báo cáo giải thích được cho giáo viên và phụ huynh.

**Scope phiên bản đầu:** Math Grade 5 + English Grade 5 (Reading + Speaking).

**Bối cảnh:** đồ án tốt nghiệp, sản phẩm nội bộ để kiểm thử, ưu tiên dịch vụ miễn phí, chạy local, database MongoDB Atlas.

## Trạng thái

Đã có khung repo và đặc tả nháp của bài đầu tiên. Code được làm theo task trong [docs/tasks/BACKLOG.md](docs/tasks/BACKLOG.md).

## Chạy ở máy local

```bash
make setup
```

Chép file credentials Atlas thành `.env` của API (file này đã gitignore, không bao giờ commit):

```bash
cp ~/Downloads/atlas-credentials.env services/api/.env
```

Kiểm tra kết nối database, chạy test và API:

```bash
make db-ping
```

```bash
make test
```

```bash
make api
```

## Tài liệu

- **Bắt đầu từ đây:** [docs/blueprint/00-START-HERE.md](docs/blueprint/00-START-HERE.md). Gồm audit, Q1–Q18 và mục lục 48 PART.
- **Việc cho phiên cloud:** [docs/tasks/BACKLOG.md](docs/tasks/BACKLOG.md).
- **Quy ước cho phiên AI:** [CLAUDE.md](CLAUDE.md).
