/**
 * Scene z-index map. Higher numbers render on top.
 */
export const Z_LAYERS = {
  gradient: -2,
  waterRipple: -1,
  sceneBase: 1,
  sunMoon: 2,
  clouds: 4,
  bridge: 5,
  bridgeReflection: 4,
  boat: 11,
  boatReflection: 2,
  lilyPads: 8,
  lilyPadTextLayer: 9,
  nav: 13, // highest
  willows: 10,
  blossoms: 10,
  uiCards: 12,
  overlays: 12
} as const;

export type ZLayerKey = keyof typeof Z_LAYERS;
