import { useLayoutEffect, useRef, useState } from 'react';
import styled from 'styled-components';

// Empty canvas to inspect the background scene with no UI cards/components.
const SceneCanvas = styled.div`
  width: 100%;
  overflow: hidden;
`;

export function GardenPage() {
  const ref = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(() => window.innerHeight);

  useLayoutEffect(() => {
    const update = () => {
      const top = ref.current?.getBoundingClientRect().top ?? 0;
      const available = Math.max(0, window.innerHeight - top);
      setHeight(available);
    };
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);

  return <SceneCanvas ref={ref} aria-label="Scene inspection canvas" style={{ height }} />;
}
