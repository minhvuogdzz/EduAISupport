import type { Mood } from "../components/Mascot";

export const BUDDY_MOMENTS: { mood: Mood; label: string; quote: string; text: string }[] = [
  {
    mood: "happy",
    label: "Chào con",
    quote: "Chào con! Hôm nay mình khám phá gì nhỉ?",
    text: "Một lời chào thân quen, để mỗi buổi học bắt đầu thật nhẹ nhàng.",
  },
  {
    mood: "listening",
    label: "Lắng nghe",
    quote: "Buddy đang nghe đây. Con kể cách con nghĩ nhé!",
    text: "Con có thể gõ hoặc nói. Cách con giải thích cũng quan trọng như đáp án.",
  },
  {
    mood: "thinking",
    label: "Cùng suy nghĩ",
    quote: "Mình thử nhìn bài này theo một cách khác nhé?",
    text: "Khi con còn vướng, Buddy gợi mở từng chút để con tự tìm ra cách làm.",
  },
  {
    mood: "encouraging",
    label: "Động viên",
    quote: "Chưa ra cũng không sao. Mình thử thêm một bước!",
    text: "Một người bạn kiên nhẫn, cho con thêm tự tin để tiếp tục thử.",
  },
  {
    mood: "celebrating",
    label: "Ăn mừng",
    quote: "A, con tìm ra rồi! Kể Buddy nghe vì sao nhé!",
    text: "Niềm vui đến từ điều con thực sự hiểu, qua từng câu trả lời và cách giải thích.",
  },
];
