import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Dashboard } from "@/pages/Dashboard"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 10000,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Dashboard />
    </QueryClientProvider>
  )
}

export default App
