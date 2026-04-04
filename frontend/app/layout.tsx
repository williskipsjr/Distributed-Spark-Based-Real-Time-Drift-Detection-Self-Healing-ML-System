import type { Metadata } from 'next'
import { Analytics } from '@vercel/analytics/next'
import { Providers } from './providers'
import './globals.css'

export const metadata: Metadata = {
  title: 'ML Analytics Dashboard',
  description: 'Real-time monitoring and control for ML systems',
  generator: 'v0.app',
  icons: {
    icon: [
      {
        url: '/icon-light-32x32.png',
        media: '(prefers-color-scheme: light)',
      },
      {
        url: '/icon-dark-32x32.png',
        media: '(prefers-color-scheme: dark)',
      },
      {
        url: '/icon.svg',
        type: 'image/svg+xml',
      },
    ],
    apple: '/apple-icon.png',
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="font-sans antialiased" suppressHydrationWarning>
        <Providers>
          {children}
        </Providers>
        <Analytics />
      </body>
    </html>
  )
}
