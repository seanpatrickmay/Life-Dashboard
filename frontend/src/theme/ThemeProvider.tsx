import React from 'react';
import { ThemeProvider as StyledThemeProvider } from 'styled-components';
import { lightTheme, darkTheme, type FeatureSceneSetting, type SceneDensity, type HorizonSetting } from './monetTheme';

type Moment = 'morning' | 'noon' | 'twilight' | 'night';
type ArtIntensity = 'rich' | 'minimal' | 'flat';

type Mode = 'light' | 'dark' | 'system';

type ThemeModeContextType = {
  mode: Mode; // selected
  effective: 'light' | 'dark'; // applied
  setMode: (m: Mode) => void;
  toggle: () => void; // light<->dark (keeps system untouched)
  // Monet pixel-art controls
  intensity: ArtIntensity;
  setIntensity: (i: ArtIntensity) => void;
  motion: boolean;
  setMotion: (v: boolean) => void;
  timeOfDayMode: 'auto' | Moment;
  setTimeOfDayMode: (m: 'auto' | Moment) => void;
  moment: Moment; // effective
  featureScene: FeatureSceneSetting;
  setFeatureScene: (scene: FeatureSceneSetting) => void;
  willowEnabled: boolean;
  setWillowEnabled: (value: boolean) => void;
  sceneDensity: SceneDensity;
  setSceneDensity: (value: SceneDensity) => void;
  horizonMode: HorizonSetting;
  setHorizonMode: (value: HorizonSetting) => void;
  sceneHorizon: number;
};

export const ThemeModeContext = React.createContext<ThemeModeContextType | undefined>(undefined);

function getSystemPref(): 'light' | 'dark' {
  if (typeof window === 'undefined' || !window.matchMedia) return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function useSystemListener(onChange: (v: 'light' | 'dark') => void) {
  React.useEffect(() => {
    const mql = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e: MediaQueryListEvent) => onChange(e.matches ? 'dark' : 'light');
    if ((mql as any).addEventListener) mql.addEventListener('change', handler);
    else (mql as any).addListener?.(handler);
    return () => {
      if ((mql as any).removeEventListener) mql.removeEventListener('change', handler);
      else (mql as any).removeListener?.(handler);
    };
  }, [onChange]);
}

const readStoredMode = (): Mode => {
  if (typeof window === 'undefined') return 'system';
  const stored = window.localStorage.getItem('themeMode') as Mode | null;
  return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system';
};

const readStored = <T extends string>(key: string, fallback: T): T => {
  if (typeof window === 'undefined') return fallback;
  const raw = window.localStorage.getItem(key);
  return (raw as T) || fallback;
};

const readStoredFeatureScene = (): FeatureSceneSetting => {
  if (typeof window === 'undefined') return 'auto';
  const raw = window.localStorage.getItem('featureScene');
  const valid: FeatureSceneSetting[] = ['auto', 'bridge', 'koi', 'boat', 'none'];
  return valid.includes((raw as FeatureSceneSetting) ?? 'auto') ? (raw as FeatureSceneSetting) : 'auto';
};

const readStoredWillow = (): boolean => {
  if (typeof window === 'undefined') return true;
  const raw = window.localStorage.getItem('willowEnabled');
  if (raw === null) return true;
  return raw === 'true';
};

const readStoredSceneDensity = (): SceneDensity => {
  if (typeof window === 'undefined') return 'sparse';
  const raw = window.localStorage.getItem('sceneDensity') as SceneDensity | null;
  const valid: SceneDensity[] = ['sparse', 'balanced', 'lush'];
  return valid.includes(raw ?? 'sparse') ? (raw as SceneDensity) : 'sparse';
};

const readStoredHorizonMode = (): HorizonSetting => {
  if (typeof window === 'undefined') return 'auto';
  const raw = window.localStorage.getItem('horizonMode') as HorizonSetting | null;
  const valid: HorizonSetting[] = ['auto', 'low', 'mid', 'high'];
  return valid.includes(raw ?? 'auto') ? (raw as HorizonSetting) : 'auto';
};

