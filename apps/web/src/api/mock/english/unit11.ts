/**
 * Unit 11 "Family time" for the in-browser mock (ENG-7a): nodes, relations, misconceptions and a few
 * items, copied from docs/pedagogy/english-g5/unit-11-family-time (ENG-3, draft approved by default on
 * 12/11/2026). Copied, not loaded: the files there will be renamed when the English loader lands (ENG-3b).
 * Only practice items carry answers here, as the math mock does; the bundle is for trying the UI only.
 */
import type { KnowledgeRelation, NodeLayer } from "../../contract";

export const UNIT = { chapter_id: "eng-g5-u11-family-time", title: "Unit 11: Family time" } as const;

export interface UnitNode {
  node_id: string;
  name: string;
  layer: NodeLayer;
  order: number;
  /** The target pattern, said beside the Vietnamese name (ADR-060 §8). */
  pattern: string;
  home_tip: string;
  /** A sentence for the parent to try at home (ADR-060 §9.3). */
  example: string;
}

export const NODES: UnitNode[] = [
  {
    node_id: "ENG5-U11-VOCAB",
    name: "Cụm từ hoạt động kỳ nghỉ",
    layer: "BASIC",
    order: 0,
    pattern: "collect seashells, eat seafood, buy souvenirs…",
    home_tip:
      "Xem lại ảnh một chuyến đi của gia đình, chỉ vào từng ảnh và hỏi con bằng tiếng Việt: ở đây cả nhà làm gì? Con nói câu tiếng Anh.",
    example: "We took photos.",
  },
  {
    node_id: "ENG5-U11-PAST",
    name: "Dạng quá khứ của động từ",
    layer: "BASIC",
    order: 1,
    pattern: "walk → walked, swim → swam, buy → bought",
    home_tip:
      "Buổi tối, hỏi con bằng tiếng Việt “hôm nay con làm gì?” rồi cùng con nói câu tiếng Anh ở quá khứ.",
    example: "I walked to school.",
  },
  {
    node_id: "ENG5-U11-DIDYOU",
    name: "Hỏi và trả lời “Did you …?”",
    layer: "BASIC",
    order: 2,
    pattern: "Did you …? – Yes, I did. / No, I didn't.",
    home_tip:
      "Cuối tuần, hỏi con bằng tiếng Anh về một việc con vừa làm, để con trả lời “Yes, I did.” hoặc “No, I didn't.”",
    example: "Did you take photos?",
  },
  {
    node_id: "ENG5-U11-WHATDID",
    name: "Kể việc gia đình đã làm",
    layer: "BASIC",
    order: 3,
    pattern: "What did your family do in …? – We …",
    home_tip:
      "Khi cả nhà đi chơi về, hỏi con câu tiếng Anh dưới đây và giúp con trả lời bằng câu bắt đầu bằng “We …”.",
    example: "What did our family do there?",
  },
  {
    node_id: "ENG5-U11-STRESS",
    name: "Trọng âm trong câu hỏi Wh-",
    layer: "BASIC",
    order: 4,
    pattern: "'When did you 'go to 'London?",
    home_tip: "Cùng con vỗ tay theo câu dưới đây: vỗ ba cái đúng vào When, go, London.",
    example: "When did you go to London?",
  },
  {
    node_id: "ENG5-U11-TRIP",
    name: "Kể và hỏi đáp về chuyến đi của gia đình",
    layer: "IMPLEMENT",
    order: 5,
    pattern: "Last summer, my family went to … We …",
    home_tip:
      "Làm một trang nhật ký ảnh về chuyến đi gần nhất của cả nhà; dưới mỗi ảnh, cùng con viết một câu tiếng Anh.",
    example: "We swam in the sea.",
  },
];

export const RELATIONS: KnowledgeRelation[] = [
  { source: "ENG5-U11-VOCAB", target: "ENG5-U11-PAST", type: "PREREQUISITE" },
  { source: "ENG5-U11-PAST", target: "ENG5-U11-DIDYOU", type: "PREREQUISITE" },
  { source: "ENG5-U11-PAST", target: "ENG5-U11-WHATDID", type: "PREREQUISITE" },
  { source: "ENG5-U11-WHATDID", target: "ENG5-U11-STRESS", type: "PREREQUISITE" },
  { source: "ENG5-U11-DIDYOU", target: "ENG5-U11-WHATDID", type: "SIMILAR" },
  { source: "ENG5-U11-DIDYOU", target: "ENG5-U11-TRIP", type: "APPLICATION" },
  { source: "ENG5-U11-WHATDID", target: "ENG5-U11-TRIP", type: "APPLICATION" },
];

export interface UnitMisconception {
  id: string;
  node_id: string;
  name: string;
  severity: "CRITICAL" | "NORMAL";
  /** What the parent reads under "Con cần luyện thêm" (ADR-060 §9.3). */
  parent: string;
}

