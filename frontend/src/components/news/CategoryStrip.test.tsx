// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from 'styled-components';
import { testTheme } from '../../test/renderWithProviders';
import { CategoryStrip } from './CategoryStrip';

function wrap(ui: React.ReactElement) {
  return render(<ThemeProvider theme={testTheme}>{ui}</ThemeProvider>);
}

describe('CategoryStrip', () => {
  it('renders All pill plus all category pills', () => {
    wrap(<CategoryStrip active="all" onChange={() => {}} />);
    expect(screen.getByText('All')).toBeInTheDocument();
    expect(screen.getByText('Tech')).toBeInTheDocument();
    expect(screen.getByText('Science')).toBeInTheDocument();
    expect(screen.getByText('World')).toBeInTheDocument();
  });

  it('marks the active pill as selected', () => {
    wrap(<CategoryStrip active="tech" onChange={() => {}} />);
    expect(screen.getByRole('tab', { name: 'Tech' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: 'All' })).toHaveAttribute('aria-selected', 'false');
  });

  it('calls onChange with the correct category when a pill is clicked', () => {
    const onChange = vi.fn();
    wrap(<CategoryStrip active="all" onChange={onChange} />);
    fireEvent.click(screen.getByText('Science'));
    expect(onChange).toHaveBeenCalledWith('science');
  });

  it('calls onChange with "all" when All pill is clicked', () => {
    const onChange = vi.fn();
    wrap(<CategoryStrip active="tech" onChange={onChange} />);
    fireEvent.click(screen.getByText('All'));
    expect(onChange).toHaveBeenCalledWith('all');
  });

  it('shows counts when provided', () => {
    wrap(<CategoryStrip active="all" counts={{ tech: 5, science: 3 }} onChange={() => {}} />);
    expect(screen.getByText('Tech (5)')).toBeInTheDocument();
    expect(screen.getByText('Science (3)')).toBeInTheDocument();
  });

  it('does NOT render an AI&Dev pill (that is a separate entry card)', () => {
    wrap(<CategoryStrip active="all" onChange={() => {}} />);
    expect(screen.queryByText(/ai.*dev/i)).not.toBeInTheDocument();
  });
});
