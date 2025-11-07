import styled from 'styled-components';
import { useThemeMode } from '../theme/ThemeProvider';
import { Card } from '../components/common/Card';

const Row = styled.div`
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
`;

const Segment = styled.div`
  display: inline-flex;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  border-radius: 12px;
  overflow: hidden;

  button {
    font-family: ${({ theme }) => theme.fonts.heading};
    font-size: 0.7rem;
    letter-spacing: 0.5px;
    padding: 10px 14px;
    background: transparent;
    border: 0;
    cursor: pointer;
    color: ${({ theme }) => theme.colors.textSecondary};
  }

  button.active {
    background: ${({ theme }) => theme.colors.backgroundCard};
    color: ${({ theme }) => theme.colors.textPrimary};
  }
`;

const featureSceneOptions = [
  { value: 'auto', label: 'Auto' },
  { value: 'bridge', label: 'Bridge' },
  { value: 'koi', label: 'Koi' },
  { value: 'boat', label: 'Boat' },
  { value: 'none', label: 'None' }
] as const;

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

export function SettingsPage() {
  const {
    mode, effective, setMode, toggle,
    intensity, setIntensity,
    motion, setMotion,
    timeOfDayMode, setTimeOfDayMode,
    moment,
    featureScene, setFeatureScene,
    willowEnabled, setWillowEnabled,
    sceneDensity, setSceneDensity,
    horizonMode, setHorizonMode,
    sceneHorizon
  } = useThemeMode();
  const setSeg = (val: 'light' | 'dark' | 'system') => () => setMode(val);
  const setFeature = (val: (typeof featureSceneOptions)[number]['value']) => () => setFeatureScene(val);
  const setDensity = (val: (typeof densityOptions)[number]['value']) => () => setSceneDensity(val);
  const setHorizon = (val: (typeof horizonOptions)[number]['value']) => () => setHorizonMode(val);
  return (
    <Card>
      <h2>Settings</h2>
      <p>Customize update cadence and display preferences.</p>

      <h3>Appearance</h3>
      <Row>
        <span style={{ fontFamily: '"Press Start 2P", cursive', fontSize: '0.8rem' }}>Theme:</span>
        <Segment>
          <button onClick={setSeg('light')} className={mode === 'light' ? 'active' : ''}>Light</button>
          <button onClick={setSeg('dark')} className={mode === 'dark' ? 'active' : ''}>Dark</button>
          <button onClick={setSeg('system')} className={mode === 'system' ? 'active' : ''}>System</button>
        </Segment>
        <button onClick={toggle} style={{ marginLeft: 'auto' }}>Toggle</button>
      </Row>
      <p style={{ opacity: 0.7, marginTop: 8 }}>Applied: {effective}</p>

      <h3 style={{ marginTop: 24 }}>Monet Pixel Art</h3>
      <Row>
        <span style={{ fontFamily: '"Press Start 2P", cursive', fontSize: '0.8rem' }}>Intensity:</span>
        <Segment>
          <button onClick={() => setIntensity('rich')} className={intensity === 'rich' ? 'active' : ''}>Rich</button>
          <button onClick={() => setIntensity('minimal')} className={intensity === 'minimal' ? 'active' : ''}>Minimal</button>
          <button onClick={() => setIntensity('flat')} className={intensity === 'flat' ? 'active' : ''}>Flat</button>
        </Segment>
      </Row>
      <Row style={{ marginTop: 12 }}>
        <span style={{ fontFamily: '"Press Start 2P", cursive', fontSize: '0.8rem' }}>Motion:</span>
        <Segment>
          <button onClick={() => setMotion(true)} className={motion ? 'active' : ''}>On</button>
          <button onClick={() => setMotion(false)} className={!motion ? 'active' : ''}>Off</button>
        </Segment>
      </Row>
      <Row style={{ marginTop: 12 }}>
        <span style={{ fontFamily: '"Press Start 2P", cursive', fontSize: '0.8rem' }}>Time of day:</span>
        <Segment>
          <button onClick={() => setTimeOfDayMode('auto')} className={timeOfDayMode === 'auto' ? 'active' : ''}>Auto</button>
          <button onClick={() => setTimeOfDayMode('morning')} className={timeOfDayMode === 'morning' ? 'active' : ''}>Morning</button>
          <button onClick={() => setTimeOfDayMode('noon')} className={timeOfDayMode === 'noon' ? 'active' : ''}>Noon</button>
          <button onClick={() => setTimeOfDayMode('twilight')} className={timeOfDayMode === 'twilight' ? 'active' : ''}>Twilight</button>
          <button onClick={() => setTimeOfDayMode('night')} className={timeOfDayMode === 'night' ? 'active' : ''}>Night</button>
        </Segment>
        <span style={{ marginLeft: 'auto', opacity: 0.7 }}>Current: {moment}</span>
      </Row>
      <Row style={{ marginTop: 12 }}>
        <span style={{ fontFamily: '"Press Start 2P", cursive', fontSize: '0.8rem' }}>Scene focus:</span>
        <Segment>
          {featureSceneOptions.map((opt) => (
            <button
              key={opt.value}
              onClick={setFeature(opt.value)}
              className={featureScene === opt.value ? 'active' : ''}
            >
              {opt.label}
            </button>
          ))}
        </Segment>
        <span style={{ opacity: 0.6 }}>Auto follows the current time of day.</span>
      </Row>
      <Row style={{ marginTop: 12 }}>
        <span style={{ fontFamily: '"Press Start 2P", cursive', fontSize: '0.8rem' }}>Willow drape:</span>
        <Segment>
          <button onClick={() => setWillowEnabled(true)} className={willowEnabled ? 'active' : ''}>On</button>
          <button onClick={() => setWillowEnabled(false)} className={!willowEnabled ? 'active' : ''}>Off</button>
        </Segment>
      </Row>
      <Row style={{ marginTop: 12 }}>
        <span style={{ fontFamily: '"Press Start 2P", cursive', fontSize: '0.8rem' }}>Scene density:</span>
        <Segment>
          {densityOptions.map((opt) => (
            <button key={opt.value} onClick={setDensity(opt.value)} className={sceneDensity === opt.value ? 'active' : ''}>
              {opt.label}
            </button>
          ))}
        </Segment>
      </Row>
      <Row style={{ marginTop: 12 }}>
        <span style={{ fontFamily: '"Press Start 2P", cursive', fontSize: '0.8rem' }}>Horizon line:</span>
        <Segment>
          {horizonOptions.map((opt) => (
            <button key={opt.value} onClick={setHorizon(opt.value)} className={horizonMode === opt.value ? 'active' : ''}>
              {opt.label}
            </button>
          ))}
        </Segment>
        <span style={{ opacity: 0.6 }}>Current: {(sceneHorizon * 100).toFixed(0)}% height</span>
      </Row>
    </Card>
  );
}
