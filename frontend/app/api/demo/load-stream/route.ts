import { NextRequest, NextResponse } from 'next/server'
import { buildRecordedStreamEnvelope } from '@/lib/demo/streams/recorded-stream'

export const runtime = 'nodejs'

export async function GET(request: NextRequest) {
  const url = new URL(request.url)
  const limit = Number(url.searchParams.get('limit') ?? '48')
  const tick = Number(url.searchParams.get('tick') ?? '0')

  try {
    const payload = await buildRecordedStreamEnvelope(
      Number.isFinite(limit) ? limit : 48,
      Number.isFinite(tick) ? tick : 0
    )

    return NextResponse.json(payload, {
      headers: {
        'Cache-Control': 'no-store',
      },
    })
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'Failed to load recorded parquet stream',
      },
      { status: 500 }
    )
  }
}
