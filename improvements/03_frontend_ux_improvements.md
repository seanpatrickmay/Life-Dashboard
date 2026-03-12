# Frontend UX & Accessibility Improvements Guide

## Phase 3: UI/UX and Accessibility Enhancements (Week 3-4)

### 1. Critical Accessibility Fixes

#### 1.1 ARIA Labels and Keyboard Navigation
```tsx
// frontend/src/components/common/AccessibleButton.tsx
import React, { forwardRef } from 'react';
import styled from 'styled-components';

interface AccessibleButtonProps {
  label: string;
  ariaLabel?: string;
  onClick: () => void;
  variant?: 'primary' | 'secondary' | 'danger';
  disabled?: boolean;
  loading?: boolean;
  icon?: React.ReactNode;
  children: React.ReactNode;
}

export const AccessibleButton = forwardRef<HTMLButtonElement, AccessibleButtonProps>(
  ({ label, ariaLabel, onClick, variant = 'primary', disabled, loading, icon, children }, ref) => {
    const handleKeyPress = (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        if (!disabled && !loading) {
          onClick();
        }
      }
    };

    return (
      <StyledButton
        ref={ref}
        onClick={onClick}
        onKeyDown={handleKeyPress}
        disabled={disabled || loading}
        variant={variant}
        aria-label={ariaLabel || label}
        aria-busy={loading}
        aria-disabled={disabled}
        role="button"
        tabIndex={disabled ? -1 : 0}
      >
        {loading ? (
          <>
            <Spinner aria-hidden="true" />
            <span className="sr-only">Loading...</span>
          </>
        ) : (
          <>
            {icon && <IconWrapper aria-hidden="true">{icon}</IconWrapper>}
            {children}
          </>
        )}
      </StyledButton>
    );
  }
);

AccessibleButton.displayName = 'AccessibleButton';

const StyledButton = styled.button<{ variant: string }>`
  /* Ensure minimum touch target size */
  min-height: 44px;
  min-width: 44px;
  padding: 12px 24px;

  /* Focus styles for keyboard navigation */
  &:focus-visible {
    outline: 3px solid ${props => props.theme.colors.focus};
    outline-offset: 2px;
  }

  /* Remove default focus outline */
  &:focus:not(:focus-visible) {
    outline: none;
  }

  /* High contrast mode support */
  @media (prefers-contrast: high) {
    border: 2px solid currentColor;
  }

  /* Reduced motion support */
  @media (prefers-reduced-motion: reduce) {
    transition: none;
  }
`;

const Spinner = styled.div`
  width: 16px;
  height: 16px;
  border: 2px solid transparent;
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
`;

const IconWrapper = styled.span`
  display: inline-flex;
  margin-right: 8px;
`;

// Screen reader only text utility
export const ScreenReaderOnly = styled.span`
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
`;
```

