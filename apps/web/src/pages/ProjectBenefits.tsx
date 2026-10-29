import { BookIcon, ChartIcon, UsersIcon } from "../components/icons";

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
    <>
      <section id="benefits" className="benefits-section">
        <div className="benefits-heading" data-reveal>
          <p className="eyebrow">VÌ SAO CÓ MONKEY EDU?</p>
          <h2>
            Đáp án là một điểm đến.
            <br />
            <em>Hiểu bài là cả hành trình.</em>
          </h2>
          <p>
            Một câu trả lời đúng chưa kể hết câu chuyện. Monkey Edu kết nối việc học của con, sự đồng hành của
            bố mẹ và góc nhìn chuyên môn của thầy cô.
          </p>
        </div>
        <div className="benefit-grid">
          <article data-reveal>
            <span className="benefit-icon">
              <BookIcon aria-hidden="true" />
            </span>
            <span className="eyebrow">CHO HỌC SINH</span>
            <h3>
              Tự nghĩ được.
              <br /> Tự tin hơn.
            </h3>
            <p>
              Đi từ ví dụ đến cách làm, nhận gợi ý khi cần và tự giải thích lại. Con có cơ hội luyện tư duy
              thay vì chỉ chép một lời giải.
            </p>
            <span className="benefit-detail">Gợi mở từng bước · Chữ & giọng nói</span>
          </article>
          <article data-reveal>
            <span className="benefit-icon">
              <UsersIcon aria-hidden="true" />
            </span>
            <span className="eyebrow">CHO PHỤ HUYNH</span>
            <h3>
              Biết con tiến bộ
              <br /> ở chỗ nào.
            </h3>
            <p>
              Xem nhịp học, phần con đã vững và phần cần luyện thêm, cùng gợi ý đồng hành tại nhà bằng ngôn
              ngữ dễ hiểu.
            </p>
            <span className="benefit-detail">Xu hướng học tập · Gợi ý giúp con</span>
          </article>
          <article data-reveal>
            <span className="benefit-icon">
              <ChartIcon aria-hidden="true" />
            </span>
            <span className="eyebrow">CHO GIÁO VIÊN</span>
            <h3>
              Thấy chỗ vướng.
              <br /> Giúp đúng lúc.
            </h3>
            <p>
              Từ bức tranh cả lớp đến từng câu trả lời: nhận ra lỗi sai phổ biến, xem mức hiểu và bằng chứng
              để chọn chỗ cần hỗ trợ.
            </p>
            <span className="benefit-detail">Bản đồ kiến thức · Báo cáo từng em</span>
          </article>
        </div>
        <div className="benefits-principle" data-reveal>
          <span className="eyebrow">NGUYÊN TẮC CỦA DỰ ÁN</span>
          <p>
            Gia sư Buddy đồng hành cùng người dạy. <strong>Thầy cô giữ vai trò định hướng.</strong>
          </p>
          <span>Nội dung có bước duyệt. Nhận định học tập có bằng chứng để xem lại.</span>
        </div>
      </section>
      <section id="comparison" className="comparison-section">
        <div className="comparison-heading" data-reveal>
          <div>
            <p className="eyebrow">CHỌN CÁCH ĐỒNG HÀNH PHÙ HỢP</p>
            <h2>
              Buddy khác gì
              <br />
              <em>một công cụ trả lời?</em>
            </h2>
          </div>
          <p>
            Giá trị của Monkey Buddy nằm ở cách tổ chức một hành trình học Toán: có mục tiêu, có gợi mở, có
            ghi nhận tiến bộ và có người lớn cùng đồng hành.
          </p>
        </div>
        <div
          className="comparison-scroll"
          role="region"
          aria-label="So sánh các cách học Toán"
          tabIndex={0}
          data-reveal
        >
          <table className="comparison-table">
            <caption>Ba cách hỗ trợ học tập, nhìn từ trải nghiệm của con</caption>
            <thead>
              <tr>
                <th scope="col">Điều mình quan tâm</th>
                <th scope="col">
                  <span>01</span>Công cụ hỏi đáp đa dụng<small>Một cuộc trò chuyện mở</small>
                </th>
                <th scope="col">
                  <span>02</span>Video & bài tập<small>Một lộ trình có sẵn</small>
                </th>
                <th scope="col" className="buddy-column">
                  <span>CÙNG CON HIỂU BÀI</span>Monkey Buddy<small>Người bạn học Toán của con</small>
                </th>
              </tr>
            </thead>
            <tbody>
              {COMPARISON.map((row) => (
                <tr key={row.question}>
                  <th scope="row">{row.question}</th>
                  <td data-label="Công cụ hỏi đáp đa dụng">{row.chat}</td>
                  <td data-label="Video & bài tập">{row.fixed}</td>
                  <td className="buddy-column" data-label="Monkey Buddy">
                    {row.buddy}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="comparison-note">
          So sánh cách học minh họa; tính năng cụ thể tùy công cụ và cách thiết lập. Đây không phải bảng xếp
          hạng công cụ hay số đo hiệu quả học tập.
        </p>
        <div className="project-scope" data-reveal>
          <span className="scope-mark" aria-hidden="true">
            5
          </span>
          <div>
            <h3>Bắt đầu nhỏ, đi vào chiều sâu.</h3>
            <p>
              Phiên bản hiện tại tập trung vào Toán lớp 5: Số thập phân và Diện tích hình tam giác, hình
              thang. Mục tiêu là giúp con hiểu cách làm và giúp thầy cô nhìn rõ quá trình học.
            </p>
          </div>
          <a className="text-link" href="#curriculum">
            Khám phá bài học <span aria-hidden="true">↗</span>
          </a>
        </div>
      </section>
    </>
  );
}
