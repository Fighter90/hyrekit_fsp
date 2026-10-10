import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from '../api/client'
import type { Catalog } from '../api/types'
import { gradeLabel } from '../lib/format'

interface CatalogContextType {
  catalog: Catalog | null
  error: string | null
  specTitle: (code: string | null | undefined) => string
  industryTitle: (code: string | null | undefined) => string
  gradeTitle: (code: string | null | undefined) => string
}

const CatalogContext = createContext<CatalogContextType | null>(null)

/** Справочник загружается один раз и кешируется на всё приложение. */
export function CatalogProvider({ children }: { children: ReactNode }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.catalog().then(setCatalog).catch((e: unknown) => {
      setError(e instanceof Error ? e.message : 'Справочник недоступен')
    })
  }, [])

  const value = useMemo<CatalogContextType>(() => {
    const find = <T extends { code: string; title: string }>(list: T[] | undefined, code: string | null | undefined) =>
      code ? list?.find((x) => x.code === code)?.title ?? code : '—'
    return {
      catalog,
      error,
      specTitle: (c) => find(catalog?.specializations, c),
      industryTitle: (c) => find(catalog?.industries, c),
      gradeTitle: (c) => (c ? catalog?.grades.find((g) => g.code === c)?.title ?? gradeLabel(c) : '—'),
    }
  }, [catalog, error])

  return <CatalogContext.Provider value={value}>{children}</CatalogContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useCatalog() {
  const ctx = useContext(CatalogContext)
  if (!ctx) throw new Error('useCatalog must be used within CatalogProvider')
  return ctx
}