#### 1.2 Fix Color Contrast Issues
```tsx
// frontend/src/styles/theme.ts
export const improvedTheme = {
  colors: {
    // WCAG AA compliant color palette
    primary: {
      light: '#5B9FE3',  // 3:1 on white
      main: '#2C7CC9',   // 4.5:1 on white
      dark: '#1A5490',   // 7:1 on white
      contrast: '#FFFFFF'
    },
    text: {
      primary: '#1A1A1A',   // 15:1 on white
      secondary: '#525252', // 7:1 on white
      disabled: '#767676',  // 4.5:1 on white
      inverse: '#FFFFFF'
    },
    background: {
      default: '#FFFFFF',
      paper: '#F8F9FA',
      elevated: '#FFFFFF',
      overlay: 'rgba(0, 0, 0, 0.5)'
    },
    error: {
      main: '#C62828',     // 5:1 on white
      light: '#EF5350',    // 3:1 on white
      dark: '#8B0000',     // 9:1 on white
      background: '#FFEBEE'
    },
    success: {
      main: '#2E7D32',     // 5:1 on white
      light: '#66BB6A',    // 3:1 on white
      dark: '#1B5E20',     // 10:1 on white
      background: '#E8F5E9'
    },
    warning: {
      main: '#F57C00',     // 3:1 on white
      dark: '#E65100',     // 4.5:1 on white
      background: '#FFF3E0',
      text: '#000000'      // Use black text on warning colors
    },
    // Focus indicator color
    focus: '#0066CC',
    focusLight: 'rgba(0, 102, 204, 0.25)'
  },

  // Improved typography for readability
  typography: {
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    fontSize: {
      xs: '0.75rem',   // 12px
      sm: '0.875rem',  // 14px
      base: '1rem',    // 16px - minimum for body text
      lg: '1.125rem',  // 18px
      xl: '1.25rem',   // 20px
      '2xl': '1.5rem', // 24px
      '3xl': '1.875rem', // 30px
      '4xl': '2.25rem'  // 36px
    },
    lineHeight: {
      tight: 1.25,
      normal: 1.5,     // Minimum for body text
      relaxed: 1.75,
      loose: 2
    },
    fontWeight: {
      normal: 400,
      medium: 500,
      semibold: 600,
      bold: 700
    }
  },

  spacing: {
    // Consistent spacing scale
    xs: '0.25rem',   // 4px
    sm: '0.5rem',    // 8px
    md: '1rem',      // 16px
    lg: '1.5rem',    // 24px
    xl: '2rem',      // 32px
    '2xl': '3rem',   // 48px
    '3xl': '4rem'    // 64px
  },

  breakpoints: {
    xs: '320px',
    sm: '640px',
    md: '768px',
    lg: '1024px',
    xl: '1280px',
    '2xl': '1536px'
  },

  // Z-index scale
  zIndex: {
    dropdown: 1000,
    sticky: 1020,
    fixed: 1030,
    modalBackdrop: 1040,
    modal: 1050,
    popover: 1060,
    tooltip: 1070,
    toast: 1080
  }
};

// Contrast checking utility
export function getContrastRatio(foreground: string, background: string): number {
  // Implementation of WCAG contrast ratio calculation
  const getLuminance = (color: string) => {
    // Convert hex to RGB and calculate relative luminance
    const rgb = parseInt(color.slice(1), 16);
    const r = (rgb >> 16) & 0xff;
    const g = (rgb >> 8) & 0xff;
    const b = (rgb >> 0) & 0xff;

    const sRGB = [r, g, b].map(val => {
      val = val / 255;
      return val <= 0.03928 ? val / 12.92 : Math.pow((val + 0.055) / 1.055, 2.4);
    });

    return 0.2126 * sRGB[0] + 0.7152 * sRGB[1] + 0.0722 * sRGB[2];
  };

  const l1 = getLuminance(foreground);
  const l2 = getLuminance(background);

  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);

  return (lighter + 0.05) / (darker + 0.05);
}
```

#### 1.3 Skip Navigation Links
```tsx
// frontend/src/components/layout/SkipLinks.tsx
import React from 'react';
import styled from 'styled-components';

export const SkipLinks: React.FC = () => {
  return (
    <SkipLinksContainer>
      <SkipLink href="#main-navigation">Skip to navigation</SkipLink>
      <SkipLink href="#main-content">Skip to main content</SkipLink>
      <SkipLink href="#footer">Skip to footer</SkipLink>
    </SkipLinksContainer>
  );
};

const SkipLinksContainer = styled.div`
  position: absolute;
  top: -100%;
  left: 0;
  z-index: 999;

  &:focus-within {
    top: 0;
  }
`;

const SkipLink = styled.a`
  display: inline-block;
  padding: ${props => props.theme.spacing.md};
  background: ${props => props.theme.colors.primary.main};
  color: ${props => props.theme.colors.primary.contrast};
  text-decoration: none;
  font-weight: ${props => props.theme.typography.fontWeight.semibold};

  &:focus {
    outline: 3px solid ${props => props.theme.colors.focus};
    outline-offset: 2px;
  }

  &:hover {
    background: ${props => props.theme.colors.primary.dark};
  }
`;
```

### 2. User Feedback Systems

