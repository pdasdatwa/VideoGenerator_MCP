import React from "react";
import { Img, OffthreadVideo, useCurrentFrame, useVideoConfig } from "remotion";
import { presetMotion, sampleNumber, sampleVec } from "./animations/motion";
import { Anim, Crop, LayerProps } from "./types";

type Box = {
  left: number;
  top: number;
  opacity: number;
  transform: string;
  width: number;
  height: number;
  scale: number;
  rotation: number;
};

type SafeArea = { top: number; bottom: number; left: number; right: number };

export function useLayerBox(layer: LayerProps, width: number, height: number, safeArea?: SafeArea): Box | null {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const time = frame / fps;
  if (time < layer.start || time >= layer.start + layer.duration) {
    return null;
  }
  return boxAt(layer, width, height, time - layer.start, frame, fps, safeArea);
}

function boxAt(
  layer: LayerProps,
  width: number,
  height: number,
  local: number,
  frame: number,
  fps: number,
  safeArea?: SafeArea,
): Box {
  const easing = layer.animation.easing || "ease_out";
  const position = sampleVec(layer.position, local, layer.duration, easing, frame, fps, { x: 0.5, y: 0.5 });
  const anchor = sampleVec(layer.anchor, local, layer.duration, easing, frame, fps, { x: 0.5, y: 0.5 });
  let scale = sampleNumber(layer.scale, local, layer.duration, easing, frame, fps);
  let rotation = sampleNumber(layer.rotation, local, layer.duration, easing, frame, fps);
  let opacity = sampleNumber(layer.opacity, local, layer.duration, easing, frame, fps);
  const motion = presetMotion(layer.animation.type, local, layer.animation.duration || layer.duration, easing, frame, fps, width, height);
  scale *= motion.scale;
  rotation += motion.rotate;
  opacity *= motion.opacity;
  const boxWidth = (layer.width || 0.5) * width;
  const boxHeight = (layer.height || 0.3) * height;
  let left = position.x * width + motion.x - boxWidth * anchor.x;
  let top = position.y * height + motion.y - boxHeight * anchor.y;
  if (layer.respectSafeArea && safeArea) {
    const minX = safeArea.left * width;
    const maxX = Math.max(minX, width - safeArea.right * width - boxWidth);
    const minY = safeArea.top * height;
    const maxY = Math.max(minY, height - safeArea.bottom * height - boxHeight);
    left = Math.min(maxX, Math.max(minX, left));
    top = Math.min(maxY, Math.max(minY, top));
  }
  return {
    left,
    top,
    opacity: Math.max(0, Math.min(1, opacity)),
    transform: `scale(${scale}) rotate(${rotation}deg)`,
    width: boxWidth,
    height: boxHeight,
    scale,
    rotation,
  };
}

function sampleEffect(anim: Anim | null | undefined, local: number, duration: number, frame: number, fps: number): number {
  if (!anim) {
    return 0;
  }
  return sampleNumber(anim, local, duration, "linear", frame, fps);
}

