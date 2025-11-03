import Dashboard from './components/Dashboard'
import './App.css'

function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>ERAS - Emergency Response Assistance System</h1>
      </header>
      <main className="app-main">
        <Dashboard />
      </main>
    </div>
  )
}

export default App

