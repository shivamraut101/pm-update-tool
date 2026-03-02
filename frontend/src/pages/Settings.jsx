import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import { api } from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner'

export default function Settings() {
  const { data, loading, error } = useApi('/api/settings')
  const [testStatus, setTestStatus] = useState({ text: '', type: '' })
  const [testing, setTesting] = useState(false)

  if (loading) return <LoadingSpinner />
  if (error) return <div className="text-red-600 p-4">Error: {error}</div>

  const s = data

  async function testEmail() {
    setTesting(true)
    setTestStatus({ text: 'Sending...', type: 'info' })
    try {
      const result = await api('/api/test-email', { method: 'POST' })
      setTestStatus({
        text: `Sent to ${(result.to || []).join(', ')}`,
        type: 'success',
      })
    } catch (e) {
      setTestStatus({ text: e.message, type: 'error' })
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="fade-in max-w-3xl">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Settings</h1>

      <div className="space-y-6">
        {/* Schedule */}
        <Section title="Schedule">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="Daily Brief Time" value={s.daily_brief_time} />
            <Field label="Timezone" value={s.timezone} />
            <Field label="Weekly Report Day" value={s.weekly_report_day} />
            <Field label="Weekly Report Time" value={s.weekly_report_time} />
            <Field label="No-Update Reminder Time" value={s.reminder_no_update_time} />
          </div>
          <p className="text-xs text-gray-400 mt-3">
            Edit these in the .env file and restart the server.
          </p>
        </Section>

        {/* Email */}
        <Section title="Email (Resend)">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="Resend API Key" value={s.resend_api_key || 'Not configured'} />
            <Field label="From Email" value={s.from_email || 'Not configured'} />
            <Field label="Management Emails" value={s.management_emails || 'Not configured'} span={2} />
          </div>
          <div className="mt-3 flex items-center">
            <button
              onClick={testEmail}
              disabled={testing}
              className={`px-4 py-2 rounded text-sm text-white ${
                testing
                  ? 'bg-gray-400 cursor-not-allowed'
                  : 'bg-indigo-600 hover:bg-indigo-700'
              }`}
            >
              Send Test Email
            </button>
            {testStatus.text && (
              <span
                className={`ml-2 text-sm ${
                  testStatus.type === 'success'
                    ? 'text-green-600 font-medium'
                    : testStatus.type === 'error'
                    ? 'text-red-600'
                    : 'text-blue-600'
                }`}
              >
                {testStatus.text}
              </span>
            )}
          </div>
        </Section>

        {/* Telegram */}
        <Section title="Telegram Bot">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="Bot Token" value={s.telegram_bot_token || 'Not configured'} />
            <Field label="Chat ID" value={s.telegram_chat_id || 'Not configured'} />
            <Field label="Management Chat ID" value={s.management_telegram_chat_id || 'Not configured'} />
            <Field label="Mode" value={s.app_url ? 'Webhook' : 'Long Polling'} />
            {s.app_url && (
              <Field label="Webhook URL" value={`${s.app_url}/api/telegram/webhook`} span={2} />
            )}
          </div>
        </Section>

        {/* AI */}
        <Section title="AI (Google Gemini)">
          <Field label="API Key" value={s.gemini_api_key || 'Not configured'} />
          <p className="text-xs text-gray-400 mt-2">
            Paid tier. Models: gemini-2.5-flash, gemini-2.5-pro, gemini-2.0-flash.
          </p>
        </Section>
      </div>

      <div className="mt-6 text-center text-xs text-gray-400">Version: 2.0 (React + Resend)</div>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="bg-white rounded-lg shadow p-5">
      <h2 className="text-lg font-semibold text-gray-700 mb-4">{title}</h2>
      {children}
    </div>
  )
}

function Field({ label, value, span }) {
  return (
    <div className={span === 2 ? 'md:col-span-2' : ''}>
      <label className="block text-sm text-gray-600 mb-1">{label}</label>
      <input
        type="text"
        value={value}
        className="w-full border rounded px-3 py-2 bg-gray-50"
        disabled
        readOnly
      />
    </div>
  )
}