#### 2.1 Toast Notification System
```tsx
// frontend/src/components/feedback/ToastProvider.tsx
import React, { createContext, useContext, useState, useCallback } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import styled from 'styled-components';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';

interface Toast {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  title: string;
  message?: string;
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
}

interface ToastContextType {
  showToast: (toast: Omit<Toast, 'id'>) => void;
  hideToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextType | null>(null);

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }
  return context;
};

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((toast: Omit<Toast, 'id'>) => {
    const id = Date.now().toString();
    const newToast = { ...toast, id };

    setToasts(prev => [...prev, newToast]);

    // Auto-dismiss after duration
    if (toast.duration !== 0) {
      setTimeout(() => {
        hideToast(id);
      }, toast.duration || 5000);
    }
  }, []);

  const hideToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ showToast, hideToast }}>
      {children}
      <ToastContainer>
        <AnimatePresence>
          {toasts.map(toast => (
            <ToastItem key={toast.id} toast={toast} onClose={() => hideToast(toast.id)} />
          ))}
        </AnimatePresence>
      </ToastContainer>
    </ToastContext.Provider>
  );
};

const ToastItem: React.FC<{ toast: Toast; onClose: () => void }> = ({ toast, onClose }) => {
  const icons = {
    success: <CheckCircle size={20} />,
    error: <AlertCircle size={20} />,
    info: <Info size={20} />,
    warning: <AlertTriangle size={20} />
  };

  return (
    <StyledToast
      type={toast.type}
      initial={{ opacity: 0, y: 50, scale: 0.3 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.5, transition: { duration: 0.2 } }}
      layout
      role="alert"
      aria-live="polite"
    >
      <ToastIcon type={toast.type}>{icons[toast.type]}</ToastIcon>

      <ToastContent>
        <ToastTitle>{toast.title}</ToastTitle>
        {toast.message && <ToastMessage>{toast.message}</ToastMessage>}
        {toast.action && (
          <ToastAction onClick={toast.action.onClick}>
            {toast.action.label}
          </ToastAction>
        )}
      </ToastContent>

      <CloseButton
        onClick={onClose}
        aria-label="Dismiss notification"
      >
        <X size={16} />
      </CloseButton>
    </StyledToast>
  );
};

const ToastContainer = styled.div`
  position: fixed;
  bottom: ${props => props.theme.spacing.lg};
  right: ${props => props.theme.spacing.lg};
  z-index: ${props => props.theme.zIndex.toast};
  display: flex;
  flex-direction: column;
  gap: ${props => props.theme.spacing.md};
  pointer-events: none;

  @media (max-width: ${props => props.theme.breakpoints.sm}) {
    left: ${props => props.theme.spacing.md};
    right: ${props => props.theme.spacing.md};
    bottom: ${props => props.theme.spacing.md};
  }
`;

const StyledToast = styled(motion.div)<{ type: Toast['type'] }>`
  display: flex;
  align-items: flex-start;
  gap: ${props => props.theme.spacing.md};
  padding: ${props => props.theme.spacing.md};
  background: white;
  border-radius: 8px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
  border-left: 4px solid ${props => props.theme.colors[props.type].main};
  pointer-events: all;
  max-width: 400px;
  min-width: 300px;
`;

const ToastIcon = styled.div<{ type: Toast['type'] }>`
  color: ${props => props.theme.colors[props.type].main};
  flex-shrink: 0;
`;

const ToastContent = styled.div`
  flex: 1;
`;

const ToastTitle = styled.h3`
  margin: 0;
  font-size: ${props => props.theme.typography.fontSize.base};
  font-weight: ${props => props.theme.typography.fontWeight.semibold};
  color: ${props => props.theme.colors.text.primary};
`;

const ToastMessage = styled.p`
  margin: 4px 0 0;
  font-size: ${props => props.theme.typography.fontSize.sm};
  color: ${props => props.theme.colors.text.secondary};
`;

const ToastAction = styled.button`
  margin-top: 8px;
  padding: 4px 8px;
  background: transparent;
  border: 1px solid currentColor;
  border-radius: 4px;
  color: ${props => props.theme.colors.primary.main};
  font-size: ${props => props.theme.typography.fontSize.sm};
  cursor: pointer;

  &:hover {
    background: ${props => props.theme.colors.primary.light};
    color: white;
  }
