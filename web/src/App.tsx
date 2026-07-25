import { useState, useRef, useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import './index.css';

interface Message {
  role: 'user' | 'ai';
  content: string;
}

interface ToolInfo {
  name: string;
  category: string;
  icon: string;
  description: string;
}

interface DaemonStatus {
  state: string;
  stale?: boolean;
  age_seconds?: number;
  wake_word?: {
    state: string;
    backend?: string | null;
    detections?: number;
    last_detected_at?: string | null;
    detail?: string | null;
  };
  websocket?: {
    state: string;
    reconnect_attempts?: number;
  };
  services?: Record<string, { state: string; restart_count?: number }>;
  voice?: {
    state: string;
    wake_phrase?: string;
    conversation_active?: boolean;
    partial_transcript?: string;
    transcript?: string | null;
    response_text?: string;
    interruption_count?: number;
    detail?: string | null;
  };
}

interface PlannerStatus {
  active?: {
    status: string;
    intent: string;
    steps: Array<{ status: string }>;
  } | null;
  known_plans?: number;
}

interface SysStatus {
  status: string;
  model: string;
  os: string;
  python: string;
  cpu_cores: number;
  cpu_percent: number;
  mem_used_gb: number;
  mem_total_gb: number;
  mem_percent: number;
  uptime: string;
  tool_count: number;
  daemon?: DaemonStatus;
  planner?: PlannerStatus;
}

interface ProjectFile {
  name: string;
  path: string;
  type: string;
}

const API = 'http://127.0.0.1:8001';

// Preset files for explorer view
const PROJECT_FILES: ProjectFile[] = [
  { name: 'server.py', path: 'server.py', type: 'Python' },
  { name: 'api.py', path: 'api.py', type: 'Python' },
  { name: 'pyproject.toml', path: 'pyproject.toml', type: 'Config' },
  { name: 'web/src/App.tsx', path: 'web/src/App.tsx', type: 'React' },
  { name: 'web/src/index.css', path: 'web/src/index.css', type: 'CSS' }
];

export default function App() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'terminal' | 'tools' | 'memory' | 'files'>('dashboard');
  const [messages, setMessages] = useState<Message[]>([
    { role: 'ai', content: '**VEGAS OS — Subsystems operational.**\n\nAll core capabilities are exposed in the registry. Connect workspace tools, execute sandbox runs, or query persistent facts from the left sidebar or the direct chat tab.' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [memLoading, setMemLoading] = useState(false);
  const [resetLoading, setResetLoading] = useState(false);
  const [sys, setSys] = useState<SysStatus | null>(null);
  const [daemonStatus, setDaemonStatus] = useState<DaemonStatus | null>(null);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Memory Panel State
  const [memFact, setMemFact] = useState('');
  const [memQuery, setMemQuery] = useState('');
  const [memDisplay, setMemDisplay] = useState('Perform a search or save a fact to inspect memory values here.');

  // CPU and Memory history state (for live SVG graphs)
  const [cpuHistory, setCpuHistory] = useState<number[]>(new Array(20).fill(0));
  const [memHistory, setMemHistory] = useState<number[]>(new Array(20).fill(0));

  // Console output log simulation
  const [consoleLines, setConsoleLines] = useState<string[]>([
    'VEGAS OS Kernel Version 2.0.0 Initializing...',
    'Mounting sandboxed file structures...',
    'Loading custom Python execution environments...',
    'Registering tool components onto memory map...',
    'Core runtime established. Host connection: nominal.'
  ]);

  // Sandboxed File Explorer State
  const [activeFile, setActiveFile] = useState<ProjectFile>(PROJECT_FILES[0]);
  const [fileContent, setFileContent] = useState('Loading file contents...');

  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Poll system status and collect history
  useEffect(() => {
    const poll = () => {
      fetch(`${API}/api/system-status`)
        .then(r => r.json())
        .then((data: SysStatus) => {
          setSys(data);
          if (data.daemon) setDaemonStatus(data.daemon);
          setCpuHistory(prev => [...prev.slice(-19), data.cpu_percent || 0]);
          setMemHistory(prev => [...prev.slice(-19), data.mem_percent || 0]);
          // Add a random kernel console event for visual fidelity
          const events = [
            `Polling core stats... CPU: ${data.cpu_percent}% | MEM: ${data.mem_percent}%`,
            'SQLite memory pool heartbeat ok',
            'Flushing active event buffer log',
            'Verifying requires_confirmation decorators...'
          ];
          setConsoleLines(prev => [...prev.slice(-30), events[Math.floor(Math.random() * events.length)]]);
        })
        .catch(() => {});
    };
    poll();
    const interval = setInterval(poll, 3000);
    return () => clearInterval(interval);
  }, []);

  // The existing REST poll is retained as a fallback. The daemon status socket
  // gives the dashboard immediate updates and reconnects after API restarts.
  useEffect(() => {
    let socket: WebSocket | null = null;
    let reconnectTimer: number | undefined;
    let attempts = 0;
    let disposed = false;

    const connect = () => {
      if (disposed) return;
      socket = new WebSocket(`${API.replace(/^http/, 'ws')}/api/daemon/status/ws`);
      socket.onmessage = event => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === 'daemon_status' && message.payload) {
            setDaemonStatus(message.payload as DaemonStatus);
            attempts = 0;
          }
        } catch {
          // Polling remains available if an invalid frame is received.
        }
      };
      socket.onerror = () => socket?.close();
      socket.onclose = () => {
        if (disposed) return;
        const delay = Math.min(30_000, 1_000 * 2 ** attempts);
        attempts += 1;
        reconnectTimer = window.setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      disposed = true;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, []);

  const daemon = daemonStatus ?? sys?.daemon ?? null;
  const daemonState = daemon?.state?.toUpperCase() || 'CONNECTING';
  const wakeWordState = daemon?.wake_word?.state?.toUpperCase() || 'UNKNOWN';
  const voiceState = daemon?.voice?.state?.toUpperCase() || 'UNKNOWN';
  const voicePreview = daemon?.voice?.partial_transcript || daemon?.voice?.transcript || daemon?.voice?.detail || 'awaiting Hey Vegas';
  const plannerState = sys?.planner?.active?.status?.toUpperCase() || 'IDLE';
  const plannerIntent = sys?.planner?.active?.intent || 'no active plan';
  const plannerSteps = Array.isArray(sys?.planner?.active?.steps) ? sys.planner.active.steps : [];
  const plannerDone = plannerSteps.filter(step => step && step.status === 'success').length;

  // Fetch tools registry
  useEffect(() => {
    fetch(`${API}/api/tools`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(d => setTools(d.tools || []))
      .catch(() => {});
  }, []);

  // Fetch active file content
  useEffect(() => {
    setFileContent('Fetching file content from backend...');
    fetch(`${API}/api/files/view?path=${encodeURIComponent(activeFile.path)}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(d => {
        setFileContent(d.content || d.error || d.detail || 'No content found.');
      })
      .catch((err) => {
        setFileContent(`Error loading file contents: ${err.message || err}. Make sure api.py is running on port 8001.`);
      });
  }, [activeFile]);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const sendCommand = async (text: string) => {
    if (!text.trim() || loading) return;
    setMessages(prev => [...prev, { role: 'user', content: text }]);
    setLoading(true);
    // Switch to terminal tab when a command is sent so user sees result
    setActiveTab('terminal');
    
    try {
      const res = await fetch(`${API}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });
      const data = await res.json();
      setMessages(prev => [
        ...prev,
        { role: 'ai', content: data.error ? `**Error:** ${data.error}` : data.response }
      ]);
    } catch {
      setMessages(prev => [
        ...prev,
        { role: 'ai', content: '**Connection Error** — Unable to communicate with VEGAS API Backend. Verify port 8001 is active.' }
      ]);
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const handleInputSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    sendCommand(input.trim());
    setInput('');
  };

  const handleResetSession = async () => {
    if (resetLoading) return;
    setResetLoading(true);
    try {
      await fetch(`${API}/api/reset`, { method: 'POST' });
      setMessages([{ role: 'ai', content: '**Terminal session context flushed.** Persistence records are intact.\n\nWhat command shall we execute next?' }]);
    } catch { /* ignore */ }
    finally {
      setResetLoading(false);
    }
  };

  const handleMemoryAction = async (action: 'remember' | 'recall') => {
    const val = action === 'remember' ? memFact : memQuery;
    if (!val.trim() || memLoading) return;
    setMemLoading(true);
    setMemDisplay('Communicating with memory pool...');
    try {
      const ep = action === 'remember' ? '/api/memory/remember' : '/api/memory/recall';
      const body = action === 'remember' ? { fact: val } : { query: val };
      const res = await fetch(`${API}${ep}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      setMemDisplay(data.result);
      if (action === 'remember') setMemFact('');
    } catch {
      setMemDisplay('Error communicating with memory endpoints.');
    } finally {
      setMemLoading(false);
    }
  };

  // Helper to generate SVG polyline path from history array
  const getLinePath = (history: number[]) => {
    const width = 400;
    const height = 150;
    const padding = 10;
    if (!history || history.length < 2) {
      return `${padding},${height - padding} ${width - padding},${height - padding}`;
    }
    const xStep = (width - padding * 2) / (history.length - 1);
    
    return history.map((val, idx) => {
      const x = padding + idx * xStep;
      // Invert Y coordinate for SVG
      const y = height - padding - (val / 100) * (height - padding * 2);
      return `${x},${y}`;
    }).join(' ');
  };

  // Memoize SVG polyline path strings
  const cpuLinePath = useMemo(() => getLinePath(cpuHistory), [cpuHistory]);
  const memLinePath = useMemo(() => getLinePath(memHistory), [memHistory]);

  // Filter tools memoized
  const filteredTools = useMemo(() => {
    return tools.filter(t => 
      t.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
      t.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.category.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [tools, searchQuery]);

  return (
    <>
      <div className="hud-grid" />
      <div className="hud-ambient-glow" />
      
      <div className="app-shell">
        {/* ═══════════════ APP SIDEBAR ═══════════════ */}
        <div className="app-sidebar">
          <div className="sidebar-brand">
            <div className="brand-icon-wrapper">V</div>
            <div className="brand-title-wrap">
              <h1>VEGAS OS</h1>
              <span>AI Command Core</span>
            </div>
          </div>

          <div className="sidebar-menu">
            <button 
              className={`menu-item ${activeTab === 'dashboard' ? 'active' : ''}`}
              onClick={() => setActiveTab('dashboard')}
            >
              <svg className="menu-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2v-4zM14 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2v-4z" />
              </svg>
              Dashboard HUD
            </button>

            <button 
              className={`menu-item ${activeTab === 'terminal' ? 'active' : ''}`}
              onClick={() => setActiveTab('terminal')}
            >
              <svg className="menu-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              Command Terminal
            </button>

            <button 
              className={`menu-item ${activeTab === 'tools' ? 'active' : ''}`}
              onClick={() => setActiveTab('tools')}
            >
              <svg className="menu-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
              </svg>
              Tools Registry
            </button>

            <button 
              className={`menu-item ${activeTab === 'memory' ? 'active' : ''}`}
              onClick={() => setActiveTab('memory')}
            >
              <svg className="menu-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 113.536 0V21h2v-2.238a9.04 9.04 0 002.828-9.9" />
              </svg>
              Memory Console
            </button>

            <button 
              className={`menu-item ${activeTab === 'files' ? 'active' : ''}`}
              onClick={() => setActiveTab('files')}
            >
              <svg className="menu-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
              </svg>
              File Sandbox
            </button>
          </div>

          <div className="sidebar-footer">
            <div className="status-indicator-bar">
              <div className={`status-dot ${daemon?.state === 'running' ? 'running' : 'degraded'}`}></div>
              <span>DAEMON {daemonState}</span>
            </div>
          </div>
        </div>

        {/* ═══════════════ MAIN VIEWPORT ═══════════════ */}
        <div className="display-canvas">
          <div className="canvas-header">
            <span className="canvas-title">
              {activeTab === 'dashboard' && 'Dashboard Overview'}
              {activeTab === 'terminal' && 'Core AIOS Terminal'}
              {activeTab === 'tools' && 'Available Tools Map'}
              {activeTab === 'memory' && 'Cognitive Memory Pool'}
              {activeTab === 'files' && 'Sandboxed File Inspector'}
            </span>
            {activeTab === 'terminal' && (
              <button className="btn-ghost" onClick={handleResetSession} disabled={resetLoading}>
                {resetLoading ? 'Flushing...' : 'Reset Context'}
              </button>
            )}
          </div>

          <div className="canvas-content">
            {/* ─── TAB: DASHBOARD ─── */}
            {activeTab === 'dashboard' && (
              <div className="dashboard-view">
                <div className="dashboard-left">
                  {/* System Diagnostics HUD */}
                  <div className="dashboard-card">
                    <span className="card-title">Subsystem Resources</span>
                    <div className="diagnostics-grid">
                      <div className="diag-item">
                        <span className="diag-label">Core Kernel Status</span>
                        <span className="diag-value highlight">{sys?.status || 'ONLINE'}</span>
                      </div>
                      <div className="diag-item">
                        <span className="diag-label">Active Processor (CPU)</span>
                        <span className="diag-value">{sys ? `${sys.cpu_percent}%` : '0%'}</span>
                        <div className="diag-progress-track">
                          <div className="diag-progress-fill cpu" style={{ width: `${sys?.cpu_percent || 0}%` }}></div>
                        </div>
                      </div>
                      <div className="diag-item">
                        <span className="diag-label">Memory Utilization</span>
                        <span className="diag-value">{sys ? `${sys.mem_percent}%` : '0%'}</span>
                        <div className="diag-progress-track">
                          <div className="diag-progress-fill mem" style={{ width: `${sys?.mem_percent || 0}%` }}></div>
                        </div>
                      </div>
                      <div className="diag-item">
                        <span className="diag-label">VEGAS Daemon</span>
                        <span className={`diag-value ${daemon?.state === 'running' ? 'highlight' : ''}`}>{daemonState}</span>
                        <span className="diag-label">{daemon?.websocket?.state || 'socket connecting'}</span>
                      </div>
                      <div className="diag-item">
                        <span className="diag-label">Wake Word</span>
                        <span className={`diag-value ${wakeWordState === 'LISTENING' ? 'highlight' : ''}`}>{wakeWordState}</span>
                        <span className="diag-label">{daemon?.wake_word?.detections || 0} detections</span>
                      </div>
                      <div className="diag-item voice-diagnostic">
                        <span className="diag-label">Voice Interface</span>
                        <span className={`diag-value ${voiceState === 'LISTENING' || voiceState === 'SPEAKING' ? 'highlight' : ''}`}>{voiceState}</span>
                        <span className="diag-label voice-preview">{voicePreview}</span>
                      </div>
                      <div className="diag-item planner-diagnostic">
                        <span className="diag-label">Planner Brain</span>
                        <span className={`diag-value ${plannerState === 'RUNNING' || plannerState === 'PLANNED' ? 'highlight' : ''}`}>{plannerState}</span>
                        <span className="diag-label voice-preview">{plannerIntent} · {plannerDone}/{plannerSteps.length} steps</span>
                      </div>
                    </div>
                  </div>

                  {/* SVG Chart HUD */}
                  <div className="dashboard-card">
                    <span className="card-title">Real-Time Core Load History</span>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                      <div>
                        <span className="diag-label" style={{ marginBottom: '8px', display: 'block' }}>CPU Load Graph</span>
                        <div className="chart-box">
                          <span className="chart-overlay-value">{sys?.cpu_percent || 0}%</span>
                          <svg width="100%" height="100%" viewBox="0 0 400 150" preserveAspectRatio="none">
                            <polyline
                              fill="none"
                              stroke="var(--accent-blue)"
                              strokeWidth="2"
                              points={cpuLinePath}
                            />
                          </svg>
                        </div>
                      </div>
                      <div>
                        <span className="diag-label" style={{ marginBottom: '8px', display: 'block' }}>Memory Load Graph</span>
                        <div className="chart-box">
                          <span className="chart-overlay-value">{sys?.mem_percent || 0}%</span>
                          <svg width="100%" height="100%" viewBox="0 0 400 150" preserveAspectRatio="none">
                            <polyline
                              fill="none"
                              stroke="var(--accent-purple)"
                              strokeWidth="2"
                              points={memLinePath}
                            />
                          </svg>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* System Kernel Console Logs */}
                  <div className="dashboard-card">
                    <span className="card-title">Kernel Event Stream</span>
                    <div className="console-box">
                      {consoleLines.length === 0 ? (
                        <div className="console-line">&gt; Subsystems initialized. Awaiting kernel telemetry stream...</div>
                      ) : (
                        consoleLines.map((line, idx) => (
                          <div key={`console-${idx}-${line.slice(0, 10)}`} className={`console-line ${line.includes('nominal') || line.includes('ok') ? 'success' : ''}`}>
                            &gt; {line}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>

                <div className="dashboard-right">
                  {/* Quick Action Matrix */}
                  <div className="dashboard-card" style={{ height: '100%' }}>
                    <span className="card-title">Direct Diagnostics Actions</span>
                    <div className="actions-grid">
                      <button className="action-tile" onClick={() => sendCommand('Run the full world monitor situation report')}>
                        <span className="action-tile-icon">🌍</span>
                        <span>World Monitor</span>
                      </button>
                      <button className="action-tile" onClick={() => sendCommand('Give me full system diagnostics')}>
                        <span className="action-tile-icon">💻</span>
                        <span>Diagnostics</span>
                      </button>
                      <button className="action-tile" onClick={() => sendCommand('Search the web for the latest tech updates')}>
                        <span className="action-tile-icon">🔍</span>
                        <span>Tech News</span>
                      </button>
                      <button className="action-tile" onClick={() => sendCommand('List pending scheduler crons')}>
                        <span className="action-tile-icon">⏱️</span>
                        <span>Schedule Check</span>
                      </button>
                      <button className="action-tile" onClick={() => sendCommand('List all active memories')}>
                        <span className="action-tile-icon">🧠</span>
                        <span>Memory Dump</span>
                      </button>
                      <button className="action-tile" onClick={() => sendCommand('Run git status')}>
                        <span className="action-tile-icon">📊</span>
                        <span>Git Check</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ─── TAB: TERMINAL (CHAT) ─── */}
            {activeTab === 'terminal' && (
              <div className="terminal-view">
                <div className="chat-scroll">
                  {messages.map((m, idx) => (
                    <div key={`msg-${idx}-${m.role}`} className={`chat-row ${m.role}`}>
                      <div className="avatar-sphere">
                        {m.role === 'user' ? 'U' : 'V'}
                      </div>
                      <div className="chat-bubble">
                        <ReactMarkdown>{m.content}</ReactMarkdown>
                      </div>
                    </div>
                  ))}
                  {loading && (
                    <div className="executing-wrapper">
                      <div className="avatar-sphere">V</div>
                      <div className="executing-box">
                        <span className="executing-text">Executing</span>
                        <div className="executing-dots">
                          <span></span>
                          <span></span>
                          <span></span>
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={chatEndRef} />
                </div>

                <form className="terminal-input-wrap" onSubmit={handleInputSubmit}>
                  <div className="terminal-input-row">
                    <input
                      ref={inputRef}
                      type="text"
                      className="terminal-input-field"
                      value={input}
                      onChange={e => setInput(e.target.value)}
                      placeholder="Enter command payload..."
                      disabled={loading}
                      autoFocus
                    />
                    <button type="submit" className="terminal-send-btn" disabled={!input.trim() || loading}>
                      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                      </svg>
                    </button>
                  </div>
                </form>
              </div>
            )}

            {/* ─── TAB: TOOLS GRID ─── */}
            {activeTab === 'tools' && (
              <div className="tools-view">
                <div className="tools-toolbar">
                  <div className="search-input-wrap">
                    <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="var(--color-muted)" strokeWidth="2.5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    <input
                      type="text"
                      className="search-field"
                      placeholder="Search active tools..."
                      value={searchQuery}
                      onChange={e => setSearchQuery(e.target.value)}
                    />
                  </div>
                  <span className="count-pill">{filteredTools.length} / {tools.length} Tools</span>
                </div>

                <div className="tools-grid-scroll">
                  <div className="tools-grid">
                    {filteredTools.length === 0 ? (
                      <div className="empty-state-box" style={{ gridColumn: '1 / -1', padding: '40px 20px', textAlign: 'center', color: 'var(--color-muted)' }}>
                        <p style={{ margin: 0, fontSize: '14px', color: 'var(--color-text)' }}>No tools matching &quot;{searchQuery}&quot;</p>
                        <span style={{ fontSize: '12px', opacity: 0.7 }}>Try searching for &quot;file&quot;, &quot;git&quot;, &quot;browser&quot;, or &quot;system&quot;</span>
                      </div>
                    ) : (
                      filteredTools.map(t => (
                        <div key={t.name} className="tool-card" onClick={() => sendCommand(`Use the ${t.name} tool`)}>
                          <div className="tool-card-header">
                            <span className="tool-icon-box">{t.icon}</span>
                            <span className="tool-cat-badge">{t.category}</span>
                          </div>
                          <span className="tool-card-title">{t.name}</span>
                          <p className="tool-card-desc">{t.description}</p>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* ─── TAB: MEMORY CONSOLE ─── */}
            {activeTab === 'memory' && (
              <div className="memory-view">
                <div className="memory-left-form">
                  <div className="form-group">
                    <span className="form-label">Remember a Preference / Fact</span>
                    <input
                      type="text"
                      className="form-input"
                      value={memFact}
                      onChange={e => setMemFact(e.target.value)}
                      placeholder="e.g. User prefers light theme in files"
                    />
                  </div>
                  <div className="form-btn-row">
                    <button className="form-btn primary" onClick={() => handleMemoryAction('remember')} disabled={memLoading || !memFact.trim()}>
                      {memLoading ? 'Saving...' : 'Commit Fact'}
                    </button>
                  </div>

                  <div className="form-group" style={{ marginTop: '20px' }}>
                    <span className="form-label">Recall Stored Fact (Search)</span>
                    <input
                      type="text"
                      className="form-input"
                      value={memQuery}
                      onChange={e => setMemQuery(e.target.value)}
                      placeholder="Enter search keywords..."
                    />
                  </div>
                  <div className="form-btn-row">
                    <button className="form-btn secondary" onClick={() => handleMemoryAction('recall')} disabled={memLoading || !memQuery.trim()}>
                      {memLoading ? 'Searching...' : 'Query Memories'}
                    </button>
                  </div>
                </div>

                <div className="memory-right-display">
                  <div className="display-header">
                    <span className="display-title">Memory Response Block</span>
                  </div>
                  <div className="display-body">
                    {memDisplay}
                  </div>
                </div>
              </div>
            )}

            {/* ─── TAB: FILE SYSTEM EXPLORER ─── */}
            {activeTab === 'files' && (
              <div className="explorer-view">
                <div className="explorer-sidebar">
                  <span className="form-label">Workspace Files</span>
                  {PROJECT_FILES.map(f => (
                    <div
                      key={f.name}
                      className={`explorer-tree-item ${activeFile.name === f.name ? 'active' : ''}`}
                      onClick={() => setActiveFile(f)}
                    >
                      <span>📄</span>
                      <span>{f.name}</span>
                    </div>
                  ))}
                </div>
                <div className="explorer-main">
                  <div className="editor-header">
                    <span>{activeFile.path}</span>
                  </div>
                  <div className="editor-content">
                    {fileContent}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
