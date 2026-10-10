import { lazy, type ComponentType } from 'react'

const RELOAD_KEY = 'hyrekit:chunk-reload'

/** Ошибка загрузки чанка: вкладка открыта до выкладки, старых файлов на сервере уже нет. */
export function isChunkError(err: unknown): boolean {
  const msg = err instanceof Error ? `${err.name} ${err.message}` : String(err)
  return /dynamically imported module|Importing a module script failed|ChunkLoadError|Loading chunk|error loading dynamically/i.test(msg)
}

/** Перезагрузить страницу один раз за выкладку; вторая ошибка подряд уходит в ErrorBoundary. */
export function reloadOnce(): boolean {
  try {
    if (sessionStorage.getItem(RELOAD_KEY)) return false
    sessionStorage.setItem(RELOAD_KEY, '1')
  } catch {
    return false
  }
  window.location.reload()
  return true
}

/** Успешная загрузка снимает отметку, чтобы следующая выкладка тоже обновила вкладку. */
function loaded() {
  try {
    sessionStorage.removeItem(RELOAD_KEY)
  } catch {
    /* хранилище недоступно — не страшно */
  }
}

/**
 * `React.lazy` с восстановлением после выкладки: если чанк страницы не найден,
 * вкладка перезагружается и получает свежий index.html с новыми именами файлов.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- то же ограничение типа, что у React.lazy
export function lazyPage<T extends ComponentType<any>>(load: () => Promise<{ default: T }>) {
  return lazy(() =>
    load().then(
      (mod) => {
        loaded()
        return mod
      },
      (err: unknown) => {
        if (isChunkError(err) && reloadOnce()) return new Promise<{ default: T }>(() => {})
        throw err
      },
    ),
  )
}
