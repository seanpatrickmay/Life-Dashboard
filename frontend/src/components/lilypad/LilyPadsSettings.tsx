import styled from 'styled-components';
import { LilyPadCard } from './LilyPadCard';
import { useThemeMode } from '../../theme/ThemeProvider';

const Stage = styled.div`
  position: relative;
  min-height: calc(100vh + 160px);
  padding-bottom: 320px;
  color: #ffffff;
`;

const ControlStack = styled.div`
  display: flex;
  flex-direction: column;
  gap: 14px;
  width: 100%;
`;

const ControlRow = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
`;

const Segment = styled.div`
  display: inline-flex;
  border: 1px solid rgba(255, 255, 255, 0.35);
  border-radius: 12px;
  overflow: hidden;

  button {
    font-family: ${({ theme }) => theme.fonts.heading};
    font-size: 0.7rem;
    letter-spacing: 0.5px;
    padding: 10px 14px;
    background: rgba(255, 255, 255, 0.08);
    border: 0;
    cursor: pointer;
    color: #ffffff;
  }

  button.active {
    background: rgba(255, 255, 255, 0.25);
    color: #0a1724;
  }
`;

const Label = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.75rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.8);
`;

const SliderCluster = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: auto;
  input[type='range'] {
    flex: 1;
  }
`;

const Readout = styled.span<{ $muted?: boolean }>`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.9);
  opacity: ${(p) => (p.$muted ? 0.5 : 0.85)};
  width: 80px;
  text-align: right;
`;

const Hint = styled.p`
  margin: 0;
  font-size: 0.85rem;
  opacity: 0.75;
  color: rgba(255, 255, 255, 0.82);
