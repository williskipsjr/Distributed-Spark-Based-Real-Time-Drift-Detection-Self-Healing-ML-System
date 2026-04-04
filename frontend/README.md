# ML Analytics Dashboard

A real-time monitoring and control dashboard for ML systems with data drift detection, system health monitoring, and service management capabilities.

## Features

### Phase A (Implemented)

#### 1. **Overview Dashboard**
- Key performance indicators (KPIs) for model metrics
- Real-time system health status
- Actual vs Predicted values chart
- Active model information
- Model accuracy tracking

#### 2. **Drift Detection**
- Real-time drift detection status
- Feature-level drift analysis
- Drift score timeline visualization
- Drifted features count tracking
- Historical drift data

#### 3. **System Health Monitoring**
- Overall system status tracking
- Component health status
- Component-level messages and timestamps
- Health summary statistics

#### 4. **Service Control**
- Service management (start, stop, restart)
- Pipeline control (start, stop)
- Dry-run mode (enabled by default)
- Service logs display
- Production mode confirmation dialogs
- Real-time status updates
- Action result notifications

## Setup Instructions

### Prerequisites
- Node.js 18+
- npm or pnpm

### Installation

1. **Clone or download the project:**
   ```bash
   git clone <repository-url>
   cd ml-analytics-dashboard
   ```

2. **Install dependencies:**
   ```bash
   pnpm install
   # or
   npm install
   ```

3. **Configure environment variables:**
   Copy `.env.example` to `.env.local`:
   ```bash
   cp .env.example .env.local
   ```

   Edit `.env.local` with your API configuration:
   ```env
   NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
   NEXT_PUBLIC_CONTROL_API_KEY=your-api-key-here
   ```

### Running the Application

**Development mode:**
```bash
pnpm dev
```

The dashboard will be available at `http://localhost:3000`

**Production build:**
```bash
pnpm build
pnpm start
```

## Project Structure

```
app/
├── dashboard/
│   ├── layout.tsx          # Dashboard layout with navigation
│   ├── overview/page.tsx   # Overview dashboard
│   ├── drift/page.tsx      # Drift detection
│   ├── health/page.tsx     # System health
│   └── control/page.tsx    # Service control
├── providers.tsx           # React Query & Theme providers
├── layout.tsx              # Root layout
└── page.tsx                # Root redirect

lib/
├── api/
│   ├── client.ts           # API client with envelope handling
│   ├── types.ts            # Zod schemas for all responses
│   └── hooks.ts            # React Query hooks for data fetching

components/
└── dashboard/
    ├── status-badge.tsx    # Status indicator component
    ├── kpi-card.tsx        # KPI card component
    ├── timestamp.tsx       # Formatted timestamp component
    ├── error-state.tsx     # Error handling component
    └── skeleton.tsx        # Loading skeleton components
```

## API Integration

The dashboard connects to ML system APIs with the following endpoints:

### Read Endpoints (30-second polling)
- `GET /read/summary` - System summary
- `GET /read/predictions` - Model predictions with actual values
- `GET /read/drift/current` - Current drift detection status
- `GET /read/drift/history` - Historical drift data
- `GET /read/system/health` - System component health
- `GET /read/models/active` - Active model information
- `GET /read/models/versions` - Model version history
- `GET /read/self-healing/status` - Self-healing decisions

### Control Endpoints (10-second polling)
- `GET /control/services` - List services and status
- `POST /control/services/{service}/start` - Start service
- `POST /control/services/{service}/stop` - Stop service
- `POST /control/services/{service}/restart` - Restart service
- `GET /control/services/{service}/logs` - Service logs
- `POST /control/pipeline/start` - Start pipeline
- `POST /control/pipeline/stop` - Stop pipeline

All responses are wrapped in a standard envelope:
```json
{
  "generated_at": "2024-01-01T12:00:00Z",
  "data_as_of": "2024-01-01T12:00:00Z",
  "stale_after_seconds": 30,
  "is_stale": false,
  "source_status": "ok",
  "data": { ... }
}
```

## Control Page Safety Features

- **Dry-Run Mode (Default)**: All control actions default to dry-run, simulating changes without executing them
- **Production Mode Toggle**: Switch to production mode for actual execution
- **Confirmation Dialogs**: Require explicit confirmation for all actions in production mode
- **Action Results**: Toast notifications display action success/failure
- **Auto-Refresh**: Status and logs automatically refresh after actions
- **Service Logs**: View real-time service logs for debugging

## Architecture

### Technology Stack
- **Framework**: Next.js 16.2 with App Router
- **State Management**: TanStack React Query (30s/10s polling)
- **Data Validation**: Zod schemas
- **UI Components**: shadcn/ui components
- **Charts**: Recharts
- **Styling**: Tailwind CSS
- **Theme**: next-themes (Dark mode by default)

### Data Flow
1. API client fetches data with automatic envelope validation
2. React Query manages caching, polling, and synchronization
3. Components consume data via custom hooks
4. UI updates in real-time as data refreshes

## Dark Mode

The dashboard comes with dark mode enabled by default. Theme switching is automatically configured through `next-themes`.

## Responsive Design

The dashboard is fully responsive:
- Mobile: Single column with collapsible sidebar
- Tablet: Multi-column layouts
- Desktop: Full-width layouts with expanded visualizations

## Error Handling

- Network errors display user-friendly error states
- Failed API requests show retry options
- Invalid data is caught by Zod validation
- Control actions provide detailed error feedback

## Phase B (Upcoming)

- Models page (active model details + versions history)
- Self-Healing page (decision tracking + history)
- Advanced polish and animations
- Performance optimizations
- Additional customization options

## Notes

- API Base URL defaults to `http://127.0.0.1:8000` if not configured
- Control API Key is optional but required for service control actions
- All timestamps are converted to local timezone for display
- Polling intervals: Read endpoints (30s), Control endpoints (10s)
- Stale data detection based on `stale_after_seconds` envelope field

## Troubleshooting

**"Failed to connect to API"**
- Check that `NEXT_PUBLIC_API_BASE_URL` is correctly configured
- Verify the API service is running and accessible
- Check browser console for CORS errors

**"Control actions not working"**
- Ensure `NEXT_PUBLIC_CONTROL_API_KEY` is set correctly
- Verify API authentication is properly configured
- Check that dry-run mode is disabled for production actions

**"Data not updating"**
- Check browser's Network tab for API requests
- Verify API responses include the required envelope fields
- Check that polling interval timings align with API capabilities

## Support

For issues or questions, check the implementation details in the source code or contact your system administrator.
