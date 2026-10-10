/** Версия сборки фронтенда: подставляется Vite при сборке (vite.config.ts). */
export const APP_VERSION = __APP_VERSION__
export const APP_COMMIT = __APP_COMMIT__
export const APP_BUILT_AT = __APP_BUILT_AT__

/** «v0.1.0 · a7b191c» */
export function versionLabel(version = APP_VERSION, commit = APP_COMMIT): string {
  return commit && commit !== 'dev' ? `v${version} · ${commit}` : `v${version}`
}
