import React from 'react';
import { ThemeProvider as StyledThemeProvider } from 'styled-components';
import { lightTheme, darkTheme, scenePalettesByMoment, haloTokens, type FeatureSceneSetting, type SceneDensity, type HorizonSetting, type Moment } from './monetTheme';
import { fetchSceneTime } from '../services/api';

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
  // Scene test controls
  timeTestEnabled: boolean;
  setTimeTestEnabled: (v: boolean) => void;
  sceneHour: number; // 0–24 float
  setSceneHour: (h: number) => void;
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

export const DEFAULT_TIME_ZONE = 'America/New_York';

const manualMomentHours: Record<Moment, number> = {
  morning: 8,
  noon: 12,
  twilight: 18,
  night: 0
};

export function getHourInTimeZone(date = new Date(), timeZone: string = DEFAULT_TIME_ZONE) {
  try {
    const formatter = new Intl.DateTimeFormat('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
      timeZone
    });
    const parts = formatter.formatToParts(date);
    const pick = (type: Intl.DateTimeFormatPartTypes) =>
      Number(parts.find((p) => p.type === type)?.value ?? '0');
    const hour = pick('hour');
    const minute = pick('minute');
    const second = pick('second');
    return hour + minute / 60 + second / 3600;
  } catch {
    return (
      date.getUTCHours() +
      date.getUTCMinutes() / 60 +
      date.getUTCSeconds() / 3600
    );
  }
}

