import { NextRequest, NextResponse } from 'next/server'
import { buildRecordedDriftResponse } from '@/lib/demo/streams/recorded-drift'

export const runtime = 'nodejs'

export async function GET(request: NextRequest) {
  const url = new URL(request.url)
  const tick = Number(url.searchParams.get('tick') ?? '0')

  try {
    const payload = await buildRecordedDriftResponse(Number.isFinite(tick) ? tick : 0)

    return NextResponse.json(payload, {
      headers: {
        'Cache-Control': 'no-store',
      },
    })
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'Failed to load recorded drift stream',
      },
      { status: 500 }
    )
  }
}
