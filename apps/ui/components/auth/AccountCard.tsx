'use client'

import Link from 'next/link'

/** The frame of the account pages (forgot and reset password, invitations, email verification). */
export default function AccountCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white rounded-xl p-8 shadow-2xl space-y-5">
        <div>
          <p className="text-sm font-semibold text-blue-700">Logforge</p>
          <h1 className="text-2xl font-bold text-slate-900 mt-1">{title}</h1>
        </div>
        {children}
        <p className="text-sm text-slate-500"><Link href="/login" className="text-blue-700 hover:underline">Back to sign in</Link></p>
      </div>
    </div>
  )
}

export const inputClass = 'w-full h-11 px-3 rounded-md border border-slate-300 text-slate-900 focus:border-blue-500 focus:outline-none'
export const buttonClass = 'w-full h-11 rounded-md bg-blue-700 hover:bg-blue-800 text-white font-medium disabled:opacity-50'
