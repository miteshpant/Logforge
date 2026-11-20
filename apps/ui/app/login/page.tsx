'use client'

import Link from 'next/link'

import { useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, Shield, BarChart3, Eye, Zap } from 'lucide-react'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { login, error, clearError } = useAuth()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!email || !password) {
      return
    }

    try {
      setIsSubmitting(true)
      clearError()
      await login(email, password)
    } catch (error) {
      // Error is handled by AuthContext
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-6xl grid lg:grid-cols-2 gap-8 items-center">
        
        {/* Left Side - Branding & Features */}
        <div className="text-white space-y-8 lg:pr-8">
          <div className="space-y-4">
            <div className="flex items-center space-x-3">
              <div className="w-12 h-12 bg-blue-600 rounded-lg flex items-center justify-center">
                <BarChart3 className="w-7 h-7 text-white" />
              </div>
              <div>
                <h1 className="text-3xl font-bold">Logforge</h1>
                <p className="text-blue-200">Enterprise Observability Platform</p>
              </div>
            </div>
            
            <h2 className="text-4xl font-bold leading-tight">
              Advanced Log Analytics
              <br />
              <span className="text-blue-400">Built for Scale</span>
            </h2>
            
            <p className="text-xl text-slate-300 leading-relaxed">
              Monitor, analyze, and secure your infrastructure with enterprise-grade 
              observability that scales to billions of events per day.
            </p>
          </div>

          {/* Feature Highlights */}
          <div className="grid gap-4">
            <div className="flex items-start space-x-3">
              <div className="w-8 h-8 bg-blue-600/20 rounded-lg flex items-center justify-center flex-shrink-0 mt-1">
                <Zap className="w-4 h-4 text-blue-400" />
              </div>
              <div>
                <h3 className="font-semibold text-lg">Real-time Processing</h3>
                <p className="text-slate-400">Process 50K+ events per second with sub-second query response times</p>
              </div>
            </div>
            
            <div className="flex items-start space-x-3">
              <div className="w-8 h-8 bg-green-600/20 rounded-lg flex items-center justify-center flex-shrink-0 mt-1">
                <Shield className="w-4 h-4 text-green-400" />
              </div>
              <div>
                <h3 className="font-semibold text-lg">Security Analytics</h3>
                <p className="text-slate-400">SIEM capabilities with Sigma rules and threat intelligence</p>
              </div>
            </div>
            
            <div className="flex items-start space-x-3">
              <div className="w-8 h-8 bg-purple-600/20 rounded-lg flex items-center justify-center flex-shrink-0 mt-1">
                <Eye className="w-4 h-4 text-purple-400" />
              </div>
              <div>
                <h3 className="font-semibold text-lg">Complete Observability</h3>
                <p className="text-slate-400">Logs, metrics, traces, and APM in one unified platform</p>
              </div>
            </div>
          </div>

          {/* Cost Comparison */}
          <div className="bg-white/5 backdrop-blur-sm rounded-xl p-6 border border-white/10">
            <h3 className="font-semibold text-lg mb-3">Enterprise Value</h3>
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-300">vs. Splunk/Elastic</span>
              <span className="text-green-400 font-bold">60-80% Cost Reduction</span>
            </div>
            <div className="w-full bg-slate-700 rounded-full h-2 mt-2">
              <div className="bg-gradient-to-r from-green-400 to-blue-500 h-2 rounded-full w-4/5"></div>
            </div>
          </div>
        </div>

        {/* Right Side - Login Form */}
        <div className="w-full max-w-md mx-auto">
          <Card className="bg-white/95 backdrop-blur-sm border-0 shadow-2xl" data-testid="login-form">
            <CardHeader className="space-y-2 text-center">
              <CardTitle className="text-2xl font-bold text-slate-900">Welcome Back</CardTitle>
              <CardDescription className="text-slate-600">
                Sign in to your Logforge tenant
              </CardDescription>
            </CardHeader>
            
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-6">
                {error && (
                  <Alert variant="destructive" className="border-red-200 bg-red-50" data-testid="error-message">
                    <AlertDescription className="text-red-800">
                      {error}
                    </AlertDescription>
                  </Alert>
                )}

                <div className="space-y-2">
                  <Label htmlFor="email" className="text-sm font-medium text-slate-700">
                    Email Address
                  </Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="your-email@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="h-11 border-slate-200 focus:border-blue-500 focus:ring-blue-500"
                    required
                    disabled={isSubmitting}
                    data-testid="email-input"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="password" className="text-sm font-medium text-slate-700">
                    Password
                  </Label>
                  <Input
                    id="password"
                    type="password"
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="h-11 border-slate-200 focus:border-blue-500 focus:ring-blue-500"
                    required
                    disabled={isSubmitting}
                    data-testid="password-input"
                  />
                  <div className="text-right">
                    <Link href="/forgot-password" className="text-sm text-blue-700 hover:underline" data-testid="forgot-password">
                      Forgot your password?
                    </Link>
                  </div>
                </div>

                <Button
                  type="submit"
                  className="w-full h-11 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 font-medium text-white shadow-lg transition-all duration-200"
                  disabled={isSubmitting || !email || !password}
                  data-testid="login-button"
                >
                  {isSubmitting ? (
                    <div className="flex items-center space-x-2">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Signing In...</span>
                    </div>
                  ) : (
                    'Sign In to Dashboard'
                  )}
                </Button>

                {/* Enterprise SSO Options */}
                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <span className="w-full border-t border-slate-200" />
                  </div>
                  <div className="relative flex justify-center text-xs uppercase">
                    <span className="bg-white px-2 text-slate-500">Or continue with</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <Button
                    type="button"
                    variant="outline"
                    className="h-11 border-slate-200 hover:bg-slate-50"
                    data-testid="sso-saml"
                    onClick={() => alert('SAML SSO - Contact your administrator to configure')}
                  >
                    <Shield className="w-4 h-4 mr-2" />
                    SAML
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    className="h-11 border-slate-200 hover:bg-slate-50"
                    data-testid="sso-oidc"
                    onClick={() => alert('OIDC SSO - Contact your administrator to configure')}
                  >
                    <Eye className="w-4 h-4 mr-2" />
                    OIDC
                  </Button>
                </div>

                <div className="text-center pt-4">
                  <p className="text-sm text-slate-500">
                    Need access?{' '}
                    <button 
                      type="button"
                      className="text-blue-600 hover:text-blue-700 font-medium"
                      onClick={() => alert('Contact your administrator for access')}
                      data-testid="contact-admin"
                    >
                      Contact Administrator
                    </button>
                  </p>
                </div>
              </form>
            </CardContent>
          </Card>
          
          {/* Enterprise Security Notice */}
          <div className="mt-6 text-center">
            <div className="inline-flex items-center space-x-2 text-white/70 text-sm">
              <Shield className="w-4 h-4" />
              <span>Enterprise-grade security with SOC 2 Type II compliance</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}