export const MISCONCEPTIONS: UnitMisconception[] = [
  {
    id: "ENG5-U11-M01",
    node_id: "ENG5-U11-DIDYOU",
    name: "Hỏi chuyện đã qua mà dùng do hoặc bỏ did",
    severity: "CRITICAL",
    parent: "Con hay hỏi chuyện hôm qua bằng “Do you …?”; câu hỏi về chuyện đã qua cần “Did”.",
  },
  {
    id: "ENG5-U11-M02",
    node_id: "ENG5-U11-DIDYOU",
    name: "Sau did vẫn đổi động từ sang quá khứ",
    severity: "CRITICAL",
    parent: "Con hay nói “Did you swam?”; sau “did” động từ giữ nguyên.",
  },
  {
    id: "ENG5-U11-M03",
    node_id: "ENG5-U11-DIDYOU",
    name: "Nhầm Yes, I did với Yes, I do (hoặc Yes, I will)",
    severity: "CRITICAL",
    parent: "Con hay đáp “Yes, I do.” khi bạn hỏi “Did you …?”; hỏi bằng did thì đáp bằng did.",
  },
  {
    id: "ENG5-U11-M04",
    node_id: "ENG5-U11-PAST",
    name: "Kể chuyện đã qua bằng động từ nguyên mẫu",
    severity: "CRITICAL",
    parent: "Con hay quên đổi động từ sang quá khứ khi kể chuyện đã qua.",
  },
  {
    id: "ENG5-U11-M05",
    node_id: "ENG5-U11-PAST",
    name: "Thêm -ed cho động từ có dạng quá khứ riêng",
    severity: "NORMAL",
    parent: "Con hay viết “buyed”, “taked”; các từ này có dạng riêng: bought, took.",
  },
  {
    id: "ENG5-U11-M06",
    node_id: "ENG5-U11-VOCAB",
    name: "Nhầm nghĩa giữa các cụm hoạt động",
    severity: "NORMAL",
    parent: "Con còn nhầm nghĩa vài cụm từ, ví dụ “collect seashells” và “buy souvenirs”.",
  },
  {
    id: "ENG5-U11-M07",
    node_id: "ENG5-U11-WHATDID",
    name: "Sau We dùng động từ nguyên mẫu",
    severity: "CRITICAL",
    parent: "Con hay quên đổi động từ sang quá khứ sau “We …”, ví dụ nói “We eat seafood.”",
  },
  {
    id: "ENG5-U11-M08",
    node_id: "ENG5-U11-WHATDID",
    name: "Câu hỏi Wh- về quá khứ thiếu did hoặc dùng do",
    severity: "NORMAL",
    parent: "Con hay quên “did” trong câu hỏi “What did your family do …?”.",
  },
  {
    id: "ENG5-U11-M09",
    node_id: "ENG5-U11-WHATDID",
    name: "Trả lời lệch câu hỏi Wh-",
    severity: "NORMAL",
    parent: "Con đôi khi trả lời nơi chốn khi bạn hỏi “What … do?” (làm gì).",
  },
  {
    id: "ENG5-U11-M10",
    node_id: "ENG5-U11-STRESS",
    name: "Nhấn vào từ chức năng",
    severity: "NORMAL",
    parent: "Con còn nhấn vào “did”, “to” thay vì từ để hỏi, động từ chính và tên nơi chốn.",
  },
  {
    id: "ENG5-U11-M11",
    node_id: "ENG5-U11-TRIP",
    name: "Kể chuyến đi lẫn động từ nguyên mẫu",
    severity: "CRITICAL",
    parent: "Khi kể cả chuyến đi, con còn lẫn động từ nguyên mẫu.",
  },
  {
    id: "ENG5-U11-M12",
    node_id: "ENG5-U11-TRIP",
    name: "Trả lời lệch câu hỏi khi kể chuyến đi",
    severity: "NORMAL",
    parent: "Con đôi khi kể việc làm khi bạn hỏi “When …?” (khi nào).",
  },
];

/** One step of the mock tutor on a node: the theory with its question, or an item. */
export type ScriptStep =
  | { kind: "THEORY"; step: 1; text: string; ask: string; accept: string[]; reply: string }
  | { kind: "EXAMPLE"; step: 3; text: string }
  | {
      kind: "ITEM";
      step: 2 | 4 | 5;
      item_id: string;
      stem: string;
      format: "choice" | "open";
      options?: { id: string; text: string }[];
      /** Accepted answers after normalization (DI-110 in short): lower case, no punctuation. */
      accept: string[];
      hints: string[];
      /** The model sentence the tutor reads at H7 (DI-108: after it, the item ends as WORKED). */
      model: string;
    };

