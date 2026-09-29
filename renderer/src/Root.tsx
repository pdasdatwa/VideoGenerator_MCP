import React from "react";
import { Composition } from "remotion";
import { Scene } from "./Scene";
import { SceneProps } from "./types";

const defaultProps: SceneProps = {
  sceneId: "scene",
  rendererVersion: "0.1.0",
  width: 1080,
  height: 1920,
  fps: 30,
  duration: 1,
  background: { type: "color", value: "#000000" },
  layers: [],
  safeArea: { top: 0.08, bottom: 0.08, left: 0.06, right: 0.06 },
  globalEffects: {
    brightness: 1,
    contrast: 1,
    saturation: 1,
    tint: null,
    tint_opacity: 0,
    vignette: 0,
  },
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Scene"
      component={Scene}
      durationInFrames={30}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={defaultProps}
      calculateMetadata={({ props }) => {
        return {
          durationInFrames: Math.max(1, Math.round(props.duration * props.fps)),
          fps: props.fps,
          width: props.width,
          height: props.height,
        };
      }}
    />
  );
};
