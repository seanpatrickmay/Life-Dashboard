import styled from 'styled-components';

// Empty canvas to inspect the background scene with no UI cards/components.
const SceneCanvas = styled.div`
  min-height: 140vh; /* give room to view arc + reflections */
`;

export function GardenPage() {
  return <SceneCanvas aria-label="Scene inspection canvas" />;
}

