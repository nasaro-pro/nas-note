export type RecorderFormat = { mime: string; ext: string };

export type MicDevice = { deviceId: string; label: string };

export type PcmCapture = {
  pause: () => void;
  resume: () => void;
  stop: () => Promise<Blob>;
};

type AudioConstraint = MediaTrackConstraints & { voiceIsolation?: boolean };

export function isAppWebview(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent || "";
  return /Electron/i.test(ua) || /Cursor\//i.test(ua);
}

export function pickRecorderFormat(): RecorderFormat {
  const options: RecorderFormat[] = [
    { mime: "audio/webm;codecs=opus", ext: ".webm" },
    { mime: "audio/webm", ext: ".webm" },
    { mime: "audio/mp4", ext: ".m4a" },
    { mime: "audio/ogg;codecs=opus", ext: ".ogg" },
    { mime: "audio/ogg", ext: ".ogg" },
  ];
  if (typeof MediaRecorder === "undefined") {
    return { mime: "", ext: ".wav" };
  }
  return options.find((o) => MediaRecorder.isTypeSupported(o.mime)) ?? { mime: "", ext: ".wav" };
}

export function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function defaultRecordingTitle(at = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `녹음 ${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())} ${pad(at.getHours())}-${pad(at.getMinutes())}`;
}

export function recordingFileName(ext: string, at = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `recording-${at.getFullYear()}${pad(at.getMonth() + 1)}${pad(at.getDate())}-${pad(at.getHours())}${pad(at.getMinutes())}${pad(at.getSeconds())}${ext}`;
}

export function micErrorMessage(err: unknown): string {
  const name = err && typeof err === "object" && "name" in err ? String((err as { name: string }).name) : "";
  const msg = err instanceof Error ? err.message : "";
  if (name === "NotAllowedError" || name === "PermissionDeniedError") {
    return "브라우저가 마이크를 막았습니다. 주소창 왼쪽 자물쇠/마이크 아이콘에서 허용하세요.";
  }
  if (name === "NotFoundError" || name === "DevicesNotFoundError") {
    return "마이크를 찾지 못했습니다. Windows 소리 설정에서 입력 장치가 켜져 있는지 확인하세요.";
  }
  if (name === "NotReadableError" || name === "TrackStartError") {
    if (isAppWebview()) {
      return "Cursor 안 미리보기에서는 마이크가 열리지 않습니다. Chrome 또는 Edge를 켜고 주소창에 http://localhost:5173/ 을 입력하세요.";
    }
    return "마이크를 열지 못했습니다. Discord/Slack 통화와 음성 설정을 끄고, Windows 설정 → 개인 정보 보호 및 보안 → 마이크에서 데스크톱 앱 허용을 켠 뒤 다시 누르세요.";
  }
  if (name === "OverconstrainedError" || name === "ConstraintNotSatisfiedError") {
    return "이 마이크는 기본 설정으로 열 수 없습니다. 아래 장치를 바꿔 보거나 Windows 기본 입력을 바꾸세요.";
  }
  if (name === "SecurityError" || name === "NotSupportedError") {
    return "마이크는 http://localhost:5173/ 에서만 됩니다. 주소창을 그걸로 바꿔 여세요.";
  }
  if (name === "AbortError") {
    return "마이크 요청이 취소됐습니다. 다시 녹음 시작을 누르세요.";
  }
  if (msg) return `마이크를 열 수 없습니다. (${name || msg})`;
  return "마이크를 열 수 없습니다. Chrome/Edge에서 http://localhost:5173/ 으로 다시 시도하세요.";
}

