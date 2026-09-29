import React from "react";
import { AbsoluteFill, Img, OffthreadVideo, useCurrentFrame, useVideoConfig } from "remotion";
import "@fontsource/inter/400.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import { cameraTransform, sampleCamera } from "./animations/camera";
import { LayerView } from "./Layer";
import { CameraProps, SceneProps } from "./types";

export const Scene: React.FC<SceneProps> = (props) => {
  const { width, height } = props;
  const effects = props.globalEffects;
  const layers = [...props.layers].sort((a, b) => a.zIndex - b.zIndex);
  const filter = `brightness(${effects.brightness}) contrast(${effects.contrast}) saturate(${effects.saturation})`;
  const content = (
    <>
      {props.background.type === "color" ? (
        <AbsoluteFill style={{ backgroundColor: props.background.value || "#000" }} />
      ) : null}
      {props.background.type === "image" && props.background.src ? (
        <Img src={props.background.src} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      ) : null}
      {props.background.type === "video" && props.background.src ? (
        <OffthreadVideo src={props.background.src} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      ) : null}
      {layers.map((layer) => (
        <LayerView key={layer.id} layer={layer} width={width} height={height} safeArea={props.safeArea} />
      ))}
    </>
  );
  return (
    <AbsoluteFill style={{ backgroundColor: "#000", fontFamily: "Inter, sans-serif" }}>
      <AbsoluteFill style={{ filter }}>
        {props.camera ? (
          <CameraView camera={props.camera} width={width} height={height} duration={props.duration}>
            {content}
          </CameraView>
        ) : (
          content
        )}
      </AbsoluteFill>
      {effects.tint && effects.tint_opacity > 0 ? (
        <AbsoluteFill style={{ backgroundColor: effects.tint, opacity: effects.tint_opacity }} />
      ) : null}
      {effects.vignette > 0 ? (
        <AbsoluteFill
          style={{
            background: `radial-gradient(circle, transparent 40%, rgba(0,0,0,${effects.vignette}) 100%)`,
          }}
        />
      ) : null}
    </AbsoluteFill>
  );
};

const CameraView: React.FC<{
  camera: CameraProps;
  width: number;
  height: number;
  duration: number;
  children: React.ReactNode;
}> = ({ camera, width, height, duration, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const view = sampleCamera(camera, frame / fps, duration, frame, fps);
  return (
    <AbsoluteFill style={{ transform: cameraTransform(view, width, height), transformOrigin: "center center" }}>
      {children}
    </AbsoluteFill>
  );
};
