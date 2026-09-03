import { useEffect, useRef, useState } from "react";
import { Circle, Pause, Play, RotateCcw, Square } from "lucide-react";
import { api } from "../api";
import {
  defaultRecordingTitle,
  formatElapsed,
  isAppWebview,
  listMics,
  micErrorMessage,
  openMicrophone,
  pickRecorderFormat,
  recordingFileName,
  startPcmCapture,
  type MicDevice,
  type PcmCapture,
} from "../lib/recorder";

type Phase = "idle" | "recording" | "paused" | "ready";

function makeRecorder(stream: MediaStream, mime: string): MediaRecorder | null {
  if (typeof MediaRecorder === "undefined") return null;
  if (mime) {
    try {
      return new MediaRecorder(stream, { mimeType: mime });
    } catch {
      /* fall through */
    }
  }
  try {
    return new MediaRecorder(stream);
  } catch {
    return null;
  }
}

export function Recorder({
  onReady,
  onClear,
}: {
  onReady: (file: File, title: string) => void;
  onClear: () => void;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");
  const [previewUrl, setPreviewUrl] = useState("");
  const [mics, setMics] = useState<MicDevice[]>([]);
  const [deviceId, setDeviceId] = useState("");
  const [busy, setBusy] = useState(false);
  const [sysMode, setSysMode] = useState(false);
  const recRef = useRef<MediaRecorder | null>(null);
  const pcmRef = useRef<PcmCapture | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef(0);
  const elapsedRef = useRef(0);
  const tickRef = useRef(0);
  const ignoreStopRef = useRef(false);
  const finishingRef = useRef(false);
  const sysRef = useRef(false);
  const formatRef = useRef(pickRecorderFormat());
  const previewRef = useRef("");
  const onReadyRef = useRef(onReady);
  const onClearRef = useRef(onClear);
  onReadyRef.current = onReady;
  onClearRef.current = onClear;

  function stopTracks() {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }

  function clearTick() {
    if (tickRef.current) window.clearInterval(tickRef.current);
    tickRef.current = 0;
  }

  useEffect(() => {
    void listMics()
      .then((list) => {
        setMics(list);
        setDeviceId((prev) => {
          if (prev) return prev;
          const real = list.find((m) => m.deviceId && m.deviceId !== "default" && m.deviceId !== "communications");
          return real?.deviceId || list[0]?.deviceId || "";
        });
      })
      .catch(() => {
        /* labels appear after the first mic prompt */
      });
    return () => {
      ignoreStopRef.current = true;
      clearTick();
      try {
        if (recRef.current && recRef.current.state !== "inactive") recRef.current.stop();
      } catch {
        /* already stopped */
      }
      void pcmRef.current?.stop();
      pcmRef.current = null;
      if (sysRef.current) {
        sysRef.current = false;
        void api.recordStop().catch(() => undefined);
      }
      stopTracks();
      if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    };
  }, []);

  function startTick() {
    clearTick();
    tickRef.current = window.setInterval(() => {
      setElapsed(elapsedRef.current + (Date.now() - startedAtRef.current));
    }, 200);
  }

  function publishFile(blob: Blob, mime: string, ext: string) {
    const title = defaultRecordingTitle();
    const file = new File([blob], recordingFileName(ext), { type: mime });
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    const url = URL.createObjectURL(blob);
    previewRef.current = url;
    setPreviewUrl(url);
    setPhase("ready");
    onReadyRef.current(file, title);
  }

  async function finishCapture(rec: MediaRecorder | null) {
    if (finishingRef.current) return;
    finishingRef.current = true;
    stopTracks();
    clearTick();
    const pcm = pcmRef.current;
    pcmRef.current = null;
    let wav: Blob | null = null;
    if (pcm) {
      try {
        wav = await pcm.stop();
      } catch {
        wav = null;
      }
    }
    if (ignoreStopRef.current) {
      finishingRef.current = false;
      return;
    }
    const mime = (rec?.mimeType || formatRef.current.mime || "audio/webm").split(";")[0];
    const recorded = new Blob(chunksRef.current, { type: mime || "audio/webm" });
    if (recorded.size >= 256) {
      const ext = mime.includes("mp4") ? ".m4a" : mime.includes("ogg") ? ".ogg" : formatRef.current.ext || ".webm";
      publishFile(recorded, mime || "audio/webm", ext);
      finishingRef.current = false;
      return;
    }
    if (wav && wav.size >= 256) {
      publishFile(wav, "audio/wav", ".wav");
      finishingRef.current = false;
      return;
    }
    setError("녹음 데이터가 비었습니다. 마이크가 음소거인지 확인한 뒤 조금 더 말하고 끝내세요.");
    setPhase("idle");
    onClearRef.current();
    finishingRef.current = false;
  }

  async function start() {
    setError("");
    ignoreStopRef.current = false;
    finishingRef.current = false;
    if (typeof window !== "undefined" && !window.isSecureContext) {
      setError("마이크는 http://localhost:5173/ 주소에서만 됩니다. 주소창을 그걸로 바꾸세요.");
      return;
    }
    setBusy(true);
    formatRef.current = pickRecorderFormat();
    sysRef.current = false;
    setSysMode(false);

    let stream: MediaStream | null = null;
    try {
      stream = await openMicrophone(deviceId || undefined);
    } catch {
      stream = null;
    }
    if (!stream) {
      try {
        await api.recordStart();
        sysRef.current = true;
        setSysMode(true);
        elapsedRef.current = 0;
        startedAtRef.current = Date.now();
        setElapsed(0);
        setPhase("recording");
        setBusy(false);
        startTick();
        return;
      } catch (sysErr) {
        stopTracks();
        setError(sysErr instanceof Error ? sysErr.message : micErrorMessage(sysErr));
        setBusy(false);
        return;
      }
    }
    streamRef.current = stream;
    chunksRef.current = [];
    try {
      const listed = await listMics();
      setMics(listed);
    } catch {
      /* ignore */
    }
    pcmRef.current = await startPcmCapture(stream);
    const rec = makeRecorder(stream, formatRef.current.mime);
    recRef.current = rec;
    if (rec) {
      rec.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onerror = () => {
        setError("녹음 엔진이 멈췄습니다. 다시 녹음 시작을 누르세요.");
        setPhase("idle");
        void pcmRef.current?.stop();
        pcmRef.current = null;
        stopTracks();
      };
      rec.onstop = () => {
        void finishCapture(rec);
      };
    }
    elapsedRef.current = 0;
    startedAtRef.current = Date.now();
    setElapsed(0);
    let started = false;
    if (rec) {
      try {
        rec.start(1000);
        started = true;
      } catch {
        try {
          rec.start();
          started = true;
        } catch {
          started = false;
        }
      }
    }
    if (!started && !pcmRef.current) {
      stopTracks();
      setError("이 브라우저는 녹음을 지원하지 않습니다. Chrome 또는 Edge를 쓰세요.");
      setBusy(false);
      return;
    }
    setPhase("recording");
    setBusy(false);
    startTick();
  }

  function pause() {
    if (sysRef.current) return;
    const rec = recRef.current;
    if (rec && rec.state === "recording") {
      try {
        rec.pause();
      } catch {
        return;
      }
    } else if (!pcmRef.current) {
      return;
    }
    pcmRef.current?.pause();
    elapsedRef.current += Date.now() - startedAtRef.current;
    clearTick();
    setElapsed(elapsedRef.current);
    setPhase("paused");
  }

  function resume() {
    const rec = recRef.current;
    if (rec && rec.state === "paused") {
      try {
        rec.resume();
      } catch {
        return;
      }
    } else if (!pcmRef.current) {
      return;
    }
    pcmRef.current?.resume();
    startedAtRef.current = Date.now();
    setPhase("recording");
    startTick();
  }

  function stop() {
    if (sysRef.current) {
      if (finishingRef.current) return;
      finishingRef.current = true;
      clearTick();
      void (async () => {
        try {
          const blob = await api.recordStop();
          sysRef.current = false;
          setSysMode(false);
          if (ignoreStopRef.current) {
            finishingRef.current = false;
            return;
          }
          if (blob.size < 256) {
            setError("녹음 데이터가 비었습니다. 조금 더 말한 뒤 끝내세요.");
            setPhase("idle");
            onClearRef.current();
            finishingRef.current = false;
            return;
          }
          publishFile(blob, "audio/wav", ".wav");
        } catch (err) {
          sysRef.current = false;
          setSysMode(false);
          setError(err instanceof Error ? err.message : "시스템 녹음을 저장하지 못했습니다.");
          setPhase("idle");
          onClearRef.current();
        }
        finishingRef.current = false;
      })();
      return;
    }
    const rec = recRef.current;
    if (rec && rec.state !== "inactive") {
      try {
        rec.requestData();
      } catch {
        /* some browsers have no requestData */
      }
      rec.stop();
      return;
    }
    void finishCapture(null);
  }

  function reset() {
    ignoreStopRef.current = true;
    const rec = recRef.current;
    if (rec && rec.state !== "inactive") {
      try {
        rec.stop();
      } catch {
        /* ignore */
      }
    }
    void pcmRef.current?.stop();
    pcmRef.current = null;
    if (sysRef.current) {
      sysRef.current = false;
      setSysMode(false);
      void api.recordStop().catch(() => undefined);
    }
    stopTracks();
    clearTick();
    chunksRef.current = [];
    recRef.current = null;
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    previewRef.current = "";
    setPreviewUrl("");
    setElapsed(0);
    elapsedRef.current = 0;
    setPhase("idle");
    setError("");
    finishingRef.current = false;
    ignoreStopRef.current = false;
    onClearRef.current();
  }

  const embedded = isAppWebview();

  return (
    <div className="rec-panel">
      {embedded ? (
        <p className="banner warn rec-embed" role="status">
          Cursor 안 창에서는 마이크가 안 열립니다. Chrome 또는 Edge에서{" "}
          <a href="http://localhost:5173/upload?mode=record">http://localhost:5173/</a>
          을 여세요.
        </p>
      ) : null}
      {error ? (
        <p className="err" role="alert">
          {error}
        </p>
      ) : null}
      {phase === "idle" && mics.length > 1 ? (
        <label className="rec-device">
          마이크
          <select value={deviceId} onChange={(e) => setDeviceId(e.target.value)}>
            {mics.map((mic) => (
              <option key={mic.deviceId || mic.label} value={mic.deviceId}>
                {mic.label}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      <div className="rec-time" aria-live="polite">
        {phase === "recording" ? <span className="rec-dot" /> : null}
        {formatElapsed(elapsed)}
      </div>
      <p className="caption rec-hint">
        {phase === "idle"
          ? embedded
            ? "이 미리보기가 아니라 Chrome/Edge의 localhost:5173 에서 녹음하세요."
            : "녹음 시작을 누른 뒤 말하면 됩니다."
          : phase === "recording"
            ? sysMode
              ? "시스템 녹음 중입니다. 말하고 이 창을 닫지 마세요."
              : "말하고 있는 동안 이 창을 닫지 마세요."
            : phase === "paused"
              ? "일시정지됨. 이어서 녹음하거나 끝내고 정리하세요."
              : "미리 듣고, 제목을 확인한 뒤 정리 시작을 누르세요."}
      </p>
      {previewUrl ? <audio className="rec-audio" src={previewUrl} controls /> : null}
      <div className="rec-actions">
        {phase === "idle" ? (
          <button className="btn btn-primary" type="button" disabled={busy} onClick={() => void start()}>
            <Circle size={16} fill="currentColor" />
            {busy ? "마이크 여는 중" : "녹음 시작"}
          </button>
        ) : null}
        {phase === "recording" ? (
          <>
            {sysMode ? null : (
              <button className="btn btn-secondary" type="button" onClick={pause}>
                <Pause size={16} />
                일시정지
              </button>
            )}
            <button className="btn btn-primary" type="button" onClick={stop}>
              <Square size={16} />
              녹음 끝내기
            </button>
          </>
        ) : null}
        {phase === "paused" ? (
          <>
            <button className="btn btn-secondary" type="button" onClick={resume}>
              <Play size={16} />
              이어서 녹음
            </button>
            <button className="btn btn-primary" type="button" onClick={stop}>
              <Square size={16} />
              녹음 끝내기
            </button>
          </>
        ) : null}
        {phase === "ready" ? (
          <button className="btn btn-ghost" type="button" onClick={reset}>
            <RotateCcw size={16} />
            다시 녹음
          </button>
        ) : null}
      </div>
    </div>
  );
}
