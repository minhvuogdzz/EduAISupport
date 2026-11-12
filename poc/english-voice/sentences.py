"""ENG-POC-voice: the sentences the tutor (and a child) would say in the Grade 5 unit "My family".

Each item: id, kind, the full text, the English target the learner must hear/say, and for mixed
sentences the Vietnamese and English parts in speaking order (used to build the "hybrid" reference
audio: Vietnamese by VieNeu, English by a standard English system voice).

Kinds:
  word    a single target word, as the teacher models it
  pattern a full English sentence pattern
  teacher a Vietnamese teacher sentence carrying an English target
  child   a mixed sentence as a child would answer ("con nghĩ là mother")
"""

from __future__ import annotations

# (id, kind, text, english_target, parts)  parts: list of (lang, text) in order; None = single language
SENTENCES: list[tuple[str, str, str, str, list[tuple[str, str]] | None]] = [
    ("w1", "word", "Mother.", "mother", None),
    ("w2", "word", "Father.", "father", None),
    ("w3", "word", "Sister.", "sister", None),
    ("w4", "word", "Brother.", "brother", None),
    ("w5", "word", "Grandmother.", "grandmother", None),
    ("w6", "word", "Grandfather.", "grandfather", None),
    ("p1", "pattern", "This is my mother.", "this is my mother", None),
    ("p2", "pattern", "She is my sister.", "she is my sister", None),
    ("p3", "pattern", "He is my brother.", "he is my brother", None),
    ("p4", "pattern", "Who is this?", "who is this", None),
    (
        "p5",
        "pattern",
        "How many people are there in your family?",
        "how many people are there in your family",
        None,
    ),
    ("p6", "pattern", "There are four people in my family.", "there are four people in my family", None),
    (
        "t1",
        "teacher",
        "Con nói theo cô nhé: This is my father.",
        "this is my father",
        [("vi", "Con nói theo cô nhé:"), ("en", "This is my father.")],
    ),
    (
        "t2",
        "teacher",
        "Từ mother nghĩa là mẹ.",
        "mother",
        [("vi", "Từ"), ("en", "mother"), ("vi", "nghĩa là mẹ.")],
    ),
    (
        "t3",
        "teacher",
        "Từ grandfather nghĩa là ông.",
        "grandfather",
        [("vi", "Từ"), ("en", "grandfather"), ("vi", "nghĩa là ông.")],
    ),
    (
        "t4",
        "teacher",
        "Cô hỏi nhé: Who is this?",
        "who is this",
        [("vi", "Cô hỏi nhé:"), ("en", "Who is this?")],
    ),
    (
        "t5",
        "teacher",
        "Giỏi lắm! Con đọc lại nhé: She is my sister.",
        "she is my sister",
        [("vi", "Giỏi lắm! Con đọc lại nhé:"), ("en", "She is my sister.")],
    ),
    (
        "s1",
        "child",
        "Con nghĩ là mother.",
        "mother",
        [("vi", "Con nghĩ là"), ("en", "mother.")],
    ),
    (
        "s2",
        "child",
        "Dạ, this is my grandmother.",
        "this is my grandmother",
        [("vi", "Dạ,"), ("en", "this is my grandmother.")],
    ),
    (
        "s3",
        "child",
        "Brother là anh trai ạ.",
        "brother",
        [("en", "Brother"), ("vi", "là anh trai ạ.")],
    ),
]
