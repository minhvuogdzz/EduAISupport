import { useAutoAdvance } from "../lib/useAutoAdvance";
import { Mascot } from "../components/Mascot";
import { BUDDY_MOMENTS } from "./buddyMoments";

export function BuddyShowcase() {
  const { ref, selected, setSelected, playing, setPlaying, running, reduced } = useAutoAdvance(
    BUDDY_MOMENTS.length,
  );
  const moment = BUDDY_MOMENTS[selected];
  return (
    <section id="buddy" ref={ref} className={`buddy-section ${running ? "" : "buddy-paused"}`}>
      <div className="buddy-stage" data-reveal>
        <span className="buddy-stage-caption">GẶP NGƯỜI BẠN MỚI CỦA CON</span>
        <div className="buddy-stage-art">
          <span className="buddy-stage-orbit" aria-hidden="true" />
          <span className="buddy-doodle buddy-doodle-one" aria-hidden="true">
            a + b
          </span>
          <span className="buddy-doodle buddy-doodle-two" aria-hidden="true">
            0,3
          </span>
          <Mascot size={300} mood={moment.mood} animated={playing && !reduced} label="Monkey Buddy" />
          <span className="buddy-name-tag">
            Monkey Buddy <span aria-hidden="true">✦</span>
          </span>
        </div>
        <button className="buddy-motion-toggle" onClick={() => setPlaying(!playing)} aria-pressed={!playing}>
          {playing ? "Tạm dừng tự đổi cảm xúc" : "Bật tự đổi cảm xúc"}
        </button>
      </div>
      <div className="buddy-intro" data-reveal>
        <p className="eyebrow">LINH VẬT CỦA MONKEY EDU</p>
        <h2>
          Một người bạn nhỏ.
          <br />
          <em>Thật nhiều thấu hiểu.</em>
        </h2>
        <p>
          Đây là Monkey Buddy — chú khỉ tò mò với chiếc khăn vàng và một tinh thần luôn sẵn sàng thử. Buddy
          đồng hành cùng con qua từng khoảnh khắc học Toán.
        </p>
        <p className="buddy-autoplay-note">
          {reduced
            ? "Chọn một cảm xúc để khám phá cùng Buddy."
            : "Mỗi 2 giây, một nét đáng yêu. Con cũng có thể bấm chọn nhé."}
        </p>
        <div className="buddy-moods" role="group" aria-label="Khám phá biểu cảm Monkey Buddy">
          {BUDDY_MOMENTS.map((item, index) => (
            <button key={item.mood} aria-pressed={selected === index} onClick={() => setSelected(index)}>
              <Mascot size={44} mood={item.mood} />
              <span>{item.label}</span>
              {selected === index && (
                <span
                  key={selected}
                  className={`buddy-mood-timer ${running ? "is-running" : ""}`}
                  aria-hidden="true"
                />
              )}
            </button>
          ))}
        </div>
        <div className="buddy-step-controls">
          <button
            aria-label="Biểu cảm trước"
            onClick={() => setSelected((selected - 1 + BUDDY_MOMENTS.length) % BUDDY_MOMENTS.length)}
          >
            ←
          </button>
          <span>
            0{selected + 1} / 0{BUDDY_MOMENTS.length}
          </span>
          <button
            aria-label="Biểu cảm tiếp theo"
            onClick={() => setSelected((selected + 1) % BUDDY_MOMENTS.length)}
          >
            →
          </button>
        </div>
        <div className="buddy-moment" aria-live={running ? "off" : "polite"} aria-atomic="true">
          <blockquote>“{moment.quote}”</blockquote>
          <p>{moment.text}</p>
        </div>
      </div>
    </section>
  );
}