/** The mock session walks the first two nodes the way the tutor will: steps 1 to 6 of ADR-059. */
export const SCRIPT: Record<string, ScriptStep[]> = {
  "ENG5-U11-DIDYOU": [
    {
      kind: "THEORY",
      step: 1,
      text: "Trong sách, bạn Mary hỏi Mai về Chủ nhật tuần trước: “Did you swim?” Mai trả lời: “Yes, I did. I swam with my mother.” Câu hỏi bắt đầu bằng Did để hỏi một việc đã qua, và sau Did, động từ swim giữ nguyên. Nếu không bơi, Mai sẽ nói: “No, I didn't.”",
      ask: "Bạn hỏi “Did you take photos?” và con đã chụp ảnh. Con trả lời ngắn là “Yes, I do.” hay “Yes, I did.”?",
      accept: ["yes i did", "i did", "did"],
      reply: "Đúng rồi! Bạn hỏi bằng did nên con đáp bằng did: Yes, I did.",
    },
    {
      kind: "ITEM",
      step: 2,
      item_id: "U11-DY-CC-01",
      stem: "A: Did you (walk / walked) on the beach last Sunday? B: Yes, I did. Con chọn từ đúng cho câu hỏi của A nhé?",
      format: "choice",
      options: [
        { id: "A", text: "walk" },
        { id: "B", text: "walked" },
      ],
      accept: ["a", "walk", "did you walk on the beach last sunday"],
      hints: [
        "Câu của A bắt đầu bằng Did. Did đã cho biết đây là chuyện đã qua chưa?",
        "Sau did, động từ giữ nguyên, không đổi sang quá khứ nữa.",
      ],
      model: "Did you walk on the beach last Sunday?",
    },
    {
      kind: "EXAMPLE",
      step: 3,
      text: "Cô làm mẫu nhé. Hỏi bạn đã đi dạo trên bãi biển chưa: “Did you walk on the beach?” Bạn có đi nên trả lời ngắn: “Yes, I did.” Rồi kể thêm bằng động từ quá khứ: “I walked on the beach with my family.”",
    },
    {
      kind: "ITEM",
      step: 4,
      item_id: "U11-DY-PR-01",
      stem: "Bạn hỏi: “Did you take photos?” Câu trả lời nào đúng?",
      format: "choice",
      options: [
        { id: "A", text: "Yes, I did. I took photos with my mother." },
        { id: "B", text: "Yes, I will." },
        { id: "C", text: "Yes, I do." },
      ],
      accept: ["a", "yes i did i took photos with my mother", "yes i did"],
      hints: [
        "Bạn hỏi bằng chữ nào ở đầu câu: Do, Did hay Will?",
        "Câu hỏi bắt đầu bằng Did thì câu trả lời ngắn cũng dùng did: Yes, I did. hoặc No, I didn't.",
      ],
      model: "Yes, I did. I took photos with my mother.",
    },
    {
      kind: "ITEM",
      step: 5,
      item_id: "U11-DY-PR-02",
      stem: "Trong tranh, bạn của con đang nhặt vỏ sò trên bãi biển cùng anh trai. Con hỏi bạn xem bạn đã nhặt vỏ sò chưa, bằng câu bắt đầu bằng “Did you …?” nhé.",
      format: "open",
      accept: ["did you collect seashells", "did you collect seashells with your brother"],
      hints: [
        "Nhặt vỏ sò tiếng Anh là cụm nào, con còn nhớ không?",
        "Câu hỏi về việc đã làm: Did you + động từ giữ nguyên? Nhặt vỏ sò là collect seashells.",
        "Con nói tiếp nhé: Did you collect s…?",
      ],
      model: "Did you collect seashells?",
    },
  ],
  "ENG5-U11-WHATDID": [
    {
      kind: "THEORY",
      step: 1,
      text: "Hai bạn trong sách xem ảnh gia đình. Một bạn hỏi: “What did your family do in Ha Long?” Bạn kia trả lời: “We took a boat trip around the bay.” Câu trả lời bắt đầu bằng We, và động từ took ở dạng quá khứ vì chuyến đi đã qua.",
      ask: "Bạn hỏi “What did your family do in Nha Trang?” và cả nhà con đã ăn hải sản. Con trả lời bằng câu bắt đầu bằng We thế nào?",
      accept: ["we ate seafood", "ate seafood"],
      reply: "Giỏi quá! Cả nhà đã ăn hải sản nên con nói: We ate seafood.",
    },
    {
      kind: "ITEM",
      step: 2,
      item_id: "U11-WD-PR-01",
      stem: "Trong tranh, cả nhà đang ăn tôm, cua, cá ở Nha Trang. Bạn hỏi: “What did your family do in Nha Trang?” Con trả lời bằng câu bắt đầu bằng We nhé.",
      format: "open",
      accept: ["we ate seafood", "we ate some seafood"],
      hints: [
        "Trong tranh cả nhà đang làm gì? Ăn hải sản tiếng Anh là cụm nào?",
        "Câu trả lời kể chuyện đã qua: We + động từ quá khứ. Eat có dạng quá khứ riêng là ate.",
        "Con nói tiếp nhé: We ate s…",
      ],
      model: "We ate seafood.",
    },
  ],
};

/** The node the mock session starts on, and the one after it. */
export const SESSION_NODES = ["ENG5-U11-DIDYOU", "ENG5-U11-WHATDID"] as const;
