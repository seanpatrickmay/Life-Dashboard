# Scene Components Folder

## Purpose
Contains the Monet pond scene renderer that layers sprites, water textures, and overlays behind every page.

## File Overview

| File | Description |
| --- | --- |
| `SceneComposer.tsx` | Builds the multi-layer pond background (water, pads, blossoms, right-justified bridge, shoreline islands, orbital overlays) used by `PageBackground`. |
| `SceneForegroundContext.tsx` | Provides registration/dimming for foreground sprites so HUD elements can fade overlapping blossoms. |
