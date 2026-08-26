import { useState, useEffect, useRef } from 'react'
import CustomProviderModal from './CustomProviderModal'

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
        className="w-full pixel-input px-3 py-2 text-[10px] placeholder:text-moss-600"
      />

      <div className="absolute right-3 top-1/2 -translate-y-1/2 text-moss-400 pointer-events-none"
        style={{ transform: isOpen ? 'translateY(-50%) rotate(180deg)' : 'translateY(-50%)', transition: 'transform 0.2s' }}
      >
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor" className="w-4 h-4">
          <path strokeLinecap="square" strokeLinejoin="miter" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
        </svg>
      </div>

      {isOpen && (
        <div className="absolute z-50 w-full mt-1 bg-moss-900 pixel-border max-h-60 overflow-y-auto">
          {filteredOptions.length === 0 ? (
            <div className="p-3 text-moss-500 text-[8px] italic text-center">No models found</div>
          ) : (
            filteredOptions.map((opt) => (
              <div
                key={opt}
                onClick={() => {
                  onChange(opt);
                  setSearch(opt);
                  setIsOpen(false);
                }}
                className={`px-3 py-2 cursor-pointer text-[8px] hover:bg-provider-600/30 ${value === opt ? 'bg-provider-600/40 text-provider-400' : 'text-moss-200'}`}
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
  
  const [sourceModel, setSourceModel] = useState("opus");
  const [provider, setProvider] = useState("openrouter");
  const [targetModel, setTargetModel] = useState("");
  
  const [launchTarget, setLaunchTarget] = useState<string>('terminal');
  const [launchMode, setLaunchMode] = useState<'local' | 'git'>('local');
  const [localPath, setLocalPath] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [isLaunching, setIsLaunching] = useState(false);

  const [ideList, setIdeList] = useState<Record<string, { name: string; version: string; binary: string; supports_claude_extension: boolean }>>({});

  const [codexInfo, setCodexInfo] = useState<{ name: string; version: string } | null>(null);

  const [availableModels, setAvailableModels] = useState<Record<string, string[]>>({
    openrouter: [],
    deepseekplatform: []
  });
  const [isLoadingModels, setIsLoadingModels] = useState(true);
  const [customProviders, setCustomProviders] = useState<Record<string, any>>({});
  const [showCustomModal, setShowCustomModal] = useState(false);

  const fetchMappings = () => {
    fetch('/api/models')
      .then(r => r.json())
      .then(d => setMappings(d.mappings || {}));
  }

  useEffect(() => {
    fetchMappings();
  }, []);

  useEffect(() => {
    fetch('/api/ide-detect')
      .then(r => r.json())
      .then(d => setIdeList(d.detected || {}))
      .catch(() => {});

    fetch('/api/codex-detect')
      .then(r => r.json())
      .then(d => setCodexInfo(d.detected?.binary ? d.detected : null))
      .catch(() => {});
  }, []);

  const fetchCustomProviders = () => {
    fetch('/api/custom-providers')
      .then(r => r.json())
      .then(d => setCustomProviders(d.providers || {}))
      .catch(() => {});
  };

  useEffect(() => {
    fetchCustomProviders();
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
    setTargetModel("");
  };

  const launchClaude = async () => {
    setIsLaunching(true);

    if (launchTarget === 'terminal' || launchTarget === 'codex') {
      const endpoint = launchTarget === 'codex' ? '/api/codex-launch' : '/api/launch';
      const payload = {
        path: launchMode === 'local' ? localPath : null,
        repo_url: launchMode === 'git' ? repoUrl : null
      };
      try {
        if (launchTarget === 'codex') {
          await fetch('/api/codex-setup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
          });
        }
        await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      } catch (e) {
        console.error(e);
      }
    } else {
      try {
        await fetch('/api/ide-setup', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ editors: [launchTarget] })
        });
        await fetch('/api/ide-launch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ editor: launchTarget, path: localPath || null })
        });
      } catch (e) {
        console.error(e);
      }
    }
    setTimeout(() => setIsLaunching(false), 1000);
  };

  const currentProviderModels = availableModels[provider] || [];

  return (
    <div className="min-h-screen bg-moss-950 font-pixel flex flex-col">
      <div className="flex-1">
        <div className="max-w-5xl mx-auto pt-12 px-6 pb-8">
          <div className="mb-8">
            <h1 className="text-4xl font-pixel text-claude-500 mb-2 tracking-normal" style={{ textShadow: '4px 4px 0 #8b4513' }}>
              freeClaude
            </h1>
            <p className="text-moss-400 text-[8px]">UNIVERSAL PROXY DASHBOARD</p>
          </div>

          {/* Tab Navigation */}
          <div className="flex gap-0 mb-8 border-b-4 border-moss-700">
            <button 
              onClick={() => setActiveTab('routing')}
              className={`px-5 py-3 font-pixel text-[9px] border-4 border-b-0 transition-none ${activeTab === 'routing' ? 'bg-moss-900 border-provider-500 text-provider-400' : 'bg-moss-950 border-transparent text-moss-500 hover:text-moss-300'}`}
            >
              <div className="flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="square" strokeLinejoin="miter" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" /></svg>
                MODEL ROUTING
              </div>
            </button>
            <button 
              onClick={() => setActiveTab('launcher')}
              className={`px-5 py-3 font-pixel text-[9px] border-4 border-b-0 transition-none ${activeTab === 'launcher' ? 'bg-moss-900 border-claude-500 text-claude-400' : 'bg-moss-950 border-transparent text-moss-500 hover:text-moss-300'}`}
            >
              <div className="flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="square" strokeLinejoin="miter" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                AGENT LAUNCHER
              </div>
            </button>
          </div>

          {/* TAB CONTENT: ROUTING */}
          {activeTab === 'routing' && (
            <div className="pixel-card p-6 mb-8">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-sm font-pixel text-provider-400 flex items-center gap-3">
                  <span className="pixel-border-provider px-2 py-1 text-[10px] text-provider-300">◈</span>
                  ACTIVE MODEL ROUTES
                </h2>
                <button onClick={() => setShowCustomModal(true)} className="pixel-btn text-[7px] px-3 py-2">+ ADD CUSTOM PROVIDER</button>
              </div>
              
              <div className="space-y-2 mb-8">
                {Object.entries(mappings).map(([src, tgt]) => (
                  <div key={src} className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-3 bg-moss-950 pixel-border">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4 w-full">
                      <span className="text-[8px] text-claude-500 bg-moss-950 px-3 py-2 min-w-[100px] text-center border-4 border-claude-600">{src.toUpperCase()}</span>
                      <span className="text-moss-600 hidden sm:block text-sm">→</span>
                      <span className="text-[7px] text-provider-400 bg-moss-950 px-3 py-2 break-all border-4 border-provider-600">{tgt}</span>
                    </div>
                  </div>
                ))}
                
                {Object.keys(mappings).length === 0 && (
                  <div className="text-center py-10 text-moss-500 text-[8px] bg-moss-950 pixel-border">NO ACTIVE MODEL ROUTES CONFIGURED.</div>
                )}
              </div>

              <div className="bg-moss-950 p-5 pixel-border">
                <h3 className="text-[10px] font-pixel text-provider-400 mb-5 flex items-center gap-2">
                  <span className="text-provider-500">+</span>
                  ADD OR UPDATE ROUTE
                </h3>
                
                <div className="flex flex-col lg:flex-row gap-4">
                  <div className="flex-1">
                    <label className="block text-[7px] font-pixel text-claude-500 mb-2">SOURCE MODEL</label>
                    <select 
                      value={sourceModel}
                      onChange={e => setSourceModel(e.target.value)}
                      className="w-full pixel-input px-3 py-2 text-[9px] appearance-none"
                      style={{ backgroundImage: `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%239ca3af' stroke-linecap='square' stroke-linejoin='miter' stroke-width='2' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`, backgroundPosition: 'right 0.5rem center', backgroundRepeat: 'no-repeat', backgroundSize: '1em 1em' }}
                    >
                      <option value="opus">OPUS</option>
                      <option value="sonnet">SONNET</option>
                      <option value="haiku">HAIKU</option>
                      <option value="codex">CODEX</option>
                    </select>
                  </div>

                  <div className="hidden lg:flex items-center justify-center pt-6 text-moss-600 text-sm">→</div>

                  <div className="flex-1">
                    <label className="block text-[7px] font-pixel text-provider-500 mb-2">TARGET PROVIDER</label>
                    <select 
                      value={provider}
                      onChange={e => {
                        setProvider(e.target.value);
                        setTargetModel("");
                      }}
                      className="w-full pixel-input px-3 py-2 text-[9px] appearance-none"
                      style={{ backgroundImage: `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%239ca3af' stroke-linecap='square' stroke-linejoin='miter' stroke-width='2' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`, backgroundPosition: 'right 0.5rem center', backgroundRepeat: 'no-repeat', backgroundSize: '1em 1em' }}
                    >
                      <option value="openrouter">OPENROUTER</option>
                      <option value="deepseekplatform">DEEPSEEK</option>
                      {Object.keys(customProviders).map(id => (
                        <option key={id} value={id}>{customProviders[id].display_name?.toUpperCase() || id.toUpperCase()}</option>
                      ))}
                    </select>
                  </div>

                  <div className="flex-[2]">
                    <div className="flex items-center justify-between mb-2">
                      <label className="block text-[7px] font-pixel text-provider-500">
                        TARGET MODEL
                      </label>
                      {isLoadingModels && <span className="text-[7px] animate-blink text-provider-500">LOADING...</span>}
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
                      className="w-full lg:w-auto pixel-btn-provider text-[8px] py-3 px-6"
                    >
                      SAVE ROUTE
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB CONTENT: LAUNCHER */}
          {activeTab === 'launcher' && (
            <div className="pixel-card p-6 mb-8">
              <h2 className="text-sm font-pixel text-claude-500 mb-3 flex items-center gap-3" style={{ textShadow: '3px 3px 0 #8b4513' }}>
                <span className="pixel-border-claude px-2 py-1 text-[10px] text-claude-400">★</span>
                AGENT LAUNCHER
              </h2>
              <p className="text-moss-400 text-[7px] mb-6 max-w-2xl leading-relaxed">
                Launch Claude Code or Codex directly with proxy env pre-configured (<code className="text-claude-500 bg-moss-950 px-1">ANTHROPIC_BASE_URL</code> for Claude Code, <code className="text-claude-500 bg-moss-950 px-1">~/.codex/config.toml</code> for Codex). Open your existing local projects or automatically clone a Git repository to start coding immediately.
              </p>

              <div className="bg-moss-950 p-2 mb-5 border-4 border-moss-700 inline-flex flex-wrap gap-1">
                <button 
                  onClick={() => setLaunchTarget('terminal')}
                  className={`px-4 py-2 font-pixel text-[8px] border-4 transition-none ${launchTarget === 'terminal' ? 'bg-moss-800 border-moss-500 text-moss-200' : 'bg-moss-950 border-transparent text-moss-500 hover:text-moss-300'}`}
                >
                  TERMINAL
                </button>
                <button 
                  onClick={() => setLaunchTarget('codex')}
                  title={codexInfo ? `${codexInfo.name} ${codexInfo.version} detected — auto-writes ~/.codex/config.toml` : 'Codex CLI not found in PATH — install with `npm install -g @openai/codex`'}
                  className={`px-4 py-2 font-pixel text-[8px] border-4 transition-none ${launchTarget === 'codex' ? 'bg-moss-800 border-moss-500 text-moss-200' : 'bg-moss-950 border-transparent text-moss-500 hover:text-moss-300'} ${!codexInfo ? 'opacity-60' : ''}`}
                >
                  {codexInfo ? 'CODEX' : 'CODEX *'}
                </button>
                {Object.entries(ideList).map(([id, info]) => (
                  <button 
                    key={id}
                    onClick={() => setLaunchTarget(id)}
                    title={info.supports_claude_extension ? 'Auto-configure Claude Code extension' : 'Will launch IDE - use terminal inside it with `claude` CLI'}
                    className={`px-4 py-2 font-pixel text-[8px] border-4 transition-none ${launchTarget === id ? 'bg-claude-700/30 border-claude-500 text-claude-400' : 'bg-moss-950 border-transparent text-moss-500 hover:text-moss-300'} ${!info.supports_claude_extension ? 'opacity-60' : ''}`}
                  >
                    {info.name.toUpperCase()}{!info.supports_claude_extension ? ' *' : ''}
                  </button>
                ))}
              </div>

              {(launchTarget === 'terminal' || launchTarget === 'codex') && (
                <div className="bg-moss-950 p-2 mb-5 border-4 border-moss-700 inline-flex">
                  <button 
                    onClick={() => setLaunchMode('local')}
                    className={`px-4 py-2 font-pixel text-[8px] border-4 transition-none ${launchMode === 'local' ? 'bg-moss-800 border-moss-500 text-moss-200' : 'bg-moss-950 border-transparent text-moss-500 hover:text-moss-300'}`}
                  >
                    LOCAL DIRECTORY
                  </button>
                  <button 
                    onClick={() => setLaunchMode('git')}
                    className={`px-4 py-2 font-pixel text-[8px] border-4 transition-none ${launchMode === 'git' ? 'bg-moss-800 border-moss-500 text-moss-200' : 'bg-moss-950 border-transparent text-moss-500 hover:text-moss-300'}`}
                  >
                    GIT REPOSITORY
                  </button>
                </div>
              )}

              <div className="bg-moss-950 p-6 pixel-border max-w-3xl">
                {(launchTarget === 'terminal' || launchTarget === 'codex') && launchMode === 'git' ? (
                  <div>
                    <label className="block text-[8px] font-pixel text-claude-500 mb-3">
                      GIT REPOSITORY URL
                    </label>
                    <input 
                      type="text" 
                      value={repoUrl}
                      onChange={e => setRepoUrl(e.target.value)}
                      placeholder="e.g. https://github.com/facebook/react.git" 
                      className="w-full pixel-input px-4 py-3 text-[8px] placeholder:text-moss-600 mb-2"
                    />
                    <p className="text-[7px] text-moss-500 mb-5 mt-2 flex items-center gap-2">
                      <svg className="w-3 h-3 text-moss-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="square" strokeLinejoin="miter" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                      Repo will be cloned to freeClaude/projects/ and the agent will open automatically.
                    </p>
                  </div>
                ) : (
                  <div>
                    <label className="block text-[8px] font-pixel text-claude-500 mb-3">
                      PROJECT FOLDER PATH
                    </label>
                    <div className="flex gap-2 mb-2">
                      <input 
                        type="text" 
                        value={localPath}
                        onChange={e => setLocalPath(e.target.value)}
                        placeholder="e.g. /home/user/projects/myapp or leave blank" 
                        className="flex-1 pixel-input px-4 py-3 text-[8px] placeholder:text-moss-600"
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
                        className="px-4 py-3 pixel-btn text-[8px]"
                      >
                        BROWSE...
                      </button>
                    </div>
                    <p className="text-[7px] text-moss-500 mb-5 mt-2 flex items-center gap-2">
                      <svg className="w-3 h-3 text-moss-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="square" strokeLinejoin="miter" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                      {launchTarget === 'terminal' ? 'A new terminal window will open at this location with Claude loaded.' : launchTarget === 'codex' ? 'Writes ~/.codex/config.toml, then a new terminal window opens at this location with Codex routed through the proxy.' : ideList[launchTarget]?.supports_claude_extension ? `${ideList[launchTarget]?.name || 'IDE'} will open with Claude Code + Codex pre-configured.` : `${ideList[launchTarget]?.name || 'IDE'} will open. Use the built-in terminal and run \`claude\` — proxy env is already configured.`}
                    </p>
                  </div>
                )}

                <button 
                  onClick={launchClaude}
                  disabled={isLaunching || ((launchTarget === 'terminal' || launchTarget === 'codex') && launchMode === 'git' && !repoUrl)}
                  className="w-full sm:w-auto flex items-center justify-center gap-3 pixel-btn-claude text-[10px] py-4 px-8"
                >
                  {isLaunching ? (
                    <>
                      <span className="animate-blink">▌</span>
                      LAUNCHING...
                    </>
                  ) : (
                    <>
                      {launchTarget === 'codex' ? 'LAUNCH CODEX' : launchTarget === 'terminal' ? 'LAUNCH CLAUDE CODE' : `LAUNCH IN ${ideList[launchTarget]?.name?.toUpperCase() || 'IDE'}`}
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="square" strokeLinejoin="miter" d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {showCustomModal && <CustomProviderModal
        customProviders={customProviders}
        onClose={() => setShowCustomModal(false)}
        onSaved={() => {
          setShowCustomModal(false);
          fetchCustomProviders();
          fetch('/api/available-models').then(r=>r.json()).then(d=>setAvailableModels(d)).catch(()=>{});
        }}
      />}

      {/* Footer */}
      <footer className="bg-moss-900 border-t-4 border-moss-700 py-4 px-6 flex-shrink-0">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <a 
            href="https://github.com/momadhuynh04/freeClaude.git"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[8px] font-pixel text-moss-400 hover:text-claude-500 transition-none flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
            github.com/momadhuynh04/freeClaude
          </a>
          <span className="text-[8px] font-pixel text-moss-500">
            © {new Date().getFullYear()} HUYNHHOANG04
          </span>
        </div>
      </footer>
    </div>
  );
}

export default App;