export function computeMomentFromHour(h: number): Moment {
  // Morning: 06:00–10:59, Noon: 11:00–16:59, Twilight: 17:00–20:59, Night: 21:00–05:59
  if (h >= 6 && h < 11) return 'morning';
  if (h >= 11 && h < 17) return 'noon';
  if (h >= 17 && h < 21) return 'twilight';
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
  const [timeTestEnabled, setTimeTestEnabled] = React.useState<boolean>(false);
  const [autoSceneHour, setAutoSceneHour] = React.useState<number>(() =>
    getHourInTimeZone(new Date(), DEFAULT_TIME_ZONE)
  );
  const [sceneHour, setSceneHour] = React.useState<number>(() =>
    getHourInTimeZone(new Date(), DEFAULT_TIME_ZONE)
  );

  const userEffective = mode === 'system' ? system : mode; // retained only for UI display
  const autoHour = autoSceneHour;
  const resolvedMoment: Moment = timeTestEnabled
    ? computeMomentFromHour(sceneHour)
    : timeOfDayMode === 'auto'
        ? computeMomentFromHour(autoHour)
        : timeOfDayMode;
  const controlHour = timeTestEnabled
    ? sceneHour
    : timeOfDayMode === 'auto'
        ? autoHour
        : manualMomentHours[timeOfDayMode];
  // Moment-driven theme selection: morning/noon -> light, twilight/night -> dark
  const appliedMode: 'light' | 'dark' = (resolvedMoment === 'morning' || resolvedMoment === 'noon') ? 'light' : 'dark';
  const base = appliedMode === 'dark' ? darkTheme : lightTheme;
  const horizonBase = base.scene?.horizonByMoment?.[resolvedMoment] ?? 0.7;
  const horizonOffset =
    horizonMode === 'low' ? -0.05 : horizonMode === 'high' ? 0.05 : horizonMode === 'mid' ? 0.02 : 0;
  const resolvedHorizon = Math.min(0.82, Math.max(0.6, horizonBase + horizonOffset));
  const theme = {
    ...base,
    intensity,
    motion,
    moment: resolvedMoment,
    featureScene,
    willowEnabled,
    sceneDensity,
    sceneHorizon: resolvedHorizon,
    horizonMode,
    timeTestEnabled,
    sceneHour: controlHour
  } as const;

  const api = React.useMemo<ThemeModeContextType>(
    () => ({
      mode,
      effective: appliedMode,
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
      moment: resolvedMoment,
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
      timeTestEnabled,
      setTimeTestEnabled: (v: boolean) => {
        setTimeTestEnabled(v);
      },
      sceneHour,
      setSceneHour: (h: number) => {
        const clamped = Math.min(24, Math.max(0, h));
        setSceneHour(clamped);
      },
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
        const next = appliedMode === 'dark' ? 'light' : 'dark';
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
    [mode, appliedMode, intensity, motion, timeOfDayMode, resolvedMoment, featureScene, willowEnabled, sceneDensity, horizonMode, resolvedHorizon, timeTestEnabled, sceneHour]
  );

  // Ensure body reflects current effective mode on first mount and when system changes
  React.useEffect(() => {
    try {
      document.body.classList.toggle('dark-mode', appliedMode === 'dark');
      document.body.setAttribute('data-theme', appliedMode);
      document.body.setAttribute('data-moment', resolvedMoment);
      document.body.setAttribute('data-intensity', intensity);
      document.body.setAttribute('data-motion', motion ? 'on' : 'off');
      document.body.setAttribute('data-feature-scene', featureScene);
      document.body.setAttribute('data-willow', willowEnabled ? 'on' : 'off');
      document.body.setAttribute('data-scene-density', sceneDensity);
      document.body.setAttribute('data-horizon', resolvedHorizon.toFixed(2));
    } catch {}
  }, [appliedMode, resolvedMoment, intensity, motion, featureScene, willowEnabled, sceneDensity, resolvedHorizon]);

  // Override scene palette per moment so background colors differ for all four times.
  const themedScenePalette = scenePalettesByMoment[resolvedMoment];
  // Moment-driven accents (subtle hue shift through the day)
  const momentAccent = (() => {
    switch (resolvedMoment) {
      case 'morning': return { accent: '#FFC075', accentSoft: 'rgba(255,192,117,0.28)' }; // ember 200
      case 'noon': return { accent: '#7ED7C4', accentSoft: 'rgba(126,215,196,0.28)' };   // pond 200
      case 'twilight': return { accent: '#BF6BAB', accentSoft: 'rgba(191,107,171,0.28)' }; // bloom 300
      case 'night': return { accent: '#C2D5FF', accentSoft: 'rgba(194,213,255,0.28)' };   // sky 200
      default: return { accent: '#E6A9D3', accentSoft: 'rgba(230,169,211,0.28)' };
    }
  })();
  const halo = haloTokens[resolvedMoment];

  const themed = React.useMemo(() => ({
    ...theme,
    colors: {
      ...theme.colors,
      accent: momentAccent.accent,
      accentSoft: momentAccent.accentSoft
    },
    scene: {
      ...(theme.scene ?? { horizonByMoment: {} as Record<Moment, number> }),
      palette: themedScenePalette
    },
    tokens: {
      ...(theme.tokens ?? {}),
      halo
    }
  }), [theme, themedScenePalette, momentAccent, halo]);

  React.useEffect(() => {
    if (timeOfDayMode !== 'auto') return;

    let cancelled = false;

    const syncFromServer = async () => {
      try {
        const response = await fetchSceneTime();
        if (!cancelled) {
          setAutoSceneHour(response.hour_decimal);
        }
      } catch {
        if (!cancelled) {
          setAutoSceneHour(getHourInTimeZone(new Date(), DEFAULT_TIME_ZONE));
        }
      }
    };

    syncFromServer();

    const tickId = window.setInterval(() => {
      if (!cancelled) {
        setAutoSceneHour(getHourInTimeZone(new Date(), DEFAULT_TIME_ZONE));
      }
    }, 30_000);

    const refreshId = window.setInterval(syncFromServer, 10 * 60 * 1000);

    return () => {
      cancelled = true;
      window.clearInterval(tickId);
      window.clearInterval(refreshId);
    };
  }, [timeOfDayMode]);

  React.useEffect(() => {
    if (timeTestEnabled) return;
    if (timeOfDayMode === 'auto') {
      setSceneHour(autoSceneHour);
    }
  }, [autoSceneHour, timeOfDayMode, timeTestEnabled]);

  React.useEffect(() => {
    if (timeTestEnabled) return;
    if (timeOfDayMode !== 'auto') {
      setSceneHour(manualMomentHours[timeOfDayMode]);
    }
  }, [timeOfDayMode, timeTestEnabled]);

  return (
    <ThemeModeContext.Provider value={api}>
      <StyledThemeProvider theme={themed}>{children}</StyledThemeProvider>
    </ThemeModeContext.Provider>
  );
}

export function useThemeMode() {
  const ctx = React.useContext(ThemeModeContext);
  if (!ctx) throw new Error('useThemeMode must be used within ThemeProvider');
  return ctx;
}