`;

const CloseButton = styled.button`
  padding: 4px;
  background: transparent;
  border: none;
  color: ${props => props.theme.colors.text.secondary};
  cursor: pointer;
  flex-shrink: 0;

  &:hover {
    color: ${props => props.theme.colors.text.primary};
  }

  &:focus-visible {
    outline: 2px solid ${props => props.theme.colors.focus};
    outline-offset: 2px;
  }
`;
```

#### 2.2 Loading States and Skeletons
```tsx
// frontend/src/components/feedback/LoadingSkeleton.tsx
import React from 'react';
import styled, { keyframes } from 'styled-components';

interface SkeletonProps {
  variant?: 'text' | 'rect' | 'circle';
  width?: string | number;
  height?: string | number;
  count?: number;
  animation?: 'pulse' | 'wave';
}

export const Skeleton: React.FC<SkeletonProps> = ({
  variant = 'text',
  width,
  height,
  count = 1,
  animation = 'pulse'
}) => {
  const elements = Array.from({ length: count }, (_, i) => (
    <SkeletonElement
      key={i}
      variant={variant}
      width={width}
      height={height}
      animation={animation}
      role="presentation"
      aria-hidden="true"
    />
  ));

  return <>{elements}</>;
};

const pulse = keyframes`
  0% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
  100% {
    opacity: 1;
  }
`;

const wave = keyframes`
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
`;

const SkeletonElement = styled.div<SkeletonProps>`
  background: ${props => props.theme.colors.background.paper};
  border-radius: ${props => {
    switch (props.variant) {
      case 'circle':
        return '50%';
      case 'text':
        return '4px';
      default:
        return '8px';
    }
  }};
  width: ${props => {
    if (props.width) return typeof props.width === 'number' ? `${props.width}px` : props.width;
    switch (props.variant) {
      case 'circle':
        return '40px';
      case 'text':
        return '100%';
      default:
        return '100%';
    }
  }};
  height: ${props => {
    if (props.height) return typeof props.height === 'number' ? `${props.height}px` : props.height;
    switch (props.variant) {
      case 'circle':
        return '40px';
      case 'text':
        return '1em';
      default:
        return '20px';
    }
  }};
  margin-bottom: ${props => props.variant === 'text' ? '8px' : '0'};
  position: relative;
  overflow: hidden;

  ${props => props.animation === 'pulse' && `
    animation: ${pulse} 1.5s ease-in-out infinite;
  `}

  ${props => props.animation === 'wave' && `
    &::after {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: linear-gradient(
        90deg,
        transparent,
        rgba(255, 255, 255, 0.4),
        transparent
      );
      animation: ${wave} 1.2s linear infinite;
    }
  `}
`;

// Complex skeleton layouts
export const TodoSkeleton: React.FC = () => (
  <SkeletonContainer>
    <SkeletonHeader>
      <Skeleton variant="circle" width={24} height={24} />
      <Skeleton variant="text" width="60%" />
    </SkeletonHeader>
    <Skeleton variant="text" width="100%" />
    <Skeleton variant="text" width="40%" />
  </SkeletonContainer>
);

export const MetricCardSkeleton: React.FC = () => (
  <SkeletonCard>
    <Skeleton variant="text" width="40%" height={20} />
    <Skeleton variant="rect" width="100%" height={60} />
    <SkeletonFooter>
      <Skeleton variant="text" width="30%" />
      <Skeleton variant="text" width="30%" />
    </SkeletonFooter>
  </SkeletonCard>
);

const SkeletonContainer = styled.div`
  padding: ${props => props.theme.spacing.md};
  border: 1px solid ${props => props.theme.colors.background.paper};
  border-radius: 8px;
`;

const SkeletonHeader = styled.div`
  display: flex;
  align-items: center;
  gap: ${props => props.theme.spacing.sm};
  margin-bottom: ${props => props.theme.spacing.sm};
`;

const SkeletonCard = styled.div`
  padding: ${props => props.theme.spacing.lg};
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
`;

const SkeletonFooter = styled.div`
  display: flex;
  justify-content: space-between;
  margin-top: ${props => props.theme.spacing.md};
`;
```

