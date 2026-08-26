import { useState } from 'react'

type ModelRow = { id: string; name: string; reasoning: boolean; image: boolean }
type HeaderRow = { key: string; value: string }

export default function CustomProviderModal({ customProviders, onClose, onSaved }: {
  customProviders: Record<string, any>
  onClose: () => void
  onSaved: () => void
}) {
  const [providerId, setProviderId] = useState("")
  const [displayName, setDisplayName] = useState("")
  const [providerApi, setProviderApi] = useState("openai_compatible")
  const [baseUrl, setBaseUrl] = useState("")
  const [apiKey, setApiKey] = useState("")
  const [models, setModels] = useState<ModelRow[]>([{ id: "", name: "", reasoning: false, image: false }])
  const [headers, setHeaders] = useState<HeaderRow[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState("")

  const idValid = /^[a-z0-9_-]{2,32}$/.test(providerId)
  const hasDuplicate = !!customProviders[providerId]
  const baseValid = /^https?:\/\/.+/.test(baseUrl)
  const hasModel = models.some(m => m.id.trim())
  const hasHeaders = headers.some(h => h.key.trim() && h.value.trim())
  const apiKeyEnvValid = apiKey.trim().length > 0 || hasHeaders
  const canSubmit = idValid && !hasDuplicate && displayName.trim() && baseValid && apiKeyEnvValid && hasModel && !submitting
  const allReasoning = models.length > 0 && models.every(m => m.reasoning)
  const allImage = models.length > 0 && models.every(m => m.image)

  const submit = async () => {
    setError("")
    setSubmitting(true)
    try {
      const body = {
        id: providerId.trim().toLowerCase(),
        display_name: displayName.trim(),
        provider_api: providerApi,
        base_url: baseUrl.trim(),
        api_key: apiKey.trim(),
        headers: Object.fromEntries(headers.filter(h => h.key.trim()).map(h => [h.key.trim(), h.value])),
        models: models.filter(m => m.id.trim()).map(m => ({ id: m.id.trim(), name: m.name.trim() || m.id.trim(), reasoning: m.reasoning, image: m.image })),
      }
      const res = await fetch('/api/custom-providers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        const msg = typeof data.detail === 'string' ? data.detail : data.detail ? JSON.stringify(data.detail) : data.error || `Request failed (${res.status})`
        throw new Error(msg)
      }
      onSaved()
    } catch (e: any) {
      setError(e.message || String(e))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-6" onClick={onClose}>
      <div className="pixel-card p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e=>e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[10px] font-pixel text-provider-400">Configure a custom provider. See the provider config docs.</h3>
          <button onClick={onClose} className="text-moss-400 hover:text-moss-200 text-xl leading-none">×</button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-[7px] font-pixel text-moss-400 mb-1">Provider ID</label>
            <input value={providerId} onChange={e=>setProviderId(e.target.value.toLowerCase())} placeholder="myprovider" className="w-full pixel-input px-3 py-2 text-[9px]" />
            <p className="text-[6px] text-moss-500 mt-1">{hasDuplicate ? 'ID already exists' : !providerId ? '' : !idValid ? 'Must be 2-32 chars: lowercase, numbers, hyphens, underscores' : 'Lowercase letters, numbers, hyphens, or underscores'}</p>
          </div>
          <div>
            <label className="block text-[7px] font-pixel text-moss-400 mb-1">Display name</label>
            <input value={displayName} onChange={e=>setDisplayName(e.target.value)} placeholder="My AI Provider" className="w-full pixel-input px-3 py-2 text-[9px]" />
          </div>
          <div>
            <label className="block text-[7px] font-pixel text-moss-400 mb-1">Provider API</label>
            <select value={providerApi} onChange={e=>setProviderApi(e.target.value)} className="w-full pixel-input px-3 py-2 text-[9px]">
              <option value="openai_compatible">OpenAI Compatible</option>
              <option value="anthropic">Anthropic</option>
            </select>
          </div>
          <div>
            <label className="block text-[7px] font-pixel text-moss-400 mb-1">Base URL</label>
            <input value={baseUrl} onChange={e=>setBaseUrl(e.target.value)} placeholder="https://api.myprovider.com/v1" className="w-full pixel-input px-3 py-2 text-[9px]" />
          </div>
          <div>
            <label className="block text-[7px] font-pixel text-moss-400 mb-1">API key <span className="text-moss-500 normal-case">— ENV var name, not the raw key</span></label>
            <input value={apiKey} onChange={e=>setApiKey(e.target.value)} placeholder="e.g. BEEKNOEE_API_KEY" className="w-full pixel-input px-3 py-2 text-[9px]" />
            <p className="text-[6px] text-moss-500 mt-1">Enter the ENV var <b>name</b> (e.g. BEEKNOEE_API_KEY). Put the real key in <code className="text-provider-400">.env</code> as <code className="text-provider-400">BEEKNOEE_API_KEY=sk-...</code>. Leave empty only if you use headers for auth.</p>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-[7px] font-pixel text-moss-400">Models</label>
              <div className="flex gap-3">
                <label className="flex items-center gap-1 text-[6px] text-moss-400 cursor-pointer">
                  <input type="checkbox" checked={allReasoning} onChange={e=>setModels(ms=>ms.map(m=>({...m, reasoning: e.target.checked})))} /> Toggle reasoning for all
                </label>
                <label className="flex items-center gap-1 text-[6px] text-moss-400 cursor-pointer">
                  <input type="checkbox" checked={allImage} onChange={e=>setModels(ms=>ms.map(m=>({...m, image: e.target.checked})))} /> Toggle image for all
                </label>
              </div>
            </div>
            <div className="pixel-border p-3 space-y-2 bg-moss-950">
              <div className="grid grid-cols-[1fr_1fr_auto] gap-2 text-[6px] text-moss-500">
                <span>ID</span><span>Name</span><span></span>
              </div>
              {models.map((row, i) => (
                <div key={i} className="grid grid-cols-[1fr_1fr_auto] gap-2 items-center">
                  <input value={row.id} onChange={e=>setModels(ms=>ms.map((m,j)=>j===i?{...m,id:e.target.value}:m))} placeholder="model-id" className="pixel-input px-2 py-2 text-[8px]" />
                  <input value={row.name} onChange={e=>setModels(ms=>ms.map((m,j)=>j===i?{...m,name:e.target.value}:m))} placeholder="Display Name" className="pixel-input px-2 py-2 text-[8px]" />
                  <button onClick={()=>setModels(ms=>ms.filter((_,j)=>j!==i))} className="text-moss-500 hover:text-red-400 text-[10px] px-1">🗑</button>
                  <label className="flex items-center gap-1 text-[6px] text-moss-400"><input type="checkbox" checked={row.reasoning} onChange={e=>setModels(ms=>ms.map((m,j)=>j===i?{...m,reasoning:e.target.checked}:m))}/> Reasoning</label>
                  <label className="flex items-center gap-1 text-[6px] text-moss-400"><input type="checkbox" checked={row.image} onChange={e=>setModels(ms=>ms.map((m,j)=>j===i?{...m,image:e.target.checked}:m))}/> Image</label>
                  <span />
                </div>
              ))}
              <button onClick={()=>setModels(ms=>[...ms,{id:"",name:"",reasoning:false,image:false}])} className="text-[7px] text-provider-400 hover:text-provider-300">+ Add model</button>
            </div>
          </div>

          <div>
            <label className="block text-[7px] font-pixel text-moss-400 mb-1">Headers (optional)</label>
            <div className="space-y-2">
              {headers.map((h,i)=>(
                <div key={i} className="grid grid-cols-[1fr_1fr_auto] gap-2">
                  <input value={h.key} onChange={e=>setHeaders(hs=>hs.map((x,j)=>j===i?{...x,key:e.target.value}:x))} placeholder="Header-Name" className="pixel-input px-2 py-2 text-[8px]" />
                  <input value={h.value} onChange={e=>setHeaders(hs=>hs.map((x,j)=>j===i?{...x,value:e.target.value}:x))} placeholder="value" className="pixel-input px-2 py-2 text-[8px]" />
                  <button onClick={()=>setHeaders(hs=>hs.filter((_,j)=>j!==i))} className="text-moss-500 hover:text-red-400 text-[10px] px-1">🗑</button>
                </div>
              ))}
              <button onClick={()=>setHeaders(hs=>[...hs,{key:"",value:""}])} className="text-[7px] text-provider-400 hover:text-provider-300">+ Add header</button>
            </div>
          </div>

          {error && <div className="text-[7px] text-red-400 pixel-border p-2 bg-moss-950">{error}</div>}

          <button onClick={submit} disabled={!canSubmit} className="w-full pixel-btn-provider text-[8px] py-3 disabled:opacity-50">Submit</button>
        </div>
      </div>
    </div>
  )
}