export function filterFor(layer: LayerProps, local: number, frame: number, fps: number, motionBlurPx: number): string | undefined {
  const effects = layer.effects || {};
  const parts: string[] = [];
  const blur = sampleEffect(effects.blur, local, layer.duration, frame, fps);
  const motion = (effects.motion_blur || 0) * motionBlurPx;
  if (blur || motion) {
    parts.push(`blur(${blur + motion}px)`);
  }
  const brightness = effects.brightness ? sampleEffect(effects.brightness, local, layer.duration, frame, fps) : null;
  const bloom = effects.bloom || 0;
  if (brightness != null || bloom) {
    parts.push(`brightness(${(brightness ?? 1) * (1 + bloom * 0.35)})`);
  }
  const contrast = effects.contrast ? sampleEffect(effects.contrast, local, layer.duration, frame, fps) : null;
  if (contrast != null) {
    parts.push(`contrast(${contrast})`);
  }
  const saturation = effects.saturation ? sampleEffect(effects.saturation, local, layer.duration, frame, fps) : null;
  if (saturation != null) {
    parts.push(`saturate(${saturation})`);
  }
  if (effects.grayscale != null) {
    parts.push(`grayscale(${effects.grayscale})`);
  }
  if (effects.sepia) {
    parts.push(`sepia(${effects.sepia})`);
  }
  if (effects.drop_shadow) {
    parts.push("drop-shadow(0px 18px 24px rgba(0,0,0,0.45))");
  }
  if (effects.glow) {
    const spread = 8 + effects.glow * 24;
    parts.push(`drop-shadow(0 0 ${spread}px rgba(255,255,255,${0.35 + effects.glow * 0.4}))`);
  }
  if (bloom) {
    parts.push(`drop-shadow(0 0 ${12 * bloom}px rgba(255,255,255,${0.45 * bloom}))`);
  }
  return parts.length ? parts.join(" ") : undefined;
}

function clipFor(layer: LayerProps, box: Box, local: number, frame: number, fps: number): string | undefined {
  const mask = layer.mask;
  if (!mask) {
    return undefined;
  }
  const x = sampleNumber(mask.x, local, layer.duration, "linear", frame, fps) * box.width;
  const y = sampleNumber(mask.y, local, layer.duration, "linear", frame, fps) * box.height;
  const w = sampleNumber(mask.width, local, layer.duration, "linear", frame, fps) * box.width;
  const h = sampleNumber(mask.height, local, layer.duration, "linear", frame, fps) * box.height;
  const radius = sampleNumber(mask.radius, local, layer.duration, "linear", frame, fps) * Math.min(box.width, box.height);
  if (mask.shape === "circle") {
    return `circle(${Math.min(w, h) / 2}px at ${x}px ${y}px)`;
  }
  if (mask.shape === "ellipse") {
    return `ellipse(${w / 2}px ${h / 2}px at ${x}px ${y}px)`;
  }
  const top = y - h / 2;
  const right = box.width - (x + w / 2);
  const bottom = box.height - (y + h / 2);
  const left = x - w / 2;
  const round = mask.shape === "rounded_rect" ? ` round ${radius}px` : "";
  return `inset(${top}px ${right}px ${bottom}px ${left}px${round})`;
}

function sampleCrop(anim: Anim | null | undefined, local: number, duration: number, frame: number, fps: number): Crop | null {
  if (!anim) {
    return null;
  }
  if (anim.mode === "static") {
    return isCrop(anim.value) ? anim.value : null;
  }
  if (anim.mode === "from_to" && isCrop(anim.from) && isCrop(anim.to)) {
    const t = duration === 0 ? 1 : Math.min(1, Math.max(0, local / duration));
    return {
      x: anim.from.x + (anim.to.x - anim.from.x) * t,
      y: anim.from.y + (anim.to.y - anim.from.y) * t,
      width: anim.from.width + (anim.to.width - anim.from.width) * t,
      height: anim.from.height + (anim.to.height - anim.from.height) * t,
    };
  }
  if (anim.mode === "keyframes") {
    const frames = anim.keyframes.filter((item) => isCrop(item.value)) as { time: number; value: Crop }[];
    if (!frames.length) {
      return null;
    }
    const x = sampleNumber({ mode: "keyframes", keyframes: frames.map((item) => ({ time: item.time, value: item.value.x })) }, local, duration, "linear", frame, fps);
    const y = sampleNumber({ mode: "keyframes", keyframes: frames.map((item) => ({ time: item.time, value: item.value.y })) }, local, duration, "linear", frame, fps);
    const width = sampleNumber({ mode: "keyframes", keyframes: frames.map((item) => ({ time: item.time, value: item.value.width })) }, local, duration, "linear", frame, fps);
    const height = sampleNumber({ mode: "keyframes", keyframes: frames.map((item) => ({ time: item.time, value: item.value.height })) }, local, duration, "linear", frame, fps);
    return { x, y, width, height };
  }
  return null;
}

