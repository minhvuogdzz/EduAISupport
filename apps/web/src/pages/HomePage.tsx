import type { ReactNode } from "react";
import { Link } from "react-router";

import type { KnowledgeRelation } from "../api/contract";
import { AppShell } from "../components/AppShell";
import {
  ArrowRightIcon,
  BookIcon,
  ChartIcon,
  CheckIcon,
  HeartIcon,
  PencilIcon,
  ShieldIcon,
  SparklesIcon,
  UsersIcon,
  XIcon,
} from "../components/icons";
import { TEACHING_STEPS } from "../components/labels";
import { Mascot } from "../components/Mascot";
import { KnowledgeMap, type MapNode } from "../features/teaching/KnowledgeMap";

const STEP_DETAIL = [
  "Hỏi nhanh bài cũ để chắc nền đã vững.",
  "Giảng ngắn bằng hình ảnh quen thuộc, rồi hỏi con.",
  "Con trả lời và nói lại quy tắc bằng lời của mình.",
  "Cô làm mẫu từng bước, rồi cô với con cùng làm.",
  "Con tự làm; khi cần, cô gợi ý từ nhẹ đến chi tiết.",
  "Bài có lời văn, tình huống mới để dùng điều vừa học.",
  "Đủ bằng chứng mới qua bài; chưa đủ thì ôn đúng chỗ.",
];

const CAVAT_DOES = [
  ["Không đưa đáp án ngay", "Cô gợi ý để con tự tìm ra, từ hiểu đề đến từng bước."],
  ["Hỏi “vì sao” và mời con nói lại", "Hiểu là giải thích được, không chỉ chọn đúng."],
  ["Hổng bài nền thì quay về dạy lại", "Cô biết bài nào cần học trước bài nào."],
  ["Điểm từng bài có bằng chứng", "Mỗi lần cộng, trừ điểm đều ghi rõ vì sao."],
] as const;

const CHATBOT_DOES = [
  "Đưa đáp án ngay khi con hỏi",
  "Không biết con hiểu tới đâu",
  "Không có lộ trình bài học",
  "Không giải thích được điểm số",
];

/** An illustration of the chapter graph (statuses made up for the picture). */
const SAMPLE_NODES: MapNode[] = [
  { node_id: "a", name: "Phân số thập phân", layer: "BASIC", status: "PASSED", level: 4 },
  { node_id: "b", name: "Khái niệm số thập phân", layer: "BASIC", status: "PASSED", level: 3 },
  { node_id: "c", name: "Giá trị theo hàng của số thập phân", layer: "BASIC", status: "CURRENT", level: 2 },
  { node_id: "d", name: "Số thập phân bằng nhau", layer: "BASIC", status: "LOCKED", level: null },
  { node_id: "e", name: "So sánh hai số thập phân", layer: "IMPLEMENT", status: "LOCKED", level: null },
  {
    node_id: "f",
    name: "Sắp xếp thứ tự các số thập phân",
    layer: "IMPLEMENT",
    status: "LOCKED",
    level: null,
  },
  { node_id: "g", name: "Vận dụng so sánh số thập phân", layer: "IMPLEMENT", status: "LOCKED", level: null },
];
const SAMPLE_RELATIONS: KnowledgeRelation[] = [
  { source: "a", target: "b", type: "PREREQUISITE" },
  { source: "b", target: "c", type: "PREREQUISITE" },
  { source: "c", target: "d", type: "PREREQUISITE" },
  { source: "c", target: "e", type: "APPLICATION" },
  { source: "d", target: "e", type: "APPLICATION" },
  { source: "e", target: "f", type: "PREREQUISITE" },
  { source: "c", target: "f", type: "APPLICATION" },
  { source: "e", target: "g", type: "PREREQUISITE" },
  { source: "b", target: "g", type: "APPLICATION" },
];

