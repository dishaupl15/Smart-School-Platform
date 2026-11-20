import { Component, type ErrorInfo, type ReactNode } from "react";
import { Trans } from "react-i18next";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Application rendering failed.", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="error-screen">
          <h1>
            <Trans i18nKey="errors.unexpectedTitle" />
          </h1>
          <p>
            <Trans i18nKey="errors.unexpectedBody" />
          </p>
        </main>
      );
    }

    return this.props.children;
  }
}
