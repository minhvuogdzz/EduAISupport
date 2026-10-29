import { useCallback, useEffect, useRef, useState } from "react";

import { useApi } from "../../../api/apiContext";
import type { ChatTurn, Modality, VoiceStatus } from "../../../api/contract";
import { browserListen, browserSpeak, canBrowserListen, canBrowserSpeak } from "./browserVoice";
import { canRecord, closeMic, openMic, recordTurn, waitForVoice } from "./recorder";

export type VoicePhase = "off" | "speaking" | "listening" | "hearing" | "waiting";

export interface VoiceLive {
  /** The browser can do voice at all (an ear and a voice, from the server or its own). */
  available: boolean;
  on: boolean;
  phase: VoicePhase;
  /** What the tutor heard last (or is hearing, with the browser's ear). */
  heard: string;
  level: number;
  problem: string | null;
  toggle: () => void;
  /** Listen now (the child taps the microphone, also over the tutor), or stop listening. */
  listenNow: () => void;
  /** The child can talk over the tutor (VOICE-2): the microphone was allowed once already. */
  bargeIn: boolean;
}

interface Options {
  turns: ChatTurn[];
  /** The child may speak: the session waits for words and nothing is being sent. */
  canSpeak: boolean;
  submit: (text: string, modality: Modality) => Promise<boolean>;
}

const NOT_HEARD = "Cô chưa nghe rõ, con nói lại nhé.";
const LISTEN_AFTER_MS = 300;
const SENTENCE_CHARS = 160;

/** The tutor's message in sentences, short ones joined up to ``SENTENCE_CHARS``. */
export function sentences(text: string): string[] {
  const pieces = text
    .split(/(?<=[.!?…])\s+|\n+/)
    .map((p) => p.trim())
    .filter(Boolean);
  const out: string[] = [];
  for (const piece of pieces) {
    const last = out.at(-1);
    if (last !== undefined && last.length + piece.length + 1 <= SENTENCE_CHARS)
      out[out.length - 1] = `${last} ${piece}`;
    else out.push(piece);
  }
  return out.length ? out : [text];
}

/**
 * Voice live (ADR-030): the tutor reads each new message aloud, then listens to the child, who answers by
 * speaking; the words go through the same command as typing (modality VOICE). Typing keeps working. The
 * server's ear (Groq Whisper) and voice (VieNeu-TTS) first, the browser's own when the server has none.
 */