#### 2.3 Confirmation Dialogs
```tsx
// frontend/src/components/feedback/ConfirmDialog.tsx
import React, { useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import styled from 'styled-components';
import { AlertTriangle } from 'lucide-react';
import FocusTrap from 'focus-trap-react';

interface ConfirmDialogProps {
  isOpen: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  type?: 'danger' | 'warning' | 'info';
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  onConfirm,
  onCancel,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  type = 'warning'
}) => {
  const cancelButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (isOpen) {
      // Save current focus
      const previousFocus = document.activeElement as HTMLElement;

      // Focus cancel button when dialog opens
      setTimeout(() => {
        cancelButtonRef.current?.focus();
      }, 0);

      // Restore focus when dialog closes
      return () => {
        previousFocus?.focus();
      };
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return createPortal(
    <FocusTrap>
      <DialogOverlay
        onClick={onCancel}
        role="presentation"
        aria-hidden="true"
      >
        <DialogContent
          onClick={(e) => e.stopPropagation()}
          role="alertdialog"
          aria-labelledby="dialog-title"
          aria-describedby="dialog-message"
          aria-modal="true"
        >
          <DialogHeader type={type}>
            <AlertTriangle size={24} />
            <DialogTitle id="dialog-title">{title}</DialogTitle>
          </DialogHeader>

          <DialogMessage id="dialog-message">
            {message}
          </DialogMessage>

          <DialogActions>
            <CancelButton
              ref={cancelButtonRef}
              onClick={onCancel}
              type="button"
            >
              {cancelLabel}
            </CancelButton>
            <ConfirmButton
              onClick={onConfirm}
              type={type}
            >
              {confirmLabel}
            </ConfirmButton>
          </DialogActions>
        </DialogContent>
      </DialogOverlay>
    </FocusTrap>,
    document.body
  );
};

const DialogOverlay = styled.div`
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: ${props => props.theme.zIndex.modalBackdrop};
  animation: fadeIn 0.2s ease-out;

  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }
