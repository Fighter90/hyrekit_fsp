import { afterEach, describe, expect, it, vi } from 'vitest'
import { Suspense } from 'react'
import { render, screen } from '@testing-library/react'
import ErrorBoundary from '../components/ErrorBoundary'
import { isChunkError, lazyPage, reloadOnce } from '../lib/lazyPage'

const reload = vi.fn()

afterEach(() => {
  sessionStorage.clear()
  reload.mockReset()
  vi.unstubAllGlobals()
})

function stubReload() {
  vi.stubGlobal('location', { ...window.location, reload })
}

describe('lazyPage', () => {
  it('распознаёт ошибку загрузки чанка', () => {
    expect(isChunkError(new TypeError('Failed to fetch dynamically imported module: /assets/A-1.js'))).toBe(true)
    expect(isChunkError(new TypeError('Importing a module script failed.'))).toBe(true)
    expect(isChunkError(new Error('boom'))).toBe(false)
  })

  it('перезагружает вкладку только один раз подряд', () => {
    stubReload()
    expect(reloadOnce()).toBe(true)
    expect(reloadOnce()).toBe(false)
    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('устаревший чанк — перезагрузка вместо ошибки', async () => {
    stubReload()
    const Page = lazyPage(() => Promise.reject(new TypeError('Failed to fetch dynamically imported module: /assets/X.js')))
    render(
      <ErrorBoundary>
        <Suspense fallback={<p>загрузка</p>}>
          <Page />
        </Suspense>
      </ErrorBoundary>,
    )
    await vi.waitFor(() => expect(reload).toHaveBeenCalledTimes(1))
    expect(screen.getByText('загрузка')).toBeInTheDocument()
  })

  it('повторная ошибка после перезагрузки уходит в ErrorBoundary', async () => {
    stubReload()
    sessionStorage.setItem('hyrekit:chunk-reload', '1')
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const Page = lazyPage(() => Promise.reject(new TypeError('Failed to fetch dynamically imported module: /assets/X.js')))
    render(
      <ErrorBoundary>
        <Suspense fallback={<p>загрузка</p>}>
          <Page />
        </Suspense>
      </ErrorBoundary>,
    )
    expect(await screen.findByText('Что-то пошло не так')).toBeInTheDocument()
    expect(reload).not.toHaveBeenCalled()
  })

  it('успешная загрузка снимает отметку перезагрузки', async () => {
    sessionStorage.setItem('hyrekit:chunk-reload', '1')
    const Page = lazyPage(() => Promise.resolve({ default: () => <p>страница</p> }))
    render(
      <Suspense fallback={null}>
        <Page />
      </Suspense>,
    )
    expect(await screen.findByText('страница')).toBeInTheDocument()
    expect(sessionStorage.getItem('hyrekit:chunk-reload')).toBeNull()
  })
})
