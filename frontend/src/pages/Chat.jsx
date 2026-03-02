import { useState, useRef, useEffect, useCallback } from 'react'
import { useApi } from '../hooks/useApi'
import { apiForm } from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner'

export default function Chat() {
  const { data, loading, error } = useApi('/api/dashboard/chat')
  const [updates, setUpdates] = useState([])
  const [text, setText] = useState('')
  const [files, setFiles] = useState([])
  const [previews, setPreviews] = useState([])
  const [sending, setSending] = useState(false)
  const [showDrop, setShowDrop] = useState(false)
  const fileInputRef = useRef(null)
  const feedRef = useRef(null)

  useEffect(() => {
    if (data?.updates) setUpdates(data.updates)
  }, [data])

  const addFiles = useCallback((newFiles) => {
    const imageFiles = Array.from(newFiles).filter((f) => f.type.startsWith('image/'))
    setFiles((prev) => [...prev, ...imageFiles])
    for (const file of imageFiles) {
      const reader = new FileReader()
      reader.onload = (e) => {
        setPreviews((prev) => [...prev, { name: file.name, src: e.target.result }])
      }
      reader.readAsDataURL(file)
    }
  }, [])

  function removePreview(index) {
    setFiles((prev) => prev.filter((_, i) => i !== index))
    setPreviews((prev) => prev.filter((_, i) => i !== index))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!text.trim() && files.length === 0) return

    setSending(true)
    const formData = new FormData()
    formData.append('raw_text', text)
    formData.append('source', 'web')
    for (const file of files) {
      formData.append('screenshots', file)
    }

    try {
      const result = await apiForm('/api/updates', formData)
      setUpdates((prev) => [result, ...prev])
      setText('')
      setFiles([])
      setPreviews([])
      setShowDrop(false)
    } catch (err) {
      alert('Error submitting update: ' + err.message)
    } finally {
      setSending(false)
    }
  }

  function handleKeyDown(e) {
    if (e.ctrlKey && e.key === 'Enter') {
      handleSubmit(e)
    }
  }

  // Drag-drop handlers
  function handleDragOver(e) {
    e.preventDefault()
    setShowDrop(true)
  }

  function handleDrop(e) {
    e.preventDefault()
    const droppedFiles = Array.from(e.dataTransfer.files).filter((f) =>
      f.type.startsWith('image/')
    )
    addFiles(droppedFiles)
  }

  if (loading) return <LoadingSpinner />
  if (error) return <div className="text-red-600 p-4">Error: {error}</div>

  return (
    <div
      className="fade-in max-w-4xl mx-auto"
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      <h1 className="text-2xl font-bold text-gray-800 mb-4">Daily Updates</h1>

      {/* Updates Feed */}
      <div ref={feedRef} className="space-y-4 mb-6 max-h-[500px] overflow-y-auto">
        {updates.map((u) => (
          <UpdateBubble key={u._id} update={u} />
        ))}
        {updates.length === 0 && (
          <p className="text-gray-400 text-center py-8">
            No updates yet today. Start typing below to add your first update.
          </p>
        )}
      </div>

      {/* Input Area */}
      <div className="bg-white rounded-lg shadow-lg p-4 sticky bottom-4">
        <form onSubmit={handleSubmit}>
          {/* Drop zone */}
          {showDrop && (
            <div
              className="border-2 border-dashed border-gray-300 rounded-lg p-4 mb-3 text-center text-gray-400 hover:border-indigo-400 transition-colors cursor-pointer"
              onClick={() => fileInputRef.current?.click()}
            >
              <p>Drop screenshots here or click to upload</p>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept="image/*"
                className="hidden"
                onChange={(e) => addFiles(e.target.files)}
              />
            </div>
          )}

          {/* Previews */}
          {previews.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {previews.map((p, i) => (
                <div key={i} className="relative">
                  <img
                    src={p.src}
                    alt={p.name}
                    className="w-16 h-16 object-cover rounded border"
                  />
                  <button
                    type="button"
                    onClick={() => removePreview(i)}
                    className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-5 h-5 text-xs flex items-center justify-center"
                  >
                    x
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Text input row */}
          <div className="flex items-end space-x-2">
            <button
              type="button"
              onClick={() => {
                setShowDrop(!showDrop)
                if (!showDrop) fileInputRef.current?.click()
              }}
              className="p-2 text-gray-400 hover:text-indigo-600"
              title="Attach screenshot"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
                />
              </svg>
            </button>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={handleKeyDown}
              className="flex-1 border rounded-lg px-3 py-2 resize-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              rows="2"
              placeholder="What happened today? Mention team members, projects, client updates..."
            />
            <button
              type="submit"
              disabled={sending}
              className="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
            >
              {sending ? '...' : 'Send'}
            </button>
          </div>
        </form>
        {sending && (
          <div className="text-center py-2">
            <span className="text-indigo-600">Processing with AI...</span>
          </div>
        )}
      </div>
    </div>
  )
}

function UpdateBubble({ update }) {
  const u = update
  const parsed = u.parsed || {}
  const teamUpdates = parsed.team_updates || []
  const actionItems = parsed.action_items || []
  const blockers = parsed.blockers || []

  return (
    <div className="fade-in">
      {/* User message */}
      <div className="flex justify-end mb-2">
        <div className="chat-bubble bg-indigo-600 text-white rounded-2xl rounded-br-md px-4 py-2 shadow">
          <p>{u.raw_text}</p>
          {u.has_screenshot && (
            <p className="text-indigo-200 text-xs mt-1">
              + {u.screenshot_paths?.length || 0} screenshot(s)
            </p>
          )}
          <p className="text-indigo-200 text-xs mt-1">via {u.source}</p>
        </div>
      </div>

      {/* AI parsed response */}
      <div className="flex justify-start mb-2">
        <div className="chat-bubble bg-white border rounded-2xl rounded-bl-md px-4 py-2 shadow-sm">
          {teamUpdates.map((tu, i) => (
            <div key={i}>
              <div className="flex items-center space-x-2 mb-1">
                <span className="text-xs font-semibold bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded">
                  {tu.team_member_name}
                </span>
                <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                  {tu.project_name}
                </span>
                <span
                  className={`text-xs px-2 py-0.5 rounded ${
                    tu.status === 'completed'
                      ? 'bg-green-50 text-green-700'
                      : tu.status === 'blocked'
                      ? 'bg-red-50 text-red-700'
                      : 'bg-blue-50 text-blue-700'
                  }`}
                >
                  {tu.status}
                </span>
              </div>
              <p className="text-sm text-gray-700 ml-2 mb-2">{tu.summary}</p>
            </div>
          ))}
          {actionItems.map((ai, i) => (
            <p key={`a${i}`} className="text-sm text-amber-700">
              Action: {ai.description}
            </p>
          ))}
          {blockers.map((b, i) => (
            <p key={`b${i}`} className="text-sm text-red-700">
              Blocker: {b.description}
            </p>
          ))}
          {parsed.general_notes && (
            <p className="text-sm text-gray-500 italic">{parsed.general_notes}</p>
          )}
          {teamUpdates.length === 0 &&
            actionItems.length === 0 &&
            blockers.length === 0 &&
            !parsed.general_notes && (
              <p className="text-sm text-gray-400 italic">Processing...</p>
            )}
        </div>
      </div>
    </div>
  )
}
