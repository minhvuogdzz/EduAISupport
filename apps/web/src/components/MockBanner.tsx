import { useApi } from "../api/apiContext";

/** Says plainly that nothing on screen comes from the real tutor while the mock API is in use. */
export function MockBanner() {
  const api = useApi();
  if (api.engine !== "mock") return null;
  return (
    <p className="bg-amber-100 px-4 py-1.5 text-center text-sm text-amber-950">
      Chế độ giả lập (mock): chưa nối máy chủ. Lời của cô là câu mẫu, chưa phải lời của Gia sư Buddy.
    </p>
  );
}