`;

const DialogContent = styled.div`
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  max-width: 400px;
  width: 90%;
  max-height: 90vh;
  overflow: auto;
  animation: slideUp 0.3s ease-out;

  @keyframes slideUp {
    from {
      transform: translateY(20px);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }
`;

const DialogHeader = styled.div<{ type: string }>`
  display: flex;
  align-items: center;
  gap: ${props => props.theme.spacing.md};
  padding: ${props => props.theme.spacing.lg};
  border-bottom: 1px solid ${props => props.theme.colors.background.paper};
  color: ${props => props.theme.colors[props.type]?.main || props.theme.colors.warning.main};
`;

const DialogTitle = styled.h2`
  margin: 0;
  font-size: ${props => props.theme.typography.fontSize.xl};
  font-weight: ${props => props.theme.typography.fontWeight.semibold};
  color: ${props => props.theme.colors.text.primary};
`;

const DialogMessage = styled.p`
  padding: ${props => props.theme.spacing.lg};
  margin: 0;
  color: ${props => props.theme.colors.text.secondary};
  line-height: ${props => props.theme.typography.lineHeight.relaxed};
`;

const DialogActions = styled.div`
  display: flex;
  gap: ${props => props.theme.spacing.md};
  justify-content: flex-end;
  padding: ${props => props.theme.spacing.lg};
  border-top: 1px solid ${props => props.theme.colors.background.paper};
`;

const Button = styled.button`
  padding: ${props => props.theme.spacing.sm} ${props => props.theme.spacing.lg};
  border-radius: 8px;
  font-size: ${props => props.theme.typography.fontSize.base};
  font-weight: ${props => props.theme.typography.fontWeight.medium};
  cursor: pointer;
  transition: all 0.2s;
  min-width: 100px;

  &:focus-visible {
    outline: 3px solid ${props => props.theme.colors.focus};
    outline-offset: 2px;
  }
`;

const CancelButton = styled(Button)`
  background: transparent;
  border: 1px solid ${props => props.theme.colors.text.secondary};
  color: ${props => props.theme.colors.text.primary};

  &:hover {
    background: ${props => props.theme.colors.background.paper};
  }
`;

const ConfirmButton = styled(Button)<{ type: string }>`
  background: ${props => props.theme.colors[props.type]?.main || props.theme.colors.warning.main};
  border: none;
  color: white;

  &:hover {
    background: ${props => props.theme.colors[props.type]?.dark || props.theme.colors.warning.dark};
  }
`;
```

### 3. Mobile Responsiveness

#### 3.1 Responsive Navigation
```tsx
// frontend/src/components/layout/ResponsiveNavigation.tsx
import React, { useState } from 'react';
import styled from 'styled-components';
import { Menu, X, Home, Calendar, BarChart3, Settings } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useMediaQuery } from '../../hooks/useMediaQuery';

export const ResponsiveNavigation: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const isMobile = useMediaQuery(`(max-width: ${props => props.theme.breakpoints.md})`);

  const navItems = [
    { to: '/', label: 'Dashboard', icon: <Home /> },
    { to: '/calendar', label: 'Calendar', icon: <Calendar /> },
    { to: '/metrics', label: 'Metrics', icon: <BarChart3 /> },
    { to: '/settings', label: 'Settings', icon: <Settings /> }
  ];

  return (
    <>
      {isMobile ? (
        <>
          <MobileHeader>
            <MenuButton
              onClick={() => setIsOpen(!isOpen)}
              aria-label="Toggle navigation menu"
              aria-expanded={isOpen}
            >
              {isOpen ? <X /> : <Menu />}
            </MenuButton>
          </MobileHeader>

          <MobileDrawer isOpen={isOpen}>
            <DrawerOverlay onClick={() => setIsOpen(false)} />
            <DrawerContent>
              <nav role="navigation" aria-label="Main navigation">
                {navItems.map(item => (
                  <MobileNavLink
                    key={item.to}
                    to={item.to}
                    onClick={() => setIsOpen(false)}
                  >
                    {item.icon}
                    <span>{item.label}</span>
                  </MobileNavLink>
                ))}
              </nav>
            </DrawerContent>
          </MobileDrawer>

          <MobileBottomNav>
            {navItems.slice(0, 4).map(item => (
              <BottomNavItem
                key={item.to}
                to={item.to}
              >
                {item.icon}
                <BottomNavLabel>{item.label}</BottomNavLabel>
              </BottomNavItem>
            ))}
          </MobileBottomNav>
        </>
      ) : (
        <DesktopNav>
          {navItems.map(item => (
            <DesktopNavLink
              key={item.to}
              to={item.to}
            >
              {item.icon}
              <span>{item.label}</span>
            </DesktopNavLink>
          ))}
        </DesktopNav>
      )}
    </>
  );
};

const MobileHeader = styled.header`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 56px;
  background: white;
  border-bottom: 1px solid ${props => props.theme.colors.background.paper};
  display: flex;
  align-items: center;
  padding: 0 ${props => props.theme.spacing.md};
  z-index: ${props => props.theme.zIndex.sticky};
`;

const MenuButton = styled.button`
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  background: transparent;
  border: none;
  color: ${props => props.theme.colors.text.primary};
  cursor: pointer;
`;

const MobileDrawer = styled.div<{ isOpen: boolean }>`
  position: fixed;
  inset: 0;
  z-index: ${props => props.theme.zIndex.modal};
  pointer-events: ${props => props.isOpen ? 'all' : 'none'};
  visibility: ${props => props.isOpen ? 'visible' : 'hidden'};
`;

const DrawerOverlay = styled.div`
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  opacity: ${props => props.isOpen ? 1 : 0};
  transition: opacity 0.3s;
`;

const DrawerContent = styled.div`
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 280px;
  background: white;
  transform: ${props => props.isOpen ? 'translateX(0)' : 'translateX(-100%)'};
  transition: transform 0.3s;
  padding: ${props => props.theme.spacing.lg};
`;

const MobileNavLink = styled(NavLink)`
  display: flex;
  align-items: center;
  gap: ${props => props.theme.spacing.md};
  padding: ${props => props.theme.spacing.md};
  color: ${props => props.theme.colors.text.primary};
  text-decoration: none;
  border-radius: 8px;

  &.active {
    background: ${props => props.theme.colors.primary.light};
    color: ${props => props.theme.colors.primary.main};
  }
`;

const MobileBottomNav = styled.nav`
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 56px;
  background: white;
  border-top: 1px solid ${props => props.theme.colors.background.paper};
  display: flex;
  justify-content: space-around;
  z-index: ${props => props.theme.zIndex.sticky};

  @supports (padding-bottom: env(safe-area-inset-bottom)) {
    padding-bottom: env(safe-area-inset-bottom);
    height: calc(56px + env(safe-area-inset-bottom));
  }
`;

const BottomNavItem = styled(NavLink)`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  color: ${props => props.theme.colors.text.secondary};
  text-decoration: none;

  &.active {
    color: ${props => props.theme.colors.primary.main};
  }
`;

const BottomNavLabel = styled.span`
  font-size: ${props => props.theme.typography.fontSize.xs};
  margin-top: 2px;
`;

const DesktopNav = styled.nav`
  display: flex;
  gap: ${props => props.theme.spacing.md};
`;

const DesktopNavLink = styled(NavLink)`
  display: flex;
  align-items: center;
  gap: ${props => props.theme.spacing.sm};
  padding: ${props => props.theme.spacing.sm} ${props => props.theme.spacing.md};
  color: ${props => props.theme.colors.text.primary};
  text-decoration: none;
  border-radius: 8px;
  transition: all 0.2s;

  &:hover {
    background: ${props => props.theme.colors.background.paper};
  }

  &.active {
    background: ${props => props.theme.colors.primary.light};
    color: ${props => props.theme.colors.primary.main};
  }
`;
```

### 4. Performance Optimizations

#### 4.1 Code Splitting and Lazy Loading
```tsx
// frontend/src/App.tsx
import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ErrorBoundary } from './components/errors/ErrorBoundary';
import { LoadingFallback } from './components/feedback/LoadingFallback';

// Lazy load route components
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Metrics = lazy(() => import('./pages/Metrics'));
const Calendar = lazy(() => import('./pages/Calendar'));
const Settings = lazy(() => import('./pages/Settings'));
const Todos = lazy(() => import('./pages/Todos'));
const Projects = lazy(() => import('./pages/Projects'));

export const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Suspense fallback={<LoadingFallback />}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/metrics" element={<Metrics />} />
            <Route path="/calendar" element={<Calendar />} />
            <Route path="/todos" element={<Todos />} />
            <Route path="/projects" element={<Projects />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ErrorBoundary>
  );
};
```

#### 4.2 Virtual Scrolling for Large Lists
```tsx
// frontend/src/components/optimized/VirtualList.tsx
import React, { useCallback, useRef } from 'react';
import { VariableSizeList as List } from 'react-window';
import AutoSizer from 'react-virtualized-auto-sizer';
import styled from 'styled-components';

interface VirtualListProps<T> {
  items: T[];
  itemHeight: number | ((index: number) => number);
  renderItem: (item: T, index: number) => React.ReactNode;
  overscan?: number;
}

export function VirtualList<T>({
  items,
  itemHeight,
  renderItem,
  overscan = 5
}: VirtualListProps<T>) {
  const listRef = useRef<List>(null);

  const getItemSize = useCallback(
    (index: number) => {
      if (typeof itemHeight === 'function') {
        return itemHeight(index);
      }
      return itemHeight;
    },
    [itemHeight]
  );

  const Row = useCallback(
    ({ index, style }) => {
      return (
        <div style={style}>
          {renderItem(items[index], index)}
        </div>
      );
    },
    [items, renderItem]
  );

  return (
    <ListContainer>
      <AutoSizer>
        {({ height, width }) => (
          <List
            ref={listRef}
            height={height}
            width={width}
            itemCount={items.length}
            itemSize={getItemSize}
            overscanCount={overscan}
          >
            {Row}
          </List>
        )}
      </AutoSizer>
    </ListContainer>
  );
}

const ListContainer = styled.div`
  flex: 1;
  height: 100%;
`;
```

This comprehensive frontend improvement guide addresses all critical UI/UX issues identified in the audit, including accessibility compliance, user feedback mechanisms, mobile responsiveness, and performance optimizations.