function isCrop(value: unknown): value is Crop {
  return typeof value === "object" && value !== null && "width" in value && "height" in value;
}

export function LayerView({
  layer,
  width,
  height,
  safeArea,
}: {
  layer: LayerProps;
  width: number;
  height: number;
  safeArea?: SafeArea;
}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const box = useLayerBox(layer, width, height, safeArea);
  if (!box) {
    return null;
  }
  const local = frame / fps - layer.start;
  const previous = boxAt(layer, width, height, Math.max(0, local - 1 / fps), Math.max(0, frame - 1), fps, safeArea);
  const speed = Math.hypot(box.left - previous.left, box.top - previous.top) + Math.abs(box.rotation - previous.rotation) * 0.8 + Math.abs(box.scale - previous.scale) * 40;
  const common: React.CSSProperties = {
    position: "absolute",
    left: box.left,
    top: box.top,
    width: box.width,
    height: box.height,
    opacity: box.opacity,
    transform: box.transform,
    transformOrigin: "center center",
    filter: filterFor(layer, local, frame, fps, Math.min(24, speed)),
    clipPath: clipFor(layer, box, local, frame, fps),
    mixBlendMode: layer.blendMode && layer.blendMode !== "normal" ? layer.blendMode : undefined,
    zIndex: layer.zIndex,
    overflow: "hidden",
  };
  const crop = sampleCrop(layer.crop, local, layer.duration, frame, fps);
  return (
    <div style={common}>
      {layer.type === "image" && layer.src ? <ImageLayer layer={layer} crop={crop} /> : null}
      {layer.type === "video" && layer.src ? <VideoLayer layer={layer} crop={crop} /> : null}
      {layer.type === "svg" && layer.svg ? <SvgLayer layer={layer} /> : null}
      {layer.type === "text" && layer.text ? <TextLayer layer={layer} frameWidth={width} /> : null}
      {layer.type === "shape" ? <ShapeLayer layer={layer} /> : null}
      {layer.effects?.vignette ? (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `radial-gradient(circle, transparent 45%, rgba(0,0,0,${layer.effects.vignette}) 100%)`,
            pointerEvents: "none",
          }}
        />
      ) : null}
      {layer.effects?.grain ? <Grain amount={layer.effects.grain} filterId={`grain-${layer.id}`} /> : null}
      {layer.effects?.color_tint && layer.effects.color_tint.amount > 0 ? (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: layer.effects.color_tint.color,
            opacity: layer.effects.color_tint.amount,
            mixBlendMode: "multiply",
            pointerEvents: "none",
          }}
        />
      ) : null}
    </div>
  );
}

function mediaFit(layer: LayerProps): React.CSSProperties {
  return {
    width: "100%",
    height: "100%",
    objectFit: layer.fit === "fill" ? "fill" : layer.fit === "contain" ? "contain" : "cover",
  };
}

function cropStyle(crop: Crop | null): React.CSSProperties {
  if (!crop || crop.width <= 0 || crop.height <= 0) {
    return { width: "100%", height: "100%" };
  }
  return {
    position: "absolute",
    width: `${100 / crop.width}%`,
    height: `${100 / crop.height}%`,
    left: `${(-crop.x / crop.width) * 100}%`,
    top: `${(-crop.y / crop.height) * 100}%`,
  };
}

function ImageLayer({ layer, crop }: { layer: LayerProps; crop: Crop | null }) {
  return <Img src={layer.src || ""} style={{ ...mediaFit(layer), ...cropStyle(crop) }} />;
}

