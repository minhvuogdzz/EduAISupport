import { Link } from "react-router";

export function NotFoundPage() {
  return (
    <main className="mx-auto flex max-w-xl flex-col items-center gap-6 px-4 py-16 text-center">
      <title>Không tìm thấy trang · CAVAT</title>
      <h1 className="text-3xl font-bold">Không tìm thấy trang này</h1>
      <Link to="/" className="rounded-2xl bg-teal-700 px-6 py-3 text-xl font-semibold text-white">
        Về trang chính
      </Link>
    </main>
  );
}
