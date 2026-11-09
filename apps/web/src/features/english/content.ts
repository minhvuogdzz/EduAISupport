import type { ComponentType, SVGProps } from "react";

import {
  BookIcon,
  ChatBubbleIcon,
  HeadphonesIcon,
  HeartIcon,
  MapPinIcon,
  PencilIcon,
  StarIcon,
  UsersIcon,
  UtensilsIcon,
} from "../../components/icons";

type Icon = ComponentType<SVGProps<SVGSVGElement>>;

export interface EnglishSkill {
  name: string;
  label: string;
  note: string;
  icon: Icon;
  tone: string;
}

export interface EnglishUnit {
  id: string;
  title: string;
  subtitle: string;
  goal: string;
  icon: Icon;
  tone: string;
  words: { word: string; meaning: string }[];
  phrases: { en: string; vi: string }[];
  starters: string[];
}

/** The four skills a lesson will walk through once the English tutor exists. */
export const ENGLISH_SKILLS: EnglishSkill[] = [
  { name: "Listening", label: "Nghe", note: "Làm quen âm thanh", icon: HeadphonesIcon, tone: "tone-sky" },
  { name: "Speaking", label: "Nói", note: "Tập nói cùng Buddy", icon: ChatBubbleIcon, tone: "tone-coral" },
  { name: "Reading", label: "Đọc", note: "Đọc câu chuyện ngắn", icon: BookIcon, tone: "tone-leaf" },
  { name: "Writing", label: "Viết", note: "Viết câu của riêng con", icon: PencilIcon, tone: "tone-grape" },
];

/**
 * The illustrative topics of the English preview. They show what the module will look like: no tutor,
 * grading or progress stands behind them, and the teacher has not reviewed them as a curriculum.
 */
export const ENGLISH_UNITS: EnglishUnit[] = [
  {
    id: "hello-friends",
    title: "Hello, friends!",
    subtitle: "Chào hỏi và giới thiệu bản thân",
    goal: "Con chào bạn mới, nói tên và tuổi của mình.",
    icon: UsersIcon,
    tone: "tone-coral",
    words: [
      { word: "hello", meaning: "xin chào" },
      { word: "name", meaning: "tên" },
      { word: "friend", meaning: "bạn bè" },
      { word: "nice", meaning: "vui, tốt" },
    ],
    phrases: [
      { en: "What's your name?", vi: "Bạn tên là gì?" },
      { en: "Nice to meet you!", vi: "Rất vui được gặp bạn!" },
    ],
    starters: ["Cách giới thiệu tên?", "“Hello” và “Hi” khác gì nhau?"],
  },
  {
    id: "my-family",
    title: "My family",
    subtitle: "Gia đình thân yêu của con",
    goal: "Con kể về những người trong gia đình.",
    icon: HeartIcon,
    tone: "tone-rose",
    words: [
      { word: "mother", meaning: "mẹ" },
      { word: "father", meaning: "bố" },
      { word: "sister", meaning: "chị, em gái" },
      { word: "brother", meaning: "anh, em trai" },
    ],
    phrases: [
      { en: "This is my mother.", vi: "Đây là mẹ của mình." },
      { en: "I have one brother.", vi: "Mình có một anh trai." },
    ],
    starters: ["Kể về bố mẹ thế nào?", "“Brother” là anh hay em?"],
  },
  {
    id: "school-day",
    title: "My school day",
    subtitle: "Một ngày ở trường",
    goal: "Con nói về môn học và việc làm trong ngày.",
    icon: BookIcon,
    tone: "tone-sky",
    words: [
      { word: "school", meaning: "trường học" },
      { word: "subject", meaning: "môn học" },
      { word: "teacher", meaning: "cô giáo, thầy giáo" },
      { word: "lesson", meaning: "bài học" },
    ],
    phrases: [
      { en: "I go to school at seven.", vi: "Mình đi học lúc bảy giờ." },
      { en: "My favourite subject is Maths.", vi: "Môn mình thích nhất là Toán." },
    ],
    starters: ["Nói giờ đi học ra sao?", "Môn Toán tiếng Anh là gì?"],
  },
  {
    id: "food-drinks",
    title: "Food and drinks",
    subtitle: "Món con thích ăn, thích uống",
    goal: "Con nói món mình thích và mời bạn ăn cùng.",
    icon: UtensilsIcon,
    tone: "tone-sun",
    words: [
      { word: "rice", meaning: "cơm" },
      { word: "noodles", meaning: "mì, phở, bún" },
      { word: "juice", meaning: "nước ép" },
      { word: "hungry", meaning: "đói bụng" },
    ],
    phrases: [
      { en: "I like noodles.", vi: "Mình thích ăn mì." },
      { en: "Would you like some juice?", vi: "Bạn uống chút nước ép nhé?" },
    ],
    starters: ["Cách mời bạn ăn?", "“Noodles” có phải là phở không?"],
  },
  {
    id: "my-hobbies",
    title: "My hobbies",
    subtitle: "Sở thích và thời gian rảnh",
    goal: "Con kể việc mình thích làm sau giờ học.",
    icon: StarIcon,
    tone: "tone-grape",
    words: [
      { word: "draw", meaning: "vẽ" },
      { word: "sing", meaning: "hát" },
      { word: "swim", meaning: "bơi" },
      { word: "read", meaning: "đọc" },
    ],
    phrases: [
      { en: "I like drawing.", vi: "Mình thích vẽ." },
      { en: "What do you do at weekends?", vi: "Cuối tuần bạn làm gì?" },
    ],
    starters: ["Kể sở thích thế nào?", "Vì sao lại là “drawing”?"],
  },
  {
    id: "my-town",
    title: "Around my town",
    subtitle: "Những nơi quanh nhà con",
    goal: "Con gọi tên các địa điểm và hỏi đường ngắn.",
    icon: MapPinIcon,
    tone: "tone-leaf",
    words: [
      { word: "park", meaning: "công viên" },
      { word: "market", meaning: "chợ" },
      { word: "library", meaning: "thư viện" },
      { word: "near", meaning: "gần" },
    ],
    phrases: [
      { en: "Where is the park?", vi: "Công viên ở đâu?" },
      { en: "It's near my house.", vi: "Nó ở gần nhà mình." },
    ],
    starters: ["Hỏi đường thế nào?", "“Near” dùng ra sao?"],
  },
];

/** Sample only, shown under a "minh họa" label: what the parent's view will say, one level per topic. */
export const SAMPLE_CHILD_LEVELS = [
  "Tự làm được",
  "Làm được khi có hỗ trợ",
  "Đang làm quen",
  "Chưa học",
  "Chưa học",
  "Chưa học",
];

/** Sample only, shown under a "minh họa" label: the teacher's class view, with no real student in it. */
export const SAMPLE_CLASS = [
  { name: "Học sinh A", levels: ["Tự làm được", "Làm được khi có hỗ trợ", "Tự làm được", "Đang làm quen"] },
  {
    name: "Học sinh B",
    levels: ["Đang làm quen", "Đang làm quen", "Làm được khi có hỗ trợ", "Đang làm quen"],
  },
  {
    name: "Học sinh C",
    levels: ["Vững và vận dụng", "Tự làm được", "Tự làm được", "Làm được khi có hỗ trợ"],
  },
];
