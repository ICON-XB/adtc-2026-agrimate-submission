import { useState, useRef, useEffect, FormEvent } from 'react';
import './index.css';

// Professional, minimal icons
const BotIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="10" rx="2" />
    <circle cx="12" cy="5" r="2" />
    <path d="M12 7v4" />
    <line x1="8" y1="16" x2="8" y2="16" />
    <line x1="16" y1="16" x2="16" y2="16" />
  </svg>
);

const UserIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
);

const DatabaseIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <ellipse cx="12" cy="5" rx="9" ry="3" />
    <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
    <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
  </svg>
);

const SendIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13" />
    <polygon points="22 2 15 22 11 13 2 9 22 2" />
  </svg>
);

const TerminalIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="4 17 10 11 4 5" />
    <line x1="12" y1="19" x2="20" y2="19" />
  </svg>
);

const BookIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
  </svg>
);

const ActivityIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
  </svg>
);

type Message = {
  id: number;
  role: 'user' | 'ai';
  content: string;
  sources?: string[];
  timestamp: string;
  insufficient_evidence?: boolean;
  debug_info?: any;
  original_prompt?: string;
};

type DocumentItem = {
  filename: string;
  title: string;
};

function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 1,
      role: 'ai',
      content: 'System initialized. I am AgriMate, operating locally. Awaiting queries regarding agricultural management, crop health, or livestock monitoring.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [region, setRegion] = useState('pan-african');
  const [activeTab, setActiveTab] = useState('chat');
  const [isLoading, setIsLoading] = useState(false);
  const [isCollecting, setIsCollecting] = useState(false);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [docCount, setDocCount] = useState(0);
  const [debugMode, setDebugMode] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Fetch document metadata on mount/tab change
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch('http://127.0.0.1:8000/api/health');
        if (res.ok) {
          const data = await res.json();
          setDocCount(data.documents_indexed || 0);
        }
      } catch (e) {
        console.error("Failed to fetch health/stats", e);
      }
    };
    fetchStats();
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === 'knowledge') {
      const fetchDocs = async () => {
        try {
          const res = await fetch('http://127.0.0.1:8000/api/documents');
          if (res.ok) {
            const data = await res.json();
            setDocuments(data.documents || []);
          }
        } catch (e) {
          console.error("Failed to fetch documents list", e);
        }
      };
      fetchDocs();
    }
  }, [activeTab]);

  const handleSend = async (e?: FormEvent, retryPrompt?: string) => {
    if (e) e.preventDefault();
    const promptToSend = retryPrompt || inputValue.trim();
    if (!promptToSend) return;
    
    if (!retryPrompt) {
      const newUserMsg: Message = { 
        id: Date.now(), 
        role: 'user', 
        content: promptToSend,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, newUserMsg]);
      setInputValue('');
    }
    
    setIsLoading(true);

    // Extract history for analyzer
    const history = messages
      .filter(m => m.id > 1) // skip welcome message
      .slice(-4) // send last 4 messages
      .map(m => ({ role: m.role, content: m.content }));

    try {
      const response = await fetch('http://127.0.0.1:8000/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: promptToSend, region, history, debug: debugMode })
      });
      
      if (response.ok) {
        const data = await response.json();
        setMessages(prev => [...prev, {
          id: Date.now() + 1,
          role: 'ai',
          content: data.response,
          sources: data.sources || [],
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          insufficient_evidence: data.insufficient_evidence,
          debug_info: data.debug,
          original_prompt: promptToSend
        }]);
      } else {
        throw new Error('Backend failed');
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'ai',
        content: `Unable to connect to local RAG server. Server might be down.`,
        sources: [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCollect = async (prompt: string, msgId: number) => {
    setIsCollecting(true);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/collect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt })
      });
      if (res.ok) {
        // Retry the original query
        await handleSend(undefined, prompt);
      }
    } catch (err) {
      console.error("Online collection failed", err);
    } finally {
      setIsCollecting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const renderContent = () => {
    if (activeTab === 'chat') {
      return (
        <div className="content-container">
          <div className="chat-history">
            {messages.map((msg) => (
              <div key={msg.id} className="message-row">
                <div className={`message-avatar ${msg.role}`}>
                  {msg.role === 'ai' ? <BotIcon /> : <UserIcon />}
                </div>
                <div className="message-body">
                  <div className="message-header">
                    <span className="message-author">{msg.role === 'ai' ? 'AgriMate' : 'Operator'}</span>
                    <span className="message-time">{msg.timestamp}</span>
                  </div>
                  <div className="message-content">
                    {msg.content}
                  </div>
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="source-container">
                      {msg.sources.map((src, i) => (
                        <span key={i} className="source-badge">
                          <DatabaseIcon /> {src}
                        </span>
                      ))}
                    </div>
                  )}
                  {msg.insufficient_evidence && (
                    <div style={{ marginTop: '12px' }}>
                      <button 
                        className="primary-button" 
                        onClick={() => handleCollect(msg.original_prompt || '', msg.id)}
                        disabled={isCollecting}
                      >
                        <DatabaseIcon /> {isCollecting ? "Searching Web..." : "Search Web for New Info"}
                      </button>
                    </div>
                  )}
                  {debugMode && msg.debug_info && (
                    <div style={{ marginTop: '12px', fontSize: '11px', background: 'var(--bg-sidebar)', padding: '12px', borderRadius: '4px', border: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
                      <strong style={{ color: 'var(--text-heading)' }}>RAG Debug Panel:</strong>
                      <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', marginTop: '8px' }}>
                        {JSON.stringify(msg.debug_info.analysis, null, 2)}
                      </pre>
                      {msg.debug_info.explanation && (
                        <pre style={{ whiteSpace: 'pre-wrap', marginTop: '8px', borderTop: '1px solid #333', paddingTop: '8px' }}>
                          {msg.debug_info.explanation}
                        </pre>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="message-row">
                <div className="message-avatar ai">
                  <BotIcon />
                </div>
                <div className="message-body">
                  <div className="message-header">
                    <span className="message-author">AgriMate</span>
                  </div>
                  <div className="message-content" style={{ color: 'var(--text-muted)' }}>
                    Generating response...
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="input-area">
            <div className="input-wrapper">
              <textarea
                className="chat-textarea"
                placeholder="Query agricultural data, symptoms, or regional guidelines..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
                rows={1}
              />
              <div className="input-footer">
                <span className="input-hint">Return to send, Shift+Return for new line</span>
                <button 
                  className="primary-button" 
                  onClick={handleSend}
                  disabled={!inputValue.trim() || isLoading}
                >
                  <SendIcon /> Execute
                </button>
              </div>
            </div>
          </div>
        </div>
      );
    }

    if (activeTab === 'planner') {
      return (
        <div className="view-container">
          <div className="view-header">
            <h2 className="view-title">Crop Management Dashboard</h2>
            <p className="view-description">
              Regional planting cycles and recommended schedules for **{region.replace('-', ' ').toUpperCase()}**.
            </p>
          </div>
          
          <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', textAlign: 'left' }}>
              <thead>
                <tr style={{ background: 'var(--bg-sidebar)', borderBottom: '1px solid var(--border-color)' }}>
                  <th style={{ padding: '12px 16px', color: 'var(--text-heading)', fontWeight: '600' }}>Crop</th>
                  <th style={{ padding: '12px 16px', color: 'var(--text-heading)', fontWeight: '600' }}>Optimal Planting</th>
                  <th style={{ padding: '12px 16px', color: 'var(--text-heading)', fontWeight: '600' }}>Harvest Window</th>
                  <th style={{ padding: '12px 16px', color: 'var(--text-heading)', fontWeight: '600' }}>Key Nutrient Need</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '12px 16px', fontWeight: '500', color: 'var(--text-heading)' }}>Maize</td>
                  <td style={{ padding: '12px 16px' }}>Start of Rainy Season (Oct/Nov in South)</td>
                  <td style={{ padding: '12px 16px' }}>120–150 Days after sowing</td>
                  <td style={{ padding: '12px 16px' }}>High Nitrogen (Urea/CAN)</td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '12px 16px', fontWeight: '500', color: 'var(--text-heading)' }}>Cassava</td>
                  <td style={{ padding: '12px 16px' }}>Late Rainy Season (April/May)</td>
                  <td style={{ padding: '12px 16px' }}>9–12 Months (highly flexible)</td>
                  <td style={{ padding: '12px 16px' }}>Potassium (builds root starch)</td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '12px 16px', fontWeight: '500', color: 'var(--text-heading)' }}>Beans / Cowpeas</td>
                  <td style={{ padding: '12px 16px' }}>Mid Dry Season / Short Rains</td>
                  <td style={{ padding: '12px 16px' }}>70–90 Days after sowing</td>
                  <td style={{ padding: '12px 16px' }}>Phosphorus (assists root nodules)</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      );
    }

    if (activeTab === 'livestock') {
      return (
        <div className="view-container">
          <div className="view-header">
            <h2 className="view-title">Livestock Management & Health</h2>
            <p className="view-description">
              Diagnostic guidelines and safety procedures configured for local herds.
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div className="card">
              <h3 style={{ color: 'var(--text-heading)', fontSize: '14px', marginBottom: '12px', fontWeight: '600' }}>🛡️ Mandatory Vaccination Schedule</h3>
              <ul style={{ paddingLeft: '16px', display: 'flex', flexDirection: 'column', gap: '8px', color: 'var(--text-muted)' }}>
                <li><strong>Cattle (Lumpy Skin Disease)</strong>: Annual vaccination with live attenuated vaccine before insect vector season starts.</li>
                <li><strong>Goats/Sheep (Capripox)</strong>: Live capripoxvirus vaccine annually for all animals over 3 months old.</li>
                <li><strong>Poultry (Newcastle)</strong>: Thermostable I-2 vaccine administered every 3-4 months via eye drop.</li>
              </ul>
            </div>
            
            <div className="card">
              <h3 style={{ color: 'var(--text-heading)', fontSize: '14px', marginBottom: '12px', fontWeight: '600' }}>🚨 Critical Isolation Protocol</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '13px', lineHeight: '1.5' }}>
                If skin lumps, scabs, or unexpected blisters appear on sheep, goats, or cattle:
                <br /><br />
                1. <strong>Immediate Quarantine:</strong> Move affected animals to a dry, enclosed shelter at least 50 meters away from healthy stock.
                <br />
                2. <strong>Vector Controls:</strong> Apply insect repellent sprays to reduce biting flies and mosquitoes.
                <br />
                3. <strong>Hygiene:</strong> Disinfect all water containers and feeding troughs using a bleach solution.
              </p>
            </div>
          </div>
        </div>
      );
    }
    
    // Knowledge Base View
    return (
      <div className="view-container">
        <div className="view-header">
          <h2 className="view-title">Local Knowledge Base Directory</h2>
          <p className="view-description">
            List of indexed offline reference files stored in the RAG repository.
          </p>
        </div>
        
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px', marginBottom: '8px' }}>
            TOTAL INDEXED RESOURCES: <strong>{docCount}</strong>
          </div>
          {documents.length > 0 ? (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              {documents.map((doc, idx) => (
                <div key={idx} style={{ padding: '8px 12px', background: 'var(--bg-app)', border: '1px solid var(--border-color)', borderRadius: '4px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <BookIcon />
                  <span style={{ color: 'var(--text-heading)', fontWeight: '500' }}>{doc.title}</span>
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)', marginLeft: 'auto' }}>{doc.filename}</span>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: 'var(--text-muted)' }}>
              No offline documents found. Run the collector script to sync dataset nodes.
            </p>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="app-container">
      <aside className="sidebar">
        <div className="sidebar-header">
          <BotIcon /> AGRIMATE
        </div>
        
        <div className="sidebar-content">
          <div className="nav-section">
            <div className="nav-section-title">Workspace</div>
            <a onClick={() => setActiveTab('chat')} className={`nav-item ${activeTab === 'chat' ? 'active' : ''}`}>
              <TerminalIcon /> Console
            </a>
            <a onClick={() => setActiveTab('planner')} className={`nav-item ${activeTab === 'planner' ? 'active' : ''}`}>
              <ActivityIcon /> Crop Management
            </a>
            <a onClick={() => setActiveTab('livestock')} className={`nav-item ${activeTab === 'livestock' ? 'active' : ''}`}>
              <ActivityIcon /> Livestock
            </a>
          </div>

          <div className="nav-section">
            <div className="nav-section-title">Resources</div>
            <a onClick={() => setActiveTab('knowledge')} className={`nav-item ${activeTab === 'knowledge' ? 'active' : ''}`}>
              <BookIcon /> Local Database
            </a>
          </div>
        </div>

        <div className="sidebar-header" style={{ borderTop: '1px solid var(--border-color)', borderBottom: 'none', height: 'auto', padding: '12px 16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', width: '100%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
              <span style={{ color: 'var(--text-muted)' }}>Engine</span>
              <span style={{ color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span className="status-dot online"></span> Qwen 1.7B
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
              <span style={{ color: 'var(--text-muted)' }}>Memory</span>
              <span style={{ color: 'var(--text-primary)' }}>3.2 / 7.0 GB</span>
            </div>
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>
            <span>/</span>
            <span className="breadcrumb-active">
              {activeTab === 'chat' ? 'Console' : 
               activeTab === 'planner' ? 'Crop Management' : 
               activeTab === 'livestock' ? 'Livestock' : 'Local Database'}
            </span>
          </div>
          
          <div className="topbar-actions">
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-muted)', cursor: 'pointer' }}>
              <input 
                type="checkbox" 
                checked={debugMode} 
                onChange={(e) => setDebugMode(e.target.checked)} 
              />
              RAG Debug Mode
            </label>
            
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', padding: '4px 8px', background: 'rgba(52, 211, 153, 0.1)', color: '#34d399', borderRadius: '12px', fontWeight: '500' }}>
              <span className="status-dot online"></span> Offline-First Ready
            </div>

            <select 
              className="select-input"
              value={region}
              onChange={(e) => setRegion(e.target.value)}
            >
              <option value="pan-african">Region: Pan-African</option>
              <option value="west-africa">Region: West Africa</option>
              <option value="east-africa">Region: East Africa</option>
              <option value="southern-africa">Region: Southern Africa</option>
              <option value="north-africa">Region: North Africa</option>
              <option value="central-africa">Region: Central Africa</option>
              <option value="islands">Region: Islands</option>
            </select>
            
            <div className="message-avatar">
              <UserIcon />
            </div>
          </div>
        </header>

        {renderContent()}
        
      </main>
    </div>
  );
}

export default App;
