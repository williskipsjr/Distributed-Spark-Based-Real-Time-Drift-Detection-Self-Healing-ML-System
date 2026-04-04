'use client'

import { ReactNode } from 'react'
import { ThemeProvider } from 'next-themes'
import { QueryClientProvider, QueryClient } from '@tanstack/react-query'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 30, // 30 seconds
      gcTime: 1000 * 60 * 5, // 5 minutes
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
})

export function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ThemeProvider>
  )
}
