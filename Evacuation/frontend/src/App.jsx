import React, { useState, useEffect } from 'react';
import MapVisualizer from './MapVisualizer';
import { Flame, Users, Truck, Clock, AlertTriangle, Crosshair, ShieldAlert, CheckCircle2, Siren, Zap, Satellite, Globe, Activity, Mail, RefreshCw, CheckCircle, XCircle } from 'lucide-react';
import './App.css';

function App() {
  const [incidents, setIncidents] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState('Disconnected');
  const [emailStatuses, setEmailStatuses] = useState({
    fire: { status: 'idle', message: 'Waiting...', recipient: 'sarveshbala27@gmail.com', name: 'Fire Dept' },
    ambulance: { status: 'idle', message: 'Waiting...', recipient: 'barathrithish7@gmail.com', name: 'Ambulance' },
    rescue: { status: 'idle', message: 'Waiting...', recipient: 'balasarveshk@gmail.com', name: 'Rescue' }
  });

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/dashboard');
    ws.onopen = () => setConnectionStatus('Connected');
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === 'INCIDENT') {
          setIncidents((prev) => [payload.data, ...prev]);
        } else if (payload.type === 'EMAIL_STATUS') {
          setEmailStatuses((prev) => ({
            ...prev,
            [payload.dept_id]: {
              ...prev[payload.dept_id],
              status: payload.status,
              message: payload.message,
              timestamp: payload.timestamp
            }
          }));
        } else {
          // Fallback for older raw messages
          setIncidents((prev) => [payload, ...prev]);
        }
      } catch (e) {
        console.error("Failed to parse websocket message", e);
      }
    };
    ws.onclose = () => setConnectionStatus('Disconnected');
    return () => ws.close();
  }, []);

  const latestIncident = incidents[0] || null;

  // Mock Premium KPIs
  const activeFireArea = latestIncident ? (latestIncident.hazard_telemetry.rate_of_spread_kmh * 2.3).toFixed(1) + ' ha' : '--';
  const popAtRisk = latestIncident ? latestIncident.target_zone.estimated_population.toLocaleString() : '--';
  const unitsDeployed = latestIncident ? 27 : '--';
  const remainingTime = latestIncident ? latestIncident.hazard_telemetry.time_to_impact_mins + ' mins' : '--';

  const renderEmailIcon = (status) => {
    if (status === 'success') return <CheckCircle size={18} className="text-green" />;
    if (status === 'failed') return <XCircle size={18} className="text-red" />;
    if (status === 'pending' || status === 'retrying') return <RefreshCw size={18} className="spin text-blue" />;
    return <Mail size={18} className="text-gray" />;
  };

  const getWorkflowClass = (step) => {
    if (!latestIncident) return 'wf-step';
    const anySuccess = Object.values(emailStatuses).some(e => e.status === 'success');
    const anyPending = Object.values(emailStatuses).some(e => e.status === 'pending' || e.status === 'retrying');
    
    if (step <= 3) return 'wf-step active'; // Detection, AI, Prediction
    if (step === 4) return (anySuccess ? 'wf-step active' : (anyPending ? 'wf-step processing' : 'wf-step')); // Emails
    if (step === 5 && emailStatuses.fire.status === 'success') return 'wf-step active';
    if (step === 6 && emailStatuses.ambulance.status === 'success') return 'wf-step active';
    if (step === 7 && emailStatuses.rescue.status === 'success') return 'wf-step active';
    if (step === 8 && anySuccess) return 'wf-step active'; // Live Monitoring
    return 'wf-step';
  };

  return (
    <div className="dashboard-wrapper">
      {/* HEADER BAR */}
      <header className="dash-header">
        <div className="dash-title">
          <Globe className="icon-pulse" size={28} />
          <h1>guesin.AI</h1>
        </div>
        <div className="dash-controls">
          <div className="toggle-btn"><Satellite size={16} /> Satellite Mode</div>
          <div className={`status-badge ${connectionStatus.toLowerCase()}`}>
            <Activity size={14} /> {connectionStatus}
          </div>
          <div className="last-updated">
            Last Updated: {latestIncident ? 'Just now' : 'Waiting...'}
          </div>
        </div>
      </header>

      {/* KPI STRIP */}
      <div className="kpi-strip">
        <div className="kpi-card">
          <div className="kpi-icon-wrap bg-red"><Flame size={24} color="#dc2626" /></div>
          <div className="kpi-data">
            <span className="kpi-label">Active Fire</span>
            <span className="kpi-value">{activeFireArea}</span>
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon-wrap bg-orange"><Users size={24} color="#ea580c" /></div>
          <div className="kpi-data">
            <span className="kpi-label">Population at Risk</span>
            <span className="kpi-value">{popAtRisk}</span>
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon-wrap bg-blue"><Truck size={24} color="#2563eb" /></div>
          <div className="kpi-data">
            <span className="kpi-label">Units Deployed</span>
            <span className="kpi-value">{unitsDeployed}</span>
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-icon-wrap bg-gray"><Clock size={24} color="#4b5563" /></div>
          <div className="kpi-data">
            <span className="kpi-label">Remaining Time</span>
            <span className="kpi-value">{remainingTime}</span>
          </div>
        </div>
      </div>

      {/* WORKFLOW PIPELINE */}
      <div className="workflow-pipeline glass-panel">
        <div className={getWorkflowClass(1)}>🔥 Detection</div><div className="wf-arrow">→</div>
        <div className={getWorkflowClass(2)}>🧠 AI Analysis</div><div className="wf-arrow">→</div>
        <div className={getWorkflowClass(3)}>📍 Prediction</div><div className="wf-arrow">→</div>
        <div className={getWorkflowClass(4)}>📧 Emails Sent</div><div className="wf-arrow">→</div>
        <div className={getWorkflowClass(5)}>🚒 Fire</div><div className="wf-arrow">→</div>
        <div className={getWorkflowClass(6)}>🚑 Medical</div><div className="wf-arrow">→</div>
        <div className={getWorkflowClass(7)}>🚓 Rescue</div><div className="wf-arrow">→</div>
        <div className={getWorkflowClass(8)}>🗺️ Live Monitoring</div>
      </div>

      {/* EMERGENCY DISPATCH STATUS */}
      {latestIncident && (
        <div className="dispatch-status-section">
          <h3>Emergency Dispatch Status</h3>
          <div className="dispatch-grid">
            {Object.entries(emailStatuses).map(([key, data]) => (
              <div key={key} className={`dispatch-card status-${data.status}`}>
                <div className="dc-header">
                  <h4>{data.name}</h4>
                  <div className={`dc-badge ${data.status}`}>
                    {renderEmailIcon(data.status)}
                    <span>{data.status === 'success' ? 'Email Sent' : data.status.toUpperCase()}</span>
                  </div>
                </div>
                <div className="dc-body">
                  <p><b>To:</b> {data.recipient}</p>
                  <p><b>Status:</b> {data.message}</p>
                  {data.timestamp && <p className="dc-time">Updated: {new Date(data.timestamp).toLocaleTimeString()}</p>}
                </div>
                {data.status === 'failed' && (
                  <button className="retry-btn">Retry Dispatch</button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* MAIN GRID */}
      <main className="dash-grid">
        {/* LEFT COLUMN: EMERGENCY DETAILS */}
        <section className="left-panel">
          {latestIncident ? (
            <div className="alert-banner">
              <div className="alert-header">
                <AlertTriangle size={36} className="alert-pulse" color="#dc2626" />
                <h2>CRITICAL MAYDAY AUTONOMOUS</h2>
              </div>
              <div className="alert-metrics">
                <div className="metric"><Zap size={16}/> <b>Status:</b> LIVE INCIDENT</div>
                <div className="metric"><Flame size={16}/> <b>Severity:</b> EXTREME</div>
                <div className="metric"><Crosshair size={16}/> <b>Target:</b> {latestIncident.target_zone.settlement_name}</div>
                <div className="metric"><Clock size={16}/> <b>ETA:</b> {latestIncident.hazard_telemetry.time_to_impact_mins} mins</div>
                <div className="metric"><ShieldAlert size={16}/> <b>Risk Score:</b> 97%</div>
                <div className="metric"><CheckCircle2 size={16}/> <b>Confidence:</b> {(latestIncident.hazard_telemetry.confidence_coefficient * 100).toFixed(0)}%</div>
              </div>
            </div>
          ) : (
             <div className="alert-banner placeholder">
                <h2>No Active Mayday Triggers</h2>
                <p>System is monitoring for catastrophic thresholds.</p>
             </div>
          )}

          {latestIncident && (
            <div className="agencies-section">
              <h3>Live Agency Operations</h3>
              
              <div className="agency-detailed-card glass">
                <div className="ac-header">
                  <div className="ac-title"><Flame size={20} color="#dc2626"/> <h4>Fire Department</h4></div>
                  <span className="ac-badge badge-working">🟡 Working on Site</span>
                </div>
                <div className="ac-body">
                  <div className="ac-stat"><span>Crew:</span> 4 Units</div>
                  <div className="ac-stat"><span>ETA:</span> Arrived</div>
                </div>
                <div className="ac-progress">
                  <div className="ac-progress-text"><span>Progress</span><span>82%</span></div>
                  <div className="ac-progress-bar"><div className="ac-progress-fill" style={{width: '82%', backgroundColor: '#f59e0b'}}></div></div>
                </div>
              </div>

              <div className="agency-detailed-card glass">
                <div className="ac-header">
                  <div className="ac-title"><Siren size={20} color="#2563eb"/> <h4>Medical Team</h4></div>
                  <span className="ac-badge badge-enroute">🔵 En Route</span>
                </div>
                <div className="ac-body">
                  <div className="ac-stat"><span>Ambulances:</span> 3</div>
                  <div className="ac-stat"><span>ETA:</span> 6 mins</div>
                </div>
              </div>

              <div className="agency-detailed-card glass">
                <div className="ac-header">
                  <div className="ac-title"><ShieldAlert size={20} color="#16a34a"/> <h4>Police & Rescue</h4></div>
                  <span className="ac-badge badge-secure">🟢 Securing Area</span>
                </div>
                <div className="ac-body">
                  <div className="ac-stat"><span>Units:</span> 5</div>
                  <div className="ac-stat"><span>Road Blocks:</span> Established</div>
                </div>
              </div>

            </div>
          )}
        </section>

        {/* RIGHT COLUMN: MAP */}
        <section className="right-panel">
          <MapVisualizer incidentData={latestIncident} />
        </section>
      </main>
    </div>
  );
}

export default App;
