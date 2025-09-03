'use client'

import { useState, useEffect } from 'react'

export default function ApiTestPage() {
  const [status, setStatus] = useState('Testing...')
  const [tenants, setTenants] = useState<any>(null)

  useEffect(() => {
    async function testApi() {
      try {
        setStatus('Fetching tenants...')
        console.log('Starting API call to http://localhost:7080/v1/tenants')
        
        const response = await fetch('http://localhost:7080/v1/tenants')
        console.log('Response received:', response.status, response.statusText)
        
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        console.log('Data parsed:', data)
        
        setTenants(data)
        setStatus('Success!')
      } catch (error) {
        console.error('API test failed:', error)
        setStatus(`Failed: ${error instanceof Error ? error.message : 'Unknown error'}`)
      }
    }
    
    testApi()
  }, [])

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">API Test Page</h1>
      <p className="mb-4">Status: {status}</p>
      
      {tenants && (
        <div className="space-y-2">
          <p className="font-semibold">Found {tenants.tenants?.length} tenants:</p>
          <ul className="list-disc list-inside">
            {tenants.tenants?.map((tenant: any) => (
              <li key={tenant.tenant_id}>
                {tenant.name} ({tenant.type}) - {tenant.tenant_id}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}