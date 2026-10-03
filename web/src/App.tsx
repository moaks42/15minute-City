import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { TooltipProvider } from '@/components/ui/tooltip'
import { CityPicker } from '@/components/onboarding/CityPicker'
import { Wizard } from '@/components/onboarding/Wizard'
import { AboutPage } from '@/pages/AboutPage'
import { ResultsPage } from '@/pages/ResultsPage'
import { useApp } from '@/state/store'

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } })

function Router() {
  const { city, view, step } = useApp()
  if (!city) return <CityPicker />
  if (view === 'about') return <AboutPage />
  if (step !== 'results') return <Wizard />
  return <ResultsPage />
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <TooltipProvider>
        <Router />
      </TooltipProvider>
    </QueryClientProvider>
  )
}