function computeMoment(now = new Date()): Moment {
  const h = now.getHours();
  if (h >= 5 && h < 11) return 'morning';
  if (h >= 11 && h < 16) return 'noon';
  if (h >= 16 && h < 21) return 'twilight';
  return 'night';
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = React.useState<Mode>(readStoredMode);
  const [system, setSystem] = React.useState<'light' | 'dark'>(getSystemPref());
  useSystemListener(setSystem);

  // Monet pixel-art controls
  const [intensity, setIntensity] = React.useState<ArtIntensity>(readStored<ArtIntensity>('artIntensity', 'rich'));
  const [motion, setMotion] = React.useState<boolean>(readStored('artMotion', 'on') === 'on');
  const [timeOfDayMode, setTimeOfDayMode] = React.useState<'auto' | Moment>(readStored<'auto' | Moment>('timeOfDayMode', 'auto'));
  const [featureScene, setFeatureScene] = React.useState<FeatureSceneSetting>(readStoredFeatureScene);
  const [willowEnabled, setWillowEnabled] = React.useState<boolean>(readStoredWillow);
  const [sceneDensity, setSceneDensity] = React.useState<SceneDensity>(readStoredSceneDensity);
  const [horizonMode, setHorizonMode] = React.useState<HorizonSetting>(readStoredHorizonMode);
  const [clock, setClock] = React.useState<Date>(new Date());

  React.useEffect(() => {
    if (timeOfDayMode !== 'auto') return;
    const id = window.setInterval(() => setClock(new Date()), 60_000);
    return () => window.clearInterval(id);
  }, [timeOfDayMode]);

  const effective = mode === 'system' ? system : mode;
  const moment: Moment = timeOfDayMode === 'auto' ? computeMoment(clock) : timeOfDayMode;
  const base = effective === 'dark' ? darkTheme : lightTheme;
  const horizonBase = base.scene?.horizonByMoment?.[moment] ?? 0.7;
  const horizonOffset =
    horizonMode === 'low' ? -0.05 : horizonMode === 'high' ? 0.05 : horizonMode === 'mid' ? 0.02 : 0;
  const resolvedHorizon = Math.min(0.82, Math.max(0.6, horizonBase + horizonOffset));
  const theme = {
    ...base,
    intensity,
    motion,
    moment,
    featureScene,
    willowEnabled,
    sceneDensity,
    sceneHorizon: resolvedHorizon,
    horizonMode
  } as const;

  const api = React.useMemo<ThemeModeContextType>(
    () => ({
      mode,
      effective,
      intensity,
      setIntensity: (i) => {
        setIntensity(i);
        try { window.localStorage.setItem('artIntensity', i); } catch {}
      },
      motion,
      setMotion: (v) => {
        setMotion(v);
        try { window.localStorage.setItem('artMotion', v ? 'on' : 'off'); } catch {}
      },
      timeOfDayMode,
      setTimeOfDayMode: (m) => {
        setTimeOfDayMode(m);
        try { window.localStorage.setItem('timeOfDayMode', m); } catch {}
      },
      moment,
      featureScene,
      setFeatureScene: (scene) => {
        setFeatureScene(scene);
        try { window.localStorage.setItem('featureScene', scene); } catch {}
      },
      willowEnabled,
      setWillowEnabled: (value) => {
        setWillowEnabled(value);
        try { window.localStorage.setItem('willowEnabled', value ? 'true' : 'false'); } catch {}
      },
      sceneDensity,
      setSceneDensity: (value) => {
        setSceneDensity(value);
        try { window.localStorage.setItem('sceneDensity', value); } catch {}
      },
      horizonMode,
      setHorizonMode: (value) => {
        setHorizonMode(value);
        try { window.localStorage.setItem('horizonMode', value); } catch {}
      },
      sceneHorizon: resolvedHorizon,
      setMode: (m) => {
        setMode(m);
        if (typeof window !== 'undefined') {
          window.localStorage.setItem('themeMode', m);
        }
        try {
          const eff = m === 'system' ? getSystemPref() : (m as 'light'|'dark');
          document.body.classList.toggle('dark-mode', eff === 'dark');
          document.body.setAttribute('data-theme', eff);
        } catch {}
      },
      toggle: () => {
        const next = effective === 'dark' ? 'light' : 'dark';
        setMode(next);
        if (typeof window !== 'undefined') {
          window.localStorage.setItem('themeMode', next);
        }
        try {
          document.body.classList.toggle('dark-mode', next === 'dark');
          document.body.setAttribute('data-theme', next);
        } catch {}
      },
    }),
    [mode, effective, intensity, motion, timeOfDayMode, moment, featureScene, willowEnabled, sceneDensity, horizonMode, resolvedHorizon]
  );

  // Ensure body reflects current effective mode on first mount and when system changes
  React.useEffect(() => {
    try {
      document.body.classList.toggle('dark-mode', effective === 'dark');
      document.body.setAttribute('data-theme', effective);
      document.body.setAttribute('data-moment', moment);
      document.body.setAttribute('data-intensity', intensity);
      document.body.setAttribute('data-motion', motion ? 'on' : 'off');
      document.body.setAttribute('data-feature-scene', featureScene);
      document.body.setAttribute('data-willow', willowEnabled ? 'on' : 'off');
      document.body.setAttribute('data-scene-density', sceneDensity);
      document.body.setAttribute('data-horizon', resolvedHorizon.toFixed(2));
    } catch {}
  }, [effective, moment, intensity, motion, featureScene, willowEnabled, sceneDensity, resolvedHorizon]);

  return (
    <ThemeModeContext.Provider value={api}>
      <StyledThemeProvider theme={theme}>{children}</StyledThemeProvider>
    </ThemeModeContext.Provider>
  );
}

export function useThemeMode() {
  const ctx = React.useContext(ThemeModeContext);
  if (!ctx) throw new Error('useThemeMode must be used within ThemeProvider');
  return ctx;
}
