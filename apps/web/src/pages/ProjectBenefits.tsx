import "./home.css";

const COMPARISON = [
  {
    question: "Buổi học bắt đầu từ đâu?",
    chat: "Từ câu hỏi người học nhập vào.",
    fixed: "Từ một bài giảng hoặc bộ câu hỏi có sẵn.",
    buddy: "Từ bài đang học và phần kiến thức con cần củng cố.",
  },
  {
    question: "Khi con chưa hiểu?",
    chat: "Người học hỏi tiếp để nhận cách giải thích khác.",
    fixed: "Xem lại bài giảng, lời giải hoặc thử lại câu hỏi.",
    buddy: "Gợi ý từng mức, làm mẫu khi cần rồi cho con tự thử.",
  },
  {
    question: "Hiểu bài được nhìn nhận thế nào?",
    chat: "Qua nội dung trao đổi trong cuộc trò chuyện.",
    fixed: "Qua đáp án và kết quả hoàn thành bài tập.",
    buddy: "Qua câu trả lời, lập luận, mức hỗ trợ và bằng chứng qua các buổi.",
  },
  {
    question: "Ai nhìn thấy hành trình học?",
    chat: "Người tham gia cuộc trò chuyện.",
    fixed: "Tùy công cụ và báo cáo của khóa học.",
    buddy: "Con xem việc học; bố mẹ xem tiến bộ; thầy cô xem bằng chứng chi tiết.",
  },
  {
    question: "Nội dung được tổ chức ra sao?",
    chat: "Theo chủ đề và yêu cầu trong lời nhắn.",
    fixed: "Theo lộ trình của tài liệu hoặc khóa học.",
    buddy: "Theo cây kiến thức và nội dung giáo viên quản lý, duyệt trước khi dạy.",
  },
];

export function ProjectBenefits() {
  return (
    <section id="comparison" className="hm-section">
      <div className="hm-intro" data-reveal>
        <p className="hm-kicker">Chọn cách đồng hành phù hợp</p>
        <h2>
          Buddy khác gì <mark>một công cụ trả lời?</mark>
        </h2>
      </div>
      <div
        className="hm-table-scroll"
        role="region"
        aria-label="So sánh các cách học"
        tabIndex={0}
        data-reveal
      >
        <table className="hm-table">
          <caption className="sr-only">Ba cách hỗ trợ học tập, nhìn từ trải nghiệm của con</caption>
          <thead>
            <tr>
              <th scope="col">Điều mình quan tâm</th>
              <th scope="col">Công cụ hỏi đáp đa dụng</th>
              <th scope="col">Video và bài tập</th>
              <th scope="col" className="is-buddy">
                Monkey Buddy
              </th>
            </tr>
          </thead>
          <tbody>
            {COMPARISON.map((row) => (
              <tr key={row.question}>
                <th scope="row">{row.question}</th>
                <td data-label="Công cụ hỏi đáp đa dụng">{row.chat}</td>
                <td data-label="Video và bài tập">{row.fixed}</td>
                <td className="is-buddy" data-label="Monkey Buddy">
                  {row.buddy}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="hm-note hm-table-note">
        So sánh cách học minh họa; tính năng cụ thể tùy công cụ và cách thiết lập. Phiên bản hiện tại dạy Toán
        lớp 5; Tiếng Anh đang ở bản xem trước giao diện.
      </p>
    </section>
  );
}