export function HomePage() {
  return (
    <AppShell>
      <title>CAVAT · Gia sư AI dạy Toán lớp 5</title>
      <Hero />
      <Section
        title="Một bài học cùng cô"
        subtitle="Bảy bước, như một cô giáo giỏi: giảng ngắn, hỏi nhiều, làm mẫu rồi để con tự làm."
      >
        <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
          {TEACHING_STEPS.map((step, index) => (
            <li key={step} className="card flex flex-col gap-2 p-5">
              <span className="flex size-9 items-center justify-center rounded-2xl bg-brand-100 text-base font-bold text-brand-900">
                {index + 1}
              </span>
              <span className="font-semibold">{step}</span>
              <span className="text-sm text-slate-600">{STEP_DETAIL[index]}</span>
            </li>
          ))}
        </ol>
      </Section>

      <Section
        title="Khác gì chatbot thông thường?"
        subtitle="Chatbot trả lời thay con. Cô dạy con cách tự trả lời."
      >
        <div className="grid gap-4 md:grid-cols-2">
          <div className="card brand-gradient p-6">
            <p className="flex items-center gap-2 text-lg font-bold text-brand-900">
              <Mascot size={36} /> CAVAT
            </p>
            <ul className="mt-4 flex flex-col gap-3">
              {CAVAT_DOES.map(([title, detail]) => (
                <li key={title} className="flex gap-3">
                  <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-brand-700 text-white">
                    <CheckIcon className="size-4" />
                  </span>
                  <span>
                    <span className="block font-semibold">{title}</span>
                    <span className="text-sm text-slate-700">{detail}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="card p-6">
            <p className="text-lg font-bold text-slate-700">Chatbot thông thường</p>
            <ul className="mt-4 flex flex-col gap-3">
              {CHATBOT_DOES.map((item) => (
                <li key={item} className="flex gap-3 text-slate-700">
                  <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-600">
                    <XIcon className="size-4" />
                  </span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Section>

      <Section
        title="Cây tri thức của chương"
        subtitle="Mỗi bài là một nút. Bài nào cần học trước, bài nào áp dụng vào bài nào, cô đều biết, nên cô dạy đúng thứ tự và quay về đúng chỗ khi con còn hổng."
      >
        <div className="grid items-center gap-6 lg:grid-cols-[minmax(0,28rem)_1fr]">
          <div className="card p-4">
            <KnowledgeMap
              nodes={SAMPLE_NODES}
              relations={SAMPLE_RELATIONS}
              title="Ví dụ cây tri thức chương Số thập phân"
            />
          </div>
          <ul className="flex flex-col gap-4">
            <Feature icon={<BookIcon className="size-6" />} title="Dạy lý thuyết và phương pháp">
              Mỗi bài có lời giảng theo hai, ba cách, bài cô làm mẫu và câu hỏi để con nói lại quy tắc.
            </Feature>
            <Feature icon={<ChartIcon className="size-6" />} title="Điểm hiểu bài theo bảy chiều">
              Làm đúng, lập luận, vận dụng, chuyển giao, tự làm, ghi nhớ, phát hiện lỗi. Điểm do quy tắc tính,
              AI không tự cho điểm.
            </Feature>
            <Feature icon={<ShieldIcon className="size-6" />} title="Đủ bằng chứng mới qua bài">
              Phải làm đúng nhiều dạng câu, giải thích được và làm được bài vận dụng.
            </Feature>
          </ul>
        </div>
      </Section>

      <Section title="Mỗi người một góc nhìn" subtitle="Cùng một dữ liệu, nói theo cách mỗi người cần.">
        <div className="grid gap-4 md:grid-cols-3">
          <RoleCard
            to="/student"
            icon={<PencilIcon className="size-6" />}
            title="Học sinh"
            tone="bg-brand-100 text-brand-900"
          >
            Học theo lộ trình của chương, biết bài nào đã nắm chắc, bài nào cần luyện thêm.
          </RoleCard>
          <RoleCard
            to="/parent"
            icon={<HeartIcon className="size-6" />}
            title="Phụ huynh"
            tone="bg-gold-soft text-amber-900"
          >
            Biết con học có đều không, hiểu bài tới đâu và nên giúp con ở nhà thế nào.
          </RoleCard>
          <RoleCard
            to="/teacher"
            icon={<UsersIcon className="size-6" />}
            title="Giáo viên"
            tone="bg-sky-soft text-sky-900"
          >
            Bản đồ cả lớp, lỗi sai phổ biến và bằng chứng đằng sau từng điểm số.
          </RoleCard>
        </div>
      </Section>

      <section className="mx-auto max-w-7xl px-4 pb-16">
        <div className="card brand-gradient flex flex-col items-center gap-4 p-8 text-center md:p-12">
          <Mascot mood="celebrating" size={96} />
          <h2 className="text-2xl font-extrabold text-balance md:text-3xl">Cô không làm bài thay con.</h2>
          <p className="max-w-2xl text-lg text-slate-700">
            Cô giúp con hiểu cách làm, để con tự tin với chính kiến thức của mình.
          </p>
          <Link
            to="/student"
            className="inline-flex items-center gap-2 rounded-full bg-brand-700 px-6 py-3 text-lg font-semibold text-white hover:bg-brand-800"
          >
            Vào học ngay <ArrowRightIcon className="size-5" />
          </Link>
        </div>
      </section>
    </AppShell>
  );
}

function Hero() {
  return (
    <section className="brand-gradient relative overflow-hidden">
      <div className="mx-auto grid max-w-7xl items-center gap-10 px-4 py-14 md:py-20 lg:grid-cols-[1.2fr_1fr]">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full bg-white/75 px-3 py-1 text-sm font-medium text-amber-900 ring-1 ring-gold/50">
            <SparklesIcon className="size-4" />
            Gia sư AI cho học sinh lớp 5
          </p>
          <h1 className="mt-4 text-3xl leading-tight font-extrabold text-balance md:text-5xl">
            Học Toán cùng cô, <span className="text-brand-700">hiểu bài thật sự</span>
          </h1>
          <p className="mt-4 max-w-xl text-lg text-slate-700">
            CAVAT dạy như một cô giáo giỏi: giảng ngắn, hỏi nhiều, làm mẫu rồi để con tự làm. Cô không đưa đáp
            án, cô gợi ý từng bước để con tự tìm ra.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              to="/student"
              className="inline-flex items-center gap-2 rounded-full bg-brand-700 px-6 py-3 text-lg font-semibold text-white shadow-sm hover:bg-brand-800"
            >
              Vào học ngay <ArrowRightIcon className="size-5" />
            </Link>
            <Link
              to="/parent"
              className="rounded-full bg-white px-6 py-3 text-lg font-semibold text-brand-900 ring-1 ring-brand-200 hover:bg-brand-50"
            >
              Phụ huynh xem tiến bộ
            </Link>
            <Link
              to="/teacher"
              className="rounded-full px-6 py-3 text-lg font-semibold text-brand-900 underline-offset-4 hover:underline"
            >
              Dành cho giáo viên
            </Link>
          </div>
          <ul className="mt-6 flex flex-wrap gap-x-5 gap-y-2 text-sm font-medium text-slate-700">
            <li className="inline-flex items-center gap-1.5">
              <ShieldIcon className="size-4 text-brand-700" /> Không làm hộ
            </li>
            <li className="inline-flex items-center gap-1.5">
              <ChartIcon className="size-4 text-brand-700" /> Điểm có bằng chứng
            </li>
            <li className="inline-flex items-center gap-1.5">
              <HeartIcon className="size-4 text-brand-700" /> Lời lẽ nhẹ nhàng, khích lệ
            </li>
          </ul>
        </div>
        <div className="flex flex-col items-center gap-3">
          <div className="relative rounded-3xl bg-white/85 px-5 py-3 text-lg font-medium shadow-sm ring-1 ring-gold/40">
            Chào con! Hôm nay mình học Số thập phân nhé.
            <span className="absolute -bottom-2 left-1/2 size-4 -translate-x-1/2 rotate-45 bg-white/85 ring-1 ring-gold/40 [clip-path:polygon(100%_0,100%_100%,0_100%)]" />
          </div>
          <Mascot size={240} label="Linh vật CAVAT" />
        </div>
      </div>
    </section>
  );
}

function Section({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <section className="mx-auto max-w-7xl px-4 py-14">
      <h2 className="text-center text-3xl font-extrabold text-balance">{title}</h2>
      <p className="mx-auto mt-2 max-w-3xl text-center text-lg text-slate-600">{subtitle}</p>
      <div className="mt-8">{children}</div>
    </section>
  );
}

function Feature({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <li className="card flex gap-4 p-5">
      <span className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-brand-100 text-brand-800">
        {icon}
      </span>
      <span>
        <span className="block text-lg font-semibold">{title}</span>
        <span className="text-slate-700">{children}</span>
      </span>
    </li>
  );
}

function RoleCard({
  to,
  icon,
  title,
  tone,
  children,
}: {
  to: string;
  icon: ReactNode;
  title: string;
  tone: string;
  children: ReactNode;
}) {
  return (
    <Link
      to={to}
      className="card group flex flex-col gap-3 p-6 transition hover:-translate-y-0.5 hover:shadow-md"
    >
      <span className={`flex size-12 items-center justify-center rounded-2xl ${tone}`}>{icon}</span>
      <span className="text-xl font-bold">{title}</span>
      <span className="text-slate-700">{children}</span>
      <span className="mt-auto inline-flex items-center gap-1 font-semibold text-brand-800 group-hover:underline">
        Vào trang {title.toLowerCase()} <ArrowRightIcon className="size-4" />
      </span>
    </Link>
  );
}
