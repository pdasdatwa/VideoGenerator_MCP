export type Anim =
  | { mode: "static"; value: number | Vec | Crop }
  | { mode: "from_to"; from: number | Vec | Crop; to: number | Vec | Crop }
  | { mode: "keyframes"; keyframes: { time: number; value: number | Vec | Crop }[] };

export type Vec = { x: number; y: number };
export type Crop = { x: number; y: number; width: number; height: number };

export type LayerProps = {
  id: string;
  type: "image" | "video" | "svg" | "text" | "shape";
  src?: string | null;
  svg?: string | null;
  text?: string | null;
  start: number;
  duration: number;
  zIndex: number;
  position: Anim;
  scale: Anim;
  rotation: Anim;
  opacity: Anim;
  anchor: Anim;
  crop?: Anim | null;
  fit: "contain" | "cover" | "crop" | "fill";
  effects: {
    blur?: Anim | null;
    brightness?: Anim | null;
    contrast?: Anim | null;
    saturation?: Anim | null;
    grayscale?: number | null;
    drop_shadow?: boolean | null;
    motion_blur?: number | null;
    sepia?: number | null;
    vignette?: number | null;
    glow?: number | null;
    bloom?: number | null;
    grain?: number | null;
    color_tint?: { color: string; amount: number } | null;
  };
  blendMode?: "normal" | "multiply" | "screen" | "overlay" | "soft_light";
  mask?: {
    shape: "rect" | "rounded_rect" | "circle" | "ellipse";
    x: Anim;
    y: Anim;
    width: Anim;
    height: Anim;
    radius: Anim;
  } | null;
  animation: { type: string; duration?: number | null; easing?: string | null };
  style: {
    font_family?: string;
    font_size?: number;
    font_weight?: number;
    color?: string;
    align?: "left" | "center" | "right";
    line_height?: number;
    letter_spacing?: number;
    max_width?: number | null;
  };
  shape?: "rect" | "ellipse" | "gradient" | null;
  fill?: string;
  width?: number;
  height?: number;
  borderRadius?: number;
  gradient?: { angle: number; stops: { color: string; offset: number }[] } | null;
  trimStart?: number;
  trimEnd?: number | null;
  playbackRate?: number;
  loop?: boolean;
  respectSafeArea?: boolean;
};

export type CameraProps = {
  position?: Anim | null;
  zoom?: Anim | null;
  rotation?: Anim | null;
};

export type SceneProps = {
  sceneId: string;
  rendererVersion: string;
  width: number;
  height: number;
  fps: number;
  duration: number;
  background: { type: "color" | "image" | "video"; value?: string | null; src?: string | null };
  layers: LayerProps[];
  safeArea: { top: number; bottom: number; left: number; right: number };
  globalEffects: {
    brightness: number;
    contrast: number;
    saturation: number;
    tint?: string | null;
    tint_opacity: number;
    vignette: number;
  };
  render?: { crf?: number };
  // Present only for cartoon scenes. A standard scene renders exactly as it did without it.
  camera?: CameraProps | null;
};
