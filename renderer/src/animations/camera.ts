import { CameraProps } from "../types";
import { sampleNumber, sampleVec } from "./motion";

export type CameraFrame = { x: number; y: number; zoom: number; rotation: number };

/**
 * Where the camera looks on this frame. position is the normalized point that ends up in the
 * centre of the frame, zoom is a magnification, rotation is degrees. Tracks are sampled
 * linearly, matching the keyframes the cartoon compiler writes.
 */
export function sampleCamera(camera: CameraProps, time: number, duration: number, frame: number, fps: number): CameraFrame {
  const position = camera.position
    ? sampleVec(camera.position, time, duration, "linear", frame, fps, { x: 0.5, y: 0.5 })
    : { x: 0.5, y: 0.5 };
  const zoom = camera.zoom ? sampleNumber(camera.zoom, time, duration, "linear", frame, fps) : 1;
  const rotation = camera.rotation ? sampleNumber(camera.rotation, time, duration, "linear", frame, fps) : 0;
  return { x: position.x, y: position.y, zoom: zoom > 0 ? zoom : 1, rotation };
}

/**
 * CSS transforms apply right to left: the frame is shifted so the camera point sits in the
 * middle, then magnified and rotated about that middle.
 */
export function cameraTransform(camera: CameraFrame, width: number, height: number): string {
  const dx = (0.5 - camera.x) * width;
  const dy = (0.5 - camera.y) * height;
  return `scale(${camera.zoom}) rotate(${camera.rotation}deg) translate(${dx}px, ${dy}px)`;
}
