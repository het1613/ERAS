import { BrowserRouter, Routes, Route } from "react-router-dom";
import Dashboard from "./components/Dashboard";
import Caller from "./components/Caller";
import CallTaker from "./components/CallTaker";
import { WebSocketProvider } from "./contexts/WebSocketContext";
import "./App.css";

function App() {
	return (
		<BrowserRouter>
			<WebSocketProvider>
				<div className="app">
					<main className="app-main">
						<Routes>
							<Route path="/" element={<Dashboard />} />
							<Route path="/caller" element={<Caller />} />
							<Route path="/call-taker" element={<CallTaker />} />
						</Routes>
					</main>
				</div>
			</WebSocketProvider>
		</BrowserRouter>
	);
}

export default App;
