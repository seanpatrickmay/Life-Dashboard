import { Component, type ErrorInfo, type ReactNode } from 'react';

type Props = {
  children: ReactNode;
};

type State = {
  hasError: boolean;
};

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack);
  }

  private handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '200px',
            gap: '16px',
            padding: '32px',
            textAlign: 'center',
            color: 'rgba(43,27,19,0.8)',
          }}
        >
          <p style={{ fontSize: '1rem', margin: 0 }}>
            Something went wrong. Please try reloading the page.
          </p>
          <button
            type="button"
            onClick={this.handleReload}
            style={{
              padding: '8px 20px',
              fontSize: '0.85rem',
              borderRadius: '8px',
              border: '1px solid rgba(43,27,19,0.2)',
              background: 'transparent',
              cursor: 'pointer',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
            }}
          >
            Reload
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
