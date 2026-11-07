import React, { useState } from 'react'
import { Bot, Plus, Pencil, Trash2, X, Loader2, PhoneOutgoing } from 'lucide-react'

const VOICES = [
  { value: '', label: 'Default (from .env)' },
  { value: 'Nalini', label: 'Nalini (Female)' },
  { value: 'Aryan', label: 'Aryan (Male)' }
]

const LANGUAGES = [
  { value: '', label: 'Default (from .env)' },
  { value: 'en-IN', label: 'English (India)' },
  { value: 'hi-IN', label: 'Hindi' },
  { value: 'bn-IN', label: 'Bengali' },
  { value: 'gu-IN', label: 'Gujarati' },
  { value: 'kn-IN', label: 'Kannada' },
  { value: 'ml-IN', label: 'Malayalam' },
  { value: 'mr-IN', label: 'Marathi' },
  { value: 'ta-IN', label: 'Tamil' },
  { value: 'te-IN', label: 'Telugu' },
  { value: 'pa-IN', label: 'Punjabi' }
]

const EMPTY_AGENT = {
  name: '',
  description: '',
  persona_name: '',
  company_name: '',
  product_name: '',
  product_description: '',
  key_features: [],
  pricing: '',
  offers: '',
  target_audience: '',
  faqs: [],
  objections: [],
  call_objective: '',
  greeting: '',
  closing_message: '',
  tone: 'Warm, polite, professional and consultative',
  additional_instructions: '',
  language: '',
  voice: '',
  key_terms: []
}

const inputCls =
  'w-full bg-gray-950 border border-gray-700 rounded-xl px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-emerald-500'

function Field({ label, hint, required, children }) {
  return (
    <div>
      <label className="text-xs font-medium text-gray-400 block mb-1">
        {label}
        {required && <span className="text-rose-400"> *</span>}
      </label>
      {children}
      {hint && <p className="text-[11px] text-gray-500 mt-1">{hint}</p>}
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="space-y-3">
      <h4 className="text-xs font-semibold uppercase tracking-wider text-emerald-400 border-b border-gray-800 pb-1">
        {title}
      </h4>
      {children}
    </div>
  )
}

// Repeating rows of {aKey, bKey} pairs (FAQs, objections)
function PairList({ items, onChange, aKey, bKey, aPlaceholder, bPlaceholder, addLabel }) {
  const update = (idx, key, value) =>
    onChange(items.map((it, i) => (i === idx ? { ...it, [key]: value } : it)))
  return (
    <div className="space-y-2">
      {items.map((it, idx) => (
        <div key={idx} className="flex gap-2 items-start">
          <div className="flex-1 space-y-1.5">
            <input
              className={inputCls}
              value={it[aKey]}
              placeholder={aPlaceholder}
              onChange={(e) => update(idx, aKey, e.target.value)}
            />
            <textarea
              rows={2}
              className={inputCls}
              value={it[bKey]}
              placeholder={bPlaceholder}
              onChange={(e) => update(idx, bKey, e.target.value)}
            />
          </div>
          <button
            type="button"
            onClick={() => onChange(items.filter((_, i) => i !== idx))}
            className="p-2 text-gray-500 hover:text-rose-400"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() => onChange([...items, { [aKey]: '', [bKey]: '' }])}
        className="text-xs text-emerald-400 hover:text-emerald-300 flex items-center space-x-1"
      >
        <Plus className="w-3.5 h-3.5" />
        <span>{addLabel}</span>
      </button>
    </div>
  )
}

const linesToList = (text) =>
  text
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean)

const csvToList = (text) =>
  text
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)

