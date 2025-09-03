'use client'

import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'

export default function FeaturesPage() {
  return (
    <div className="space-y-8">
      <div className="flex items-center space-x-4">
        <Link href="/" className="text-blue-600 hover:text-blue-800 flex items-center">
          <ArrowLeft className="h-4 w-4 mr-1" />
          ← Back to Dashboard
        </Link>
      </div>
      
      <div className="flex flex-col space-y-2">
        <h1 className="text-3xl font-bold text-gray-900">Feature Management</h1>
        <p className="text-gray-600">Configure feature availability per subscription tier</p>
      </div>

      <div className="bg-white rounded-lg shadow p-8 text-center">
        <p className="text-gray-500">Coming Soon - Feature management interface</p>
      </div>
    </div>
  )
}