function isVirtualMicId(id: string | undefined): boolean {
  return !id || id === "default" || id === "communications";
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

const RAW_AUDIO: AudioConstraint = {
  echoCancellation: false,
  noiseSuppression: false,
  autoGainControl: false,
  voiceIsolation: false,
};

export async function listMics(): Promise<MicDevice[]> {
  if (!navigator.mediaDevices?.enumerateDevices) return [];
  const devices = await navigator.mediaDevices.enumerateDevices();
  const all = devices
    .filter((d) => d.kind === "audioinput")
    .map((d, i) => ({
      deviceId: d.deviceId,
      label: d.label || `마이크 ${i + 1}`,
    }));
  const real = all.filter((d) => !isVirtualMicId(d.deviceId));
  return real.length ? real : all;
}

async function gum(constraints: MediaStreamConstraints): Promise<MediaStream> {
  const stream = await navigator.mediaDevices.getUserMedia(constraints);
  const track = stream.getAudioTracks()[0];
  if (!track || track.readyState === "ended") {
    stream.getTracks().forEach((t) => t.stop());
    throw new DOMException("Could not start audio source", "NotReadableError");
  }
  track.enabled = true;
  try {
    track.contentHint = "speech";
  } catch {
    /* older chrome */
  }
  return stream;
}

export async function openMicrophone(preferredId?: string): Promise<MediaStream> {
  if (typeof window !== "undefined" && !window.isSecureContext) {
    const err = new Error("insecure");
    err.name = "SecurityError";
    throw err;
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    const err = new Error("no mediaDevices");
    err.name = "NotSupportedError";
    throw err;
  }

  let mics: MicDevice[] = [];
  try {
    mics = await listMics();
  } catch {
    mics = [];
  }
  const hardwareId = isVirtualMicId(preferredId)
    ? mics.find((m) => !isVirtualMicId(m.deviceId))?.deviceId
    : preferredId;

  const attempts: MediaStreamConstraints[] = [
    { audio: RAW_AUDIO },
    { audio: true },
  ];
  if (hardwareId) {
    attempts.unshift({ audio: { ...RAW_AUDIO, deviceId: { ideal: hardwareId } } });
  }

  let last: unknown;
  for (const constraints of attempts) {
    try {
      return await gum(constraints);
    } catch (err) {
      last = err;
      await sleep(250);
    }
  }
  throw last ?? new DOMException("Could not start audio source", "NotReadableError");
}

function encodeWav(chunks: Float32Array[], sampleRate: number): Blob {
  let length = 0;
  for (const chunk of chunks) length += chunk.length;
  const pcm = new Int16Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    for (let i = 0; i < chunk.length; i++) {
      const sample = Math.max(-1, Math.min(1, chunk[i]));
      pcm[offset++] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    }
  }
  const bytes = pcm.byteLength;
  const buffer = new ArrayBuffer(44 + bytes);
  const view = new DataView(buffer);
  const write = (off: number, text: string) => {
    for (let i = 0; i < text.length; i++) view.setUint8(off + i, text.charCodeAt(i));
  };
  write(0, "RIFF");
  view.setUint32(4, 36 + bytes, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  write(36, "data");
  view.setUint32(40, bytes, true);
  new Uint8Array(buffer, 44).set(new Uint8Array(pcm.buffer));
  return new Blob([buffer], { type: "audio/wav" });
}

export async function startPcmCapture(stream: MediaStream): Promise<PcmCapture | null> {
  const AC =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AC) return null;
  const ctx = new AC();
  if (ctx.state === "suspended") {
    try {
      await ctx.resume();
    } catch {
      /* autoplay policy */
    }
  }
  const src = ctx.createMediaStreamSource(stream);
  const node = ctx.createScriptProcessor(4096, 1, 1);
  const chunks: Float32Array[] = [];
  let paused = false;
  node.onaudioprocess = (event) => {
    if (paused) return;
    chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
  };
  const mute = ctx.createGain();
  mute.gain.value = 0;
  src.connect(node);
  node.connect(mute);
  mute.connect(ctx.destination);
  return {
    pause() {
      paused = true;
    },
    resume() {
      paused = false;
    },
    async stop() {
      paused = true;
      try {
        node.disconnect();
        src.disconnect();
        mute.disconnect();
      } catch {
        /* already disconnected */
      }
      const rate = ctx.sampleRate;
      try {
        await ctx.close();
      } catch {
        /* already closed */
      }
      return encodeWav(chunks, rate);
    },
  };
}
