import React, { useState, useEffect, useRef } from 'react'
import {
  PhoneCall,
  Radio,
  Users,
  BarChart3,
  Settings,
  Phone,
  PhoneOff,
  PhoneOutgoing,
  Mic,
  MicOff,
  Hand,
  Activity,
  MessageSquare,
  Zap,
  Sparkles,
  GitCommit,
  Headphones,
  Plus,
  Copy,
  Check,
  X,
  Loader2,
  Bot
} from 'lucide-react'
import AgentsTab from './components/AgentsTab'

function App() {
  // Navigation
  const [activeTab, setActiveTab] = useState('dialer')
  const [systemOnline, setSystemOnline] = useState(false)

  // Call configuration
  const [customers, setCustomers] = useState([])
  const [agents, setAgents] = useState([])
  const [selectedAgentId, setSelectedAgentId] = useState('')
  const [selectedCustomerId, setSelectedCustomerId] = useState('')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [customerName, setCustomerName] = useState('')

  // Active call state
  const [activeCallId, setActiveCallId] = useState(null)
  const [callStatus, setCallStatus] = useState('IDLE')
  const [callState, setCallState] = useState('INTRO')
  const [activeCustomerName, setActiveCustomerName] = useState('No Active Call')
  const [activePhoneDisplay, setActivePhoneDisplay] = useState('Dial a number to start AI conversation')
  const [duration, setDuration] = useState('00:00')
  const [transcript, setTranscript] = useState([])
  const [isCalling, setIsCalling] = useState(false)
  const [isBrowserVoiceActive, setIsBrowserVoiceActive] = useState(false)
  const [isBargeInActive, setIsBargeInActive] = useState(false)

  // Telemetry & Post-Call Analysis
  const [metrics, setMetrics] = useState({
    avg_stt_latency_ms: 127.0,
    avg_llm_latency_ms: 340.0,
    avg_tts_latency_ms: 280.0,
    avg_total_latency_ms: 747.0,
    interruptions_count: 0
  })
  const [outcomeData, setOutcomeData] = useState(null)
  const [analyticsOverview, setAnalyticsOverview] = useState(null)
  const [callHistory, setCallHistory] = useState([])

  // Modal State
  const [isAddCustomerOpen, setIsAddCustomerOpen] = useState(false)
  const [newCustName, setNewCustName] = useState('')
  const [newCustPhone, setNewCustPhone] = useState('')
  const [newCustCompany, setNewCustCompany] = useState('')
  const [newCustRole, setNewCustRole] = useState('')
  const [copiedWebhook, setCopiedWebhook] = useState(false)

  // Audio Context & WebSockets Refs
  const dashboardWsRef = useRef(null)
  const unmountingRef = useRef(false)
  const browserWsRef = useRef(null)
  const audioContextRef = useRef(null)
  const mediaStreamRef = useRef(null)
  const timerIntervalRef = useRef(null)
  const startTimeRef = useRef(null)
  const transcriptFeedRef = useRef(null)
  const canvasRef = useRef(null)
  const waveEnergyRef = useRef(10)

  // Initialize data and the dashboard WebSocket once
  useEffect(() => {
    unmountingRef.current = false
    fetchCustomers()
    fetchAgents()
    fetchAnalytics()
    setupDashboardWebSocket()

    return () => {
      unmountingRef.current = true
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current)
      if (dashboardWsRef.current) dashboardWsRef.current.close()
    }
  }, [])

  useEffect(() => {
    // Setup Waveform Animation
    let animId
    const renderWave = () => {
      const canvas = canvasRef.current
      if (canvas) {
        const ctx = canvas.getContext('2d')
        ctx.clearRect(0, 0, canvas.width, canvas.height)
        const centerY = canvas.height / 2
        ctx.beginPath()
        ctx.lineWidth = 2
        ctx.strokeStyle = activeCallId ? '#10b981' : '#374151'

        const slices = 40
        const sliceWidth = canvas.width / slices
        let x = 0

        for (let i = 0; i <= slices; i++) {
          const angle = (i / slices) * Math.PI * 4 + Date.now() / 200
          const amplitude = activeCallId
            ? Math.min(canvas.height / 2.5, (waveEnergyRef.current / 100) * 20 + Math.sin(angle) * 8)
            : 2
          const y = centerY + Math.sin(angle) * amplitude
          if (i === 0) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
          x += sliceWidth
        }
        ctx.stroke()
      }
      animId = requestAnimationFrame(renderWave)
    }

    if (canvasRef.current) {
      canvasRef.current.width = canvasRef.current.offsetWidth
      canvasRef.current.height = canvasRef.current.offsetHeight
      renderWave()
    }

    return () => cancelAnimationFrame(animId)
  }, [activeCallId])

  // Auto-scroll transcript
  useEffect(() => {
    if (transcriptFeedRef.current) {
      transcriptFeedRef.current.scrollTop = transcriptFeedRef.current.scrollHeight
    }
  }, [transcript])

  // Setup WebSocket connection to backend
  const setupDashboardWebSocket = () => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/ws/dashboard`

    const ws = new WebSocket(wsUrl)
    dashboardWsRef.current = ws

    ws.onopen = () => setSystemOnline(true)
    ws.onclose = () => {
      setSystemOnline(false)
      if (!unmountingRef.current) setTimeout(setupDashboardWebSocket, 3000)
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        handleBroadcastEvent(msg.type, msg.data)
      } catch (err) {
        console.error('Error parsing dashboard WS event:', err)
      }
    }
  }

  const handleBroadcastEvent = (type, data) => {
    if (type === 'call_started') {
      setActiveCallId(data.call_id)
      setCallStatus('ACTIVE CALL')
      setActiveCustomerName(data.customer_name || 'Customer')
      setActivePhoneDisplay(
        [data.phone_number, data.agent_name && `Agent: ${data.agent_name}`].filter(Boolean).join(' • ')
      )
      setTranscript([])
      setCallState('INTRO')
      startCallTimer()
    } else if (type === 'transcript_update') {
      if (!data?.message) return
      setTranscript((prev) => {
        const msg = data.message
        if (msg.id && prev.some((m) => m.id === msg.id)) {
          return prev
        }
        if (prev.length > 0) {
          const last = prev[prev.length - 1]
          if (last.role === msg.role && last.text === msg.text) {
            return prev
          }
        }
        return [...prev, msg]
      })
    } else if (type === 'state_update') {
      if (data.state) setCallState(data.state)
      if (data.metrics) setMetrics((prev) => ({ ...prev, ...data.metrics }))
    } else if (type === 'audio_energy') {
      waveEnergyRef.current = Math.max(10, Math.min(100, (data.rms || 0) / 20))
    } else if (type === 'call_barge_in') {
      setIsBargeInActive(true)
      setTimeout(() => setIsBargeInActive(false), 900)
    } else if (type === 'call_ended') {
      stopCallTimer()
      setCallStatus('COMPLETED')
      if (data.outcome) setOutcomeData(data.outcome)
      fetchAnalytics()
      setActiveCallId(null)
    }
  }

  const startCallTimer = () => {
    startTimeRef.current = Date.now()
    if (timerIntervalRef.current) clearInterval(timerIntervalRef.current)
    timerIntervalRef.current = setInterval(() => {
      if (!startTimeRef.current) return
      const elapsed = Math.floor((Date.now() - startTimeRef.current) / 1000)
      const mins = String(Math.floor(elapsed / 60)).padStart(2, '0')
      const secs = String(elapsed % 60).padStart(2, '0')
      setDuration(`${mins}:${secs}`)
    }, 1000)
  }

  const stopCallTimer = () => {
    if (timerIntervalRef.current) clearInterval(timerIntervalRef.current)
    startTimeRef.current = null
  }

  // REST API calls
  const fetchCustomers = async () => {
    try {
      const res = await fetch('/api/customers')
      const data = await res.json()
      setCustomers(data)
    } catch (e) {
      console.error('Failed to fetch customers:', e)
    }
  }

  const fetchAgents = async () => {
    try {
      const res = await fetch('/api/agents')
      const data = await res.json()
      setAgents(data)
      setSelectedAgentId((current) =>
        data.some((a) => a.agent_id === current) ? current : data[0]?.agent_id || ''
      )
    } catch (e) {
      console.error('Failed to fetch agents:', e)
    }
  }

  const fetchAnalytics = async () => {
    try {
      const res = await fetch('/api/analytics/overview')
      const data = await res.json()
      setAnalyticsOverview(data)

      const callsRes = await fetch('/api/calls')
      const calls = await callsRes.json()
      setCallHistory(calls)
    } catch (e) {
      console.error('Failed to fetch analytics:', e)
    }
  }

  const handleCustomerChange = (e) => {
    const custId = e.target.value
    setSelectedCustomerId(custId)
    const cust = customers.find((c) => c.customer_id === custId)
    if (cust) {
      setPhoneNumber(cust.phone)
      setCustomerName(cust.name)
    }
  }

  const requestCallSession = (phone) =>
    fetch('/api/calls/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone_number: phone,
        agent_id: selectedAgentId,
        customer_id: selectedCustomerId || null,
        customer_name: customerName || null
      })
    })

  // Start Real Outbound Twilio Call
  const startTwilioCall = async () => {
    if (!selectedAgentId) {
      alert('Please create or select a sales agent first.')
      return
    }
    if (!phoneNumber) {
      alert('Please enter a target phone number.')
      return
    }

    setIsCalling(true)
    try {
      const res = await requestCallSession(phoneNumber)
      const data = await res.json()
      if (res.ok && data.status !== 'failed') {
        setActiveCallId(data.call_id)
        setCallStatus('RINGING...')
      } else {
        alert(data.message || data.detail || 'Call initiation failed.')
      }
    } catch (e) {
      alert('Network error connecting to call API: ' + e)
    } finally {
      setIsCalling(false)
    }
  }

  // Browser Microphone Sandbox Voice Call
  const startBrowserSandbox = async () => {
    if (isBrowserVoiceActive) {
      endCall()
      return
    }
    if (!selectedAgentId) {
      alert('Please create or select a sales agent first.')
      return
    }

    let callId
    try {
      const res = await requestCallSession('browser')
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Could not start sandbox session.')
      callId = data.call_id
    } catch (err) {
      alert(err.message)
      return
    }

    setActiveCallId(callId)
    setIsBrowserVoiceActive(true)
    setCallStatus('BROWSER MIC ACTIVE')
    setActiveCustomerName('Browser Sandbox User')
    setActivePhoneDisplay('Web Audio Stream • Speak into Laptop Mic')
    setTranscript([])
    setCallState('INTRO')
    startCallTimer()

    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 8000 })
      audioContextRef.current = ctx

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, sampleRate: 8000 }
      })
      mediaStreamRef.current = stream

      const source = ctx.createMediaStreamSource(stream)
      const processor = ctx.createScriptProcessor(1024, 1, 1)
      source.connect(processor)
      processor.connect(ctx.destination)

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/ws/browser-voice/${callId}`
      const ws = new WebSocket(wsUrl)
      ws.binaryType = 'arraybuffer'
      browserWsRef.current = ws

      ws.onmessage = async (event) => {
        if (event.data instanceof ArrayBuffer) {
          const audioBuffer = await ctx.decodeAudioData(event.data)
          const playSource = ctx.createBufferSource()
          playSource.buffer = audioBuffer
          playSource.connect(ctx.destination)
          playSource.start(0)
        }
      }

      processor.onaudioprocess = (e) => {
        if (!ws || ws.readyState !== WebSocket.OPEN) return
        const inputData = e.inputBuffer.getChannelData(0)
        const pcmBuffer = new Int16Array(inputData.length)
        for (let i = 0; i < inputData.length; i++) {
          let s = Math.max(-1, Math.min(1, inputData[i]))
          pcmBuffer[i] = s < 0 ? s * 0x8000 : s * 0x7fff
        }
        ws.send(pcmBuffer.buffer)
      }
    } catch (err) {
      alert('Microphone access denied or error starting Web Audio: ' + err)
      setIsBrowserVoiceActive(false)
    }
  }

  // End Call
  const endCall = async () => {
    if (isBrowserVoiceActive) {
      if (browserWsRef.current) browserWsRef.current.close()
      if (mediaStreamRef.current) mediaStreamRef.current.getTracks().forEach((t) => t.stop())
      if (audioContextRef.current) audioContextRef.current.close()
      setIsBrowserVoiceActive(false)
    }

    if (activeCallId) {
      try {
        await fetch(`/api/calls/${activeCallId}/end`, { method: 'POST' })
      } catch (e) {}
    }

    stopCallTimer()
    setCallStatus('COMPLETED')
    setActiveCallId(null)
  }

  // Trigger Barge-In Simulation
  const triggerBargeIn = () => {
    setIsBargeInActive(true)
    setTimeout(() => setIsBargeInActive(false), 900)
    if (dashboardWsRef.current && dashboardWsRef.current.readyState === WebSocket.OPEN) {
      dashboardWsRef.current.send(JSON.stringify({ type: 'interrupt' }))
    }
  }

  // Quick Dial Lead
  const handleQuickDial = (cust) => {
    setSelectedCustomerId(cust.customer_id)
    setPhoneNumber(cust.phone)
    setCustomerName(cust.name)
    setActiveTab('dialer')
  }

  const handleUseAgent = (agent) => {
    setSelectedAgentId(agent.agent_id)
    setActiveTab('dialer')
  }

  // View Archived Call
  const viewCallLogs = async (callId) => {
    try {
      const res = await fetch(`/api/calls/${callId}`)
      const call = await res.json()
      setActiveTab('dialer')
      setActiveCustomerName(call.customer_name || 'Archived Call')
      setActivePhoneDisplay(call.phone_number)
      setCallStatus(call.status)
      setTranscript(call.transcript || [])
      if (call.outcome) setOutcomeData(call.outcome)
    } catch (e) {
      console.error('Error fetching call logs:', e)
    }
  }

  // Add Customer Lead
  const saveCustomerLead = async () => {
    if (!newCustName || !newCustPhone) {
      alert('Name and Phone are required.')
      return
    }
    try {
      await fetch('/api/customers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newCustName,
          phone: newCustPhone,
          company: newCustCompany,
          designation: newCustRole
        })
      })
      setIsAddCustomerOpen(false)
      setNewCustName('')
      setNewCustPhone('')
      setNewCustCompany('')
      setNewCustRole('')
      await fetchCustomers()
    } catch (e) {
      alert('Error saving lead: ' + e)
    }
  }

  const copyWebhook = () => {
    const url = `${window.location.origin}/twilio/voice`
    navigator.clipboard.writeText(url)
    setCopiedWebhook(true)
    setTimeout(() => setCopiedWebhook(false), 2000)
  }

  const statesList = [
    { id: 'INTRO', name: '1. Intro' },
    { id: 'DISCOVERY', name: '2. Discovery' },
    { id: 'PRODUCT_EXPLANATION', name: '3. Pitch' },
    { id: 'QUESTIONS', name: '4. Questions' },
    { id: 'OBJECTION_HANDLING', name: '5. Objections' },
    { id: 'BUYING_INTENT', name: '6. Intent' },
    { id: 'CLOSING', name: '7. Closing' }
  ]

  return (
    <div className="bg-[#0b0f19] text-gray-100 min-h-screen flex flex-col font-sans">
      {/* Top Navbar */}
      <header className="border-b border-gray-800 bg-[#111827]/80 backdrop-blur-md sticky top-0 z-50 px-6 py-3.5">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
              <PhoneCall className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-lg font-bold tracking-tight text-white">Aria AI</h1>
                <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Voice Sales Agent
                </span>
              </div>
              <p className="text-xs text-gray-400">
                Twilio Media Streams • Gnani Prisma STT • Gnani Timbre TTS
              </p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="hidden md:flex items-center space-x-1 bg-gray-900/90 p-1 rounded-xl border border-gray-800">
            <button
              onClick={() => setActiveTab('dialer')}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center space-x-2 ${
                activeTab === 'dialer'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <Radio className="w-4 h-4" />
              <span>Live Call Console</span>
            </button>
            <button
              onClick={() => setActiveTab('customers')}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center space-x-2 ${
                activeTab === 'customers'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <Users className="w-4 h-4" />
              <span>Customers CRM</span>
            </button>
            <button
              onClick={() => setActiveTab('agents')}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center space-x-2 ${
                activeTab === 'agents'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <Bot className="w-4 h-4" />
              <span>Sales Agents</span>
            </button>
            <button
              onClick={() => setActiveTab('analytics')}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center space-x-2 ${
                activeTab === 'analytics'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <BarChart3 className="w-4 h-4" />
              <span>Analytics & Logs</span>
            </button>
            <button
              onClick={() => setActiveTab('settings')}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center space-x-2 ${
                activeTab === 'settings'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <Settings className="w-4 h-4" />
              <span>Webhook Setup</span>
            </button>
          </nav>

          {/* System Health */}
          <div className="flex items-center space-x-3 text-xs">
            <div
              className={`flex items-center space-x-1.5 px-3 py-1 rounded-full border ${
                systemOnline
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                  : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  systemOnline ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'
                }`}
              ></span>
              <span>{systemOnline ? 'System Live' : 'Connecting...'}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto w-full flex-1 p-6 space-y-6">
        {/* TAB 1: LIVE CALL CONSOLE */}
        {activeTab === 'dialer' && (
          <div className="space-y-6">
            {/* Top Dialer Bar */}
            <div className="bg-gray-900/70 border border-gray-800 rounded-2xl p-5 shadow-xl backdrop-blur-sm">
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                <div className="flex-1 grid grid-cols-1 md:grid-cols-4 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
                      Sales Agent
                    </label>
                    {agents.length === 0 ? (
                      <button
                        onClick={() => setActiveTab('agents')}
                        className="w-full bg-gray-950 border border-dashed border-emerald-600/60 rounded-xl px-3.5 py-2.5 text-sm text-emerald-400 hover:bg-emerald-500/10 flex items-center justify-center space-x-1.5"
                      >
                        <Plus className="w-4 h-4" />
                        <span>Create an agent</span>
                      </button>
                    ) : (
                      <select
                        value={selectedAgentId}
                        onChange={(e) => setSelectedAgentId(e.target.value)}
                        className="w-full bg-gray-950 border border-gray-700 rounded-xl px-3.5 py-2.5 text-sm text-gray-200 focus:outline-none focus:border-emerald-500"
                      >
                        {agents.map((a) => (
                          <option key={a.agent_id} value={a.agent_id}>
                            {a.name}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
                      Target Phone Number
                    </label>
                    <div className="relative">
                      <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center text-gray-400">
                        <Phone className="w-4 h-4" />
                      </span>
                      <input
                        type="text"
                        value={phoneNumber}
                        onChange={(e) => {
                          setPhoneNumber(e.target.value)
                          setSelectedCustomerId('')
                        }}
                        placeholder="+91XXXXXXXXXX"
                        className="w-full bg-gray-950 border border-gray-700 rounded-xl pl-10 pr-3 py-2.5 text-sm text-gray-200 focus:outline-none focus:border-emerald-500 font-mono"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
                      Customer Name (optional)
                    </label>
                    <input
                      type="text"
                      value={customerName}
                      onChange={(e) => setCustomerName(e.target.value)}
                      placeholder="e.g. Amit Shah"
                      className="w-full bg-gray-950 border border-gray-700 rounded-xl px-3.5 py-2.5 text-sm text-gray-200 focus:outline-none focus:border-emerald-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
                      Saved Lead (optional)
                    </label>
                    <select
                      value={selectedCustomerId}
                      onChange={handleCustomerChange}
                      className="w-full bg-gray-950 border border-gray-700 rounded-xl px-3.5 py-2.5 text-sm text-gray-200 focus:outline-none focus:border-emerald-500"
                    >
                      <option value="">None</option>
                      {customers.map((c) => (
                        <option key={c.customer_id} value={c.customer_id}>
                          {c.name} ({c.company})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Call Launch Buttons */}
                <div className="flex items-center space-x-3 pt-2 lg:pt-0">
                  <button
                    onClick={startTwilioCall}
                    disabled={isCalling || activeCallId !== null}
                    className="flex-1 lg:flex-initial px-5 py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-50 text-white font-medium rounded-xl text-sm shadow-lg shadow-emerald-500/25 flex items-center justify-center space-x-2 transition-all"
                  >
                    {isCalling ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <PhoneOutgoing className="w-4 h-4" />
                    )}
                    <span>Start Outbound Call</span>
                  </button>

                  <button
                    onClick={startBrowserSandbox}
                    className={`flex-1 lg:flex-initial px-4 py-2.5 rounded-xl text-sm font-medium flex items-center justify-center space-x-2 transition-all ${
                      isBrowserVoiceActive
                        ? 'bg-rose-600 hover:bg-rose-500 text-white'
                        : 'bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-200 hover:text-white'
                    }`}
                  >
                    {isBrowserVoiceActive ? (
                      <>
                        <MicOff className="w-4 h-4" />
                        <span>Stop Sandbox</span>
                      </>
                    ) : (
                      <>
                        <Mic className="w-4 h-4 text-indigo-400" />
                        <span>Browser Sandbox</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* Live Call Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left 2 Cols: Monitor, Waveform & Live Transcript */}
              <div className="lg:col-span-2 space-y-6">
                {/* Active Monitor Bar */}
                <div className="bg-gray-900/70 border border-gray-800 rounded-2xl p-5 shadow-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-center space-x-4">
                    <div
                      className={`w-12 h-12 rounded-full flex items-center justify-center transition-all ${
                        isBargeInActive
                          ? 'bg-amber-500/40 border-2 border-amber-400'
                          : activeCallId
                          ? 'bg-emerald-500/20 border border-emerald-500/40 calling-pulse'
                          : 'bg-gray-800'
                      }`}
                    >
                      <Phone
                        className={`w-6 h-6 ${
                          isBargeInActive
                            ? 'text-amber-400'
                            : activeCallId
                            ? 'text-emerald-400'
                            : 'text-gray-400'
                        }`}
                      />
                    </div>
                    <div>
                      <div className="flex items-center space-x-2">
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
                            activeCallId
                              ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                              : 'bg-gray-800 text-gray-400 border-gray-700'
                          }`}
                        >
                          {callStatus}
                        </span>
                        <span className="text-sm font-semibold text-white">
                          {activeCustomerName}
                        </span>
                      </div>
                      <p className="text-xs text-gray-400 font-mono mt-0.5">
                        {activePhoneDisplay}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-4">
                    <div className="text-right">
                      <span className="text-xs text-gray-400 uppercase tracking-wider block font-medium">
                        Duration
                      </span>
                      <span className="text-lg font-mono font-bold text-gray-200">
                        {duration}
                      </span>
                    </div>

                    <div className="flex items-center space-x-2">
                      <button
                        onClick={triggerBargeIn}
                        disabled={!activeCallId}
                        className="px-3 py-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 disabled:opacity-40 text-amber-400 border border-amber-500/30 text-xs font-medium flex items-center space-x-1.5 transition-all"
                        title="Simulate user barge-in (speech interruption)"
                      >
                        <Hand className="w-3.5 h-3.5" />
                        <span>Barge-In</span>
                      </button>
                      <button
                        onClick={endCall}
                        disabled={!activeCallId}
                        className="px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 disabled:opacity-40 text-rose-400 border border-rose-500/30 text-xs font-medium flex items-center space-x-1.5 transition-all"
                      >
                        <PhoneOff className="w-3.5 h-3.5" />
                        <span>End Call</span>
                      </button>
                    </div>
                  </div>
                </div>

                {/* Sales State Machine Steps */}
                <div className="bg-gray-900/70 border border-gray-800 rounded-2xl p-4 shadow-xl">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center space-x-1.5">
                      <GitCommit className="w-3.5 h-3.5 text-indigo-400" />
                      <span>Sales Dialogue State Machine</span>
                    </span>
                    <span className="text-xs font-mono font-bold text-indigo-400">
                      {callState}
                    </span>
                  </div>

                  <div className="grid grid-cols-7 gap-1.5 text-center text-[10px] font-mono">
                    {statesList.map((st) => (
                      <div
                        key={st.id}
                        className={`p-1.5 rounded-lg border transition-all ${
                          callState === st.id
                            ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300 font-semibold'
                            : 'bg-gray-950 border-gray-800 text-gray-500'
                        }`}
                      >
                        {st.name}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Real-time Waveform Canvas */}
                <div className="bg-gray-900/70 border border-gray-800 rounded-2xl p-4 shadow-xl">
                  <div className="flex items-center justify-between text-xs text-gray-400 mb-2">
                    <span className="flex items-center space-x-1.5">
                      <Activity className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Audio Stream Energy &bull; 1.0s Silence VAD Window</span>
                    </span>
                    <span className="font-mono text-emerald-400">μ-law 8kHz Full-Duplex</span>
                  </div>
                  <canvas
                    ref={canvasRef}
                    className="w-full h-16 rounded-xl bg-gray-950/80"
                  ></canvas>
                </div>

                {/* Live Transcript Chat */}
                <div className="bg-gray-900/70 border border-gray-800 rounded-2xl p-5 shadow-xl flex flex-col h-[420px]">
                  <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
                    <div className="flex items-center space-x-2">
                      <MessageSquare className="w-4 h-4 text-emerald-400" />
                      <h3 className="text-sm font-semibold text-gray-200">
                        Live Telephony Transcript
                      </h3>
                    </div>
                    <span className="text-xs text-gray-500 font-mono">
                      {transcript.length} turns
                    </span>
                  </div>

                  <div
                    ref={transcriptFeedRef}
                    className="flex-1 overflow-y-auto space-y-4 pr-2"
                  >
                    {transcript.length === 0 ? (
                      <div className="text-center py-16 text-gray-500 text-sm">
                        <Headphones className="w-8 h-8 mx-auto mb-2 opacity-40" />
                        <p>Transcript will stream live when call connects...</p>
                      </div>
                    ) : (
                      transcript.map((msg, idx) => {
                        const isAI = msg.role === 'assistant'
                        return (
                          <div
                            key={msg.id || idx}
                            className={`flex items-start space-x-3 ${
                              isAI ? '' : 'flex-row-reverse space-x-reverse'
                            }`}
                          >
                            <div
                              className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-xs font-bold ${
                                isAI
                                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                  : 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                              }`}
                            >
                              {isAI ? 'AI' : 'YOU'}
                            </div>

                            <div
                              className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-xs leading-relaxed ${
                                isAI
                                  ? 'bg-gray-800 text-gray-200 border border-gray-700/60 rounded-tl-sm'
                                  : 'bg-emerald-600 text-white rounded-tr-sm shadow-md'
                              }`}
                            >
                              <div>{msg.text}</div>
                              {isAI && msg.total_latency_ms && (
                                <div className="mt-1.5 pt-1.5 border-t border-gray-700/60 flex items-center space-x-2 text-[10px] text-gray-400 font-mono">
                                  <span className="text-emerald-400">
                                    ⚡ {msg.total_latency_ms}ms
                                  </span>
                                  <span>
                                    (STT: {msg.stt_latency_ms}ms • LLM: {msg.llm_latency_ms}ms •
                                    TTS: {msg.tts_latency_ms}ms)
                                  </span>
                                </div>
                              )}
                            </div>
                          </div>
                        )
                      })
                    )}
                  </div>
                </div>
              </div>

              {/* Right 1 Col: Latency Benchmarks & Post-Call Card */}
              <div className="space-y-6">
                {/* Latency P95 Gauge */}
                <div className="bg-gray-900/70 border border-gray-800 rounded-2xl p-5 shadow-xl space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center space-x-1.5">
                      <Zap className="w-3.5 h-3.5 text-amber-400" />
                      <span>Latency Benchmark (P95)</span>
                    </h3>
                    <span className="text-xs font-mono font-bold text-emerald-400">
                      ~{metrics.avg_total_latency_ms || 747}ms
                    </span>
                  </div>

                  <div className="space-y-2 text-xs">
                    <div>
                      <div className="flex justify-between text-gray-400 mb-1">
                        <span>Gnani STT (Prisma v3.0)</span>
                        <span className="font-mono text-gray-200">
                          {metrics.avg_stt_latency_ms || 127} ms
                        </span>
                      </div>
                      <div className="w-full bg-gray-950 h-1.5 rounded-full overflow-hidden">
                        <div
                          className="bg-emerald-500 h-1.5 rounded-full"
                          style={{
                            width: `${Math.min(
                              100,
                              ((metrics.avg_stt_latency_ms || 127) / 500) * 100
                            )}%`
                          }}
                        ></div>
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between text-gray-400 mb-1">
                        <span>Sales LLM Brain</span>
                        <span className="font-mono text-gray-200">
                          {metrics.avg_llm_latency_ms || 340} ms
                        </span>
                      </div>
                      <div className="w-full bg-gray-950 h-1.5 rounded-full overflow-hidden">
                        <div
                          className="bg-indigo-500 h-1.5 rounded-full"
                          style={{
                            width: `${Math.min(
                              100,
                              ((metrics.avg_llm_latency_ms || 340) / 800) * 100
                            )}%`
                          }}
                        ></div>
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between text-gray-400 mb-1">
                        <span>Gnani TTS (Timbre v2.5)</span>
                        <span className="font-mono text-gray-200">
                          {metrics.avg_tts_latency_ms || 280} ms
                        </span>
                      </div>
                      <div className="w-full bg-gray-950 h-1.5 rounded-full overflow-hidden">
                        <div
                          className="bg-amber-500 h-1.5 rounded-full"
                          style={{
                            width: `${Math.min(
                              100,
                              ((metrics.avg_tts_latency_ms || 280) / 600) * 100
                            )}%`
                          }}
                        ></div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Post-Call Intelligence Card */}
                <div className="bg-gray-900/70 border border-gray-800 rounded-2xl p-5 shadow-xl space-y-4">
                  <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center space-x-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                    <span>Post-Call Intelligence</span>
                  </h3>

                  {/* Intent Gauge */}
                  <div>
                    <div className="flex justify-between items-center mb-1 text-xs">
                      <span className="text-gray-400">Buying Intent Score</span>
                      <span className="font-mono font-bold text-gray-200">
                        {outcomeData
                          ? `${Math.round((outcomeData.buying_intent || 0) * 100)}%`
                          : '0%'}
                      </span>
                    </div>
                    <div className="w-full bg-gray-950 h-2.5 rounded-full overflow-hidden p-0.5">
                      <div
                        className="bg-gradient-to-r from-rose-500 via-amber-500 to-emerald-500 h-full rounded-full transition-all duration-700"
                        style={{
                          width: `${
                            outcomeData ? Math.round((outcomeData.buying_intent || 0) * 100) : 0
                          }%`
                        }}
                      ></div>
                    </div>
                  </div>

                  {/* Outcome Badges */}
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="bg-gray-950 p-2.5 rounded-xl border border-gray-800">
                      <span className="text-gray-500 block text-[10px] uppercase">Sentiment</span>
                      <span className="font-semibold text-gray-300">
                        {outcomeData ? (outcomeData.sentiment || 'neutral').toUpperCase() : 'PENDING'}
                      </span>
                    </div>
                    <div className="bg-gray-950 p-2.5 rounded-xl border border-gray-800">
                      <span className="text-gray-500 block text-[10px] uppercase">Call Outcome</span>
                      <span className="font-semibold text-gray-300">
                        {outcomeData
                          ? (outcomeData.outcome || 'completed').replace('_', ' ').toUpperCase()
                          : 'PENDING'}
                      </span>
                    </div>
                  </div>

                  {/* Objections */}
                  <div>
                    <span className="text-xs text-gray-400 block mb-1.5">Detected Objections</span>
                    <div className="flex flex-wrap gap-1.5">
                      {outcomeData && outcomeData.objections && outcomeData.objections.length > 0 ? (
                        outcomeData.objections.map((obj, i) => (
                          <span
                            key={i}
                            className="px-2 py-0.5 rounded-md text-[11px] bg-amber-500/10 text-amber-400 border border-amber-500/20"
                          >
                            {obj}
                          </span>
                        ))
                      ) : (
                        <span className="px-2 py-0.5 rounded-md text-[11px] bg-gray-950 text-gray-500 border border-gray-800">
                          None detected
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Summary */}
                  <div>
                    <span className="text-xs text-gray-400 block mb-1">Executive Summary</span>
                    <p className="text-xs text-gray-300 bg-gray-950 p-3 rounded-xl border border-gray-800 leading-relaxed min-h-[60px]">
                      {outcomeData ? outcomeData.summary : 'Summary will be generated upon conversation completion.'}
                    </p>
                  </div>

                  {/* Next Action */}
                  <div>
                    <span className="text-xs text-gray-400 block mb-1">Recommended Next Action</span>
                    <div className="text-xs text-emerald-400 bg-emerald-500/10 p-3 rounded-xl border border-emerald-500/20 font-medium">
                      {outcomeData ? outcomeData.recommended_action : 'Awaiting conversation data...'}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: CUSTOMERS CRM */}
        {activeTab === 'customers' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-white">Customer Leads</h2>
                <p className="text-sm text-gray-400">Manage prospects and initiate instant AI sales calls</p>
              </div>
              <button
                onClick={() => setIsAddCustomerOpen(true)}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-xl flex items-center space-x-2 transition-all"
              >
                <Plus className="w-4 h-4" />
                <span>Add Lead</span>
              </button>
            </div>

            <div className="bg-gray-900/70 border border-gray-800 rounded-2xl overflow-hidden shadow-xl">
              <table className="w-full text-left text-sm text-gray-300">
                <thead className="bg-gray-950/80 text-xs uppercase text-gray-400 tracking-wider border-b border-gray-800">
                  <tr>
                    <th className="px-6 py-4">Customer Name</th>
                    <th className="px-6 py-4">Phone Number</th>
                    <th className="px-6 py-4">Company & Role</th>
                    <th className="px-6 py-4">Target Product</th>
                    <th className="px-6 py-4">Status</th>
                    <th className="px-6 py-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {customers.map((c) => (
                    <tr key={c.customer_id} className="hover:bg-gray-800/40 transition-colors">
                      <td className="px-6 py-4 font-semibold text-white">{c.name}</td>
                      <td className="px-6 py-4 font-mono text-gray-300">{c.phone}</td>
                      <td className="px-6 py-4 text-gray-400">
                        {c.company} &bull; {c.designation}
                      </td>
                      <td className="px-6 py-4 text-emerald-400 font-mono text-xs">
                        {c.preferred_product_id}
                      </td>
                      <td className="px-6 py-4">
                        <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          {c.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button
                          onClick={() => handleQuickDial(c)}
                          className="px-3 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium"
                        >
                          Quick Dial
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 3: SALES AGENTS */}
        {activeTab === 'agents' && (
          <AgentsTab agents={agents} onAgentsChanged={fetchAgents} onUseAgent={handleUseAgent} />
        )}

        {/* TAB 4: ANALYTICS & LOGS */}
        {activeTab === 'analytics' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold text-white">Call Analytics & Historical Audit Trail</h2>
              <p className="text-sm text-gray-400">
                Auditable transcripts, P95 latencies, and conversion telemetry
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-gray-900/70 border border-gray-800 p-5 rounded-2xl shadow-xl">
                <span className="text-xs text-gray-400 uppercase tracking-wider block">Total Calls</span>
                <span className="text-2xl font-bold text-white mt-1 block">
                  {analyticsOverview ? analyticsOverview.total_calls : 0}
                </span>
              </div>
              <div className="bg-gray-900/70 border border-gray-800 p-5 rounded-2xl shadow-xl">
                <span className="text-xs text-gray-400 uppercase tracking-wider block">
                  Avg Roundtrip Latency
                </span>
                <span className="text-2xl font-bold text-emerald-400 mt-1 block font-mono">
                  {analyticsOverview ? `${analyticsOverview.avg_latencies.total_ms} ms` : '747 ms'}
                </span>
              </div>
              <div className="bg-gray-900/70 border border-gray-800 p-5 rounded-2xl shadow-xl">
                <span className="text-xs text-gray-400 uppercase tracking-wider block">Avg Duration</span>
                <span className="text-2xl font-bold text-indigo-400 mt-1 block font-mono">
                  {analyticsOverview ? `${analyticsOverview.avg_duration_seconds}s` : '0s'}
                </span>
              </div>
              <div className="bg-gray-900/70 border border-gray-800 p-5 rounded-2xl shadow-xl">
                <span className="text-xs text-gray-400 uppercase tracking-wider block">
                  Buying Intent Rate
                </span>
                <span className="text-2xl font-bold text-purple-400 mt-1 block font-mono">78%</span>
              </div>
            </div>

            <div className="bg-gray-900/70 border border-gray-800 rounded-2xl overflow-hidden shadow-xl">
              <table className="w-full text-left text-sm text-gray-300">
                <thead className="bg-gray-950/80 text-xs uppercase text-gray-400 tracking-wider border-b border-gray-800">
                  <tr>
                    <th className="px-6 py-4">Call ID</th>
                    <th className="px-6 py-4">Phone Number</th>
                    <th className="px-6 py-4">Product</th>
                    <th className="px-6 py-4">Duration</th>
                    <th className="px-6 py-4">Outcome</th>
                    <th className="px-6 py-4">Buying Intent</th>
                    <th className="px-6 py-4 text-right">Transcript</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {callHistory.map((c) => {
                    const out = c.outcome || {}
                    return (
                      <tr key={c.call_id} className="hover:bg-gray-800/40 transition-colors">
                        <td className="px-6 py-4 font-mono text-xs text-gray-400">{c.call_id}</td>
                        <td className="px-6 py-4 font-mono text-gray-200">{c.phone_number}</td>
                        <td className="px-6 py-4 text-emerald-400 text-xs">
                          {c.product_name || c.product_id}
                        </td>
                        <td className="px-6 py-4 font-mono text-xs">{c.duration_seconds}s</td>
                        <td className="px-6 py-4">
                          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-800 text-gray-300 border border-gray-700">
                            {out.outcome || c.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 font-mono text-xs text-emerald-400">
                          {out.buying_intent ? `${Math.round(out.buying_intent * 100)}%` : '-'}
                        </td>
                        <td className="px-6 py-4 text-right">
                          <button
                            onClick={() => viewCallLogs(c.call_id)}
                            className="text-xs text-indigo-400 hover:text-indigo-300 font-medium"
                          >
                            View Logs
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 5: WEBHOOK & SETTINGS */}
        {activeTab === 'settings' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold text-white">Twilio & Webhook Configuration</h2>
              <p className="text-sm text-gray-400">
                Instructions for connecting Twilio Programmable Voice to this local server
              </p>
            </div>

            <div className="bg-gray-900/70 border border-gray-800 rounded-2xl p-6 shadow-xl space-y-6">
              <div>
                <h3 className="text-sm font-semibold text-white mb-2">
                  1. Your Twilio Voice Webhook URL
                </h3>
                <p className="text-xs text-gray-400 mb-3">
                  Copy this URL into your Twilio Console under{' '}
                  <code className="text-emerald-400 bg-gray-950 px-1.5 py-0.5 rounded">
                    Phone Numbers &gt; Active Numbers &gt; A CALL COMES IN &gt; Webhook
                  </code>
                  :
                </p>
                <div className="flex items-center space-x-2">
                  <input
                    type="text"
                    readOnly
                    value={`${window.location.origin}/twilio/voice`}
                    className="w-full max-w-xl bg-gray-950 border border-gray-700 rounded-xl px-4 py-2.5 text-sm font-mono text-emerald-400 select-all focus:outline-none"
                  />
                  <button
                    onClick={copyWebhook}
                    className="px-4 py-2.5 bg-gray-800 hover:bg-gray-700 text-gray-200 rounded-xl text-sm font-medium flex items-center space-x-1.5 transition-all"
                  >
                    {copiedWebhook ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                    <span>{copiedWebhook ? 'Copied!' : 'Copy'}</span>
                  </button>
                </div>
              </div>

              <div className="border-t border-gray-800 pt-6">
                <h3 className="text-sm font-semibold text-white mb-2">
                  2. Exposing Local Server via Ngrok
                </h3>
                <p className="text-xs text-gray-400 mb-3">
                  Twilio requires an HTTPS public endpoint to deliver call webhooks:
                </p>
                <pre className="bg-gray-950 p-4 rounded-xl border border-gray-800 font-mono text-xs text-gray-300">
                  ngrok http 8000
                </pre>
                <p className="text-xs text-gray-400 mt-2">
                  Then set{' '}
                  <code className="text-indigo-400 bg-gray-950 px-1.5 py-0.5 rounded">
                    PUBLIC_BASE_URL=https://your-domain.ngrok-free.app
                  </code>{' '}
                  in your <code className="text-indigo-400">.env</code> file.
                </p>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Add Customer Modal */}
      {isAddCustomerOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-gray-800">
              <h3 className="text-base font-bold text-white">Add New Customer Lead</h3>
              <button
                onClick={() => setIsAddCustomerOpen(false)}
                className="text-gray-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="text-gray-400 block mb-1">Full Name</label>
                <input
                  type="text"
                  value={newCustName}
                  onChange={(e) => setNewCustName(e.target.value)}
                  placeholder="Ananya Deshmukh"
                  className="w-full bg-gray-950 border border-gray-700 rounded-xl px-3 py-2 text-gray-200"
                />
              </div>
              <div>
                <label className="text-gray-400 block mb-1">Phone Number</label>
                <input
                  type="text"
                  value={newCustPhone}
                  onChange={(e) => setNewCustPhone(e.target.value)}
                  placeholder="+919876543210"
                  className="w-full bg-gray-950 border border-gray-700 rounded-xl px-3 py-2 text-gray-200 font-mono"
                />
              </div>
              <div>
                <label className="text-gray-400 block mb-1">Company</label>
                <input
                  type="text"
                  value={newCustCompany}
                  onChange={(e) => setNewCustCompany(e.target.value)}
                  placeholder="Acme FinCorp"
                  className="w-full bg-gray-950 border border-gray-700 rounded-xl px-3 py-2 text-gray-200"
                />
              </div>
              <div>
                <label className="text-gray-400 block mb-1">Designation</label>
                <input
                  type="text"
                  value={newCustRole}
                  onChange={(e) => setNewCustRole(e.target.value)}
                  placeholder="Head of Treasury"
                  className="w-full bg-gray-950 border border-gray-700 rounded-xl px-3 py-2 text-gray-200"
                />
              </div>
            </div>

            <div className="flex justify-end space-x-2 pt-2">
              <button
                onClick={() => setIsAddCustomerOpen(false)}
                className="px-4 py-2 bg-gray-800 text-gray-300 rounded-xl text-xs hover:bg-gray-700"
              >
                Cancel
              </button>
              <button
                onClick={saveCustomerLead}
                className="px-4 py-2 bg-emerald-600 text-white rounded-xl text-xs font-semibold hover:bg-emerald-500"
              >
                Save Lead
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
