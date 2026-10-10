import { useLocation } from 'react-router-dom'
import { APP_BUILT_AT, versionLabel } from '../../lib/version'
import { formatDateTime } from '../../lib/format'

/**
 * Версия hyrekit.ru в левом нижнем углу. На публичных страницах — закреплённая подпись;
 * в кабинете (inline) — строка внизу боковой панели, чтобы не перекрывать «Выйти».
 */
export default function VersionTag({ inline = false }: { inline?: boolean }) {
  const { pathname } = useLocation()
  if (!inline && pathname.startsWith('/app')) return null
  return (
    <div className={inline ? 'app-version app-version--inline' : 'app-version'} title={`Сборка ${formatDateTime(APP_BUILT_AT)}`}>
      HyreKit {versionLabel()}
    </div>
  )
}
