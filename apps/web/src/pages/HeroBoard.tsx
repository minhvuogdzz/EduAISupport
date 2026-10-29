import { useState } from "react";
import { Mascot } from "../components/Mascot";

/** A single coordinate system keeps the pen in Buddy's hand and its tip on the written underline. */
export function HeroBoard() {
  const [replay, setReplay] = useState(0);
  return (
    <div className="hero-illustration hero-enter writing-illustration">
      <p className="writing-caption">một chút tò mò, thật nhiều khám phá</p>
      <svg
        key={replay}
        className="writing-board"
        viewBox="0 0 600 500"
        role="img"
        aria-label="Monkey Buddy cầm bút viết ba phần mười bằng 0,3 lên bảng"
      >
        <rect x="32" y="53" width="510" height="350" rx="5" fill="#dce9ed" />
        <rect
          x="23"
          y="43"
          width="510"
          height="350"
          rx="5"
          fill="#f0f8fa"
          stroke="#bdd4dd"
          strokeWidth="1.5"
        />
        <text x="60" y="86" className="board-label">
          GÓC THỬ NGHĨ
        </text>
        <text x="491" y="86" textAnchor="end" className="board-label">
          01 / Số thập phân
        </text>
        <path d="M60 104H495" stroke="#bdd4dd" />
        <text x="60" y="151" className="board-question">
          Nếu một chiếc bánh
        </text>
        <text x="60" y="185" className="board-question">
          được chia thành 10 phần…
        </text>
        {Array.from({ length: 10 }, (_, i) => (
          <rect
            key={i}
            className={i < 3 ? "board-fraction-fill" : ""}
            x={60 + i * 40}
            y="213"
            width="34"
            height="42"
            rx="9"
            fill={i < 3 ? "#a56876" : "none"}
            stroke={i < 3 ? "#863b4f" : "#809da9"}
            strokeWidth="1.5"
            style={{ animationDelay: `${i * 120}ms` }}
          />
        ))}
        <g fill="#863b4f" fontFamily="Georgia, serif" textAnchor="middle">
          <text x="100" y="302" fontSize="31">
            3
          </text>
          <path d="M82 309h36" stroke="#863b4f" strokeWidth="1.5" />
          <text x="100" y="341" fontSize="31">
            10
          </text>
          <text x="166" y="324" fontSize="43">
            =
          </text>
        </g>
        <g fill="none" stroke="#863b4f" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
          <path
            className="board-ink ink-zero"
            pathLength="1"
            d="M247 281c-23-5-24 41-9 43 23 4 24-41 9-43Z"
          />
          <path className="board-ink ink-comma" pathLength="1" d="M274 319q2 7-5 14" />
          <path
            className="board-ink ink-three"
            pathLength="1"
            d="M291 285q29-14 22 7-3 8-17 9 29-7 18 16-7 11-25 5"
          />
          <path
            className="board-ink ink-underline"
            pathLength="1"
            d="M231 343q60-23 125-25"
            stroke="#a56876"
            strokeWidth="2"
          />
        </g>
        <g transform="translate(355 240)">
          <Mascot size={220} mood="happy" activity="writing" animated />
        </g>
        <text x="53" y="445" className="board-note">
          Một câu hỏi nhỏ.
        </text>
        <text x="53" y="473" className="board-note">
          Một điều mới hiểu ra.
        </text>
      </svg>
      <button className="writing-replay" onClick={() => setReplay(replay + 1)}>
        Xem Buddy viết lại <span aria-hidden="true">↻</span>
      </button>
    </div>
  );
}