export function useVoiceLive({ turns, canSpeak, submit }: Options): VoiceLive {
  const api = useApi();
  const [status, setStatus] = useState<VoiceStatus | null>(null);
  const [on, setOn] = useState(false);
  const [phase, setPhase] = useState<VoicePhase>("off");
  const [heard, setHeard] = useState("");
  const [level, setLevel] = useState(0);
  const [problem, setProblem] = useState<string | null>(null);
  const spoken = useRef(new Set<string>());
  const busy = useRef(false);
  const abort = useRef<AbortController | null>(null);
  const audioEl = useRef<HTMLAudioElement | null>(null);
  const micAllowed = useRef(false); // VOICE-2: barge-in only once the child allowed the microphone
  const mayAnswer = useRef(canSpeak);
  const [bargeIn, setBargeIn] = useState(false);
  useEffect(() => {
    mayAnswer.current = canSpeak;
  }, [canSpeak]);

  useEffect(() => {
    if (!api.voice) return;
    let alive = true;
    api.voice
      .status()
      .then((s) => alive && setStatus(s))
      .catch(() => alive && setStatus({ listen: false, speak: false, speech_model: null }));
    return () => {
      alive = false;
    };
  }, [api]);

  const serverEar = Boolean(status?.listen && api.voice && canRecord());
  const serverVoice = Boolean(status?.speak && api.voice);
  const available = (serverEar || canBrowserListen()) && (serverVoice || canBrowserSpeak());

  const play = useCallback((blob: Blob, signal: AbortSignal) => {
    const url = URL.createObjectURL(blob);
    return new Promise<void>((resolve) => {
      const el = audioEl.current ?? new Audio();
      audioEl.current = el;
      const done = () => {
        URL.revokeObjectURL(url);
        resolve();
      };
      el.src = url;
      el.onended = done;
      el.onerror = done;
      signal.addEventListener("abort", () => (el.pause(), done()), { once: true });
      void el.play().catch(done);
    });
  }, []);

  const speak = useCallback(
    async (text: string, signal: AbortSignal) => {
      if (serverVoice && api.voice) {
        // Sentence by sentence: the next one is made while this one plays, so the child hears the tutor
        // after one short sentence, not after the whole explanation (VieNeu on a CPU: about real time).
        const parts = sentences(text);
        const voiceApi = api.voice;
        let next: Promise<Blob> | null = voiceApi.speech(parts[0]);
        try {
          for (let i = 0; i < parts.length && next; i++) {
            const blob = await next;
            next = i + 1 < parts.length ? voiceApi.speech(parts[i + 1]) : null;
            next?.catch(() => undefined);
            if (signal.aborted) return;
            await play(blob, signal);
          }
          return;
        } catch {
          // the tutor's voice is not running: the browser reads instead
        }
      }
      await browserSpeak(text, signal);
    },
    [api, serverVoice, play],
  );

  const listen = useCallback(
    async (signal: AbortSignal, stream?: MediaStream): Promise<string> => {
      if (serverEar && api.voice) {
        setPhase("listening");
        const blob = await recordTurn(signal, setLevel, { stream });
        micAllowed.current = true;
        setBargeIn(true);
        setLevel(0);
        if (!blob || signal.aborted) return "";
        setPhase("hearing");
        try {
          return (await api.voice.transcribe(blob)).text.trim();
        } catch {
          if (!canBrowserListen()) throw new Error("no ear");
        }
      }
      if (stream) closeMic(stream);
      setPhase("listening");
      const words = await browserListen(setHeard, signal);
      micAllowed.current = true;
      setBargeIn(true);
      return words;
    },
    [api, serverEar],
  );

  const stop = useCallback(() => {
    abort.current?.abort();
    abort.current = null;
    busy.current = false;
    setLevel(0);
  }, []);

  const listenOnce = useCallback(
    async (stream?: MediaStream) => {
      if (busy.current) {
        if (stream) closeMic(stream);
        return;
      }
      busy.current = true;
      const controller = new AbortController();
      abort.current = controller;
      setProblem(null);
      try {
        const words = await listen(controller.signal, stream);
        if (controller.signal.aborted) return;
        if (!words) {
          setHeard("");
          setPhase("waiting");
          setProblem(NOT_HEARD);
          return;
        }
        setHeard(words);
        setPhase("waiting");
        await submit(words, "VOICE");
      } catch (error) {
        setProblem(
          error instanceof DOMException && error.name === "NotAllowedError"
            ? "Con cho phép dùng micro để nói chuyện với cô nhé."
            : "Cô chưa nghe được. Con gõ câu trả lời hoặc bấm micro thử lại nhé.",
        );
        setPhase("waiting");
      } finally {
        if (abort.current === controller) abort.current = null;
        busy.current = false;
      }
    },
    [listen, submit],
  );

  // The live loop: new tutor messages are read aloud, then the tutor listens if the child may answer.
  useEffect(() => {
    if (!on || busy.current) return;
    const fresh = turns.filter((t) => t.actor === "tutor" && !spoken.current.has(t.turn_id) && t.text);
    if (fresh.length) {
      fresh.forEach((t) => spoken.current.add(t.turn_id));
      busy.current = true;
      const controller = new AbortController();
      abort.current = controller;
      setProblem(null);
      setPhase("speaking");
      void (async () => {
        // VOICE-2: while the tutor speaks, the child may talk over it; the tutor stops and listens.
        let barged: MediaStream | null = null;
        const watching = new AbortController();
        if (micAllowed.current && mayAnswer.current) {
          void (async () => {
            try {
              const stream = await openMic();
              if (watching.signal.aborted) return closeMic(stream);
              if (await waitForVoice(stream, watching.signal)) {
                barged = stream;
                controller.abort();
              } else closeMic(stream);
            } catch {
              // no microphone now: the tutor just reads on
            }
          })();
        }
        for (const t of fresh) {
          if (controller.signal.aborted) break;
          await speak(t.text, controller.signal);
        }
        watching.abort();
        if (abort.current === controller) abort.current = null;
        busy.current = false;
        if (barged) {
          setPhase("waiting");
          void listenOnce(barged);
        } else if (!controller.signal.aborted) setPhase("waiting");
      })();
      return;
    }
    if (!(canSpeak && phase === "waiting" && !problem)) return;
    // A short breath after the tutor stops, before the microphone opens.
    const timer = window.setTimeout(() => void listenOnce(), LISTEN_AFTER_MS);
    return () => window.clearTimeout(timer);
  }, [on, turns, canSpeak, phase, problem, speak, listenOnce]);

  useEffect(() => stop, [stop]);

  function toggle() {
    if (on) {
      stop();
      setOn(false);
      setPhase("off");
      return;
    }
    // Start with the tutor's last message, so the child hears where they are; older ones stay silent.
    const tutorTurns = turns.filter((t) => t.actor === "tutor");
    tutorTurns.slice(0, -1).forEach((t) => spoken.current.add(t.turn_id));
    setProblem(null);
    setHeard("");
    setOn(true);
    setPhase("waiting");
  }

  function listenNow() {
    if (phase === "listening") {
      stop();
      setPhase("waiting");
      setProblem("Cô dừng rồi. Con bấm micro khi muốn nói nhé.");
      return;
    }
    if (phase === "speaking") stop(); // VOICE-2: the tap talks over the tutor, who stops and listens
    setProblem(null);
    void listenOnce();
  }

  return { available, on, phase, heard, level, problem, toggle, listenNow, bargeIn };
}
