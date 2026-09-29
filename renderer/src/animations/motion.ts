import { Easing, interpolate, spring } from "remotion";
import { Anim, Vec } from "./types";

export function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

export function easingProgress(name: string | null | undefined, t: number, frame: number, fps: number, durationInFrames: number): number {
  const progress = clamp01(t);
  if (name === "spring") {
    return spring({ frame, fps, durationInFrames: Math.max(1, durationInFrames), config: { damping: 14, mass: 0.6 } });
  }
  const curve =
    name === "linear"
      ? Easing.linear
      : name === "ease_in"
        ? Easing.in(Easing.quad)
        : name === "ease_in_out"
          ? Easing.inOut(Easing.quad)
          : Easing.out(Easing.quad);
  return interpolate(progress, [0, 1], [0, 1], { easing: curve, extrapolateLeft: "clamp", extrapolateRight: "clamp" });
}

export function sampleNumber(anim: Anim, time: number, duration: number, easing: string, frame: number, fps: number): number {
  if (anim.mode === "static") {
    return typeof anim.value === "number" ? anim.value : 1;
  }
  if (anim.mode === "from_to") {
    const from = typeof anim.from === "number" ? anim.from : 0;
    const to = typeof anim.to === "number" ? anim.to : 1;
    const t = easingProgress(easing, duration === 0 ? 1 : time / duration, frame, fps, Math.round(duration * fps));
    return from + (to - from) * t;
  }
  const frames = anim.keyframes.filter((item) => typeof item.value === "number") as { time: number; value: number }[];
  return sampleSeries(frames, time, easing, frame, fps);
}

export function sampleVec(anim: Anim, time: number, duration: number, easing: string, frame: number, fps: number, fallback: Vec): Vec {
  if (anim.mode === "static") {
    return isVec(anim.value) ? anim.value : fallback;
  }
  if (anim.mode === "from_to") {
    const from = isVec(anim.from) ? anim.from : fallback;
    const to = isVec(anim.to) ? anim.to : fallback;
    const t = easingProgress(easing, duration === 0 ? 1 : time / duration, frame, fps, Math.round(duration * fps));
    return { x: from.x + (to.x - from.x) * t, y: from.y + (to.y - from.y) * t };
  }
  const frames = anim.keyframes.filter((item) => isVec(item.value)) as { time: number; value: Vec }[];
  if (frames.length === 0) {
    return fallback;
  }
  const x = sampleSeries(frames.map((item) => ({ time: item.time, value: item.value.x })), time, easing, frame, fps);
  const y = sampleSeries(frames.map((item) => ({ time: item.time, value: item.value.y })), time, easing, frame, fps);
  return { x, y };
}

function fullProgress(localTime: number, duration: number, frame: number, fps: number): number {
  return easingProgress("linear", duration === 0 ? 1 : localTime / duration, frame, fps, Math.round(duration * fps));
}

function sampleSeries(frames: { time: number; value: number }[], time: number, easing: string, frame: number, fps: number): number {
  if (frames.length === 0) {
    return 0;
  }
  if (time <= frames[0].time) {
    return frames[0].value;
  }
  const last = frames[frames.length - 1];
  if (time >= last.time) {
    return last.value;
  }
  for (let index = 0; index < frames.length - 1; index += 1) {
    const left = frames[index];
    const right = frames[index + 1];
    if (time >= left.time && time <= right.time) {
      const span = right.time - left.time || 1;
      const local = (time - left.time) / span;
      const t = easingProgress(easing, local, frame, fps, Math.round(span * fps));
      return left.value + (right.value - left.value) * t;
    }
  }
  return last.value;
}

export function isVec(value: unknown): value is Vec {
  return typeof value === "object" && value !== null && "x" in value && "y" in value;
}

export type Motion = { x: number; y: number; scale: number; rotate: number; opacity: number };

