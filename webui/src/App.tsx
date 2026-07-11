import { useState, useEffect, useRef } from 'react'

// Custom Searchable Dropdown Component
function SearchableDropdown({ options, value, onChange, placeholder }: { options: string[], value: string, onChange: (val: string) => void, placeholder: string }) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const filteredOptions = options.filter(opt => opt.toLowerCase().includes(search.toLowerCase()));

  useEffect(() => {
    if (!isOpen) {
      setSearch(value);
    }
  }, [isOpen, value]);

  return (
    <div ref={wrapperRef} className="relative w-full">
      <input
        type="text"
        value={isOpen ? search : value}
        onChange={e => {
          setSearch(e.target.value);
          if (!isOpen) setIsOpen(true);
          onChange(e.target.value);
        }}
        onClick={() => setIsOpen(true)}
        placeholder={placeholder}
        className="w-full bg-[#13131a] border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/50 transition-all placeholder:text-gray-600 shadow-inner"
      />
      
      <div 
        className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none"
        style={{ transform: isOpen ? 'translateY(-50%) rotate(180deg)' : 'translateY(-50%)', transition: 'transform 0.2s' }}
      >
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
        </svg>
      </div>

      {isOpen && (
        <div className="absolute z-50 w-full mt-2 bg-[#1a1b26] border border-white/10 rounded-xl shadow-2xl max-h-60 overflow-y-auto custom-scrollbar">
          {filteredOptions.length === 0 ? (
            <div className="p-4 text-gray-500 text-sm italic text-center">No models found</div>
          ) : (
            filteredOptions.map((opt) => (
              <div
                key={opt}
                onClick={() => {
                  onChange(opt);
                  setSearch(opt);
                  setIsOpen(false);
                }}
                className={`px-4 py-2.5 cursor-pointer text-sm font-mono hover:bg-purple-500/20 transition-colors ${value === opt ? 'bg-purple-500/10 text-purple-300' : 'text-gray-300'}`}
              >
                {opt}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}


function App() {
  const [activeTab, setActiveTab] = useState<'routing' | 'launcher'>('routing');
  const [mappings, setMappings] = useState<Record<string, string>>({});
  
  // Routing Form State
  const [sourceModel, setSourceModel] = useState("opus");
  const [provider, setProvider] = useState("openrouter");
  const [targetModel, setTargetModel] = useState("");
  
  // Launcher Form State
  const [launchType, setLaunchType] = useState<'local' | 'git'>('local');
  const [localPath, setLocalPath] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [isLaunching, setIsLaunching] = useState(false);

  // Available models state
  const [availableModels, setAvailableModels] = useState<Record<string, string[]>>({
    openrouter: [],
    deepseekplatform: []
  });
  const [isLoadingModels, setIsLoadingModels] = useState(true);

  const fetchMappings = () => {
    fetch('/api/models')
      .then(r => r.json())
      .then(d => setMappings(d.mappings || {}));
  }

  useEffect(() => {
    fetchMappings();
  }, []);

  useEffect(() => {
    setIsLoadingModels(true);
    fetch('/api/available-models')
      .then(r => r.json())
      .then(d => {
        setAvailableModels(d);
        setIsLoadingModels(false);
      })
      .catch(err => {
        console.error("Error fetching models:", err);
        setIsLoadingModels(false);
      });
  }, []);

  const addMapping = async () => {
    if (!sourceModel || !targetModel) return;
    
    const cleanTarget = targetModel.startsWith(provider + "/") 
      ? targetModel.replace(provider + "/", "") 
      : targetModel;

    const fullTarget = `${provider}/${cleanTarget}`;

    const res = await fetch('/api/models', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_model: sourceModel, target: fullTarget })
    });
    
    const d = await res.json();
    setMappings(d.mappings);
    setTargetModel(""); // reset
  };

  const launchClaude = async () => {
    setIsLaunching(true);
    const payload = {
      path: launchType === 'local' ? localPath : null,
      repo_url: launchType === 'git' ? repoUrl : null
    };

    try {
      await fetch('/api/launch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    } catch (e) {
      console.error(e);
    }
    setTimeout(() => setIsLaunching(false), 1000); // UI feel
  };

  const currentProviderModels = availableModels[provider] || [];

  return (
    <div className="min-h-screen bg-[#08080c] bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(120,119,198,0.15),rgba(255,255,255,0))] font-sans relative overflow-hidden">
      {/* Background decoration */}
      <div className="absolute top-[-10%] left-[-10%] w-96 h-96 bg-purple-500/20 rounded-full blur-[120px] pointer-events-none"></div>
      <div className="absolute bottom-[-10%] right-[-10%] w-96 h-96 bg-cyan-500/10 rounded-full blur-[120px] pointer-events-none"></div>

      <div className="max-w-5xl mx-auto pt-16 px-6 pb-20 relative z-10">
        <div className="flex flex-col items-center sm:items-start mb-8">
          <h1 className="text-5xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-cyan-400 mb-2">
            freeClaude
          </h1>
          <p className="text-gray-400 text-lg">Universal Proxy Dashboard</p>
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-4 mb-8 border-b border-white/10 pb-4">
          <button 
            onClick={() => setActiveTab('routing')}
            className={`px-6 py-3 rounded-xl font-semibold transition-all ${activeTab === 'routing' ? 'bg-white/10 text-white shadow-lg border border-white/10' : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'}`}
          >
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" /></svg>
              Model Routing
            </div>
          </button>
          <button 
            onClick={() => setActiveTab('launcher')}
            className={`px-6 py-3 rounded-xl font-semibold transition-all ${activeTab === 'launcher' ? 'bg-gradient-to-r from-purple-600/20 to-cyan-600/20 text-white shadow-lg border border-purple-500/30' : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'}`}
          >
            <div className="flex items-center gap-2 text-purple-300">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
              Claude Launcher
            </div>
          </button>
        </div>

        {/* TAB CONTENT: ROUTING */}
        {activeTab === 'routing' && (
          <div className="backdrop-blur-2xl bg-white/[0.02] border border-white/10 rounded-3xl p-8 shadow-2xl mb-8 transition-all hover:border-white/20 animate-fade-in">
            <h2 className="text-2xl font-semibold text-white mb-8 flex items-center gap-3">
              <span className="bg-purple-500/20 p-2.5 rounded-xl text-purple-400 border border-purple-500/30">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" /></svg>
              </span>
              Active Model Routes
            </h2>
            
            <div className="space-y-3 mb-10">
              {Object.entries(mappings).map(([src, tgt]) => (
                <div key={src} className="flex flex-col sm:flex-row items-start sm:items-center justify-between group p-4 rounded-2xl bg-black/40 border border-white/5 hover:border-purple-500/40 hover:bg-white/[0.04] transition-all shadow-inner">
                  <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-6 w-full">
                    <span className="font-mono text-sm text-cyan-300 bg-cyan-500/10 px-4 py-2 rounded-lg min-w-[120px] text-center uppercase tracking-widest font-bold border border-cyan-500/20 shadow-[0_0_15px_rgba(6,182,212,0.1)]">{src}</span>
                    <span className="text-gray-600 hidden sm:block">
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" /></svg>
                    </span>
                    <span className="font-mono text-sm text-purple-300 bg-purple-500/10 px-4 py-2 rounded-lg break-all border border-purple-500/20 shadow-[0_0_15px_rgba(168,85,247,0.1)]">{tgt}</span>
                  </div>
                </div>
              ))}
              
              {Object.keys(mappings).length === 0 && (
                <div className="text-center py-12 text-gray-500 italic bg-black/20 rounded-2xl border border-dashed border-white/10">No active model routes configured.</div>
              )}
            </div>

            <div className="bg-black/40 p-6 rounded-2xl border border-white/10 relative">
              <div className="absolute top-0 right-0 w-64 h-64 bg-purple-500/5 rounded-full blur-[80px] pointer-events-none"></div>

              <h3 className="text-lg font-medium text-white mb-6 flex items-center gap-2">
                <svg className="w-5 h-5 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
                Add or Update Route
              </h3>
              
              <div className="flex flex-col lg:flex-row gap-5 relative z-10">
                <div className="flex-1">
                  <label className="block text-[11px] font-bold text-gray-400 mb-2 uppercase tracking-widest">Claude Model</label>
                  <select 
                    value={sourceModel}
                    onChange={e => setSourceModel(e.target.value)}
                    className="w-full bg-[#13131a] border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/50 transition-all cursor-pointer appearance-none shadow-inner font-medium"
                    style={{ backgroundImage: `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%239ca3af' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`, backgroundPosition: 'right 0.75rem center', backgroundRepeat: 'no-repeat', backgroundSize: '1.2em 1.2em' }}
                  >
                    <option value="opus">Opus</option>
                    <option value="sonnet">Sonnet</option>
                    <option value="haiku">Haiku</option>
                  </select>
                </div>

                <div className="hidden lg:flex items-center justify-center pt-6 text-gray-600">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 8l4 4m0 0l-4 4m4-4H3" /></svg>
                </div>

                <div className="flex-1">
                  <label className="block text-[11px] font-bold text-gray-400 mb-2 uppercase tracking-widest">Target Provider</label>
                  <select 
                    value={provider}
                    onChange={e => {
                      setProvider(e.target.value);
                      setTargetModel(""); // reset model when provider changes
                    }}
                    className="w-full bg-[#13131a] border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/50 transition-all cursor-pointer appearance-none shadow-inner font-medium"
                    style={{ backgroundImage: `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%239ca3af' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`, backgroundPosition: 'right 0.75rem center', backgroundRepeat: 'no-repeat', backgroundSize: '1.2em 1.2em' }}
                  >
                    <option value="openrouter">OpenRouter</option>
                    <option value="deepseekplatform">DeepSeek</option>
                  </select>
                </div>

                <div className="flex-[2]">
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-[11px] font-bold text-gray-400 uppercase tracking-widest">
                      Target Model
                    </label>
                    {isLoadingModels && <span className="text-[10px] animate-pulse text-purple-400 tracking-wider">LOADING API...</span>}
                  </div>
                  
                  <SearchableDropdown 
                    options={currentProviderModels}
                    value={targetModel}
                    onChange={setTargetModel}
                    placeholder="Search and select a model..."
                  />
                </div>

                <div className="flex items-end">
                  <button 
                    onClick={addMapping}
                    disabled={!targetModel}
                    className="w-full lg:w-auto bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 disabled:from-gray-700 disabled:to-gray-800 disabled:text-gray-500 disabled:cursor-not-allowed text-white font-bold py-3 px-8 rounded-xl transition-all shadow-lg shadow-purple-500/25 active:scale-95 border border-purple-500/30"
                  >
                    Save Route
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB CONTENT: LAUNCHER */}
        {activeTab === 'launcher' && (
          <div className="backdrop-blur-2xl bg-white/[0.02] border border-white/10 rounded-3xl p-8 shadow-2xl mb-8 transition-all hover:border-white/20 animate-fade-in relative overflow-hidden">
            
            {/* Background Glows for Launcher */}
            <div className="absolute top-[-20%] right-[-10%] w-96 h-96 bg-cyan-500/10 rounded-full blur-[100px] pointer-events-none"></div>

            <h2 className="text-2xl font-semibold text-white mb-4 flex items-center gap-3">
              <span className="bg-cyan-500/20 p-2.5 rounded-xl text-cyan-400 border border-cyan-500/30">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M4 17h16a2 2 0 002-2V9a2 2 0 00-2-2H4a2 2 0 00-2 2v6a2 2 0 002 2z" /></svg>
              </span>
              Claude Code Launcher
            </h2>
            <p className="text-gray-400 mb-8 max-w-2xl">
              Launch Claude Code directly with <code>ANTHROPIC_BASE_URL</code> and API keys pre-configured. Open your existing local projects or automatically clone a Git repository to start coding immediately.
            </p>

            <div className="bg-black/30 p-2 rounded-2xl inline-flex mb-8 border border-white/5 relative z-10">
              <button 
                onClick={() => setLaunchType('local')}
                className={`px-6 py-2.5 rounded-xl font-medium transition-all ${launchType === 'local' ? 'bg-white/10 text-white shadow-md' : 'text-gray-400 hover:text-white'}`}
              >
                Local Directory
              </button>
              <button 
                onClick={() => setLaunchType('git')}
                className={`px-6 py-2.5 rounded-xl font-medium transition-all ${launchType === 'git' ? 'bg-white/10 text-white shadow-md' : 'text-gray-400 hover:text-white'}`}
              >
                Git Repository
              </button>
            </div>

            <div className="bg-black/40 p-8 rounded-2xl border border-white/10 relative z-10 shadow-inner max-w-3xl">
              {launchType === 'local' ? (
                <div>
                  <label className="block text-xs font-bold text-gray-400 mb-3 uppercase tracking-widest">
                    Project Folder Path
                  </label>
                  <div className="flex gap-2 mb-2">
                    <input 
                      type="text" 
                      value={localPath}
                      onChange={e => setLocalPath(e.target.value)}
                      placeholder="e.g. C:\Users\Projects\MyApp or left blank to open in proxy folder" 
                      className="flex-1 bg-[#13131a] border border-white/10 rounded-xl px-5 py-4 text-white focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/50 transition-all placeholder:text-gray-600 font-mono text-sm"
                    />
                    <button 
                      onClick={async () => {
                        try {
                          const res = await fetch('/api/browse-folder');
                          const data = await res.json();
                          if (data.path) setLocalPath(data.path);
                        } catch (e) {
                          console.error(e);
                        }
                      }}
                      className="px-6 py-4 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-cyan-400 font-semibold transition-all shadow-inner whitespace-nowrap active:scale-95"
                    >
                      Browse...
                    </button>
                  </div>
                  <p className="text-xs text-gray-500 mb-6 mt-2 flex items-center gap-2">
                    <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    A new command prompt window will open at this location with Claude loaded.
                  </p>
                </div>
              ) : (
                <div>
                  <label className="block text-xs font-bold text-gray-400 mb-3 uppercase tracking-widest">
                    Git Repository URL
                  </label>
                  <input 
                    type="text" 
                    value={repoUrl}
                    onChange={e => setRepoUrl(e.target.value)}
                    placeholder="e.g. https://github.com/facebook/react.git" 
                    className="w-full bg-[#13131a] border border-white/10 rounded-xl px-5 py-4 text-white focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/50 transition-all placeholder:text-gray-600 mb-2 font-mono text-sm"
                  />
                  <p className="text-xs text-gray-500 mb-6 mt-2 flex items-center gap-2">
                    <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    Repo will be cloned to `freeClaude/projects/` and Claude will open automatically.
                  </p>
                </div>
              )}

              <button 
                onClick={launchClaude}
                disabled={isLaunching || (launchType === 'git' && !repoUrl)}
                className="w-full sm:w-auto flex items-center justify-center gap-3 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 disabled:from-gray-700 disabled:to-gray-800 text-white font-bold py-4 px-10 rounded-xl transition-all shadow-[0_0_20px_rgba(8,145,178,0.3)] hover:shadow-[0_0_30px_rgba(8,145,178,0.5)] active:scale-95 border border-cyan-500/30 text-lg group"
              >
                {isLaunching ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-2 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                    Launching Terminal...
                  </>
                ) : (
                  <>
                    Launch Claude Code
                    <svg className="w-5 h-5 group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
                  </>
                )}
              </button>
            </div>
          </div>
        )}

      </div>
      
      {/* Inject custom scrollbar style and animations */}
      <style>{`
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: rgba(255,255,255,0.02); }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(168,85,247,0.3); border-radius: 10px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(168,85,247,0.5); }
        
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in { animation: fadeIn 0.3s ease-out forwards; }
      `}</style>
    </div>
  );
}

export default App;