function AgentFormModal({ initial, onClose, onSaved }) {
  const [form, setForm] = useState({ ...EMPTY_AGENT, ...initial })
  const [featuresText, setFeaturesText] = useState((initial.key_features || []).join('\n'))
  const [keyTermsText, setKeyTermsText] = useState((initial.key_terms || []).join(', '))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const isEdit = Boolean(initial.agent_id)

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const save = async () => {
    if (!form.name.trim() || !form.product_name.trim() || !form.product_description.trim()) {
      setError('Agent name, product name and product description are required.')
      return
    }
    setSaving(true)
    setError('')
    const body = {
      ...EMPTY_AGENT,
      ...Object.fromEntries(Object.keys(EMPTY_AGENT).map((k) => [k, form[k] ?? EMPTY_AGENT[k]])),
      key_features: linesToList(featuresText),
      key_terms: csvToList(keyTermsText),
      faqs: form.faqs.filter((f) => f.q.trim() && f.a.trim()),
      objections: form.objections.filter((o) => o.objection.trim() && o.response.trim())
    }
    try {
      const res = await fetch(isEdit ? `/api/agents/${initial.agent_id}` : '/api/agents', {
        method: isEdit ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      })
      const data = await res.json()
      if (!res.ok) {
        const detail = Array.isArray(data.detail)
          ? data.detail.map((d) => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join(', ')
          : data.detail
        throw new Error(detail || 'Failed to save agent.')
      }
      onSaved(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl max-w-3xl w-full shadow-2xl flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div>
            <h3 className="text-base font-bold text-white">
              {isEdit ? 'Edit Sales Agent' : 'Create Sales Agent'}
            </h3>
            <p className="text-xs text-gray-400">
              The AI will only use the information you enter here during calls.
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="overflow-y-auto px-6 py-5 space-y-6">
          <Section title="Agent Identity">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Field label="Agent Name" required hint="Shown in the dashboard agent picker">
                <input className={inputCls} value={form.name} onChange={set('name')} placeholder="Solar Sales Agent" />
              </Field>
              <Field label="Persona Name" hint="Name the agent introduces itself with on the call">
                <input className={inputCls} value={form.persona_name} onChange={set('persona_name')} placeholder="Riya" />
              </Field>
              <Field label="Company Name">
                <input className={inputCls} value={form.company_name} onChange={set('company_name')} placeholder="SunVolt Energy" />
              </Field>
              <Field label="Tone / Speaking Style">
                <input className={inputCls} value={form.tone} onChange={set('tone')} />
              </Field>
            </div>
            <Field label="Description" hint="Internal note on what this agent is used for">
              <textarea rows={2} className={inputCls} value={form.description} onChange={set('description')} />
            </Field>
          </Section>

          <Section title="Product Details">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Field label="Product / Service Name" required>
                <input className={inputCls} value={form.product_name} onChange={set('product_name')} placeholder="SunVolt Rooftop Solar" />
              </Field>
              <Field label="Target Audience">
                <input className={inputCls} value={form.target_audience} onChange={set('target_audience')} placeholder="Homeowners in Gujarat" />
              </Field>
            </div>
            <Field label="Product Description" required>
              <textarea rows={4} className={inputCls} value={form.product_description} onChange={set('product_description')} placeholder="What the product is, what problem it solves, how it works..." />
            </Field>
            <Field label="Key Features & Benefits" hint="One per line">
              <textarea rows={4} className={inputCls} value={featuresText} onChange={(e) => setFeaturesText(e.target.value)} placeholder={'25 year panel warranty\nFree installation\nGovernment subsidy assistance'} />
            </Field>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Field label="Pricing" hint="The agent will never quote any other price">
                <textarea rows={3} className={inputCls} value={form.pricing} onChange={set('pricing')} />
              </Field>
              <Field label="Approved Offers / Discounts" hint="Leave empty if the agent must not offer discounts">
                <textarea rows={3} className={inputCls} value={form.offers} onChange={set('offers')} />
              </Field>
            </div>
          </Section>

          <Section title="FAQs">
            <PairList
              items={form.faqs}
              onChange={(faqs) => setForm((f) => ({ ...f, faqs }))}
              aKey="q"
              bKey="a"
              aPlaceholder="Question, e.g. Is there a warranty?"
              bPlaceholder="Answer the agent should give"
              addLabel="Add FAQ"
            />
          </Section>

          <Section title="Objection Handling">
            <PairList
              items={form.objections}
              onChange={(objections) => setForm((f) => ({ ...f, objections }))}
              aKey="objection"
              bKey="response"
              aPlaceholder="Objection, e.g. It's too expensive"
              bPlaceholder="How the agent should respond"
              addLabel="Add Objection"
            />
          </Section>

          <Section title="Conversation Flow">
            <Field label="Call Objective" hint="What counts as success, e.g. book a free site survey">
              <input className={inputCls} value={form.call_objective} onChange={set('call_objective')} />
            </Field>
            <Field
              label="Opening Greeting"
              hint="Spoken when the call connects. Placeholders: {customer_name}, {agent_name}, {company_name}, {product_name}. Leave empty for an automatic greeting."
            >
              <textarea rows={2} className={inputCls} value={form.greeting} onChange={set('greeting')} placeholder="Hi {customer_name}, this is {agent_name} from {company_name}. Do you have two minutes?" />
            </Field>
            <Field label="Closing Message">
              <input className={inputCls} value={form.closing_message} onChange={set('closing_message')} placeholder="Thank you for your time, have a great day!" />
            </Field>
            <Field label="Additional Instructions" hint="Any extra rules, e.g. always confirm the customer's city">
              <textarea rows={3} className={inputCls} value={form.additional_instructions} onChange={set('additional_instructions')} />
            </Field>
          </Section>

          <Section title="Voice (Gnani)">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Field label="TTS Voice">
                <select className={inputCls} value={form.voice} onChange={set('voice')}>
                  {VOICES.map((v) => (
                    <option key={v.value} value={v.value}>{v.label}</option>
                  ))}
                </select>
              </Field>
              <Field label="Speaking Language">
                <select className={inputCls} value={form.language} onChange={set('language')}>
                  {LANGUAGES.map((l) => (
                    <option key={l.value} value={l.value}>{l.label}</option>
                  ))}
                </select>
              </Field>
            </div>
            <Field label="STT Key Terms" hint="Comma-separated brand names / jargon to improve speech recognition">
              <input className={inputCls} value={keyTermsText} onChange={(e) => setKeyTermsText(e.target.value)} placeholder="SunVolt, kilowatt, net metering" />
            </Field>
          </Section>
        </div>

        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-800">
          <span className="text-xs text-rose-400">{error}</span>
          <div className="flex space-x-2">
            <button onClick={onClose} className="px-4 py-2 bg-gray-800 text-gray-300 rounded-xl text-xs hover:bg-gray-700">
              Cancel
            </button>
            <button
              onClick={save}
              disabled={saving}
              className="px-4 py-2 bg-emerald-600 text-white rounded-xl text-xs font-semibold hover:bg-emerald-500 disabled:opacity-50 flex items-center space-x-1.5"
            >
              {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>{isEdit ? 'Save Changes' : 'Create Agent'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function AgentsTab({ agents, onAgentsChanged, onUseAgent }) {
  const [editing, setEditing] = useState(null)

  const deleteAgent = async (agent) => {
    if (!window.confirm(`Delete agent "${agent.name}"?`)) return
    const res = await fetch(`/api/agents/${agent.agent_id}`, { method: 'DELETE' })
    if (!res.ok) {
      alert('Failed to delete agent.')
      return
    }
    onAgentsChanged()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Sales Agents</h2>
          <p className="text-sm text-gray-400">
            Each agent has its own product knowledge, script and voice. Pick one in the Live Call Console to dial.
          </p>
        </div>
        <button
          onClick={() => setEditing({})}
          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-xl flex items-center space-x-2 transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>Create Agent</span>
        </button>
      </div>

      {agents.length === 0 ? (
        <div className="bg-gray-900/70 border border-dashed border-gray-700 rounded-2xl p-12 text-center">
          <Bot className="w-10 h-10 mx-auto text-gray-600 mb-3" />
          <p className="text-sm text-gray-400 mb-4">No agents yet. Create one with your product details to start calling.</p>
          <button
            onClick={() => setEditing({})}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-xl"
          >
            Create your first agent
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {agents.map((a) => (
            <div key={a.agent_id} className="bg-gray-900/70 border border-gray-800 rounded-2xl p-6 shadow-xl space-y-4 flex flex-col">
              <div className="flex items-start justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
                    <Bot className="w-5 h-5 text-emerald-400" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-white">{a.name}</h3>
                    <p className="text-xs text-gray-400">
                      {a.persona_name ? `"${a.persona_name}"` : 'No persona'}
                      {a.company_name ? ` • ${a.company_name}` : ''}
                    </p>
                  </div>
                </div>
                <div className="flex items-center space-x-1">
                  <button onClick={() => setEditing(a)} className="p-2 text-gray-400 hover:text-white" title="Edit">
                    <Pencil className="w-4 h-4" />
                  </button>
                  <button onClick={() => deleteAgent(a)} className="p-2 text-gray-400 hover:text-rose-400" title="Delete">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {a.description && <p className="text-xs text-gray-400">{a.description}</p>}

              <div>
                <span className="text-xs font-semibold text-gray-400 block mb-1">Product</span>
                <p className="text-sm text-emerald-400 font-medium">{a.product_name}</p>
                <p className="text-xs text-gray-300 leading-relaxed line-clamp-3 mt-1">{a.product_description}</p>
              </div>

              <div className="flex flex-wrap gap-1.5 text-[11px]">
                <span className="px-2 py-0.5 bg-gray-950 border border-gray-800 rounded text-gray-400">
                  {(a.key_features || []).length} features
                </span>
                <span className="px-2 py-0.5 bg-gray-950 border border-gray-800 rounded text-gray-400">
                  {(a.faqs || []).length} FAQs
                </span>
                <span className="px-2 py-0.5 bg-gray-950 border border-gray-800 rounded text-gray-400">
                  {(a.objections || []).length} objections
                </span>
                <span className="px-2 py-0.5 bg-gray-950 border border-gray-800 rounded text-gray-400">
                  Voice: {a.voice || 'default'} • {a.language || 'default'}
                </span>
              </div>

              <div className="pt-2 mt-auto">
                <button
                  onClick={() => onUseAgent(a)}
                  className="w-full px-3 py-2 rounded-xl bg-gray-800 hover:bg-gray-700 border border-gray-700 text-sm text-gray-200 flex items-center justify-center space-x-2"
                >
                  <PhoneOutgoing className="w-4 h-4 text-emerald-400" />
                  <span>Call with this agent</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {editing && (
        <AgentFormModal
          initial={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            onAgentsChanged()
          }}
        />
      )}
    </div>
  )
}
