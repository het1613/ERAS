import { BrowserRouter, Routes, Route } from "react-router-dom";
import Dashboard from "./components/Dashboard";
import Caller from "./components/Caller";
import CallTaker from "./components/CallTaker";
import PastCases from "./components/PastCases";
import NavBar from "./components/NavBar";
import TestResultsModal from "./components/TestResultsModal";
import TestConsentModal from "./components/TestConsentModal";
import TlxSurveyModal from "./components/TlxSurveyModal";
import { WebSocketProvider } from "./contexts/WebSocketContext";
import { DispatchTestProvider } from "./contexts/DispatchTestContext";
import "./App.css";

function App() {
	return (
		<BrowserRouter>
			<WebSocketProvider>
				<DispatchTestProvider>
					<div className="app">
						<NavBar />
						<main className="app-main">
							<Routes>
								<Route path="/" element={<Dashboard />} />
								<Route path="/caller" element={<Caller />} />
								<Route path="/call-taker" element={<CallTaker />} />
								<Route path="/past-cases" element={<PastCases />} />
							</Routes>
						</main>
					</div>
					<TestConsentModal />
					<TlxSurveyModal />
					<TestResultsModal />
				</DispatchTestProvider>
			</WebSocketProvider>
		</BrowserRouter>
	);
}

export default App;
