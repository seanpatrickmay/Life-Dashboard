import { lightTheme, darkTheme } from './monetTheme';

export type ChartMode = 'light' | 'dark';

export function getChartTheme(mode: ChartMode) {
  return mode === 'dark' ? darkTheme.chart : lightTheme.chart;
}
