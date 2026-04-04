'use client'

import { useEffect, useState } from 'react'
import HomeClient from './home-client'

export default function Home() {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    return <div className="min-h-screen bg-background" suppressHydrationWarning />
  }

  return <HomeClient />
}
