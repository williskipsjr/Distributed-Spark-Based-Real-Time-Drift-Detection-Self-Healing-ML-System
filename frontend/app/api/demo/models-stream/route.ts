import { NextRequest, NextResponse } from 'next/server'
import { buildRecordedModelsResponse } from '@/lib/demo/recorded-models'

export const runtime = 'nodejs'

export async function GET(_: NextRequest) {
  try {
    const payload = await buildRecordedModelsResponse()

    return NextResponse.json(payload, {
      headers: {
        'Cache-Control': 'no-store',
      },
    })
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'Failed to load recorded model registry',
      },
      { status: 500 }
    )
  }
}
