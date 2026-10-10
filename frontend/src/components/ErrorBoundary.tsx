import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary:', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="fatal">
        <div className="fatal__glyph" aria-hidden>{'{ ! }'}</div>
        <h2 className="display-sm">Что-то пошло не так</h2>
        <p className="muted">Произошла непредвиденная ошибка. Обновите страницу — данные не потеряются.</p>
        <div className="row gap-sm center">
          <button className="btn btn--primary" onClick={() => window.location.reload()}>
            Обновить страницу
          </button>
          <a className="btn btn--ghost" href="/">На главную</a>
        </div>
        <details className="fatal__details">
          <summary>Детали ошибки</summary>
          <pre>{this.state.error.message}</pre>
        </details>
      </div>
    )
  }
}
