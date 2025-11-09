import React from 'react';

type SpriteRegistry = Map<string, HTMLElement | null>;

type SceneForegroundValue = {
  registerSprite: (id: string, el: HTMLElement | null) => void;
  dimSprites: (rect: DOMRect | null) => void;
  clearDims: () => void;
};

const SceneForegroundContext = React.createContext<SceneForegroundValue | undefined>(undefined);

const intersects = (a: DOMRect, b: DOMRect) =>
  !(a.right < b.left || a.left > b.right || a.bottom < b.top || a.top > b.bottom);

export function SceneForegroundProvider({ children }: { children: React.ReactNode }) {
  const spritesRef = React.useRef<SpriteRegistry>(new Map());

  const registerSprite = React.useCallback((id: string, el: HTMLElement | null) => {
    spritesRef.current.set(id, el);
  }, []);

  const clearDims = React.useCallback(() => {
    spritesRef.current.forEach((el) => {
      if (el) el.dataset.dimmed = 'false';
    });
  }, []);

  const dimSprites = React.useCallback((rect: DOMRect | null) => {
    spritesRef.current.forEach((el) => {
      if (!el) return;
      if (!rect) {
        el.dataset.dimmed = 'false';
        return;
      }
      const spriteRect = el.getBoundingClientRect();
      el.dataset.dimmed = intersects(rect, spriteRect) ? 'true' : 'false';
    });
  }, []);

  const value = React.useMemo<SceneForegroundValue>(
    () => ({ registerSprite, dimSprites, clearDims }),
    [registerSprite, dimSprites, clearDims]
  );

  return <SceneForegroundContext.Provider value={value}>{children}</SceneForegroundContext.Provider>;
}

export function useSceneForeground() {
  return React.useContext(SceneForegroundContext);
}
