/**
 * Scene z-index map. Higher numbers render on top.
 */
export const Z_LAYERS = {
  gradient: -2,
  waterRipple: -1,
  sceneBase: 1,
  sunMoon: 2,
  clouds: 3,
  bridge: 4,
  bridgeReflection: 3,
  boat: 11,
  boatReflection: 2,
  lilyPads: 6,
  lilyPadTextLayer: 5,
  nav: 8,
  willows: 9,
  blossoms: 9,
  uiCards: 6,
  overlays: 10
} as const;

export type ZLayerKey = keyof typeof Z_LAYERS;
