import type { ReactNode } from 'react'
import { AuthProvider } from './contexts/AuthContext'
import { CatalogProvider } from './contexts/CatalogContext'
import { ToastProvider } from './contexts/ToastContext'

export default function Providers({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <AuthProvider>
        <CatalogProvider>{children}</CatalogProvider>
      </AuthProvider>
    </ToastProvider>
  )
}