export function presetMotion(
  type: string,
  localTime: number,
  duration: number,
  easing: string,
  frame: number,
  fps: number,
  width: number,
  height: number,
): Motion {
  const window = Math.min(duration, 0.8);
  const t = easingProgress(easing, window === 0 ? 1 : Math.min(localTime, window) / window, frame, fps, Math.round(window * fps));
  const base: Motion = { x: 0, y: 0, scale: 1, rotate: 0, opacity: 1 };
  const travelX = width * 0.08;
  const travelY = height * 0.06;
  switch (type) {
    case "fade":
      return { ...base, opacity: t };
    case "fade_up":
      return { ...base, opacity: t, y: (1 - t) * travelY };
    case "fade_down":
      return { ...base, opacity: t, y: (t - 1) * travelY };
    case "fade_left":
      return { ...base, opacity: t, x: (1 - t) * travelX };
    case "fade_right":
      return { ...base, opacity: t, x: (t - 1) * travelX };
    case "scale_in":
      return { ...base, opacity: t, scale: 0.82 + 0.18 * t };
    case "scale_out":
      return { ...base, opacity: 1 - t, scale: 1 + 0.08 * t };
    case "slide_left":
      return { ...base, x: (1 - t) * travelX * 2 };
    case "slide_right":
      return { ...base, x: (t - 1) * travelX * 2 };
    case "slide_up":
      return { ...base, y: (1 - t) * travelY * 2 };
    case "slide_down":
      return { ...base, y: (t - 1) * travelY * 2 };
    case "rotate":
      return { ...base, rotate: (1 - t) * -8 };
    case "ken_burns": {
      const full = easingProgress("linear", duration === 0 ? 1 : localTime / duration, frame, fps, Math.round(duration * fps));
      return { ...base, scale: 1 + 0.12 * full, x: full * width * 0.02, y: full * height * -0.015 };
    }
    case "parallax": {
      const full = easingProgress("linear", duration === 0 ? 1 : localTime / duration, frame, fps, Math.round(duration * fps));
      return { ...base, y: (full - 0.5) * height * 0.04 };
    }
    case "slow_push": {
      const full = fullProgress(localTime, duration, frame, fps);
      return { ...base, scale: 1 + 0.08 * full };
    }
    case "slow_pull": {
      const full = fullProgress(localTime, duration, frame, fps);
      return { ...base, scale: 1.08 - 0.08 * full };
    }
    case "pan_left": {
      const full = fullProgress(localTime, duration, frame, fps);
      return { ...base, x: (0.5 - full) * width * 0.08 };
    }
    case "pan_right": {
      const full = fullProgress(localTime, duration, frame, fps);
      return { ...base, x: (full - 0.5) * width * 0.08 };
    }
    case "pan_up": {
      const full = fullProgress(localTime, duration, frame, fps);
      return { ...base, y: (0.5 - full) * height * 0.06 };
    }
    case "pan_down": {
      const full = fullProgress(localTime, duration, frame, fps);
      return { ...base, y: (full - 0.5) * height * 0.06 };
    }
    case "orbit": {
      const full = fullProgress(localTime, duration, frame, fps);
      const angle = full * Math.PI * 2;
      return { ...base, x: Math.cos(angle) * width * 0.03, y: Math.sin(angle) * height * 0.02, rotate: full * 8 };
    }
    case "float": {
      const full = fullProgress(localTime, duration, frame, fps);
      return { ...base, y: Math.sin(full * Math.PI * 2) * height * 0.015 };
    }
    case "drift": {
      const full = fullProgress(localTime, duration, frame, fps);
      return { ...base, x: (full - 0.5) * width * 0.04, y: Math.sin(full * Math.PI) * height * 0.01 };
    }
    case "shake": {
      const full = fullProgress(localTime, duration, frame, fps);
      const amp = (1 - full) * 6;
      return { ...base, x: Math.sin(full * 40) * amp, y: Math.cos(full * 36) * amp };
    }
    case "handheld": {
      const full = fullProgress(localTime, duration, frame, fps);
      return {
        ...base,
        x: Math.sin(full * Math.PI * 6) * width * 0.004,
        y: Math.cos(full * Math.PI * 5) * height * 0.004,
        rotate: Math.sin(full * Math.PI * 4) * 0.4,
      };
    }
    default:
      return base;
  }
}