function VideoLayer({ layer, crop }: { layer: LayerProps; crop: Crop | null }) {
  const { fps } = useVideoConfig();
  const trimBefore = Math.round((layer.trimStart || 0) * fps);
  const trimAfter = layer.trimEnd != null ? Math.round(layer.trimEnd * fps) : undefined;
  return (
    <OffthreadVideo
      src={layer.src || ""}
      trimBefore={trimBefore}
      trimAfter={trimAfter}
      playbackRate={layer.playbackRate || 1}
      loop={layer.loop}
      style={{ ...mediaFit(layer), ...cropStyle(crop), objectFit: layer.fit === "contain" ? "contain" : "cover" }}
    />
  );
}

function SvgLayer({ layer, style }: { layer: LayerProps; style?: React.CSSProperties }) {
  // Without a fit the markup keeps the width and height it declares, which is how standard
  // scenes have always drawn SVG. With a fit it is sized to the layer box instead.
  const markup = layer.fit ? fitSvgMarkup(layer.svg || "", layer.fit) : layer.svg || "";
  return <div style={{ ...style, width: "100%", height: "100%", overflow: "hidden" }} dangerouslySetInnerHTML={{ __html: markup }} />;
}

function fitSvgMarkup(markup: string, fit: string): string {
  const preserve = fit === "fill" ? "none" : fit === "contain" ? "xMidYMid meet" : "xMidYMid slice";
  return markup.replace(/<svg\b([^>]*)>/i, (_match, attrs: string) => {
    const cleaned = attrs.replace(/\s(width|height|preserveAspectRatio)\s*=\s*("[^"]*"|'[^']*')/gi, "");
    return `<svg${cleaned} width="100%" height="100%" preserveAspectRatio="${preserve}">`;
  });
}

function TextLayer({ layer, frameWidth }: { layer: LayerProps; frameWidth: number }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const local = frame / fps - layer.start;
  const text = layer.text || "";
  const textStyle = layer.style || {};
  const maxWidth = (textStyle.max_width || 0.84) * frameWidth;
  const reveal = revealText(text, layer.animation.type, local, layer.animation.duration || 0.8, layer.duration);
  return (
    <div
      style={{
        width: maxWidth,
        height: "auto",
        color: textStyle.color || "#FFFFFF",
        fontFamily: textStyle.font_family || "Inter, sans-serif",
        fontSize: textStyle.font_size || 64,
        fontWeight: textStyle.font_weight || 700,
        lineHeight: textStyle.line_height || 1.15,
        letterSpacing: textStyle.letter_spacing || 0,
        textAlign: textStyle.align || "center",
        whiteSpace: "pre-wrap",
      }}
    >
      {reveal}
    </div>
  );
}

function revealText(text: string, type: string, local: number, duration: number, layerDuration: number): string {
  const window = type === "typewriter" ? layerDuration : duration;
  const progress = Math.min(1, Math.max(0, window === 0 ? 1 : local / window));
  if (type === "word_reveal") {
    const words = text.split(" ");
    const count = Math.max(1, Math.ceil(words.length * progress));
    return words.slice(0, count).join(" ");
  }
  if (type === "character_reveal" || type === "typewriter") {
    const count = Math.max(1, Math.ceil(text.length * progress));
    return text.slice(0, count);
  }
  return text;
}

function ShapeLayer({ layer }: { layer: LayerProps }) {
  let background = layer.fill || "#FFFFFF";
  if (layer.shape === "gradient" && layer.gradient) {
    const stops = layer.gradient.stops.map((stop) => `${stop.color} ${Math.round(stop.offset * 100)}%`).join(", ");
    background = `linear-gradient(${layer.gradient.angle}deg, ${stops})`;
  }
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        background,
        borderRadius: layer.shape === "ellipse" ? "50%" : `${(layer.borderRadius || 0) * 100}%`,
      }}
    />
  );
}

function Grain({ amount, filterId }: { amount: number; filterId: string }) {
  return (
    <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", opacity: amount * 0.45, pointerEvents: "none" }}>
      <filter id={filterId}>
        <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="7" />
      </filter>
      <rect width="100%" height="100%" filter={`url(#${filterId})`} />
    </svg>
  );
}