`;

const densityOptions = [
  { value: 'sparse', label: 'Sparse' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'lush', label: 'Lush' }
] as const;

const horizonOptions = [
  { value: 'auto', label: 'Auto' },
  { value: 'low', label: 'Low' },
  { value: 'mid', label: 'Mid' },
  { value: 'high', label: 'High' }
] as const;

export function LilyPadsSettings() {
  const {
    intensity, setIntensity,
    motion, setMotion,
    timeOfDayMode, setTimeOfDayMode,
    moment,
    willowEnabled, setWillowEnabled,
    sceneDensity, setSceneDensity,
    horizonMode, setHorizonMode,
    sceneHorizon,
    timeTestEnabled, setTimeTestEnabled,
    sceneHour, setSceneHour,
    effective
  } = useThemeMode();

  const setDensity = (val: (typeof densityOptions)[number]['value']) => () => setSceneDensity(val);
  const setHorizon = (val: (typeof horizonOptions)[number]['value']) => () => setHorizonMode(val);

  const edgeOffset = -64;
  const shiftPercent = 28;

  return (
    <Stage>
      <LilyPadCard
        id="settings-time"
        side="left"
        topOffsetPx={-10}
        scale={0.9}
        aspectRatio={11.4 / 5}
        title="Time Test"
        interactive
        edgeOffsetPx={edgeOffset}
        sideShiftPercent={shiftPercent}
        contentWidthPct={0.7}
      >
        <ControlStack>
          <ControlRow>
            <Label>Manual Orbit</Label>
            <Segment>
              <button type="button" onClick={() => setTimeTestEnabled(true)} className={timeTestEnabled ? 'active' : ''}>On</button>
              <button type="button" onClick={() => setTimeTestEnabled(false)} className={!timeTestEnabled ? 'active' : ''}>Off</button>
            </Segment>
          </ControlRow>
          <SliderCluster>
            <input
              type="range"
              min={0}
              max={24}
              step={0.25}
              value={sceneHour}
              onChange={(e) => setSceneHour(parseFloat(e.target.value))}
              disabled={!timeTestEnabled}
            />
            <Readout $muted={!timeTestEnabled}>{sceneHour.toFixed(2)}h</Readout>
          </SliderCluster>
          <Hint>Applied palette: {effective} / moment {moment}</Hint>
        </ControlStack>
      </LilyPadCard>

      <LilyPadCard
        id="settings-theme"
        side="right"
        topOffsetPx={200}
        scale={0.92}
        aspectRatio={11.8 / 5}
        title="Lights & Moments"
        interactive
        edgeOffsetPx={edgeOffset}
        sideShiftPercent={shiftPercent}
        contentWidthPct={0.74}
      >
        <ControlStack>
          <ControlRow>
            <Label>Intensity</Label>
            <Segment>
              <button type="button" onClick={() => setIntensity('rich')} className={intensity === 'rich' ? 'active' : ''}>Rich</button>
              <button type="button" onClick={() => setIntensity('minimal')} className={intensity === 'minimal' ? 'active' : ''}>Minimal</button>
              <button type="button" onClick={() => setIntensity('flat')} className={intensity === 'flat' ? 'active' : ''}>Flat</button>
            </Segment>
          </ControlRow>
          <ControlRow>
            <Label>Motion</Label>
            <Segment>
              <button type="button" onClick={() => setMotion(true)} className={motion ? 'active' : ''}>On</button>
              <button type="button" onClick={() => setMotion(false)} className={!motion ? 'active' : ''}>Off</button>
            </Segment>
          </ControlRow>
          <ControlRow>
            <Label>Time of day</Label>
            <Segment>
              <button type="button" onClick={() => setTimeOfDayMode('auto')} className={timeOfDayMode === 'auto' ? 'active' : ''}>Auto</button>
              <button type="button" onClick={() => setTimeOfDayMode('morning')} className={timeOfDayMode === 'morning' ? 'active' : ''}>Morning</button>
              <button type="button" onClick={() => setTimeOfDayMode('noon')} className={timeOfDayMode === 'noon' ? 'active' : ''}>Noon</button>
              <button type="button" onClick={() => setTimeOfDayMode('twilight')} className={timeOfDayMode === 'twilight' ? 'active' : ''}>Twilight</button>
              <button type="button" onClick={() => setTimeOfDayMode('night')} className={timeOfDayMode === 'night' ? 'active' : ''}>Night</button>
            </Segment>
          </ControlRow>
        </ControlStack>
      </LilyPadCard>

      <LilyPadCard
        id="settings-scene"
        side="left"
        topOffsetPx={380}
        scale={0.94}
        aspectRatio={12 / 5}
        title="Scene Layers"
        interactive
        edgeOffsetPx={edgeOffset}
        sideShiftPercent={shiftPercent}
        contentWidthPct={0.76}
      >
        <ControlStack>
          <ControlRow>
            <Label>Willow Drapes</Label>
            <Segment>
              <button type="button" onClick={() => setWillowEnabled(true)} className={willowEnabled ? 'active' : ''}>On</button>
              <button type="button" onClick={() => setWillowEnabled(false)} className={!willowEnabled ? 'active' : ''}>Off</button>
            </Segment>
          </ControlRow>
          <ControlRow>
            <Label>Density</Label>
            <Segment>
              {densityOptions.map((opt) => (
                <button type="button" key={opt.value} onClick={setDensity(opt.value)} className={sceneDensity === opt.value ? 'active' : ''}>
                  {opt.label}
                </button>
              ))}
            </Segment>
          </ControlRow>
          <ControlRow>
            <Label>Horizon</Label>
            <Segment>
              {horizonOptions.map((opt) => (
                <button type="button" key={opt.value} onClick={setHorizon(opt.value)} className={horizonMode === opt.value ? 'active' : ''}>
                  {opt.label}
                </button>
              ))}
            </Segment>
            <Readout>{(sceneHorizon * 100).toFixed(0)}%</Readout>
          </ControlRow>
        </ControlStack>
      </LilyPadCard>
    </Stage>
  );
}
